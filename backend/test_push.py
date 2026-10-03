import json
import tempfile
import unittest
import threading
import time
from unittest.mock import patch, PropertyMock
from pathlib import Path

from push import PushService, fcm_payload


class PushTests(unittest.TestCase):
    def test_fcm_payload_is_data_only_for_device_side_deduplication(self):
        payload = fcm_payload("token", "Media Monster", "Test", "sonarr", "stopped", "event")
        message = payload["message"]
        self.assertNotIn("notification", message)
        self.assertEqual(message["data"]["body"], "Test")
        self.assertEqual(message["android"]["priority"], "HIGH")

    def test_register_stores_preferences_without_plain_token_as_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            service = PushService(credentials=Path(directory) / "missing.json", devices=path)
            result = service.register("a" * 40, True, False)
            saved = json.loads(path.read_text())
            self.assertTrue(result["ok"])
            self.assertFalse(result["pushConfigured"])
            self.assertNotIn("a" * 40, saved)
            self.assertEqual(next(iter(saved.values()))["token"], "a" * 40)

    def test_active_events_respect_preferences(self):
        service = PushService()
        status = {"containers": [
            {"name": "sonarr", "state": "running", "health": "healthy", "update": {"available": True}},
            {"name": "radarr", "state": "exited", "health": None, "update": {"available": False}},
        ]}
        events = service.active_events(status, {"notifyStopped": True, "notifyUpdates": True})
        self.assertTrue(events["sonarr|update"])
        self.assertTrue(events["radarr|stopped"])
        self.assertFalse(events["radarr|update"])

    def test_unknown_status_does_not_create_false_alarm(self):
        service = PushService()
        status = {"containers": [{"name": "sonarr", "state": "unknown", "health": None}]}
        self.assertEqual(service.active_events(status, {"notifyStopped": True}), {})

    def test_storage_alert_starts_at_ten_percent_free_space(self):
        service = PushService()
        status = {"containers": [], "storage": [
            {"name": "NUC 11", "online": True, "free": 10, "total": 100},
            {"name": "DS224", "online": True, "free": 11, "total": 100},
        ]}
        events = service.active_events(status, {})
        self.assertTrue(events["storage:NUC 11|storage"])
        self.assertFalse(events["storage:DS224|storage"])

    def test_unregister_removes_device(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            service = PushService(credentials=Path(directory) / "missing.json", devices=path)
            service.register("a" * 40, True, True)
            self.assertTrue(service.unregister("a" * 40)["ok"])
            self.assertEqual(json.loads(path.read_text()), {})

    def test_monitor_skips_snapshot_and_push_during_quiet_period(self):
        service = PushService()
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch.object(service, "check") as check, patch.object(stop, "wait", side_effect=finish):
            service.monitor(lambda: {"containers": []}, stop, quiet=lambda: True)
        check.assert_not_called()

    def test_active_problem_is_reminded_after_one_week(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            credentials = Path(directory) / "credentials.json"
            credentials.write_text("{}")
            service = PushService(credentials=credentials, devices=path)
            token = "a" * 40
            service.register(token, False, True)
            status = {"containers": [{"name": "sonarr", "state": "running",
                                      "update": {"available": True}}]}
            with patch.object(service, "send") as send, \
                    patch("push.time.time", return_value=1000):
                service.check(status)
                service.check(status)
                send.assert_called_once()

    def test_existing_active_problem_starts_reminder_clock_during_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            credentials = Path(directory) / "credentials.json"
            credentials.write_text("{}")
            service = PushService(credentials=credentials, devices=path)
            token = "a" * 40
            key = service._device_key(token)
            path.write_text(json.dumps({key: {"token": token, "notifyStopped": False,
                "notifyUpdates": True, "events": {"sonarr|update": True}}}))
            status = {"containers": [{"name": "sonarr", "state": "running",
                                      "update": {"available": True}}]}
            with patch.object(service, "send") as send, patch("push.time.time", return_value=1000):
                service.check(status)
                send.assert_not_called()
            saved = json.loads(path.read_text())[key]
            self.assertEqual(saved["sentAt"]["sonarr|update"], 1000)
            with patch.object(service, "send") as send, \
                    patch("push.time.time", return_value=1000 + service.REMINDER_SECONDS):
                service.check(status)
                send.assert_called_once()

    def test_automatic_update_notice_is_sent_to_each_registered_device(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            credentials = Path(directory) / "credentials.json"
            credentials.write_text("{}")
            service = PushService(credentials=credentials, devices=path)
            service.register("a" * 40, False, False)
            service.register("b" * 40, False, False)
            with patch.object(PushService, "configured", new_callable=PropertyMock, return_value=True), \
                    patch.object(service, "send") as send:
                service.send_automatic_update_notice(["sonarr", "radarr"])
            self.assertEqual(send.call_count, 2)
            self.assertTrue(all(call.args[2] == "Automatisch bijgewerkt: sonarr, radarr"
                                for call in send.call_args_list))


if __name__ == "__main__":
    unittest.main()
