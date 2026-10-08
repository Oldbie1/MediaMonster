"""SQLite storage for v1.

SQL lives here so a later PostgreSQL backend can replace the connection
and a few dialect helpers without rewriting routes. Callers never open
sqlite3 themselves.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def default_db_path() -> Path:
    env = os.environ.get("WEEKPLANNING_DB")
    if env:
        return Path(env)
    return DATA_DIR / "weekplanning.db"


DB_PATH = default_db_path()

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    number TEXT NOT NULL UNIQUE,
    notes TEXT NOT NULL DEFAULT '',
    comet_followup TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_machine (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    beperkt INTEGER NOT NULL DEFAULT 0,
    niet INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, machine_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    number TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    source_filename TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_lines (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    profile_number TEXT NOT NULL,
    aantal INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_MACHINES = [
    ("quadra", "Quadra", "zaag", 1),
    ("bjm", "BJM", "zaag", 2),
    ("schirmer", "Schirmer", "zaag", 3),
    ("comet", "Comet", "nabewerking", 4),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """Thin connection wrapper. Swap this class for Postgres later."""

    def __init__(self, path: Path | None = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path or default_db_path()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init()

    def init(self) -> None:
        self.conn.executescript(SCHEMA)
        for code, name, kind, order in DEFAULT_MACHINES:
            self.conn.execute(
                """
                INSERT INTO machines (code, name, kind, sort_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    kind = excluded.kind,
                    sort_order = excluded.sort_order
                """,
                (code, name, kind, order),
            )
        self.conn.commit()

    def execute(self, sql: str, params=()):
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq):
        return self.conn.executemany(sql, seq)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def fetchone(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchall()


_db: Database | None = None


def get_db(path: Path | None = None) -> Database:
    global _db
    if path is not None:
        return Database(path)
    if _db is None:
        _db = Database()
    return _db


def reset_db_singleton() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
