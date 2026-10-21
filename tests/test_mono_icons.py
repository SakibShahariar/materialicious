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
            '<style>.shape { fill: #ffffff; }</style>'
            '<path class="shape" d="M0 0h1v1z"/>'
            '</svg>'
        )
        ramp = mono_icons.build_ramp("#000000", "#c9bfff", 0.5, linear=True)
        recolored, _ = mono_icons.recolor_content(source, ramp)
        self.assertIn('<!-- fill: #ffffff; <path d="M0 0h1v1z"/> -->', recolored)
        self.assertIn('<defs><path d="M0 0h1v1z"/></defs>', recolored)
        self.assertIn('.shape { fill:#c9bfff; }', recolored)
        self.assertIn('<path class="shape" d="M0 0h1v1z" fill="#000000"/>', recolored)

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
        self.assertEqual(result.returncode, 1)
        self.assertTrue((output / "valid.mono.svg").is_file())
        self.assertIn("missing input", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
