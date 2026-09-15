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

# ── 6. Regenerate the duotone app icons from the repo's own sources ────────
# The ramps are re-derived from the color art vendored in $repo/sources/ (part
# of this git repo — no external Papirus fetch needed). Using the S-curve +
# autoscale path reproduces the exact tonal sculpture that was originally
# approved, and is idempotent: re-running with the same accent yields the same
# file, so repeated matugen runs never darken or collapse the ramps.
generator="$repo/mono-icons.py"
sources_dir="$repo/sources"
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
    com.google.Chrome
    zen-browser
    firefox-nightly
    dev.zed.Zed
    brave-origin-nightly
    wechat
    qbittorrent
    vlc
    org.gnome.Software
    org.gnome.SystemMonitor
    org.gnome.Maps
    org.gnome.Loupe
    org.gnome.Papers
    org.gnome.TextEditor
    org.gnome.Snapshot
    org.gnome.Screenshot
    org.gnome.Meld
    org.gnome.SimpleScan
    com.mattjakeman.ExtensionManager
    gparted
    io.bassi.Amberol
    libreoffice-writer
    org.gnome.Calendar
    org.gnome.DiskUtility
    org.gnome.clocks
    org.gnome.tweaks
    mpv
    org.gnome.Boxes
    org.gnome.baobab
    org.gnome.Settings
    org.gnome.Extensions
    libreoffice-impress
    btop
    org.gnome.Logs
    org.gnome.font-viewer
    org.gnome.Connections
    org.gnome.Characters
    org.gnome.Yelp
    org.gnome.Shell.Extensions
    libreoffice-base
    libreoffice-draw
    libreoffice-math
    libreoffice-startcenter
    qemu
    preferences-system
    balena-etcher
    ca.desrt.dconf-editor
    helium
    ibus-setup-hangul
    org.fedoraproject.MediaWriter
    com.github.rafostar.Clapper
)

for icon in "${duotone_icons[@]}"; do
    src="$sources_dir/$icon.svg"
    [[ -f "$src" ]] || continue
    # Per-icon ramp tweaks (mostly tone floors / inverse ramps decided by eye).
    case "$icon" in
        com.mattjakeman.ExtensionManager) extra=(--piecewise "0.43:0.50,1.0:0.92");;
        kitty)                           extra=(--piecewise "0.247:0.42,0.46:0.52,0.48:0.58,0.95:0.88,1.0:0.92");;
        org.gnome.Maps)                  extra=(--min-t 0.15);;
        org.gnome.Papers)                extra=(--min-t 0.20);;
        org.gnome.TextEditor)            extra=(--invert --min-t 0.30 --max-t 0.88);;
        libreoffice-writer)              extra=(--min-t 0.25);;
        org.gnome.Weather)               extra=(--piecewise "0.0:0.30,0.46:0.55,0.62:0.65,0.80:0.85,1.0:0.95");;
        org.gnome.tweaks)                extra=(--piecewise "0.48:0.10,0.68:0.35,0.89:0.55,1.0:0.95");;
        org.gnome.Boxes)                 extra=(--piecewise "0.31:0.40,0.77:0.72,1.0:0.98");;
        org.gnome.Settings)              extra=(--piecewise "0.65:0.05,0.75:0.30,0.86:0.55,1.0:0.92");;
        mpv)                             extra=(--piecewise "0.20:0.30,0.30:0.46,1.0:0.96");;
        btop)                            extra=(--piecewise "0.247:0.38,0.30:0.85,0.38:0.90,1.0:0.95");;
        org.gnome.Terminal)              extra=(--piecewise "0.0:0.12,0.31:0.42,0.38:0.50,0.64:0.70,1.0:0.95");;
        dev.zed.Zed)                     extra=(--piecewise "0.247:0.35,0.31:0.45,0.45:0.60,0.89:0.90,1.0:0.95");;
        org.gnome.Screenshot)            extra=(--piecewise "0.37:0.45,0.46:0.55,0.57:0.68,1.0:0.95");;
        qbittorrent)                     extra=(--piecewise "0.30:0.40,0.38:0.52,0.44:0.58,0.75:0.75,1.0:0.95");;
        gnome-control-center)            extra=(--piecewise "0.40:0.50,0.46:0.60,0.89:0.80,1.0:0.95");;
        io.bassi.Amberol)                extra=(--piecewise "0.40:0.50,0.50:0.60,0.60:0.70,1.0:0.95");;
        org.gnome.Meld)                  extra=(--piecewise "0.38:0.45,0.48:0.52,0.65:0.62,1.0:0.85");;
        brave-origin-nightly)            extra=(--piecewise "0.32:0.42,0.40:0.52,0.45:0.60,1.0:0.95");;
        org.gnome.Extensions)            extra=(--piecewise "0.66:0.50,1.0:0.92");;
        org.gnome.Shell.Extensions)      extra=(--piecewise "0.66:0.50,1.0:0.92");;
        org.gnome.font-viewer)           extra=(--piecewise "0.39:0.50,1.0:0.95");;
        org.gnome.Connections)           extra=(--piecewise "0.25:0.35,0.37:0.50,0.52:0.70,1.0:0.95");;
        org.gnome.Logs)                  extra=(--piecewise "0.51:0.75,0.69:0.55,0.78:0.55,0.9:0.60,1.0:0.95");;
        org.gnome.Characters)            extra=(--piecewise "0.39:0.70,0.53:0.72,0.74:0.78,0.9:0.55,1.0:0.95");;
        libreoffice-base)                extra=(--piecewise "0.27:0.32,0.34:0.50,0.48:0.65,0.65:0.80,1.0:0.95");;
        libreoffice-draw)                extra=(--piecewise "0.55:0.45,0.70:0.55,0.92:0.75,1.0:0.95");;
        libreoffice-startcenter)         extra=(--piecewise "0.31:0.15,0.37:0.35,0.67:0.55,0.93:0.65,1.0:0.80");;
        qemu)                            extra=(--piecewise "0.31:0.45,0.38:0.50,0.53:0.78,1.0:0.95");;
        preferences-system)              extra=(--piecewise "0.40:0.50,0.46:0.60,0.89:0.80,1.0:0.95");;
        ca.desrt.dconf-editor)           extra=(--piecewise "0.48:0.15,0.51:0.30,0.80:0.50,0.89:0.60,1.0:0.90");;
        helium)                          extra=(--piecewise "0.28:0.45,0.36:0.55,1.0:0.95");;
        com.github.rafostar.Clapper)     extra=(--piecewise "0.25:0.28,0.32:0.48,0.80:0.65,0.89:0.78,1.0:0.95");;
        org.gnome.Yelp)                  extra=(--piecewise "0.42:0.42,0.9:0.70,1.0:0.95");;
        *)                     extra=();;
    esac
    python3 "$generator" --dark "#000000" --light "$target_hex" --radius 0.5 \
        --autoscale --outdir "$target_apps" "${extra[@]}" "$src" 2>/dev/null || true
    # mono-icons.py outputs <name>.mono.svg — rename to the canonical icon name.
    mono_out="$target_apps/$icon.mono.svg"
    if [[ -f "$mono_out" ]]; then
        mv -f "$mono_out" "$target_apps/$icon.svg"
    fi
done

# ── 7. Rebuild icon cache + restore theme ────────────────────────────────────
gtk-update-icon-cache -f -t "$mono_theme" 2>/dev/null
gsettings set org.gnome.desktop.interface icon-theme "$active"
sleep 0.15