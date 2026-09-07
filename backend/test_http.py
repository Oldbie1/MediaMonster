import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import server

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.TOKEN = "t" * 48
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def call(self, path, method="GET", token=None, data=None):
        payload = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=payload, method=method)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        return urllib.request.urlopen(req, timeout=5)

    def test_no_token_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.call("/v1/status")
        self.assertEqual(failure.exception.code, 401)

    def test_status_authorized(self):
        with patch("server.snapshot", return_value={"docker": True}):
            with self.call("/v1/status", token=server.TOKEN) as response:
                self.assertEqual(json.load(response), {"docker": True})

    def test_app_update_metadata_and_public_apk(self):
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / "app-release.json"
            apk = Path(directory) / "MediaMonster-latest.apk"
            release.write_text(json.dumps({"versionCode": 14, "versionName": "0.6.0"}))
            apk.write_bytes(b"test-apk")
            with patch.object(server, "APP_RELEASE_FILE", release), patch.object(server, "APP_APK_FILE", apk):
                with self.call("/v1/app/update", token=server.TOKEN) as response:
                    data = json.load(response)
                    self.assertEqual(data["versionCode"], 14)
                    self.assertEqual(data["versionName"], "0.6.0")
                    self.assertEqual(data["downloadUrl"], "https://mm.tenhaaf.nu/v1/app/apk/0.6.0")
                with self.call("/v1/app/apk") as response:
                    self.assertEqual(response.headers.get_content_type(), "application/vnd.android.package-archive")
                    self.assertEqual(response.read(), b"test-apk")
                with self.call("/v1/app/apk/0.6.0") as response:
                    self.assertEqual(response.read(), b"test-apk")

    def test_disallowed_container(self):
        with patch("server.action") as action:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.call("/v1/containers/other/start", method="POST", token=server.TOKEN)
            self.assertEqual(failure.exception.code, 403)
            action.assert_not_called()

    def test_get_cannot_mutate(self):
        with patch("server.action") as action:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.call("/v1/containers/sonarr/stop", token=server.TOKEN)
            self.assertEqual(failure.exception.code, 404)
            action.assert_not_called()

    def test_push_registration_requires_valid_json_preferences(self):
        with patch.object(server.PUSH, "register", return_value={"ok": True, "pushConfigured": False}) as register:
            with self.call("/v1/push/register", method="POST", token=server.TOKEN, data={
                "token": "f" * 40, "notifyStopped": True,
                "notifyUpdates": False, "platform": "android",
            }) as response:
                self.assertEqual(json.load(response), {"ok": True, "pushConfigured": False})
            register.assert_called_once_with("f" * 40, True, False, "android")

    def test_password_login_returns_api_token(self):
        password = "testwachtwoord1"
        with patch.object(server, "PASSWORD_HASH", server.password_hash(password)), \
                patch.dict(server.LOGIN_ATTEMPTS, {}, clear=True):
            with self.call("/v1/login", method="POST", data={"password": password}) as response:
                self.assertEqual(json.load(response), {"token": server.TOKEN})

    def test_wrong_password_is_rejected(self):
        with patch.object(server, "PASSWORD_HASH", server.password_hash("testwachtwoord1")), \
                patch.dict(server.LOGIN_ATTEMPTS, {}, clear=True):
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.call("/v1/login", method="POST", data={"password": "verkeerd-wachtwoord"})
            self.assertEqual(failure.exception.code, 401)

    def test_unreadable_login_is_not_reported_as_wrong_password(self):
        with patch("server.record_login") as record:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.call("/v1/login", method="POST")
            self.assertEqual(failure.exception.code, 400)
            record.assert_not_called()

    def test_authenticated_user_can_set_login_password(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(server, "PASSWORD_HASH", ""), \
                patch.object(server, "PASSWORD_FILE", Path(directory) / "password.hash"):
            with self.call("/v1/password", method="POST", token=server.TOKEN,
                           data={"password": "nieuw-wachtwoord1"}) as response:
                self.assertEqual(json.load(response), {"ok": True})
            with self.call("/v1/login", method="POST",
                           data={"password": "nieuw-wachtwoord1"}) as response:
                self.assertEqual(json.load(response), {"token": server.TOKEN})

    def test_authenticated_user_can_set_maintenance(self):
        with patch("server.set_maintenance", return_value={"active": True, "until": 4600}) as setter:
            with self.call("/v1/maintenance", method="POST", token=server.TOKEN,
                           data={"minutes": 60}) as response:
                self.assertEqual(json.load(response), {"active": True, "until": 4600})
        setter.assert_called_once_with(60)

    def test_update_all_endpoint(self):
        with patch("server.update_all", return_value={"ok": True, "updated": ["sonarr"],
                                                       "failed": [], "total": 1}):
            with self.call("/v1/containers/update-all", method="POST", token=server.TOKEN,
                           data={}) as response:
                self.assertEqual(json.load(response)["updated"], ["sonarr"])
