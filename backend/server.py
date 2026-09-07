"""Media Monster API. Python 3.11+, Docker CLI and Compose; no pip dependencies."""
import concurrent.futures
import base64
import hmac
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from push import PushService

CONTAINER_FILE = Path(os.getenv("MM_CONTAINER_FILE", "/etc/media-monster-containers.conf"))
STORAGE = {"C:": "/mnt/c", "DS224": "/mnt/DS224/video", "DS716": "/mnt/DS716/video"}
TOKEN = os.getenv("MM_TOKEN", "")
PASSWORD_HASH = os.getenv("MM_PASSWORD_HASH", "")
PASSWORD_FILE = Path(os.getenv("MM_PASSWORD_FILE", str(Path(__file__).with_name("password.hash"))))
APP_RELEASE_FILE = Path(os.getenv("MM_APP_RELEASE_FILE", str(Path(__file__).with_name("app-release.json"))))
APP_APK_FILE = Path(os.getenv("MM_APP_APK_FILE", str(Path(__file__).with_name("MediaMonster-latest.apk"))))
MAINTENANCE_FILE = Path(os.getenv("MM_MAINTENANCE_FILE", str(Path(__file__).with_name("maintenance.json"))))
UPDATES = {}
LOCK = threading.Lock()
ACTION_LOCK = threading.Lock()
PUSH = PushService()
LOGIN_LOCK = threading.Lock()
LOGIN_ATTEMPTS = {}

def quiet_period(current=None):
    current = current or time.localtime()
    minute = current.tm_hour * 60 + current.tm_min
    return 75 <= minute < 90 or 225 <= minute < 270

def maintenance_status(current=None):
    now = int(time.time() if current is None else current)
    try:
        value = json.loads(MAINTENANCE_FILE.read_text(encoding="utf-8")).get("until", 0)
        until = value if isinstance(value, int) and not isinstance(value, bool) else 0
    except (OSError, ValueError, AttributeError):
        until = 0
    return {"active": until > now, "until": until if until > now else None}

def set_maintenance(minutes):
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 0 <= minutes <= 10080:
        raise ValueError("Kies een onderhoudsduur van maximaal zeven dagen")
    until = int(time.time()) + minutes * 60 if minutes else 0
    temporary = MAINTENANCE_FILE.with_suffix(MAINTENANCE_FILE.suffix + ".tmp")
    temporary.write_text(json.dumps({"until": until}, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(MAINTENANCE_FILE)
    return maintenance_status()

def monitoring_paused():
    return quiet_period() or maintenance_status()["active"]

def app_release():
    data = json.loads(APP_RELEASE_FILE.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or not isinstance(data.get("versionCode"), int)
            or data["versionCode"] < 1 or not isinstance(data.get("versionName"), str)
            or not data["versionName"] or not APP_APK_FILE.is_file()):
        raise ValueError("Ongeldige app-release")
    return {
        "versionCode": data["versionCode"],
        "versionName": data["versionName"],
        "downloadUrl": "https://mm.tenhaaf.nu/v1/app/apk/" + data["versionName"],
    }

def valid_password(password):
    return (isinstance(password, str) and 8 <= len(password) <= 256
            and any(character.isalpha() for character in password)
            and any(character.isdigit() for character in password))

def password_hash(password, iterations=310000, salt=None):
    if not valid_password(password):
        raise ValueError("Wachtwoord moet minimaal 8 tekens, 1 letter en 1 cijfer hebben")
    salt = salt or os.urandom(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(digest).decode())

def configured_password_hash():
    if PASSWORD_HASH:
        return PASSWORD_HASH
    try:
        return PASSWORD_FILE.read_text(encoding="ascii").strip()
    except OSError:
        return ""

def save_password(password):
    encoded = password_hash(password)
    temporary = PASSWORD_FILE.with_suffix(PASSWORD_FILE.suffix + ".tmp")
    temporary.write_text(encoded + "\n", encoding="ascii")
    os.chmod(temporary, 0o600)
    temporary.replace(PASSWORD_FILE)

def verify_password(password):
    try:
        algorithm, rounds, salt, expected = configured_password_hash().split("$", 3)
        if algorithm != "pbkdf2_sha256" or not isinstance(password, str) or len(password) > 256:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False

def login_key(handler):
    candidate = handler.headers.get("CF-Connecting-IP", handler.client_address[0])
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return handler.client_address[0]

def login_blocked(key):
    now = time.monotonic()
    with LOGIN_LOCK:
        attempts = LOGIN_ATTEMPTS.get(key)
        if not attempts:
            return False
        if attempts["blockedUntil"] > now:
            return True
        if now - attempts["first"] > 900:
            LOGIN_ATTEMPTS.pop(key, None)
        return False

def record_login(key, success):
    with LOGIN_LOCK:
        if success:
            LOGIN_ATTEMPTS.pop(key, None)
            return
        now = time.monotonic()
        attempts = LOGIN_ATTEMPTS.get(key)
        if not attempts or now - attempts["first"] > 900:
            attempts = {"count": 0, "first": now, "blockedUntil": 0}
        attempts["count"] += 1
        if attempts["count"] >= 5:
            attempts["blockedUntil"] = now + 300
        LOGIN_ATTEMPTS[key] = attempts

def container_names():
    """Read the shared NUC list on every request; never silently fall back."""
    names = []
    for line in CONTAINER_FILE.read_text(encoding="utf-8-sig").splitlines():
        name = line.split("#", 1)[0].strip()
        if not name:
            continue
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
            raise ValueError("Ongeldige naam in containerbestand")
        if name not in names:
            names.append(name)
    return tuple(names)

def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("Commando mislukt: " + result.stderr.strip()[-1200:])
    return result.stdout.strip()

def inspect(name):
    if name not in container_names():
        raise ValueError("Container niet toegestaan")
    return json.loads(run("docker", "inspect", name))[0]

def color(state, update):
    if state.get("Status") != "running" or state.get("Health", {}).get("Status") in ("unhealthy", "starting"):
        return "red"
    return "yellow" if update is True else "green"

def container(name):
    try:
        info = inspect(name)
        state = info["State"]
        with LOCK:
            update = dict(UPDATES.get(name, {"available": None, "checkedAt": None}))
        labels = info["Config"].get("Labels") or {}
        ports = []
        for internal, bindings in (info.get("NetworkSettings", {}).get("Ports") or {}).items():
            if bindings:
                ports.extend((binding.get("HostPort", "") + "→" + internal) for binding in bindings)
        return {"name": name, "state": state["Status"], "health": state.get("Health", {}).get("Status"),
                "color": color(state, update["available"]), "update": update,
                "image": info["Config"]["Image"], "id": info.get("Id", "")[:12],
                "createdAt": info.get("Created"), "startedAt": state.get("StartedAt"),
                "restartCount": info.get("RestartCount", 0), "ports": ports,
                "composeProject": labels.get("com.docker.compose.project"),
                "composeService": labels.get("com.docker.compose.service")}
    except Exception:
        return {"name": name, "state": "unknown", "health": None, "color": "red",
                "update": {"available": None, "checkedAt": None}, "error": "Containerstatus niet beschikbaar"}

def storage(label, path):
    try:
        if not os.path.ismount(path):
            raise RuntimeError("Opslag niet aangekoppeld")
        usage = shutil.disk_usage(path)
        return {"name": label, "online": True, "free": usage.free, "total": usage.total}
    except Exception:
        return {"name": label, "online": False, "free": None, "total": None}

def snapshot():
    names = container_names()
    try:
        run("docker", "info", "--format", "{{.ServerVersion}}", timeout=5)
        docker = True
    except Exception:
        docker = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        containers = list(pool.map(container, names)) if docker else []
        disks = list(pool.map(lambda item: storage(*item), STORAGE.items()))
    return {"timestamp": int(time.time()), "docker": docker, "containers": containers,
            "storage": disks, "maintenance": maintenance_status()}

def registry_update_available(image, description):
    """Compare registry descriptors, never config digests with index digests."""
    digest = re.search(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$", description, re.MULTILINE)
    media = re.search(r"^MediaType:\s+(\S+)", description, re.MULTILINE)
    if not digest or not media:
        raise ValueError("Registry descriptor ontbreekt")
    remote = digest.group(1)
    local = image.get("Descriptor") or {}
    repo_digests = {value.rsplit("@", 1)[-1] for value in image.get("RepoDigests", [])}
    if remote in repo_digests or remote == local.get("digest"):
        return False
    if local.get("mediaType") == media.group(1) and local.get("digest"):
        return True
    # Legacy stores expose repository digests, while Id may be a config digest.
    if not local and repo_digests:
        return True
    raise ValueError("Geen vergelijkbare lokale registry descriptor")

def check_update(name):
    """Compare the container's installed image to the registry without pulling."""
    try:
        info = inspect(name)
        image = json.loads(run("docker", "image", "inspect", info["Image"]))[0]
        description = run("docker", "buildx", "imagetools", "inspect",
                          info["Config"]["Image"], timeout=60)
        result = {"available": registry_update_available(image, description), "checkedAt": int(time.time())}
    except Exception:
        result = {"available": None, "checkedAt": int(time.time()), "error": "Updatecontrole niet beschikbaar"}
    with LOCK:
        UPDATES[name] = result
    return result

def refresh_updates():
    """Refresh missing/stale results without blocking dashboard requests."""
    now = time.time()
    with LOCK:
        pending = [
            name for name in container_names()
            if now - (UPDATES.get(name, {}).get("checkedAt") or 0)
            >= (60 if UPDATES.get(name, {}).get("available") is None else 900)
        ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(check_update, pending))

def update_monitor(stop):
    """Start immediately, then retry failed checks every minute."""
    while not stop.is_set():
        if not monitoring_paused():
            try:
                refresh_updates()
            except Exception:
                # A temporary Docker/registry failure must not terminate monitoring.
                pass
        stop.wait(60)

def compose_args(info):
    labels = info["Config"].get("Labels") or {}
    directory = labels.get("com.docker.compose.project.working_dir", "")
    files = labels.get("com.docker.compose.project.config_files", "")
    service = labels.get("com.docker.compose.service", "")
    project = labels.get("com.docker.compose.project", "")
    if not directory.startswith("/home/marco/docker/") or not files or not service or not project:
        raise ValueError("Geen ondersteunde Compose-configuratie")
    args = ["docker", "compose", "--project-directory", directory, "-p", project]
    for path in files.split(","):
        if not os.path.isabs(path):
            path = os.path.join(directory, path)
        if not os.path.realpath(path).startswith("/home/marco/docker/"):
            raise ValueError("Compose-pad niet toegestaan")
        args += ["-f", path]
    return args, service

def perform_action(name, operation):
    if operation not in ("start", "stop", "restart", "update"):
        raise ValueError("Onbekende actie")
    info = inspect(name)
    if operation == "update":
        args, service = compose_args(info)
        run(*args, "pull", service, timeout=600)
        run(*args, "up", "-d", "--no-deps", "--force-recreate", service, timeout=180)
        with LOCK:
            UPDATES.pop(name, None)
    else:
        run("docker", operation, name, timeout=90)
    deadline = time.monotonic() + 90
    while True:
        state = inspect(name)["State"]
        if operation == "stop" and state["Status"] in ("exited", "created"):
            break
        if operation != "stop" and state["Status"] == "running":
            health = state.get("Health", {}).get("Status")
            if health in (None, "healthy"):
                break
            if health == "unhealthy":
                raise RuntimeError("Container is na de actie ongezond")
        if time.monotonic() >= deadline:
            raise RuntimeError("Gewenste containerstatus niet bevestigd")
        time.sleep(2)
    return {"ok": True, "container": container(name)}

def action(name, operation):
    if operation not in ("start", "stop", "restart", "update"):
        raise ValueError("Onbekende actie")
    if not ACTION_LOCK.acquire(blocking=False):
        raise ValueError("Er loopt al een containeractie")
    try:
        return perform_action(name, operation)
    finally:
        ACTION_LOCK.release()

def update_all():
    if not ACTION_LOCK.acquire(blocking=False):
        raise ValueError("Er loopt al een containeractie")
    try:
        allowed = set(container_names())
        with LOCK:
            targets = [name for name, update in UPDATES.items()
                       if name in allowed and update.get("available") is True]
        updated, failed = [], []
        for name in targets:
            try:
                perform_action(name, "update")
                updated.append(name)
            except Exception:
                failed.append(name)
        return {"ok": not failed, "updated": updated, "failed": failed, "total": len(targets)}
    finally:
        ACTION_LOCK.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_apk(self):
        if not APP_APK_FILE.is_file():
            return self.reply(404, {"error": "Geen app-update beschikbaar"})
        size = APP_APK_FILE.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", 'attachment; filename="MediaMonster-latest.apk"')
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        with APP_APK_FILE.open("rb") as source:
            shutil.copyfileobj(source, self.wfile, length=1024 * 1024)

    def authorized(self):
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN):
            self.reply(401, {"error": "Ongeldig API-token"})
            return False
        return True

    def json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Ongeldige aanvraag")
        if not 1 <= length <= 65536:
            raise ValueError("Ongeldige aanvraag")
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Ongeldige JSON")
        if not isinstance(value, dict):
            raise ValueError("Ongeldige aanvraag")
        return value

    def do_GET(self):
        if re.fullmatch(r"/v1/app/apk(?:/[0-9]+\.[0-9]+\.[0-9]+)?", self.path):
            return self.send_apk()
        if not self.authorized():
            return
        try:
            if self.path == "/v1/status":
                return self.reply(200, snapshot())
            if self.path == "/v1/maintenance":
                return self.reply(200, maintenance_status())
            if self.path == "/v1/app/update":
                return self.reply(200, app_release())
            match = re.fullmatch(r"/v1/containers/([a-zA-Z0-9][a-zA-Z0-9_.-]*)/logs", self.path)
            if match:
                name = match[1]
                inspect(name)
                result = subprocess.run(["docker", "logs", "--tail", "50", name],
                                        capture_output=True, text=True, timeout=15)
                if result.returncode:
                    raise RuntimeError("Logs niet beschikbaar")
                return self.reply(200, {"logs": (result.stdout + result.stderr)[-30000:]})
            self.reply(404, {"error": "Niet gevonden"})
        except ValueError as exc:
            self.reply(400, {"error": str(exc)})
        except Exception:
            self.reply(503, {"error": "NUC-gegevens momenteel niet beschikbaar"})

    def do_POST(self):
        if self.path == "/v1/login":
            key = login_key(self)
            if login_blocked(key):
                return self.reply(429, {"error": "Te veel pogingen. Probeer het over vijf minuten opnieuw."})
            try:
                data = self.json_body()
                accepted = verify_password(data.get("password"))
            except ValueError:
                print("login: invalid request; content-length=" + str(self.headers.get("Content-Length", "missing")) +
                      "; transfer-encoding=" + str(self.headers.get("Transfer-Encoding", "none")), flush=True)
                return self.reply(400, {"error": "Aanmeldbericht kon niet worden gelezen. Servercontrole nodig."})
            record_login(key, accepted)
            print("login: " + ("accepted" if accepted else "password mismatch"), flush=True)
            if not accepted:
                return self.reply(401, {"error": "Onjuist wachtwoord"})
            return self.reply(200, {"token": TOKEN})
        if not self.authorized():
            return
        if self.path == "/v1/password":
            try:
                save_password(self.json_body().get("password"))
                return self.reply(200, {"ok": True})
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except OSError:
                return self.reply(503, {"error": "Wachtwoord kon niet worden opgeslagen"})
        if self.path == "/v1/maintenance":
            try:
                return self.reply(200, set_maintenance(self.json_body().get("minutes")))
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except OSError:
                return self.reply(503, {"error": "Onderhoudsmodus kon niet worden opgeslagen"})
        if self.path == "/v1/push/register":
            try:
                data = self.json_body()
                if not isinstance(data.get("notifyStopped"), bool) or not isinstance(data.get("notifyUpdates"), bool):
                    raise ValueError("Meldingsvoorkeuren ontbreken")
                return self.reply(200, PUSH.register(
                    data.get("token"), data["notifyStopped"], data["notifyUpdates"], data.get("platform", "android")))
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except Exception:
                return self.reply(503, {"error": "Pushregistratie momenteel niet beschikbaar"})
        if self.path in ("/v1/push/unregister", "/v1/push/test"):
            try:
                data = self.json_body()
                result = PUSH.unregister(data.get("token")) if self.path.endswith("unregister") else PUSH.test(data.get("token"))
                return self.reply(200, result)
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            except Exception:
                return self.reply(503, {"error": "Pushdienst momenteel niet beschikbaar"})
        if self.path == "/v1/containers/update-all":
            try:
                return self.reply(200, update_all())
            except ValueError as exc:
                return self.reply(409, {"error": str(exc)})
            except Exception:
                return self.reply(503, {"error": "Containers bijwerken is mislukt"})
        match = re.fullmatch(r"/v1/containers/([a-zA-Z0-9][a-zA-Z0-9_.-]*)/(start|stop|restart|update|check-update)", self.path)
        if not match:
            return self.reply(404, {"error": "Niet gevonden"})
        name, operation = match.groups()
        try:
            if name not in container_names():
                return self.reply(403, {"error": "Container niet toegestaan"})
            result = check_update(name) if operation == "check-update" else action(name, operation)
            self.reply(200, result)
        except ValueError as exc:
            self.reply(409, {"error": str(exc)})
        except Exception:
            self.reply(503, {"error": "Actie mislukt of status niet bevestigd. Controleer de container en logs."})

if __name__ == "__main__":
    if len(TOKEN) < 32:
        raise SystemExit("Stel MM_TOKEN in met minimaal 32 tekens")
    threading.Thread(target=update_monitor, args=(threading.Event(),), daemon=True, name="update-monitor").start()
    threading.Thread(target=PUSH.monitor, args=(snapshot, threading.Event(), monitoring_paused), daemon=True, name="push-monitor").start()
    ThreadingHTTPServer((os.getenv("MM_BIND", "127.0.0.1"), int(os.getenv("MM_PORT", "8787"))), Handler).serve_forever()




