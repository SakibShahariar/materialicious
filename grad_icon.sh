#!/usr/bin/env bash
set -uo pipefail

# Grad duotone theme recolor — runs after matugen regenerates the accent.
# 1. Re-color Material-Grad's ColorScheme-flagged SVGs (folders + ~963 apps)
# 2. Regenerate the 10 duotone app icons from Papirus sources via mono-icons.py
# 3. Rebuild the icon cache

# The project root (sources/ + mono-icons.py live there). The installed copy
# runs from ~/Scripts, so resolve the project not the script's own directory.
project=${MATERICIOUS_PROJECT:-$HOME/Projects/materialicious}
repo="$project"
colors_file=~/.config/matugen/matugen-colors.css
state=~/.local/share/matugen-icon-themes/state
mono_theme=~/.icons/Material-Grad

# ── 1. Read matugen accent ──────────────────────────────────────────────────
target_hex=""
on_primary_hex=""
colors_css=$(<"$colors_file")
if [[ $colors_css =~ (--primary:[[:space:]]*#([0-9a-fA-F]{6})) ]]; then
    target_hex=#${BASH_REMATCH[2]}
fi
if [[ $colors_css =~ (--on_primary:[[:space:]]*#([0-9a-fA-F]{6})) ]]; then
    on_primary_hex=#${BASH_REMATCH[2]}
fi
[[ -n "$target_hex" && -n "$on_primary_hex" ]] || exit 1

# ── 2. Read previous accent state ──────────────────────────────────────────
old_hex=""
old_on=""
if [[ -f $state ]]; then
    { read -r old_hex; read -r old_on; } < "$state"
fi

# Detect what accent is actually on disk (self-heal on partial/failed swap).
actual_hex=""
actual_on=""
color_src=$(rg -l -F "ColorScheme-Highlight" "$mono_theme/apps" -g '*.svg' 2>/dev/null | head -1)
if [[ -n "$color_src" ]]; then
    actual_hex=$(grep -ozP 'ColorScheme-Highlight\s*\{\s*color:\s*\K#[0-9a-fA-F]+' "$color_src" | tr '\0' '\n' | head -1)
fi
bg_src=$(rg -l -F "ColorScheme-Background" "$mono_theme/apps" -g '*.svg' 2>/dev/null | head -1)
if [[ -n "$bg_src" ]]; then
    actual_on=$(grep -ozP 'ColorScheme-Background\s*\{\s*color:\s*\K#[0-9a-fA-F]+' "$bg_src" | tr '\0' '\n' | head -1)
fi

# Fast path: accent unchanged on disk AND emblem matches → skip the ColorScheme
# sweep; the duotone regeneration below always runs (10 icons, cheap) so icons
# hardened to the current accent always exist.
if [[ -n "$actual_hex" && "$actual_hex" == "$target_hex" && "$old_on" == "$on_primary_hex" ]]; then
    need_sweep=0
else
    need_sweep=1
    # Repair: swap from the color that is really in the files, not the
    # state-tracked one.
    if [[ -n "$actual_hex" && "$actual_hex" != "$target_hex" ]]; then
        old_hex="$actual_hex"
    fi
    if [[ -n "$actual_on" && "$actual_on" != "$on_primary_hex" ]]; then
        old_on="$actual_on"
    fi
fi

# ── 3. Pre-toggle to Adwaita (only when the ColorScheme sweep will run) ────
active=$(gsettings get org.gnome.desktop.interface icon-theme | tr -d "'")
if [[ "$need_sweep" == "1" ]]; then
    gsettings set org.gnome.desktop.interface icon-theme Adwaita
fi

# ── 4. ColorScheme sweep — places (folders) ─────────────────────────────────
places_dir="$mono_theme/places"
if [[ "$need_sweep" == "1" && -d $places_dir ]]; then
    psample=$(find "$places_dir" -path '*/places/*.svg' -print -quit)
    if [[ -n "$psample" ]]; then
        p_old_hex=$(grep -ozP 'ColorScheme-Highlight\s*\{\s*color:\s*\K#[0-9a-fA-F]+' "$psample" | tr '\0' '\n' | head -1)
        pe_bg=$(find "$places_dir/scalable" "$places_dir/symbolic" -path '*/places/*.svg' -print -quit 2>/dev/null)
        if [[ -n "$pe_bg" ]]; then
            p_old_on=$(grep -ozP 'ColorScheme-Background\s*\{\s*color:\s*\K#[0-9a-fA-F]+' "$pe_bg" | tr '\0' '\n' | head -1)
        fi
        # Places diverge from apps? Fix first.
        if [[ -n "$p_old_hex" && "$p_old_hex" != "$old_hex" && "$p_old_hex" != "$target_hex" ]]; then
            rg -0 -l -F "$p_old_hex" "$places_dir" -g '*.svg' 2>/dev/null \
                | xargs -r -0 -P 6 sed -i "s/$p_old_hex/$target_hex/gI"
        fi
        # Folder emblem self-heal.
        if [[ -n "$p_old_on" && "$p_old_on" != "$on_primary_hex" ]]; then
            rg -0 -l -F "color:$p_old_on" "$places_dir" -g '*.svg' 2>/dev/null \
                | xargs -r -0 -P "$(nproc)" sed -i "s/color:$p_old_on/color:$on_primary_hex/gI"
        fi
    fi
fi

# ── 5. ColorScheme sweep — apps ─────────────────────────────────────────────
if [[ "$need_sweep" == "1" ]]; then
    if [[ -n "$old_hex" && "$old_hex" == "#"?????? ]]; then
        rg -0 -l -F "$old_hex" "$mono_theme/apps" "$places_dir" -g '*.svg' 2>/dev/null \
            | xargs -r -0 -P 6 sed -i "s/$old_hex/$target_hex/gI"
    fi
    if [[ -n "$old_on" && "$old_on" != "$on_primary_hex" ]]; then
        rg -0 -l -F "color:$old_on" "$mono_theme/apps" -g '*.svg' 2>/dev/null \
            | xargs -r -0 -P "$(nproc)" sed -i "s/color:$old_on/color:$on_primary_hex/gI"
    fi
    printf '%s\n%s\n' "$target_hex" "$on_primary_hex" > "$state"
fi

# ── 6. Re-color the existing duotone app icons using themselves ─────────────
# Each duotone SVG already carries its own tonal sculpture (a dark->accent
# ramp encoded as hardcoded hexes). On accent change we recolour those icons
# in place via mono-icons.py -- they do NOT depend on external Papirus art.
# Papirus is only consulted once at conversion time, when a brand-new icon is
# being added to the theme.
generator="$repo/mono-icons.py"
target_apps="$mono_theme/apps/scalable"

duotone_icons=(
    org.gnome.Calculator
    org.gnome.Nautilus
    kitty
    firefox
    gnome-control-center
    org.gnome.Terminal
    libreoffice-calc
    telegram
    spotify-client
    org.gnome.Weather
)

for icon in "${duotone_icons[@]}"; do
    cur="$target_apps/$icon.svg"
    [[ -f "$cur" ]] || continue
    python3 "$generator" --dark "#000000" --light "$target_hex" --radius 0.5 \
        --autoscale --outdir "$target_apps" "$cur" 2>/dev/null || true
    # mono-icons.py outputs <name>.mono.svg — rename to the canonical icon name.
    mono_out="$target_apps/$icon.mono.svg"
    if [[ -f "$mono_out" ]]; then
        mv -f "$mono_out" "$cur"
    fi
done

# ── 7. Rebuild icon cache + restore theme ────────────────────────────────────
gtk-update-icon-cache -f -t "$mono_theme" 2>/dev/null
gsettings set org.gnome.desktop.interface icon-theme "$active"
sleep 0.15