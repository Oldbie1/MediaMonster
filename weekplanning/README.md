# Weekplanning

Webapp (Nederlands) voor zaagplanning: profielcatalogus, projecten uit Rollecate-PDF, en per regel of het profiel op Quadra / BJM / Schirmer kan (of beperkt / niet), plus Comet-vervolg.

Geen inloggen. SQLite-bestand, één proces. Bedoeld voor de NAS, bereikbaar via een Cloudflare-tunnel (zoals orderpicker).

## Lokaal starten

Python 3.11+ (venv):

```bash
cd weekplanning
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080

Bij de eerste start wordt `seed/Inrichting_Elace.xlsx` eenmalig ingelezen.

```bash
.venv/bin/pytest
```

## Docker (NAS)

```bash
cd weekplanning
docker compose up -d --build
```

De database staat in `weekplanning/data/weekplanning.db` (volume `./data`). Backup = dat bestand kopiëren terwijl de container even stilstaat, of gewoon het bestand meenemen in de NAS-backup.

Poort **8080** intern. Zet de Cloudflare-tunnel naar `http://127.0.0.1:8080` (of naar het Docker-netwerkadres van de container).

## Cloudflare-tunnel (internet)

Niet vanaf deze repo jouw live NAS inrichten. Op de NAS, naast orderpicker:

1. App draait lokaal op poort 8080 (Docker of uvicorn).
2. Bestaande `cloudflared`-service: extra hostname, of een nieuwe tunnel. Zie `cloudflared.example.yml`.
3. DNS-route naar die hostname, ingress `service: http://127.0.0.1:8080`.

Eenmalig proces zonder Docker:

```bash
cd /volume1/apps/weekplanning   # voorbeeldpad
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
# systemd/synology-taak + cloudflared zoals bij orderpicker
```

Geen accounts, geen TLS in de app: TLS zit op de tunnel.

## Gebruik

- **Projecten:** PDF *Artikeloverzicht - Profielen* droppen. Projectnummer komt uit het veld `Project:` (bijv. `012510375A50`). Regels zijn bewerkbaar (aantal, toevoegen, verwijderen). Opnieuw dezelfde PDF vervangt de regels van dat projectnummer.
- **Catalogus:** zoeken, toevoegen, vlaggen Beperkt/Niet per zaagmachine, Comet-code Q / B / S / QS / X.
- Onbekende profielen (niet in de catalogus) zijn duidelijk gemarkeerd.

PDF-regels: zie de extractiespec (niet in deze map wijzigen). Excel: zaagmatrix als de koppen Quadra/BJM/Schirmer heten; anders inrichting-layout (huidige seed).

## Data

| Tabel | Inhoud |
|---|---|
| `machines` | Quadra, BJM, Schirmer, Comet |
| `profiles` | profielnummer, notitie, Comet-vervolg |
| `profile_machine` | beperkt / niet per zaagmachine |
| `projects` | projectnummer |
| `project_lines` | profiel + aantal (niet aggregeren bij import) |

Toegang loopt via `app/db.py` (`Database`). PostgreSQL is later mogelijk door die wrapper te vervangen; v1 blijft SQLite.
