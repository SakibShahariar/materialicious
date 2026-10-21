from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_SPEC = importlib.util.spec_from_file_location("mono_icons", ROOT / "mono-icons.py")
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
mono_icons = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(mono_icons)


class MonoIconsTests(unittest.TestCase):
    def test_autoscale_maps_source_luminance_endpoints_to_ramp_endpoints(self):
        ramp = mono_icons.build_ramp(
            "#000000", "#ffffff", 0.5,
            autoscale=True, src_min=0.2, src_max=0.8, linear=True,
        )
        self.assertEqual(ramp(51, 51, 51), (0, 0, 0))
        self.assertEqual(ramp(204, 204, 204), (255, 255, 255))

    def test_autoscale_degenerate_span_falls_back_to_global_mapping(self):
        ramp = mono_icons.build_ramp(
            "#000000", "#ffffff", 0.5,
            autoscale=True, src_min=0.5, src_max=0.5, linear=True,
        )
        value = ramp(128, 128, 128)
        self.assertTrue(all(126 <= channel <= 130 for channel in value))

    def test_comments_and_protected_elements_are_preserved(self):
        source = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<!-- fill: #ffffff; <path d="M0 0h1v1z"/> -->'
            '<defs><path d="M0 0h1v1z"/></defs>'
            '<style>/* fill: #ffffff; */ .shape { fill: #ffffff; }</style>'
            '<path class="shape" d="M0 0h1v1z"/>'
            '</svg>'
        )
        ramp = mono_icons.build_ramp("#000000", "#c9bfff", 0.5, linear=True)
        recolored, _ = mono_icons.recolor_content(source, ramp)
        self.assertIn('<!-- fill: #ffffff; <path d="M0 0h1v1z"/> -->', recolored)
        self.assertIn('<defs><path d="M0 0h1v1z"/></defs>', recolored)
        self.assertIn('/* fill: #ffffff; */', recolored)
        self.assertIn('.shape { fill:#c9bfff; }', recolored)
        self.assertIn('<path class="shape" d="M0 0h1v1z" fill="#000000"/>', recolored)
        quoted_source = """<svg><path fill='#ffffff'/><path stroke="#ffffff"/></svg>"""
        quoted_result, quoted_count = mono_icons.recolor_content(quoted_source, ramp)
        self.assertEqual(quoted_count, 2)
        self.assertIn("fill='#c9bfff'", quoted_result)
        self.assertIn('stroke="#c9bfff"', quoted_result)

    def test_named_and_rgba_colors_are_reported_as_unsupported(self):
        source = (
            '<svg><path fill="red"/><path fill="rgba(1, 2, 3, 0.5)"/>'
            '<!-- fill: blue -->'
            '</svg>'
        )
        unsupported = mono_icons.unsupported_color_values(source)
        self.assertIn("red", unsupported)
        self.assertIn("rgba(1, 2, 3, 0.5)", unsupported)
        self.assertNotIn("blue", unsupported)

    def test_missing_inputs_show_usage_instead_of_traceback(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "mono-icons.py")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("provide SVG input files", result.stderr)

    def test_invalid_numeric_ranges_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "icon.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M0 0h1v1z"/></svg>')
            result = subprocess.run(
                [sys.executable, str(ROOT / "mono-icons.py"), "--min-t", "0.8", "--max-t", "0.2", str(source)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("less than or equal to", result.stderr)

    def test_invalid_color_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "icon.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M0 0h1v1z"/></svg>')
            result = subprocess.run(
                [sys.executable, str(ROOT / "mono-icons.py"), "--dark", "not-a-color", str(source)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("valid #rgb or #rrggbb", result.stderr)

    def test_invalid_piecewise_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "icon.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M0 0h1v1z"/></svg>')
            result = subprocess.run(
                [sys.executable, str(ROOT / "mono-icons.py"), "--piecewise", "broken", str(source)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("invalid --piecewise", result.stderr)

    def test_hook_restores_icon_theme_and_keeps_state_on_generator_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            theme = home / ".icons" / "Material-Grad"
            (theme / "apps" / "scalable").mkdir(parents=True)
            (theme / "places").mkdir(parents=True)
            colors = home / ".config" / "matugen" / "matugen-colors.css"
            colors.parent.mkdir(parents=True)
            colors.write_text("--primary: #333333;\n--on_primary: #eeeeee;\n")
            state = home / ".local" / "share" / "matugen-icon-themes" / "state"
            state.parent.mkdir(parents=True)
            state.write_text("#111111\n#222222\n")
            (bin_dir / "rg").write_text("#!/bin/sh\nexit 1\n")
            (bin_dir / "python3").write_text("#!/bin/sh\nexit 1\n")
            (bin_dir / "gtk-update-icon-cache").write_text("#!/bin/sh\nexit 0\n")
            (bin_dir / "gsettings").write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"get\" ]; then printf \"'CustomTheme'\\n\"; exit 0; fi\n"
                'printf "%s\\n" "$*" >> "$HOME/gsettings.log"\n'
            )
            for executable in bin_dir.iterdir():
                executable.chmod(0o755)
            environment = {
                **__import__("os").environ,
                "HOME": str(home),
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "MATERICIOUS_PROJECT": str(ROOT),
            }
            result = subprocess.run(
                ["bash", str(ROOT / "grad_icon.sh")],
                capture_output=True, text=True, check=False, env=environment, timeout=30,
            )
            log = (home / "gsettings.log").read_text()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("icon-theme Adwaita", log)
            self.assertIn("icon-theme CustomTheme", log)
            self.assertEqual(state.read_text(), "#111111\n#222222\n")
            self.assertIn("generation failed", result.stderr)

    def test_mixed_batch_inputs_generate_valid_file_and_fail_overall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "valid.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M0 0h1v1z"/></svg>')
            jobs = root / "jobs.txt"
            jobs.write_text(f"{source}\n{root / 'missing.svg'}\n")
            output = root / "output"
            result = subprocess.run(
                [sys.executable, str(ROOT / "mono-icons.py"), "--jobs", str(jobs), "--outdir", str(output)],
                capture_output=True, text=True, check=False,
            )
            # Assert before TemporaryDirectory cleans up the generated output.
            self.assertEqual(result.returncode, 1)
            self.assertTrue((output / "valid.mono.svg").is_file(), result.stdout + result.stderr)
            self.assertIn("missing input", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
