import os
import sys
import unittest
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Import logic from app.py
from app import (
    validate_ply_file,
    get_history_items,
    check_viewer_server,
    PROJECT_ROOT,
    OUTPUTS_DIR,
    UPLOADS_DIR,
    SAMPLE_TEASER
)
from viewer.serve_viewer import ViewerHTTPHandler

class TestPhotoDepth3DComponents(unittest.TestCase):
    def test_paths_and_environment(self):
        self.assertTrue(PROJECT_ROOT.exists(), "Project root should exist")
        self.assertTrue(OUTPUTS_DIR.exists(), "Outputs directory should exist")
        self.assertTrue(UPLOADS_DIR.exists(), "Uploads directory should exist")
        self.assertTrue(SAMPLE_TEASER.exists(), "Sample teaser.jpg must exist in ml-sharp/data")

    def test_ply_validation_genuine(self):
        sample_ply = OUTPUTS_DIR / "sample_teaser.ply"
        self.assertTrue(sample_ply.exists(), "sample_teaser.ply must exist")
        stats = validate_ply_file(sample_ply)
        self.assertGreater(stats["file_size"], 10_000_000, "Real 3DGS file must be large (>10MB)")
        self.assertGreater(stats["vertex_count"], 1_000_000, "Should have over 1M Gaussians")
        self.assertGreaterEqual(stats["properties_count"], 7, "Should contain essential 3DGS properties")

    def test_ply_validation_invalid(self):
        # Create a fake tiny PLY file to verify it is rejected
        fake_ply = UPLOADS_DIR / "fake_test.ply"
        with open(fake_ply, "w") as f:
            f.write("ply\nformat ascii 1.0\nelement vertex 3\nend_header\n")
        try:
            with self.assertRaises(ValueError):
                validate_ply_file(fake_ply)
        finally:
            if fake_ply.exists():
                fake_ply.unlink()

    def test_safe_ply_path_resolution(self):
        # Test path traversal resistance
        handler = ViewerHTTPHandler
        # Instantiate dummy handler without socket
        resolved_traversal = handler.resolve_ply_path(handler, "../../test_output/teaser.ply")
        # Should cleanly resolve to the basename teaser.ply inside test_output / outputs without error
        self.assertIsNotNone(resolved_traversal)
        self.assertEqual(resolved_traversal.name, "teaser.ply")

        # Test non-existent file
        resolved_missing = handler.resolve_ply_path(handler, "non_existent_file_xyz123.ply")
        self.assertIsNone(resolved_missing, "Missing file should return None")

    def test_history_scanner(self):
        items = get_history_items()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0, "Should detect at least sample_teaser.ply in history")
        names = [item["name"] for item in items]
        self.assertIn("sample_teaser.ply", names)

    def test_viewer_server_alive(self):
        is_alive = check_viewer_server()
        self.assertTrue(is_alive, "Viewer server on port 8080 should be responsive")


if __name__ == "__main__":
    unittest.main()
