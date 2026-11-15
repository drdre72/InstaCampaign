"""SQLite ledger: authoritative, WAL, append-only.

Status transitions insert a new `events` row; the status column is a cached
projection of the latest event, never a silent rewrite. Approvals, posts and
assets are strictly insert-only.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .util import ROOT, utcnow

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS personas(
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    spec_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assets(
    id INTEGER PRIMARY KEY,
    persona_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- reference | generated | reel
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    prompt TEXT,
    seed INTEGER,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans(
    id INTEGER PRIMARY KEY,
    persona_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',   -- projection of latest event
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS renders(
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    item_index INTEGER NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    qc_status TEXT NOT NULL DEFAULT 'pending',  -- pending|pass|needs_manual|fail
    status TEXT NOT NULL DEFAULT 'rendered',    -- rendered|approved|exported
    created_at TEXT NOT NULL,
    UNIQUE(plan_id, item_index));
CREATE TABLE IF NOT EXISTS approvals(
    id INTEGER PRIMARY KEY,
    render_id INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    operator TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS posts(
    id INTEGER PRIMARY KEY,
    render_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    remote_id TEXT,
    media_url TEXT,
    status TEXT NOT NULL DEFAULT 'exported',
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL);
"""


def db_path() -> Path:
    return Path(os.environ.get("IC_DB", ROOT / "campaign.db"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def event(kind: str, **payload) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO events(kind, payload, created_at) VALUES(?,?,?)",
            (kind, json.dumps(payload, sort_keys=True), utcnow()),
        )


def set_plan_status(plan_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE plans SET status=? WHERE id=?", (status, plan_id))
        conn.execute(
            "INSERT INTO events(kind, payload, created_at) VALUES(?,?,?)",
            ("plan_status", json.dumps({"plan_id": plan_id, "status": status}),
             utcnow()),
        )


def set_render_status(render_id: int, status: str,
                      qc_status: str | None = None) -> None:
    with connect() as conn:
        if qc_status is None:
            conn.execute("UPDATE renders SET status=? WHERE id=?",
                         (status, render_id))
        else:
            conn.execute(
                "UPDATE renders SET status=?, qc_status=? WHERE id=?",
                (status, qc_status, render_id))
        conn.execute(
            "INSERT INTO events(kind, payload, created_at) VALUES(?,?,?)",
            ("render_status",
             json.dumps({"render_id": render_id, "status": status,
                         "qc_status": qc_status}), utcnow()),
        )


def insert_persona(name: str, spec: dict, sha256: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO personas(name, spec_json, sha256, created_at)"
            " VALUES(?,?,?,?)",
            (name, json.dumps(spec, sort_keys=True), sha256, utcnow()))
        return cur.lastrowid


def get_persona(name_or_id) -> sqlite3.Row | None:
    with connect() as conn:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            return conn.execute("SELECT * FROM personas WHERE id=?",
                                (int(name_or_id),)).fetchone()
        return conn.execute("SELECT * FROM personas WHERE name=?",
                            (name_or_id,)).fetchone()


def list_personas() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM personas ORDER BY created_at").fetchall()


def insert_plan(persona_id: int, name: str, plan: dict, sha256: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO plans(persona_id, name, plan_json, sha256,"
            " created_at) VALUES(?,?,?,?,?)",
            (persona_id, name, json.dumps(plan, sort_keys=True), sha256,
             utcnow()))
        return cur.lastrowid


def get_plan(plan_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM plans WHERE id=?",
                            (plan_id,)).fetchone()


def list_plans(status: str | None = None) -> list[sqlite3.Row]:
    with connect() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM plans WHERE status=? ORDER BY id",
                (status,)).fetchall()
        return conn.execute("SELECT * FROM plans ORDER BY id").fetchall()


def insert_render(plan_id: int, item_index: int, path: str,
                  sha256: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO renders(plan_id, item_index, path, sha256,"
            " created_at) VALUES(?,?,?,?,?)",
            (plan_id, item_index, path, sha256, utcnow()))
        return cur.lastrowid


def get_render(render_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM renders WHERE id=?",
                            (render_id,)).fetchone()


def list_renders(status: str | None = None) -> list[sqlite3.Row]:
    with connect() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM renders WHERE status=? ORDER BY id",
                (status,)).fetchall()
        return conn.execute("SELECT * FROM renders ORDER BY id").fetchall()


def insert_approval(render_id: int, sha256: str, operator: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO approvals(render_id, sha256, operator, created_at)"
            " VALUES(?,?,?,?)", (render_id, sha256, operator, utcnow()))
        return cur.lastrowid


def approved_sha(render_id: int) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT sha256 FROM approvals WHERE render_id=?"
            " ORDER BY id DESC LIMIT 1", (render_id,)).fetchone()
        return row["sha256"] if row else None


def insert_post(render_id: int, platform: str, remote_id: str | None,
                media_url: str | None, status: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts(render_id, platform, remote_id, media_url,"
            " status, created_at) VALUES(?,?,?,?,?,?)",
            (render_id, platform, remote_id, media_url, status, utcnow()))
        return cur.lastrowid
