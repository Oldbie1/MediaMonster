import threading
import unittest
from unittest.mock import patch
import server

class MonitorTests(unittest.TestCase):
    def test_quiet_period_boundaries(self):
        def at(hour, minute):
            return server.time.struct_time((2026, 9, 6, hour, minute, 0, 0, 0, -1))
        self.assertFalse(server.quiet_period(at(1, 14)))
        self.assertTrue(server.quiet_period(at(1, 15)))
        self.assertTrue(server.quiet_period(at(1, 29)))
        self.assertFalse(server.quiet_period(at(1, 30)))
        self.assertFalse(server.quiet_period(at(3, 44)))
        self.assertTrue(server.quiet_period(at(3, 45)))
        self.assertTrue(server.quiet_period(at(4, 29)))
        self.assertFalse(server.quiet_period(at(4, 30)))

    def test_startup_checks_every_container(self):
        with patch.dict(server.UPDATES, {}, clear=True), patch("server.check_update") as check:
            server.refresh_updates()
            self.assertCountEqual([c.args[0] for c in check.call_args_list], server.container_names())

    def test_fresh_results_are_cached_and_failed_results_retried(self):
        cache = {n: {"available": False, "checkedAt": 950} for n in server.container_names()}
        cache["sonarr"] = {"available": None, "checkedAt": 900}
        cache["radarr"] = {"available": True, "checkedAt": 50}
        with patch.dict(server.UPDATES, cache, clear=True), patch("server.time.time", return_value=1000), patch("server.check_update") as check:
            server.refresh_updates()
            self.assertCountEqual([c.args[0] for c in check.call_args_list], ["sonarr", "radarr"])

    def test_monitor_starts_immediately_and_survives_failure(self):
        stop = threading.Event()
        calls = []
        def refresh():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary")
            stop.set()
        with patch("server.refresh_updates", side_effect=refresh), \
                patch("server.quiet_period", return_value=False), patch.object(stop, "wait"):
            server.update_monitor(stop)
        self.assertEqual(len(calls), 2)

    def test_monitor_skips_checks_during_quiet_period(self):
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch("server.refresh_updates") as refresh, \
                patch("server.quiet_period", return_value=True), \
                patch.object(stop, "wait", side_effect=finish):
            server.update_monitor(stop)
        refresh.assert_not_called()

    def test_monitor_skips_checks_during_maintenance(self):
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch("server.refresh_updates") as refresh, \
                patch("server.monitoring_paused", return_value=True), \
                patch.object(stop, "wait", side_effect=finish):
            server.update_monitor(stop)
        refresh.assert_not_called()

    def test_monitor_updates_and_notifies_when_automatic_updates_are_enabled(self):
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch("server.refresh_updates"), \
                patch("server.monitoring_paused", return_value=False), \
                patch("server.automatic_updates_enabled", return_value=True), \
                patch("server.update_all", return_value={"updated": ["sonarr"]}) as update_all, \
                patch.object(server.PUSH, "send_automatic_update_notice") as notice, \
                patch.object(stop, "wait", side_effect=finish):
            server.update_monitor(stop)
        update_all.assert_called_once()
        notice.assert_called_once_with(["sonarr"])

    def test_monitor_checks_updates_when_automatic_recovery_is_disabled(self):
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch("server.refresh_updates") as refresh, \
                patch("server.monitoring_paused", return_value=False), \
                patch("server.automatic_recovery_enabled", return_value=False), \
                patch("server.automatic_updates_enabled", return_value=False), \
                patch("server.update_all") as update_all, \
                patch.object(stop, "wait", side_effect=finish):
            server.update_monitor(stop)
        refresh.assert_called_once()
        update_all.assert_not_called()

    def test_automatic_updates_run_independently_of_recovery(self):
        stop = threading.Event()
        def finish(_):
            stop.set()
        with patch("server.refresh_updates"), \
                patch("server.monitoring_paused", return_value=False), \
                patch("server.automatic_recovery_enabled", return_value=False), \
                patch("server.automatic_updates_enabled", return_value=True), \
                patch("server.update_all", return_value={"updated": ["radarr"]}) as update_all, \
                patch.object(server.PUSH, "send_automatic_update_notice") as notice, \
                patch.object(stop, "wait", side_effect=finish):
            server.update_monitor(stop)
        update_all.assert_called_once()
        notice.assert_called_once_with(["radarr"])

