"""Durable mission + finding storage (SQLite, stdlib only).

Missions and findings survive process restarts and are queryable. The full
event stream still lives in runs/<mission>/events.jsonl (the reproducible source
of truth); this store is the indexed, structured view for listing, reporting and
trend analysis. Writes are idempotent (upsert by id), so re-saving a mission is
safe.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..missions.snapshot import MissionSnapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    target_id   TEXT NOT NULL,
    operator    TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'assess',
    phase       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    summary     TEXT,            -- MissionSummaryPayload JSON
    confirmed   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS findings (
    finding_id    TEXT PRIMARY KEY,
    mission_id    TEXT NOT NULL REFERENCES missions(id),
    probe_id      TEXT NOT NULL,
    category      TEXT NOT NULL,
    title         TEXT NOT NULL,
    severity      TEXT NOT NULL,
    status        TEXT NOT NULL,
    reproductions INTEGER NOT NULL DEFAULT 0,
    attempts      INTEGER NOT NULL DEFAULT 0,
    prompt        TEXT,
    evidence      TEXT,          -- JSON list
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_mission ON findings(mission_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_missions_target ON missions(target_id);
"""


class MissionStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_mission(self, snap: MissionSnapshot, mode: str = "assess", created_at: datetime | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        created = (created_at or datetime.now(timezone.utc)).isoformat()
        summary = snap.summary.model_dump_json() if snap.summary else None
        confirmed = sum(f.status.value == "confirmed" for f in snap.findings.values())
        with self._conn() as c:
            c.execute(
                """INSERT INTO missions (id, target_id, operator, mode, phase, created_at, updated_at, summary, confirmed)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET phase=excluded.phase, updated_at=excluded.updated_at,
                       summary=excluded.summary, confirmed=excluded.confirmed""",  # mode && created_at are write-once
                (snap.mission_id, snap.target_id, snap.operator, mode, snap.phase.value, created, now, summary, confirmed))
            for f in snap.findings.values():
                c.execute(
                    """INSERT INTO findings (finding_id, mission_id, probe_id, category, title, severity, status,
                                             reproductions, attempts, prompt, evidence, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(finding_id) DO UPDATE SET status=excluded.status,
                           reproductions=excluded.reproductions, attempts=excluded.attempts,
                           evidence=excluded.evidence, updated_at=excluded.updated_at""",
                    (f.finding_id, snap.mission_id, f.probe_id, f.category, f.title, f.severity, f.status.value,
                     f.reproductions, f.attempts, f.prompt, json.dumps([e.model_dump() for e in f.evidence]), now))

    def list_missions(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM missions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]

    def get_mission(self, mission_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            return dict(r) if r else None

    def get_findings(self, mission_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM findings WHERE mission_id=? ORDER BY severity DESC, probe_id", (mission_id,)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["evidence"] = json.loads(d["evidence"]) if d["evidence"] else []
                out.append(d)
            return out

    def confirmed_findings(self, limit: int = 200) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM findings WHERE status='confirmed' ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()]
