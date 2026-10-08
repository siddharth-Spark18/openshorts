"""Lightweight SQLite persistence for job history and projects (Fix 2 & 3).

The database lives at /app/output/jobs.db so it survives container restarts
via the existing ``./output:/app/output`` Docker volume mount.

Schema
------
jobs
    job_id       TEXT PRIMARY KEY
    status       TEXT           -- queued | processing | completed | failed
    created_at   TEXT           -- ISO-8601 UTC
    started_at   TEXT           -- NULL until the worker picks it up
    finished_at  TEXT           -- NULL until terminal state
    input_source TEXT           -- URL or original filename (best-effort)
    clip_count   INTEGER        -- NULL until completed
    project_id   TEXT           -- FK → projects.id (NULL until assigned)

projects
    id           TEXT PRIMARY KEY   -- uuid4
    name         TEXT NOT NULL
    created_at   TEXT NOT NULL      -- ISO-8601 UTC

All writes are best-effort: a failure here must never crash the main pipeline.
"""

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

# Keep the DB on the volume-mounted output dir so it outlives the container.
_DB_PATH = os.environ.get("JOBS_DB_PATH", "/app/output/jobs.db")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _conn():
    """Thread-safe per-call connection (WAL mode)."""
    db_dir = os.path.dirname(_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    con = sqlite3.connect(_DB_PATH, timeout=10, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    try:
        with _conn() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id       TEXT PRIMARY KEY,
                    status       TEXT,
                    created_at   TEXT,
                    started_at   TEXT,
                    finished_at  TEXT,
                    input_source TEXT,
                    clip_count   INTEGER,
                    project_id   TEXT REFERENCES projects(id)
                );

                -- Generic key-value store for persisted settings (API keys, etc.).
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
        print(f"📦 jobs_db: initialised at {_DB_PATH}")
    except Exception as e:
        print(f"⚠️ jobs_db: could not initialise DB: {e}")


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def record_job_created(job_id: str, input_source: str = "") -> None:
    """Insert a new job row (status=queued)."""
    try:
        with _conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO jobs (job_id, status, created_at, input_source) "
                "VALUES (?, 'queued', ?, ?)",
                (job_id, _utcnow(), input_source or ""),
            )
    except Exception as e:
        print(f"⚠️ jobs_db: record_job_created({job_id}): {e}")


def record_job_started(job_id: str) -> None:
    try:
        with _conn() as con:
            con.execute(
                "UPDATE jobs SET status='processing', started_at=? WHERE job_id=?",
                (_utcnow(), job_id),
            )
    except Exception as e:
        print(f"⚠️ jobs_db: record_job_started({job_id}): {e}")


def record_job_finished(job_id: str, status: str, clip_count: Optional[int] = None) -> None:
    """Call when a job reaches a terminal state (completed / failed)."""
    try:
        with _conn() as con:
            con.execute(
                "UPDATE jobs SET status=?, finished_at=?, clip_count=? WHERE job_id=?",
                (status, _utcnow(), clip_count, job_id),
            )
    except Exception as e:
        print(f"⚠️ jobs_db: record_job_finished({job_id}): {e}")


def list_jobs(limit: int = 100) -> list:
    """Return the most-recent jobs, newest first."""
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT job_id, status, created_at, started_at, finished_at, "
                "input_source, clip_count, project_id "
                "FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"⚠️ jobs_db: list_jobs: {e}")
        return []


def get_job(job_id: str) -> Optional[dict]:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT job_id, status, created_at, started_at, finished_at, "
                "input_source, clip_count, project_id FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"⚠️ jobs_db: get_job({job_id}): {e}")
        return None


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------

def create_project(name: str) -> dict:
    """Create a new named project and return its record."""
    project_id = str(uuid.uuid4())
    now = _utcnow()
    with _conn() as con:
        con.execute(
            "INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)",
            (project_id, name, now),
        )
    return {"id": project_id, "name": name, "created_at": now}


def list_projects() -> list:
    """Return all projects, newest first, with their associated job ids."""
    try:
        with _conn() as con:
            projects = con.execute(
                "SELECT id, name, created_at FROM projects ORDER BY created_at DESC"
            ).fetchall()
            result = []
            for p in projects:
                p_dict = dict(p)
                jobs_rows = con.execute(
                    "SELECT job_id, status, created_at, clip_count "
                    "FROM jobs WHERE project_id=? ORDER BY created_at DESC",
                    (p["id"],),
                ).fetchall()
                p_dict["jobs"] = [dict(j) for j in jobs_rows]
                result.append(p_dict)
        return result
    except Exception as e:
        print(f"⚠️ jobs_db: list_projects: {e}")
        return []


def get_project(project_id: str) -> Optional[dict]:
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT id, name, created_at FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            p = dict(row)
            jobs_rows = con.execute(
                "SELECT job_id, status, created_at, clip_count "
                "FROM jobs WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            p["jobs"] = [dict(j) for j in jobs_rows]
        return p
    except Exception as e:
        print(f"⚠️ jobs_db: get_project({project_id}): {e}")
        return None


def rename_project(project_id: str, new_name: str) -> bool:
    try:
        with _conn() as con:
            cur = con.execute(
                "UPDATE projects SET name=? WHERE id=?",
                (new_name, project_id),
            )
        return cur.rowcount > 0
    except Exception as e:
        print(f"⚠️ jobs_db: rename_project({project_id}): {e}")
        return False


def delete_project(project_id: str) -> bool:
    """Delete a project (jobs are unlinked, not deleted)."""
    try:
        with _conn() as con:
            con.execute(
                "UPDATE jobs SET project_id=NULL WHERE project_id=?",
                (project_id,),
            )
            cur = con.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return cur.rowcount > 0
    except Exception as e:
        print(f"⚠️ jobs_db: delete_project({project_id}): {e}")
        return False


def assign_job_to_project(job_id: str, project_id: Optional[str]) -> bool:
    """Assign (or unassign when project_id=None) a job to a project."""
    try:
        with _conn() as con:
            cur = con.execute(
                "UPDATE jobs SET project_id=? WHERE job_id=?",
                (project_id, job_id),
            )
        return cur.rowcount > 0
    except Exception as e:
        print(f"⚠️ jobs_db: assign_job_to_project({job_id}): {e}")
        return False


# ---------------------------------------------------------------------------
# Settings helpers (API key persistence, Fix 4)
# ---------------------------------------------------------------------------

# Keys that are allowed to be stored/retrieved via the settings API.
# Keeping an allowlist prevents the endpoint from becoming a generic secret store.
ALLOWED_SETTINGS = {
    "gemini_key",
    "upload_post_key",
    "upload_user_id",
    "elevenlabs_key",
    "fal_key",
}


def get_setting(key: str) -> Optional[str]:
    """Return the stored value for key, or None."""
    if key not in ALLOWED_SETTINGS:
        return None
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else None
    except Exception as e:
        print(f"⚠️ jobs_db: get_setting({key}): {e}")
        return None


def set_setting(key: str, value: Optional[str]) -> bool:
    """Upsert a setting. Pass value=None / empty string to clear it."""
    if key not in ALLOWED_SETTINGS:
        return False
    try:
        with _conn() as con:
            if value:
                con.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            else:
                con.execute("DELETE FROM settings WHERE key=?", (key,))
        return True
    except Exception as e:
        print(f"⚠️ jobs_db: set_setting({key}): {e}")
        return False


def get_all_settings() -> dict:
    """Return all stored settings as a plain dict."""
    try:
        with _conn() as con:
            rows = con.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows if r["key"] in ALLOWED_SETTINGS}
    except Exception as e:
        print(f"⚠️ jobs_db: get_all_settings: {e}")
        return {}
