"""SQLite state store for goldfish sessions and runs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Dict, List

from .utils import kb_root, now


SCHEMA_VERSION = 2


def state_db_path(root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "scripts" / "goldfish" / "output_cache" / "goldfish.db"


class GoldfishState:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or kb_root()
        self.path = state_db_path(self.root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.session() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    use_llm INTEGER NOT NULL,
                    provider TEXT,
                    model TEXT,
                    counts_json TEXT NOT NULL,
                    paths_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    title TEXT NOT NULL,
                    target_type TEXT,
                    score REAL,
                    url TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sources_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    source_name TEXT,
                    status TEXT,
                    error TEXT,
                    items_count INTEGER DEFAULT 0,
                    manual_review_count INTEGER DEFAULT 0,
                    last_success_at TEXT,
                    quality_score REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "sources_health", "manual_review_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "sources_health", "last_success_at", "TEXT")
            self._ensure_column(conn, "sources_health", "quality_score", "REAL DEFAULT 0")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def record_run(
        self,
        report: Dict[str, Any],
        settings: Dict[str, Any],
        insights: List[Dict[str, Any]],
        source_health: List[Dict[str, Any]] | None = None,
    ) -> int:
        created = now(settings.get("timezone", "Asia/Shanghai")).isoformat()
        with self.session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs(date, dry_run, use_llm, provider, model, counts_json, paths_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.get("date", ""),
                    int(bool(report.get("dry_run"))),
                    int(bool(report.get("use_llm"))),
                    settings.get("llm_provider", ""),
                    settings.get("llm_model", ""),
                    json.dumps(report.get("counts", {}), ensure_ascii=False),
                    json.dumps(report.get("paths", {}), ensure_ascii=False),
                    created,
                ),
            )
            run_id = int(cursor.lastrowid)
            for insight in insights:
                conn.execute(
                    """
                    INSERT INTO insights(run_id, title, target_type, score, url, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        insight.get("title", ""),
                        insight.get("target_type", ""),
                        float(insight.get("score", 0) or 0),
                        insight.get("url", ""),
                        json.dumps(_json_safe_insight(insight), ensure_ascii=False),
                        created,
                    ),
                )
            for record in source_health or []:
                conn.execute(
                    """
                    INSERT INTO sources_health(
                        run_id, source_name, status, error, items_count,
                        manual_review_count, last_success_at, quality_score, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        record.get("source_name", ""),
                        record.get("status", ""),
                        record.get("error_message") or record.get("error", ""),
                        int(record.get("items_count", 0) or 0),
                        int(record.get("manual_review_count", 0) or 0),
                        record.get("last_success_at", ""),
                        float(record.get("quality_score", 0) or 0),
                        record.get("created_at") or created,
                    ),
                )
            return run_id

    def record_message(self, session_id: str, role: str, content: str) -> None:
        with self.session() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now().isoformat()),
            )

    def recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def last_run(self) -> Dict[str, Any] | None:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def recent_source_health(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM sources_health ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def source_health_summary(self, limit: int = 8) -> Dict[str, Any]:
        with self.session() as conn:
            failing = conn.execute(
                """
                SELECT source_name,
                       COUNT(*) AS fail_count,
                       MAX(created_at) AS last_checked,
                       MAX(error) AS last_error
                FROM sources_health
                WHERE status = 'fail'
                GROUP BY source_name
                ORDER BY fail_count DESC, last_checked DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            valuable = conn.execute(
                """
                SELECT source_name,
                       AVG(quality_score) AS average_quality,
                       SUM(items_count) AS total_items,
                       MAX(last_success_at) AS last_success_at
                FROM sources_health
                WHERE status = 'success'
                GROUP BY source_name
                ORDER BY average_quality DESC, total_items DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {
            "failing_sources": [dict(row) for row in failing],
            "valuable_sources": [dict(row) for row in valuable],
        }

    def search_insights(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        like = f"%{query}%"
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM insights
                WHERE title LIKE ? OR target_type LIKE ? OR url LIKE ? OR payload_json LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        like = f"%{query}%"
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_message_sessions(self, limit: int = 3) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT session_id,
                       COUNT(*) AS message_count,
                       MAX(created_at) AS last_seen
                FROM messages
                GROUP BY session_id
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


def _json_safe_insight(insight: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(insight)
    source_item = safe.get("source_item")
    if isinstance(source_item, dict):
        safe["source_item"] = {
            key: value
            for key, value in source_item.items()
            if key not in {"raw_content"} and isinstance(value, (str, int, float, bool, list, dict, type(None)))
        }
    return safe
