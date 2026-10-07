# API-installatie

Huidige host: Ubuntu-VM in Proxmox. Appversie 1.0.13.

## Live-map
`/home/marco/mediamonster` is de actieve installatie. Wijzig die pas na testen van deze bron.

Kopieer vanuit `backend/` met:

    ./install-linux.sh /home/marco/mediamonster

Het script zet `server.py`, `push.py`, `app-release.json`, de systemd-unit en de hulpscripts in de live-map. Het overschrijft geen `api.env`, wachtwoordhash, Firebase-serviceaccount, apparaatregistratie of activiteitenlog.

Daarna, alleen als het wachtwoord nog ontbreekt of opnieuw moet:

    ./set-password.sh

## Bestanden op de VM
| Bestand | Rol |
|---|---|
| `server.py`, `push.py` | API |
| `app-release.json` | App-updateversie (1.0.13 / 45) |
| `MediaMonster-latest.apk` | Officiële APK, niet in Git |
| `api.env` | Token, bind, poort, `MM_STORAGE` (mode 0600) |
| `password.hash` | Alleen PBKDF2-hash |
| `firebase-service-account.json` | Server-sleutel, nooit in Git |
| `automatic-updates.json`, `automatic-recovery.json`, `maintenance.json`, `recovery.json`, `activity.json`, `push-devices.json` | Runtime, nooit in Git |

## Standaard `api.env`
Nieuwe installaties krijgen:

    MM_BIND=0.0.0.0
    MM_PORT=8787
    MM_STORAGE={"NUC 11":"/","DS224":"/mnt/DS224/video","DS716":"/mnt/DS716/video"}

Zonder `MM_STORAGE` gebruikt `server.py` dezelfde paden. De code luistert zonder `MM_BIND` op `127.0.0.1`; het installatiescript bindt `0.0.0.0` voor LAN. Zet de API niet via port-forwarding open op internet.

## Service
User-unit: `~/.config/systemd/user/mediamonster-api.service`. Linger wordt door het installatiescript aangezet.

    systemctl --user status mediamonster-api

## Gedrag
- Achtergrondupdatecontrole start bij de API en is onafhankelijk van automatisch herstarten
- Geslaagde registrycontroles ongeveer 15 minuten in cache; mislukte na ongeveer 1 minuut opnieuw
- Automatisch bijwerken en crash-recovery zijn aparte schakelaars
- Registrycontrole vereist Docker Buildx
- Referentie: https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/

## Bereik
HTTP op LAN of Tailscale; HTTPS via `https://mm.tenhaaf.nu`. Zonder token: HTTP 401.
