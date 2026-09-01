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

    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        strategy TEXT,
        objective_metric TEXT,
        objective_direction TEXT,
        config TEXT,
        best_build_id INTEGER,
        best_value REAL
    );

    CREATE TABLE IF NOT EXISTS experiment_trials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER NOT NULL,
        trial_number INTEGER NOT NULL,
        build_id INTEGER,
        parameters TEXT,
        metrics TEXT,
        objective_value REAL,
        status TEXT,
        FOREIGN KEY (experiment_id) REFERENCES experiments(id),
        FOREIGN KEY (build_id) REFERENCES builds(id)
    );

    CREATE INDEX IF NOT EXISTS idx_trials_experiment ON experiment_trials(experiment_id);

    CREATE TABLE IF NOT EXISTS registry_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        artifact_name TEXT NOT NULL,
        version TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        build_id INTEGER,
        stage TEXT NOT NULL DEFAULT 'dev',
        tags TEXT,
        metadata TEXT,
        metrics TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(artifact_name, version)
    );

    CREATE INDEX IF NOT EXISTS idx_registry_artifact ON registry_versions(artifact_name);
    CREATE INDEX IF NOT EXISTS idx_registry_stage ON registry_versions(stage);
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
        self._migrate(conn)
        with self._connections_lock:
            self._connections.append(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Apply lightweight schema migrations for existing databases."""
        build_cols = {row[1] for row in conn.execute("PRAGMA table_info(builds)")}
        if "parameters" not in build_cols:
            conn.execute("ALTER TABLE builds ADD COLUMN parameters TEXT")
        if "experiment_id" not in build_cols:
            conn.execute("ALTER TABLE builds ADD COLUMN experiment_id INTEGER")
        if "trial_number" not in build_cols:
            conn.execute("ALTER TABLE builds ADD COLUMN trial_number INTEGER")
        conn.commit()

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

    def start_build(
        self,
        git: GitInfo | None = None,
        *,
        parameters: dict[str, Any] | None = None,
        experiment_id: int | None = None,
        trial_number: int | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO builds (
                timestamp, status, git_commit, git_branch, git_dirty,
                parameters, experiment_id, trial_number
            )
            VALUES (?, 'running', ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                git.commit if git else None,
                git.branch if git else None,
                int(git.dirty) if git and git.dirty is not None else None,
                json.dumps(parameters or {}),
                experiment_id,
                trial_number,
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
        return [self._normalize_build_row(row) for row in rows]

    def get_build(self, build_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM builds WHERE id = ?", (build_id,)
        ).fetchone()
        return self._normalize_build_row(row) if row else None

    def get_latest_build_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM builds WHERE status = 'success' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def get_previous_build_id(self, before_id: int | None = None) -> int | None:
        if before_id is None:
            row = self.conn.execute(
                """
                SELECT id FROM builds WHERE status = 'success'
                ORDER BY id DESC LIMIT 1 OFFSET 1
                """
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT id FROM builds
                WHERE status = 'success' AND id < ?
                ORDER BY id DESC LIMIT 1
                """,
                (before_id,),
            ).fetchone()
        return row["id"] if row else None

    def create_experiment(
        self,
        name: str,
        *,
        strategy: str,
        objective_metric: str,
        objective_direction: str,
        config: dict[str, Any],
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO experiments (
                name, created_at, status, strategy,
                objective_metric, objective_direction, config
            )
            VALUES (?, ?, 'running', ?, ?, ?, ?)
            """,
            (
                name,
                now,
                strategy,
                objective_metric,
                objective_direction,
                json.dumps(config),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish_experiment(
        self,
        experiment_id: int,
        *,
        status: str,
        best_build_id: int | None = None,
        best_value: float | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE experiments SET status = ?, best_build_id = ?, best_value = ?
            WHERE id = ?
            """,
            (status, best_build_id, best_value, experiment_id),
        )
        self.conn.commit()

    def save_trial(
        self,
        experiment_id: int,
        trial_number: int,
        *,
        build_id: int | None,
        parameters: dict[str, Any],
        metrics: dict[str, Any],
        objective_value: float | None,
        status: str,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO experiment_trials (
                experiment_id, trial_number, build_id, parameters,
                metrics, objective_value, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                trial_number,
                build_id,
                json.dumps(parameters),
                json.dumps(metrics),
                objective_value,
                status,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_experiments(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM experiments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_experiment(self, experiment_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_experiment_trials(self, experiment_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM experiment_trials
            WHERE experiment_id = ?
            ORDER BY trial_number
            """,
            (experiment_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _normalize_build_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for list_key in ("changed_artifacts", "rebuilt", "reused", "failed"):
            val = data.get(list_key)
            if isinstance(val, str):
                data[list_key] = json.loads(val or "[]")
        for dict_key in ("metrics", "parameters"):
            val = data.get(dict_key)
            if isinstance(val, str):
                data[dict_key] = json.loads(val or "{}")
        return data

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

    def register_artifact_version(
        self,
        artifact_name: str,
        version: str,
        *,
        fingerprint: str,
        build_id: int | None = None,
        stage: str = "dev",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO registry_versions (
                artifact_name, version, fingerprint, build_id, stage,
                tags, metadata, metrics, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_name, version) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                build_id = excluded.build_id,
                stage = excluded.stage,
                tags = excluded.tags,
                metadata = excluded.metadata,
                metrics = excluded.metrics,
                created_at = excluded.created_at
            """,
            (
                artifact_name,
                version,
                fingerprint,
                build_id,
                stage,
                json.dumps(tags or []),
                json.dumps(metadata or {}),
                json.dumps(metrics or {}),
                now,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def list_registry_versions(
        self,
        artifact_name: str | None = None,
        *,
        stage: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM registry_versions WHERE 1=1"
        params: list[Any] = []
        if artifact_name:
            query += " AND artifact_name = ?"
            params.append(artifact_name)
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._normalize_registry_row(row) for row in rows]

    def get_registry_version(self, artifact_name: str, version: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM registry_versions WHERE artifact_name = ? AND version = ?",
            (artifact_name, version),
        ).fetchone()
        return self._normalize_registry_row(row) if row else None

    def get_latest_registry_version(
        self,
        artifact_name: str,
        *,
        stage: str | None = None,
    ) -> dict[str, Any] | None:
        if stage:
            row = self.conn.execute(
                """
                SELECT * FROM registry_versions
                WHERE artifact_name = ? AND stage = ?
                ORDER BY id DESC LIMIT 1
                """,
                (artifact_name, stage),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT * FROM registry_versions
                WHERE artifact_name = ?
                ORDER BY id DESC LIMIT 1
                """,
                (artifact_name,),
            ).fetchone()
        return self._normalize_registry_row(row) if row else None

    def promote_registry_version(self, artifact_name: str, version: str, stage: str) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE registry_versions SET stage = ?
            WHERE artifact_name = ? AND version = ?
            """,
            (stage, artifact_name, version),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def tag_registry_version(self, artifact_name: str, version: str, tags: list[str]) -> bool:
        row = self.get_registry_version(artifact_name, version)
        if not row:
            return False
        merged = sorted(set((row.get("tags") or []) + tags))
        self.conn.execute(
            """
            UPDATE registry_versions SET tags = ?
            WHERE artifact_name = ? AND version = ?
            """,
            (json.dumps(merged), artifact_name, version),
        )
        self.conn.commit()
        return True

    def _normalize_registry_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("tags", "metadata", "metrics"):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = json.loads(val or ("[]" if key == "tags" else "{}"))
        return data

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
