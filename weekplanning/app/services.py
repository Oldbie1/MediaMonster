from __future__ import annotations

from .db import Database, get_db, utcnow
from .pdf_extract import ExtractedProject, PdfExtractError, extract_from_bytes

COMET_LABELS = {
    None: "Geen Comet",
    "": "Geen Comet",
    "Q": "Na Quadra nog Comet",
    "B": "Na BJM nog Comet",
    "S": "Na Schirmer nog Comet",
    "QS": "Na Quadra of Schirmer nog Comet",
    "X": "Altijd Comet",
}


def machine_fit(profile_row, constraints: dict, machines: list[dict]) -> dict:
    comet = (profile_row or {}).get("comet_followup") if profile_row else None
    known = profile_row is not None
    zaag = []
    for m in machines:
        if m["kind"] != "zaag":
            continue
        if not known:
            status = "onbekend"
            label = "Onbekend profiel"
        else:
            c = constraints.get(m["code"], {"beperkt": 0, "niet": 0})
            if c.get("niet"):
                status, label = "niet", "Niet zagen"
            elif c.get("beperkt"):
                status, label = "beperkt", "Beperkt"
            else:
                status, label = "kan", "Kan zagen"
        zaag.append({
            "code": m["code"],
            "name": m["name"],
            "status": status,
            "label": label,
        })
    return {
        "known": known,
        "machines": zaag,
        "comet_followup": comet or None,
        "comet_label": COMET_LABELS.get(comet, COMET_LABELS[None]) if known else "Onbekend",
    }


def list_machines(db: Database) -> list[dict]:
    return [dict(r) for r in db.fetchall(
        "SELECT id, code, name, kind, sort_order FROM machines ORDER BY sort_order"
    )]


def enrich_line(db: Database, profile_number: str, machines: list[dict]) -> dict:
    profile = db.fetchone("SELECT * FROM profiles WHERE number = ?", (profile_number,))
    constraints = {}
    if profile:
        rows = db.fetchall(
            """
            SELECT m.code, pm.beperkt, pm.niet
            FROM profile_machine pm
            JOIN machines m ON m.id = pm.machine_id
            WHERE pm.profile_id = ?
            """,
            (profile["id"],),
        )
        for r in rows:
            constraints[r["code"]] = {"beperkt": r["beperkt"], "niet": r["niet"]}
    fit = machine_fit(dict(profile) if profile else None, constraints, machines)
    return {
        "profile_number": profile_number,
        "notes": profile["notes"] if profile else "",
        **fit,
    }


def serialize_profile(db: Database, profile, machines) -> dict:
    constraints = {
        r["code"]: {"beperkt": bool(r["beperkt"]), "niet": bool(r["niet"])}
        for r in db.fetchall(
            """
            SELECT m.code, pm.beperkt, pm.niet
            FROM profile_machine pm
            JOIN machines m ON m.id = pm.machine_id
            WHERE pm.profile_id = ?
            """,
            (profile["id"],),
        )
    }
    out_flags = {}
    for m in machines:
        if m["kind"] != "zaag":
            continue
        c = constraints.get(m["code"], {"beperkt": False, "niet": False})
        out_flags[m["code"]] = c
    return {
        "id": profile["id"],
        "number": profile["number"],
        "notes": profile["notes"],
        "comet_followup": profile["comet_followup"],
        "comet_label": COMET_LABELS.get(profile["comet_followup"], "Geen Comet"),
        "source": profile["source"],
        "machine_flags": out_flags,
        **machine_fit(dict(profile), {
            k: {"beperkt": int(v["beperkt"]), "niet": int(v["niet"])}
            for k, v in out_flags.items()
        }, machines),
    }


def list_profiles(db: Database, q: str = "") -> list[dict]:
    machines = list_machines(db)
    if q:
        rows = db.fetchall(
            """
            SELECT * FROM profiles
            WHERE number LIKE ? OR notes LIKE ?
            ORDER BY number
            """,
            (f"%{q}%", f"%{q}%"),
        )
    else:
        rows = db.fetchall("SELECT * FROM profiles ORDER BY number")
    return [serialize_profile(db, r, machines) for r in rows]


def upsert_profile(db: Database, number: str, notes: str, comet_followup: str | None,
                   flags: dict, source: str = "manual") -> dict:
    number = number.strip()
    if not number:
        raise ValueError("Profielnummer is verplicht")
    comet = comet_followup or None
    if comet == "":
        comet = None
    db.execute(
        """
        INSERT INTO profiles (number, notes, comet_followup, source, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(number) DO UPDATE SET
            notes = excluded.notes,
            comet_followup = excluded.comet_followup,
            source = CASE
                WHEN profiles.source = 'excel' THEN 'excel'
                ELSE excluded.source
            END,
            updated_at = excluded.updated_at
        """,
        (number, notes or "", comet, source, utcnow()),
    )
    profile = db.fetchone("SELECT * FROM profiles WHERE number = ?", (number,))
    machines = {r["code"]: r["id"] for r in db.fetchall("SELECT id, code FROM machines")}
    for code, mid in machines.items():
        if code == "comet":
            continue
        f = flags.get(code) or {}
        beperkt = 1 if f.get("beperkt") else 0
        niet = 1 if f.get("niet") else 0
        db.execute(
            """
            INSERT INTO profile_machine (profile_id, machine_id, beperkt, niet)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id, machine_id) DO UPDATE SET
                beperkt = excluded.beperkt,
                niet = excluded.niet
            """,
            (profile["id"], mid, beperkt, niet),
        )
    db.commit()
    return serialize_profile(db, profile, list_machines(db))


def save_extracted_project(db: Database, extracted: ExtractedProject, filename: str) -> dict:
    existing = db.fetchone("SELECT id FROM projects WHERE number = ?", (extracted.project,))
    now = utcnow()
    if existing:
        pid = existing["id"]
        db.execute("DELETE FROM project_lines WHERE project_id = ?", (pid,))
        db.execute(
            """
            UPDATE projects SET source_filename = ?, updated_at = ?
            WHERE id = ?
            """,
            (filename, now, pid),
        )
    else:
        cur = db.execute(
            """
            INSERT INTO projects (number, name, source_filename, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (extracted.project, extracted.project, filename, now, now),
        )
        pid = cur.lastrowid
    for i, line in enumerate(extracted.rows):
        db.execute(
            """
            INSERT INTO project_lines (project_id, profile_number, aantal, sort_order)
            VALUES (?, ?, ?, ?)
            """,
            (pid, line.profielnummer, line.aantal, i),
        )
    db.commit()
    return get_project(db, pid)


def get_project(db: Database, project_id: int) -> dict:
    project = db.fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise KeyError("project")
    machines = list_machines(db)
    lines = []
    for r in db.fetchall(
        "SELECT * FROM project_lines WHERE project_id = ? ORDER BY sort_order, id",
        (project_id,),
    ):
        extra = enrich_line(db, r["profile_number"], machines)
        lines.append({
            "id": r["id"],
            "profile_number": r["profile_number"],
            "aantal": r["aantal"],
            **extra,
        })
    return {
        "id": project["id"],
        "number": project["number"],
        "name": project["name"],
        "source_filename": project["source_filename"],
        "updated_at": project["updated_at"],
        "lines": lines,
        "unknown_count": sum(1 for ln in lines if not ln["known"]),
    }


def list_projects(db: Database) -> list[dict]:
    rows = db.fetchall(
        """
        SELECT p.*, COUNT(l.id) AS line_count, COALESCE(SUM(l.aantal), 0) AS aantal_sum
        FROM projects p
        LEFT JOIN project_lines l ON l.project_id = p.id
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """
    )
    return [dict(r) for r in rows]


def update_line_qty(db: Database, line_id: int, aantal: int) -> dict:
    if aantal < 0:
        raise ValueError("Aantal kan niet negatief zijn")
    db.execute("UPDATE project_lines SET aantal = ? WHERE id = ?", (aantal, line_id))
    row = db.fetchone("SELECT project_id FROM project_lines WHERE id = ?", (line_id,))
    if not row:
        raise KeyError("line")
    db.execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (utcnow(), row["project_id"]),
    )
    db.commit()
    return get_project(db, row["project_id"])


def add_line(db: Database, project_id: int, profile_number: str, aantal: int) -> dict:
    profile_number = profile_number.strip()
    if not profile_number:
        raise ValueError("Profielnummer is verplicht")
    if aantal < 0:
        raise ValueError("Aantal kan niet negatief zijn")
    max_sort = db.fetchone(
        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM project_lines WHERE project_id = ?",
        (project_id,),
    )["m"]
    db.execute(
        """
        INSERT INTO project_lines (project_id, profile_number, aantal, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, profile_number, aantal, max_sort + 1),
    )
    db.execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (utcnow(), project_id),
    )
    db.commit()
    return get_project(db, project_id)


def delete_line(db: Database, line_id: int) -> dict:
    row = db.fetchone("SELECT project_id FROM project_lines WHERE id = ?", (line_id,))
    if not row:
        raise KeyError("line")
    db.execute("DELETE FROM project_lines WHERE id = ?", (line_id,))
    db.execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (utcnow(), row["project_id"]),
    )
    db.commit()
    return get_project(db, row["project_id"])


def import_pdf(db: Database, data: bytes, filename: str) -> dict:
    extracted = extract_from_bytes(data)
    return save_extracted_project(db, extracted, filename)


# keep name for tests that imported the exception
_ = PdfExtractError
_ = get_db
