#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"

if [ -L "$HOME/.icons" ]; then
  echo "warning: ~/.icons is a symlink into a dotfiles repo; installing next to it would duplicate the theme."
fi

mkdir -p "$HOME/.icons"

install_theme() {
  local name="$1"
  local src="$repo/$name"
  local target="$HOME/.icons/$name"

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