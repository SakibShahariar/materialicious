#!/usr/bin/env python3
"""
Materialicious duotone icon generator
====================================

Generates the Material-Grad theme: a duotone re-paint of Material-Solo's
flat accent app icons, in the style of Omarchy's `icon-mono.sh`: instead of
painting every app icon one flat accent colour, each icon keeps its internal
light/dark structure and that structure is remapped onto a two-colour ramp.

The source is a flat monochrome SVG set. For every distinct fill/stroke
colour in the SVG we compute its relative luminance (Rec.709) and remap it
onto dark -> (accent) -> light, where:

  dark  = ink / deep tone  (the panel frame colour, kept in the palette)
  light = accent           (what the dock/theme foreground should carry)

Black artwork (shadows, outlines) lands on `dark`; white/highlights land on
`light`; mid tones spread between them through an S-curve, so a red/green/blue
logo becomes a tonal sculpture of the palette instead of a flat stamp.

Output is written next to the input as `<name>.mono.svg` (or into --outdir),
and the coat of original colours is never modified.

USAGE
-----
    mono-icons.py --dark #000000 --light #c9bfff [--radius 0.5]
                   [--outdir dir] svg1 [svg2 ...]

    mono-icons.py --dark #1a2733 --light #c9bfff --out ./Material-Mono/apps/scalable \
        apps/scalable/org.gnome.Nautilus.svg apps/scalable/firefox.svg

Colour mapping
--------------
    lum = 0.2126 R + 0.7152 G + 0.0722 B      (linear, but on the sRGB value
                                              so it matches human-perceived
                                              "how light is this swatch")
    t   = smoothstep(0, 1, (lum - dark_lum) / (1 - dark_lum))   # 0..1
    t   = s_curve(t)         # sharpen the body/detail boundary
    out = lerp(dark, light, t)

`--radius` (default 0.5) controls the S-curve knee: 0 = linear ramp,
larger = more contrast between body and detail. Values 0.3..0.7 look best.

Only `#rrggbb`, `#rgb` (expanded to `#rrggbb`) and `rgb(r,g,b)` fills/strokes
are remapped. Gradients, `currentColor` and `url(#...)` references are left
untouched (they are the rare, hand-built highlights that should stay as-is).

`--autoscale` (recommended): instead of mapping every icon onto the same
global dark/light scale, each icon's brightest colour is stretched to the
light end and its darkest to the dark end. This keeps foreground/background
contrast consistent across icons even when the source art is all-mid-tone
(e.g. a white glyph on a light-blue Telegram circle). Without it, those two
tones collapse together near the light end.
"""

import argparse
import os
import re
import sys

COLOR_RE = re.compile(
    r"(?i)(fill|stroke):\s*(#[0-9a-f]{6}|#[0-9a-f]{3}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))"
    r"|(?:\b(fill|stroke)=)\"(#[0-9a-f]{6}|#[0-9a-f]{3}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))\"",
)

SVG_RE = re.compile(r"(?i)<svg\b[^>]*>")
TAG_RE = re.compile(r"(?i)<(/?)svg\b")


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        return (int(h[0], 16) * 17, int(h[1], 16) * 17, int(h[2], 16) * 17)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#%02x%02x%02x" % (r, g, b)


def rgb_str(rgb: str) -> tuple[int, int, int]:
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", rgb)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def luminance(r: int, g: int, b: int) -> float:
    # Perceived luminance on the sRGB gamma-encoded values; good enough to
    # rank "dark vs light" swatches inside a logo.
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def s_curve(t: float, radius: float) -> float:
    # Sigmoid around 0.5 -> compresses the mid band, pushes tones toward the
    # dark or light end (same spirit as Omarchy's -sigmoidal-contrast 4x50%).
    t = max(0.0, min(1.0, t))
    # Sigmoid through (0.5, 0.5): t' = 1/(1+exp(-k*(t-0.5))), k from radius.
    k = 4.0 * radius * 10.0 / (1.0 + 4.0 * radius)
    import math

    return 1.0 / (1.0 + math.exp(-k * (t - 0.5)))


def build_ramp(dark, light, radius, autoscale=False, src_min=0.0, src_max=1.0,
               linear=False):
    dark_rgb = hex_to_rgb(dark)
    light_rgb = hex_to_rgb(light)
    dark_lum = luminance(*dark_rgb) / 255.0
    light_lum = luminance(*light_rgb) / 255.0
    global_span = light_lum - dark_lum or 1.0

    # Per-icon: stretch the source's own tone range across the ramp so the
    # darkest and brightest tones in THIS icon land on the dark/light ends
    # (telegram's light-blue circle + white plane no longer collapse together).
    src_span = src_max - src_min or 1.0

    def scale(lum):
        t = (lum - dark_lum) / global_span
        if autoscale:
            # Normalise on the RAW source luminance once. For a colourful
            # source this stretches its own range onto the ramp; for --linear
            # self-recolor the source's min/max already span the old ramp,
            # and double-normalising pushes t > 1 (channel overflow -> the
            # 8-digit hex corruption seen as wrong colours).
            t = (lum - src_min) / src_span
        # --linear preserves the source icon's own tone positions exactly
        # (used for *re-colouring* an existing duotone icon, whose sculpture
        # is already baked in). Without it the S-curve re-sharpens the ramp
        # on every pass and midtones collapse to the dark/light ends.
        # Clamp — the sigmoid normalises to [0,1] implicitly, linear must too,
        # otherwise lerp overshoots the light end.
        if linear:
            return max(0.0, min(1.0, t))
        return s_curve(t, radius)

    def ramp(r, g, b):
        lum = luminance(r, g, b) / 255.0
        t = scale(lum)
        return tuple(
            round(dark_rgb[i] + (light_rgb[i] - dark_rgb[i]) * t) for i in range(3)
        )

    return ramp


def extract_colors(content: str) -> list[tuple[int, int, int]]:
    colors = []
    for m in COLOR_RE.finditer(content):
        if m.group(1) is not None:
            val = m.group(2)
        else:
            val = m.group(4)
        if val.startswith("#"):
            r, g, b = hex_to_rgb(val)
        else:
            r, g, b = rgb_str(val)
        colors.append((r, g, b))
    return colors


def recolor_content(content: str, ramp) -> tuple[str, int]:
    def repl(m):
        if m.group(1) is not None:
            prop, val = m.group(1), m.group(2)
        else:
            prop, val = m.group(3), m.group(4)
        if val.startswith("#"):
            r, g, b = hex_to_rgb(val)
        else:
            r, g, b = rgb_str(val)
        out = rgb_to_hex(*ramp(r, g, b))
        if m.group(1) is not None:
            return f"{prop}:{out}"
        else:
            return f'{prop}="{out}"'

    new, n = COLOR_RE.subn(repl, content)
    return new, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dark", default="#000000", help="dark end of the ramp (ink)")
    ap.add_argument("--light", default="#c9bfff", help="light end of the ramp (accent)")
    ap.add_argument("--radius", type=float, default=0.5, help="S-curve knee (0..1)")
    ap.add_argument("--autoscale", action="store_true",
                    help="stretch each icon's own tone range onto the ramp")
    ap.add_argument("--linear", action="store_true",
                    help="map tones proportionally without re-sharpening "
                         "(for re-colouring an existing duotone icon)")
    ap.add_argument("--outdir", default=None, help="write <name>.mono.svg here")
    ap.add_argument("svgs", nargs="+", help="source SVG files")
    args = ap.parse_args()

    if not (args.dark.startswith("#") and args.light.startswith("#")):
        print("mono-icons: dark/light must be #rrggbb", file=sys.stderr)
        return 2

    for src in args.svgs:
        if not os.path.isfile(src):
            print(f"mono-icons: skip (missing): {src}", file=sys.stderr)
            continue
        content = open(src, encoding="utf-8", errors="ignore").read()
        src_min, src_max = 0.0, 1.0
        if args.autoscale:
            try:
                colors = extract_colors(content)
                lums = [luminance(r, g, b) / 255.0 for r, g, b in colors]
                src_min, src_max = min(lums), max(lums)
            except ValueError:
                pass
        ramp = build_ramp(args.dark, args.light, args.radius,
                          autoscale=args.autoscale, src_min=src_min, src_max=src_max,
                          linear=args.linear)
        new, n = recolor_content(content, ramp)
        if n == 0:
            print(f"mono-icons: skip (no #rrggbb/rgb() colours): {src}", file=sys.stderr)
            continue
        out_dir = args.outdir or os.path.dirname(src)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(src))[0]
        out = os.path.join(out_dir, f"{base}.mono.svg")
        open(out, "w", encoding="utf-8").write(new)
        print(f"{src} -> {out}   ({n} colours remapped)")

    return 0


if __name__ == "__main__":
    sys.exit(main())