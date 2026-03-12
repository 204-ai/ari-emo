"""
Unit tests for Ari skills.

Tests that each skill script:
  - Imports without error
  - Has the expected entry points (main, build_workflow, etc.)
  - Resolves ROOT / GENERATED paths correctly
  - Parses CLI args (--help)

Run:
  python -m pytest skills/test_skills.py -v
  # or without pytest:
  python skills/test_skills.py
"""

import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


def load_module(name: str, path: Path):
    """Import a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_help(script_path: Path) -> subprocess.CompletedProcess:
    """Run a script with --help and return the result."""
    return subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True, text=True, timeout=10,
        cwd=str(PROJECT_ROOT),
    )


# ── ComfyUI Skills ────────────────────────────────────────────────────


class TestSelfie(unittest.TestCase):
    PATH = SKILLS_DIR / "comfy" / "selfie.py"

    def test_import(self):
        mod = load_module("selfie", self.PATH)
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "build_workflow"))
        self.assertTrue(hasattr(mod, "upload_image"))
        self.assertTrue(hasattr(mod, "render_ascii_to_png"))

    def test_root_path(self):
        mod = load_module("selfie", self.PATH)
        self.assertEqual(mod.ROOT, PROJECT_ROOT)
        self.assertEqual(mod.GENERATED, PROJECT_ROOT / "generated")

    def test_comfyui_url_not_hardcoded(self):
        src = self.PATH.read_text()
        self.assertNotIn("79.168.2.183", src)

    def test_help(self):
        r = run_help(self.PATH)
        self.assertEqual(r.returncode, 0)
        self.assertIn("selfie", r.stdout.lower())


class TestMorph(unittest.TestCase):
    PATH = SKILLS_DIR / "comfy" / "morph.py"

    def test_import(self):
        mod = load_module("morph", self.PATH)
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "build_workflow"))
        self.assertTrue(hasattr(mod, "upload_image"))

    def test_root_path(self):
        mod = load_module("morph", self.PATH)
        self.assertEqual(mod.ROOT, PROJECT_ROOT)

    def test_comfyui_url_not_hardcoded(self):
        src = self.PATH.read_text()
        self.assertNotIn("79.168.2.183", src)

    def test_help(self):
        r = run_help(self.PATH)
        self.assertEqual(r.returncode, 0)
        self.assertIn("morph", r.stdout.lower())


class TestThreedee(unittest.TestCase):
    PATH = SKILLS_DIR / "comfy" / "threedee.py"

    def test_import(self):
        mod = load_module("threedee", self.PATH)
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "build_workflow"))
        self.assertTrue(hasattr(mod, "upload_image"))

    def test_root_path(self):
        mod = load_module("threedee", self.PATH)
        self.assertEqual(mod.ROOT, PROJECT_ROOT)

    def test_workflow_structure(self):
        mod = load_module("threedee", self.PATH)
        wf = mod.build_workflow("test.png", 42)
        # Must have the key nodes
        self.assertIn("1", wf)   # ImageOnlyCheckpointLoader
        self.assertIn("2", wf)   # LoadImage
        self.assertIn("7", wf)   # KSampler
        self.assertIn("9", wf)   # VoxelToMesh
        self.assertIn("10", wf)  # SaveGLB
        # VoxelToMesh must use 'algorithm' not 'method'
        self.assertIn("algorithm", wf["9"]["inputs"])
        self.assertNotIn("method", wf["9"]["inputs"])

    def test_comfyui_url_not_hardcoded(self):
        src = self.PATH.read_text()
        self.assertNotIn("79.168.2.183", src)

    def test_help(self):
        r = run_help(self.PATH)
        self.assertEqual(r.returncode, 0)
        self.assertIn("3d", r.stdout.lower())


class TestReel(unittest.TestCase):
    PATH = SKILLS_DIR / "comfy" / "reel.py"

    def test_import(self):
        mod = load_module("reel", self.PATH)
        self.assertTrue(hasattr(mod, "main"))

    def test_root_path(self):
        mod = load_module("reel", self.PATH)
        self.assertEqual(mod.ROOT, PROJECT_ROOT)

    def test_comfyui_url_not_hardcoded(self):
        src = self.PATH.read_text()
        self.assertNotIn("79.168.2.183", src)

    def test_help(self):
        r = run_help(self.PATH)
        self.assertEqual(r.returncode, 0)
        self.assertIn("reel", r.stdout.lower())


# ── Camera Skills ─────────────────────────────────────────────────────


class TestCam(unittest.TestCase):
    PATH = SKILLS_DIR / "camera" / "cam.py"

    def test_import(self):
        mod = load_module("cam", self.PATH)
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "snap"))
        self.assertTrue(hasattr(mod, "snap_ndi"))

    def test_generated_path(self):
        mod = load_module("cam", self.PATH)
        self.assertEqual(mod.GENERATED, PROJECT_ROOT / "generated")

    def test_camera_presets(self):
        mod = load_module("cam", self.PATH)
        self.assertIn("orbecc", mod.CAMERAS)
        self.assertIn("c920", mod.CAMERAS)

    def test_help(self):
        r = run_help(self.PATH)
        self.assertEqual(r.returncode, 0)
        self.assertIn("ndi", r.stdout.lower())
        self.assertIn("orbecc", r.stdout.lower())


class TestFrame(unittest.TestCase):
    PATH = SKILLS_DIR / "camera" / "frame.py"

    def test_import(self):
        mod = load_module("frame", self.PATH)
        self.assertTrue(hasattr(mod, "main"))

    def test_adb_path(self):
        mod = load_module("frame", self.PATH)
        self.assertTrue(hasattr(mod, "ADB"))

    def test_usage(self):
        """frame.py uses manual arg parsing, not argparse."""
        r = subprocess.run(
            [sys.executable, str(self.PATH)],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        # Shows usage when no args given
        combined = r.stdout + r.stderr
        self.assertIn("frame", combined.lower())


# ── Slash Command Definitions ─────────────────────────────────────────


class TestSlashCommands(unittest.TestCase):
    """Verify all .claude/commands/*.md reference correct script paths."""

    COMMANDS_DIR = PROJECT_ROOT / ".claude" / "commands"

    EXPECTED = {
        "selfie.md":  "skills/comfy/selfie.py",
        "morph.md":   "skills/comfy/morph.py",
        "3d.md":      "skills/comfy/threedee.py",
        "reel.md":    "skills/comfy/reel.py",
        "cam.md":     "skills/camera/cam.py",
        "frame.md":   "skills/camera/frame.py",
    }

    def test_commands_exist(self):
        for md_file in self.EXPECTED:
            path = self.COMMANDS_DIR / md_file
            self.assertTrue(path.exists(), f"Missing: {path}")

    def test_commands_reference_correct_scripts(self):
        for md_file, expected_script in self.EXPECTED.items():
            content = (self.COMMANDS_DIR / md_file).read_text()
            self.assertIn(
                expected_script, content,
                f"{md_file} should reference '{expected_script}'"
            )

    def test_no_hardcoded_ips(self):
        for md_file in self.EXPECTED:
            content = (self.COMMANDS_DIR / md_file).read_text()
            self.assertNotIn("79.168.2.183", content,
                             f"{md_file} contains hardcoded IP")


# ── API Routes ────────────────────────────────────────────────────────


class TestAPIRoutes(unittest.TestCase):
    """Verify the image API supports all needed MIME types."""

    def test_image_route_mime_types(self):
        route = PROJECT_ROOT / "app" / "api" / "image" / "route.ts"
        content = route.read_text()
        for ext in ["png", "jpg", "mp4", "glb", "gltf"]:
            self.assertIn(ext, content, f"Missing MIME type for .{ext}")


# ── No Hardcoded IPs in Any Skill ────────────────────────────────────


class TestNoHardcodedSecrets(unittest.TestCase):
    """Scan all skill scripts for hardcoded external IPs."""

    def test_no_comfyui_ip_in_skills(self):
        for py_file in SKILLS_DIR.rglob("*.py"):
            if py_file.name == "test_skills.py":
                continue
            content = py_file.read_text()
            self.assertNotIn(
                "79.168.2.183", content,
                f"{py_file.relative_to(PROJECT_ROOT)} contains hardcoded ComfyUI IP"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
