"""Firebase Cloud Messaging support for Media Monster, using only Python's standard library."""
import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_AUDIENCE = "https://oauth2.googleapis.com/token"


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def fcm_payload(token, title, body, container, kind, event_id):
    return {"message": {
        "token": token,
        "data": {
            "title": title, "body": body, "container": container,
            "kind": kind, "eventId": event_id,
        },
        "android": {
            "priority": "HIGH",
            "ttl": "3600s",
        },
    }}


class PushService:
    REMINDER_SECONDS = 7 * 24 * 60 * 60
    def __init__(self, credentials=None, devices=None):
        self.credentials = Path(credentials or os.getenv(
            "MM_FIREBASE_CREDENTIALS", "/home/marco/mediamonster/firebase-service-account.json"))
        self.devices_path = Path(devices or os.getenv(
            "MM_PUSH_DEVICES", "/home/marco/mediamonster/push-devices.json"))
        self.lock = threading.Lock()
        self.access_token = None
        self.access_token_expiry = 0

    @property
    def configured(self):
        return self.credentials.is_file() and shutil.which("openssl") is not None

    def _load_devices(self):
        try:
            data = json.loads(self.devices_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_devices(self, devices):
        self.devices_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.devices_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(devices, separators=(",", ":")), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.devices_path)

    @staticmethod
    def _device_key(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def register(self, token, notify_stopped, notify_updates, platform="android"):
        if not isinstance(token, str) or not 20 <= len(token) <= 4096:
            raise ValueError("Ongeldig push-token")
        if platform != "android":
            raise ValueError("Onbekend apparaatplatform")
        key = self._device_key(token)
        with self.lock:
            devices = self._load_devices()
            previous = devices.get(key, {})
            events = previous.get("events", {})
            sent_at = previous.get("sentAt", {})
            if notify_stopped and not previous.get("notifyStopped"):
                events = {name: value for name, value in events.items() if not name.endswith("|stopped")}
                sent_at = {name: value for name, value in sent_at.items() if not name.endswith("|stopped")}
            if notify_updates and not previous.get("notifyUpdates"):
                events = {name: value for name, value in events.items() if not name.endswith("|update")}
                sent_at = {name: value for name, value in sent_at.items() if not name.endswith("|update")}
            devices[key] = {
                "token": token,
                "notifyStopped": bool(notify_stopped),
                "notifyUpdates": bool(notify_updates),
                "platform": platform,
                "updatedAt": int(time.time()),
                "events": events,
                "sentAt": sent_at,
            }
            self._save_devices(devices)
        return {"ok": True, "pushConfigured": self.configured}

    def unregister(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 4096:
            raise ValueError("Ongeldig push-token")
        with self.lock:
            devices = self._load_devices()
            devices.pop(self._device_key(token), None)
            self._save_devices(devices)
        return {"ok": True}

    def test(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 4096:
            raise ValueError("Ongeldig push-token")
        with self.lock:
            device = self._load_devices().get(self._device_key(token))
        if not device or not hmac.compare_digest(device.get("token", ""), token):
            raise ValueError("Telefoon is niet geregistreerd")
        self.send(token, "Media Monster", "De testmelding werkt!", "test", "test",
                  "settings-test-" + str(int(time.time())))
        return {"ok": True}

    def _credentials(self):
        data = json.loads(self.credentials.read_text(encoding="utf-8"))
        for key in ("client_email", "private_key", "project_id"):
            if not data.get(key):
                raise ValueError("Firebase-serviceaccount is onvolledig")
        return data

    def _oauth_token(self):
        now = int(time.time())
        if self.access_token and now < self.access_token_expiry - 60:
            return self.access_token
        credentials = self._credentials()
        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        claims = _b64(json.dumps({
            "iss": credentials["client_email"], "scope": FCM_SCOPE, "aud": FCM_AUDIENCE,
            "iat": now, "exp": now + 3600,
        }, separators=(",", ":")).encode())
        unsigned = (header + "." + claims).encode("ascii")
        key_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as key_file:
                key_file.write(credentials["private_key"])
                key_path = key_file.name
            os.chmod(key_path, 0o600)
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", key_path], input=unsigned,
                capture_output=True, timeout=15, check=False)
            if result.returncode:
                raise RuntimeError("Firebase-aanmelding kon niet worden ondertekend")
        finally:
            if key_path:
                Path(key_path).unlink(missing_ok=True)
        assertion = unsigned.decode("ascii") + "." + _b64(result.stdout)
        request = urllib.request.Request(
            FCM_AUDIENCE,
            data=urllib.parse.urlencode({
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            token_data = json.load(response)
        self.access_token = token_data["access_token"]
        self.access_token_expiry = now + int(token_data.get("expires_in", 3600))
        return self.access_token

    def send(self, token, title, body, container, kind, event_id):
        credentials = self._credentials()
        payload = fcm_payload(token, title, body, container, kind, event_id)
        request = urllib.request.Request(
            "https://fcm.googleapis.com/v1/projects/{}/messages:send".format(credentials["project_id"]),
            data=json.dumps(payload).encode(), method="POST",
            headers={
                "Authorization": "Bearer " + self._oauth_token(),
                "Content-Type": "application/json; charset=utf-8",
            })
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)

    @staticmethod
    def active_events(status, device):
        events = {}
        for container in status.get("containers", []):
            name = container.get("name", "")
            state = container.get("state")
            health = container.get("health")
            if device.get("notifyStopped") and state != "unknown":
                events[name + "|stopped"] = state in ("exited", "dead", "created") or health == "unhealthy"
            update = container.get("update") or {}
            if device.get("notifyUpdates") and update.get("available") is not None:
                events[name + "|update"] = update.get("available") is True
        return events

    def check(self, status):
        if not self.configured:
            return
        with self.lock:
            devices = self._load_devices()
        dirty = False
        now = int(time.time())
        for key, device in list(devices.items()):
            current = self.active_events(status, device)
            previous = device.setdefault("events", {})
            sent_at = device.setdefault("sentAt", {})
            for event, active in current.items():
                was_active = previous.get(event, False)
                if active and was_active and event not in sent_at:
                    # Migrate pre-reminder state without immediately repeating an old alert.
                    sent_at[event] = now
                    dirty = True
                last_sent = sent_at.get(event, 0)
                remind = isinstance(last_sent, int) and now - last_sent >= self.REMINDER_SECONDS
                if active and (not was_active or remind):
                    container, kind = event.rsplit("|", 1)
                    body = (container + " is gestopt of ongezond" if kind == "stopped"
                            else "Update beschikbaar voor " + container)
                    try:
                        self.send(device["token"], "Media Monster", body, container, kind,
                                  str(now) + "-" + key[:10] + "-" + kind)
                        sent_at[event] = now
                        dirty = True
                    except urllib.error.HTTPError as exc:
                        error = exc.read().decode(errors="replace")
                        if exc.code in (400, 404) and "UNREGISTERED" in error:
                            devices.pop(key, None)
                            dirty = True
                            break
                    except Exception:
                        continue
                if previous.get(event) != active:
                    previous[event] = active
                    dirty = True
                if not active and event in sent_at:
                    sent_at.pop(event, None)
                    dirty = True
        if dirty:
            with self.lock:
                self._save_devices(devices)

    def monitor(self, snapshot, stop, quiet=None):
        while not stop.is_set():
            if quiet is None or not quiet():
                try:
                    self.check(snapshot())
                except Exception:
                    pass
            stop.wait(30)
