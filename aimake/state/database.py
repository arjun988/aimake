"""SQLite state database for artifact metadata and build history."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aimake.constants import STATE_DB
from aimake.models import ArtifactState, ArtifactStatus, GitInfo


class StateDatabase:
    """Persistent state storage using SQLite.

    Uses thread-local connections so parallel builds can safely write metadata.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS artifacts (
        name TEXT PRIMARY KEY,
        fingerprint TEXT,
        status TEXT,
        artifact_type TEXT,
        command TEXT,
        outputs TEXT,
        metadata TEXT,
        metrics TEXT,
        created_at TEXT,
        duration REAL,
        exit_code INTEGER
    );

    CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        duration REAL,
        status TEXT,
        changed_artifacts TEXT,
        rebuilt TEXT,
        reused TEXT,
        failed TEXT,
        git_commit TEXT,
        git_branch TEXT,
        git_dirty INTEGER,
        metrics TEXT
    );

    CREATE TABLE IF NOT EXISTS file_hashes (
        path TEXT PRIMARY KEY,
        hash TEXT NOT NULL,
        size INTEGER,
        mtime REAL
    );

    CREATE TABLE IF NOT EXISTS execution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        build_id INTEGER,
        artifact TEXT,
        command TEXT,
        exit_code INTEGER,
        stdout TEXT,
        stderr TEXT,
        start_time TEXT,
        end_time TEXT,
        duration REAL,
        FOREIGN KEY (build_id) REFERENCES builds(id)
    );

    CREATE INDEX IF NOT EXISTS idx_builds_timestamp ON builds(timestamp);
    CREATE INDEX IF NOT EXISTS idx_execution_build ON execution_log(build_id);
    """

    def __init__(self, aimake_dir: Path) -> None:
        self.aimake_dir = aimake_dir
        self.db_path = aimake_dir / STATE_DB
        self.aimake_dir.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(self.SCHEMA)
        with self._connections_lock:
            self._connections.append(conn)
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._create_connection()
            self._local.conn = conn
        return conn

    def close(self) -> None:
        with self._connections_lock:
            for conn in self._connections:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._connections.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None

    def get_artifact(self, name: str) -> ArtifactState | None:
        row = self.conn.execute(
            "SELECT * FROM artifacts WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_state(row)

    def get_all_artifacts(self) -> dict[str, ArtifactState]:
        rows = self.conn.execute("SELECT * FROM artifacts").fetchall()
        return {row["name"]: self._row_to_state(row) for row in rows}

    def get_fingerprints(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT name, fingerprint FROM artifacts WHERE fingerprint IS NOT NULL"
        ).fetchall()
        return {row["name"]: row["fingerprint"] for row in rows}

    def save_artifact(
        self,
        name: str,
        *,
        fingerprint: str,
        status: ArtifactStatus,
        artifact_type: str = "generic",
        command: str | None = None,
        outputs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        duration: float | None = None,
        exit_code: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO artifacts (name, fingerprint, status, artifact_type, command,
                                   outputs, metadata, metrics, created_at, duration, exit_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                status = excluded.status,
                artifact_type = excluded.artifact_type,
                command = excluded.command,
                outputs = excluded.outputs,
                metadata = excluded.metadata,
                metrics = excluded.metrics,
                created_at = excluded.created_at,
                duration = excluded.duration,
                exit_code = excluded.exit_code
            """,
            (
                name,
                fingerprint,
                status.value,
                artifact_type,
                command,
                json.dumps(outputs or []),
                json.dumps(metadata or {}),
                json.dumps(metrics or {}),
                now,
                duration,
                exit_code,
            ),
        )
        self.conn.commit()

    def delete_artifact(self, name: str) -> None:
        self.conn.execute("DELETE FROM artifacts WHERE name = ?", (name,))
        self.conn.commit()

    def clear_artifacts(self) -> None:
        self.conn.execute("DELETE FROM artifacts")
        self.conn.commit()

    def start_build(self, git: GitInfo | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO builds (timestamp, status, git_commit, git_branch, git_dirty)
            VALUES (?, 'running', ?, ?, ?)
            """,
            (
                now,
                git.commit if git else None,
                git.branch if git else None,
                int(git.dirty) if git and git.dirty is not None else None,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish_build(
        self,
        build_id: int,
        *,
        duration: float,
        status: str,
        changed: list[str],
        rebuilt: list[str],
        reused: list[str],
        failed: list[str],
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE builds SET
                duration = ?, status = ?, changed_artifacts = ?,
                rebuilt = ?, reused = ?, failed = ?, metrics = ?
            WHERE id = ?
            """,
            (
                duration,
                status,
                json.dumps(changed),
                json.dumps(rebuilt),
                json.dumps(reused),
                json.dumps(failed),
                json.dumps(metrics or {}),
                build_id,
            ),
        )
        self.conn.commit()

    def get_builds(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM builds ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_build(self, build_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM builds WHERE id = ?", (build_id,)
        ).fetchone()
        return dict(row) if row else None

    def log_execution(
        self,
        build_id: int,
        artifact: str,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        start_time: datetime,
        end_time: datetime,
        duration: float,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO execution_log
                (build_id, artifact, command, exit_code, stdout, stderr,
                 start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                build_id,
                artifact,
                command,
                exit_code,
                stdout,
                stderr,
                start_time.isoformat(),
                end_time.isoformat(),
                duration,
            ),
        )
        self.conn.commit()

    def get_file_hash(self, path: str) -> str | None:
        row = self.conn.execute(
            "SELECT hash FROM file_hashes WHERE path = ?", (path,)
        ).fetchone()
        return row["hash"] if row else None

    def save_file_hash(self, path: str, file_hash: str, size: int, mtime: float) -> None:
        self.conn.execute(
            """
            INSERT INTO file_hashes (path, hash, size, mtime)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET hash = excluded.hash, size = excluded.size, mtime = excluded.mtime
            """,
            (path, file_hash, size, mtime),
        )
        self.conn.commit()

    def _row_to_state(self, row: sqlite3.Row) -> ArtifactState:
        created = row["created_at"]
        return ArtifactState(
            name=row["name"],
            fingerprint=row["fingerprint"],
            status=ArtifactStatus(row["status"]) if row["status"] else ArtifactStatus.UNKNOWN,
            created_at=datetime.fromisoformat(created) if created else None,
            duration=row["duration"],
            outputs=json.loads(row["outputs"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            metrics=json.loads(row["metrics"] or "{}"),
            command=row["command"],
            exit_code=row["exit_code"],
        )
