import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server

class ContainerFileTests(unittest.TestCase):
    def test_comments_duplicates_order_and_live_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "containers.conf"
            with patch.object(server, "CONTAINER_FILE", path):
                path.write_text("# lijst\nsonarr\n\nradarr # film\nsonarr\n")
                self.assertEqual(server.container_names(), ("sonarr", "radarr"))
                path.write_text("new_container.1\n")
                self.assertEqual(server.container_names(), ("new_container.1",))

    def test_missing_file_never_falls_back(self):
        with patch.object(server, "CONTAINER_FILE", Path("/nonexistent/container-test.conf")):
            with self.assertRaises(FileNotFoundError):
                server.container_names()

    def test_removed_container_cannot_be_controlled(self):
        with patch("server.container_names", return_value=("radarr",)), patch("server.run") as run:
            with self.assertRaises(ValueError):
                server.inspect("sonarr")
            run.assert_not_called()

    def test_invalid_name_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "containers.conf"
            path.write_text("sonarr; rm\n")
            with patch.object(server, "CONTAINER_FILE", path):
                with self.assertRaises(ValueError):
                    server.container_names()
