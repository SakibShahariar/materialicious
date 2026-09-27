#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"

ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons"

mkdir -p "$ICONS_DIR"

install_theme() {
  local name="$1"
  local src="$repo/$name"
  local target="$ICONS_DIR/$name"

  if [ -e "$target" ] && [ "$(readlink -f "$target")" != "$src" ]; then
    echo "error: $target already exists" >&2
    exit 1
  fi

  ln -sfn "$src" "$target"
  gtk-update-icon-cache -f -t "$target" 2>/dev/null || true
  echo "installed $name -> $target"
}

install_theme Material-Solo
install_theme Material-Grad

echo "set icon theme with: gsettings set org.gnome.desktop.interface icon-theme Material-Solo"