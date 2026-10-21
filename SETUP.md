# Materialicious setup

## Install the icon themes

From the repository directory:

```sh
./install.sh
gsettings set org.gnome.desktop.interface icon-theme Material-Grad
```

Choose `Material-Solo` instead if you prefer the flat icons. Solo keeps its
baked-in accent; the hook described below updates Material-Grad only.

## Enable automatic Material-Grad recoloring

The icon themes and the matugen hook are installed separately. The hook needs
Bash, Python 3, ripgrep (`rg`), GNU-style `grep`, `find`, `xargs`, `sed`,
`nproc`, `gsettings`, `gtk-update-icon-cache`, `mktemp`, and `readlink`.
It also needs a GNOME session, an installed `~/.icons/Material-Grad` theme,
the repository's `mono-icons.py` and `sources/`, and a matugen-generated CSS
file at `~/.config/matugen/matugen-colors.css`.

1. Install the hook into your user-local executable directory:

   ```sh
   install -Dm755 grad_icon.sh "$HOME/.local/bin/materialicious-grad-hook"
   ```

2. In `~/.config/matugen/config.toml`, add a `post_hook` to the existing
   template that writes `~/.config/matugen/matugen-colors.css`. Keep that
   template's existing `input_path` and other settings:

   ```toml
   [templates.your_existing_color_template]
   # Keep your existing input_path here.
   output_path = "~/.config/matugen/matugen-colors.css"
   post_hook = "bash ~/.local/bin/materialicious-grad-hook"
   ```

   Replace `your_existing_color_template` with the actual template name and
   retain your existing template input. The generated CSS must define
   `--primary: #RRGGBB` and `--on_primary: #RRGGBB` values for the hook to read.
   Matugen runs a template's `post_hook` after generating that template's output.

3. Run matugen once and check its output if the icon accent does not change.
   The hook reports missing dependencies, paths, generation failures, and cache
   failures to standard error. It restores the active GNOME icon theme on exit
   and records state only after generation and icon-cache rebuilding succeed.

### Nonstandard repository location

The hook normally discovers the repository through the installed
`~/.icons/Material-Grad` symlink. If that symlink does not point to the
repository, set `MATERICIOUS_PROJECT` to the absolute repository path in the
matugen `post_hook`, for example:

```toml
post_hook = "MATERICIOUS_PROJECT='/absolute/path/to/materialicious' bash ~/.local/bin/materialicious-grad-hook"
```

Do not point `MATERICIOUS_PROJECT` at the theme directory itself; it must be
the repository root containing `mono-icons.py` and `sources/`.
