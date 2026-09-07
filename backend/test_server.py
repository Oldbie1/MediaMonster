import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server

class SafetyTests(unittest.TestCase):
    def test_maintenance_is_persisted_and_expires(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(server, "MAINTENANCE_FILE", Path(directory) / "maintenance.json"), \
                patch("server.time.time", return_value=1000):
            self.assertEqual(server.set_maintenance(60), {"active": True, "until": 4600})
            self.assertFalse(server.maintenance_status(4600)["active"])

    def test_update_all_only_updates_available_containers_and_continues(self):
        updates = {"sonarr": {"available": True}, "radarr": {"available": False},
                   "lidarr": {"available": True}}
        def perform(name, operation):
            if name == "lidarr":
                raise RuntimeError("failure")
        with patch.dict(server.UPDATES, updates, clear=True), \
                patch("server.container_names", return_value=("sonarr", "radarr", "lidarr")), \
                patch("server.perform_action", side_effect=perform) as action:
            result = server.update_all()
        self.assertEqual([call.args for call in action.call_args_list], [("sonarr", "update"), ("lidarr", "update")])
        self.assertEqual(result["updated"], ["sonarr"])
        self.assertEqual(result["failed"], ["lidarr"])
    def test_password_hash_verifies_without_storing_password(self):
        value = server.password_hash("testwachtwoord1", salt=b"s" * 24)
        with patch.object(server, "PASSWORD_HASH", value):
            self.assertTrue(server.verify_password("testwachtwoord1"))
            self.assertFalse(server.verify_password("verkeerd-wachtwoord"))
        self.assertNotIn("testwachtwoord1", value)

    def test_password_requires_eight_characters_letter_and_number(self):
        self.assertTrue(server.valid_password("monster1"))
        self.assertFalse(server.valid_password("monsters"))
        self.assertFalse(server.valid_password("12345678"))
        self.assertFalse(server.valid_password("m1kort"))

    def test_fifth_bad_login_is_temporarily_blocked(self):
        with patch.dict(server.LOGIN_ATTEMPTS, {}, clear=True):
            for _ in range(5):
                server.record_login("127.0.0.1", False)
            self.assertTrue(server.login_blocked("127.0.0.1"))

    def test_saved_password_is_hashed_and_readable_by_login(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(server, "PASSWORD_HASH", ""), \
                patch.object(server, "PASSWORD_FILE", Path(directory) / "password.hash"):
            server.save_password("nieuw-wachtwoord1")
            self.assertTrue(server.verify_password("nieuw-wachtwoord1"))
            self.assertNotIn("nieuw-wachtwoord1", server.PASSWORD_FILE.read_text())

    def test_stopped_beats_update(self):
        self.assertEqual(server.color({"Status": "exited"}, True), "red")
    def test_unhealthy_beats_update(self):
        self.assertEqual(server.color({"Status": "running", "Health": {"Status": "unhealthy"}}, True), "red")
    def test_update_yellow(self):
        self.assertEqual(server.color({"Status": "running"}, True), "yellow")
    def test_missing_mount_never_reports_root_space(self):
        with patch("server.os.path.ismount", return_value=False), patch("server.shutil.disk_usage") as usage:
            self.assertFalse(server.storage("DS224", "/mnt/DS224/video")["online"])
            usage.assert_not_called()
    def test_unknown_container_cannot_execute(self):
        with patch("server.run") as run:
            with self.assertRaises(ValueError):
                server.action("not-allowed", "start")
            run.assert_not_called()
    def test_arbitrary_command_rejected(self):
        with self.assertRaises(ValueError):
            server.action("sonarr", "rm")
    def test_update_failure_is_unknown(self):
        with patch("server.inspect", side_effect=RuntimeError):
            self.assertIsNone(server.check_update("sonarr")["available"])
    def test_update_requires_trusted_compose(self):
        with self.assertRaises(ValueError):
            server.compose_args({"Config": {"Labels": {}}})

if __name__ == "__main__":
    unittest.main()
