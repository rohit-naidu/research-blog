"""
orchestrator.state
==================

SQLite-backed job tracker + cost ledger.

Why SQLite and not a JSON file?
    - We need atomic writes across multiple async tasks running in parallel.
    - We need to query "what's been done?" and "how much have we spent?"
      efficiently as the run progresses.
    - The user can poke at the DB with `sqlite3 state.sqlite` if anything
      looks wrong — much more debuggable than a custom file format.

Schema:
    jobs        One row per article-stage pair. Tracks status, started/finished
                timestamps, the output path on disk, and the cost in USD.
    api_calls   Append-only log of every API call ever made. Each row has the
                model, tokens in/out, latency, dollar cost, and a foreign key
                to the parent job. Used for both cost tracking and for
                regenerating prompts later if we want to.

Status values for jobs:
    pending     not started
    running     a worker is currently executing this stage
    done        completed successfully
    failed      raised an exception
    safety_hold the safety reviewer flagged a critical issue
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

import aiosqlite


# ---------------------------------------------------------------------------
# DDL — all the CREATE TABLE statements we run at startup.
#
# IF NOT EXISTS makes this idempotent so we can call init() on every run.
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    output_path TEXT,
    started_at REAL,
    finished_at REAL,
    cost_usd REAL DEFAULT 0.0,
    error TEXT,
    UNIQUE(article_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    model TEXT NOT NULL,
    api TEXT NOT NULL,            -- 'openai' | 'grok' | 'anthropic'
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    cost_usd REAL NOT NULL,
    called_at REAL NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_calls_job ON api_calls(job_id);
CREATE INDEX IF NOT EXISTS idx_api_calls_called_at ON api_calls(called_at);

CREATE TABLE IF NOT EXISTS run_metadata (
    run_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    finished_at REAL,
    tier INTEGER NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
"""


@dataclass
class JobRecord:
    """One row from the jobs table, as a dataclass for readability."""

    id: int
    article_id: str
    stage: str
    status: str
    output_path: str | None
    started_at: float | None
    finished_at: float | None
    cost_usd: float
    error: str | None


class StateStore:
    """
    Thin async wrapper around aiosqlite.

    Use as a context manager:
        async with StateStore(db_path) as state:
            await state.start_job("supplements", "research")
            ...
            await state.finish_job("supplements", "research", output="/path/to/file")
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        # Lock to serialize writes; SQLite supports concurrent reads but
        # writes from multiple async tasks can step on each other without one.
        self._write_lock = asyncio.Lock()

    async def __aenter__(self) -> "StateStore":
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        # Initialize schema if needed.
        await self._conn.executescript(_DDL)
        await self._conn.commit()
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("StateStore not entered. Use `async with`.")
        return self._conn

    # ------------------------------------------------------------------ jobs

    async def start_job(self, article_id: str, stage: str) -> int:
        """Mark a job as running. Returns the job row id."""
        async with self._write_lock:
            now = time.time()
            await self.conn.execute(
                """
                INSERT INTO jobs (article_id, stage, status, started_at)
                VALUES (?, ?, 'running', ?)
                ON CONFLICT(article_id, stage) DO UPDATE SET
                    status = 'running',
                    started_at = excluded.started_at,
                    error = NULL
                """,
                (article_id, stage, now),
            )
            await self.conn.commit()
            cursor = await self.conn.execute(
                "SELECT id FROM jobs WHERE article_id = ? AND stage = ?",
                (article_id, stage),
            )
            row = await cursor.fetchone()
            return int(row["id"])

    async def finish_job(
        self,
        article_id: str,
        stage: str,
        *,
        output_path: str | None = None,
        cost_usd: float = 0.0,
        status: str = "done",
        error: str | None = None,
    ) -> None:
        """Mark a job as done/failed/safety_hold."""
        async with self._write_lock:
            now = time.time()
            await self.conn.execute(
                """
                UPDATE jobs SET
                    status = ?,
                    output_path = ?,
                    finished_at = ?,
                    cost_usd = cost_usd + ?,
                    error = ?
                WHERE article_id = ? AND stage = ?
                """,
                (status, output_path, now, cost_usd, error, article_id, stage),
            )
            await self.conn.commit()

    async def get_job(self, article_id: str, stage: str) -> JobRecord | None:
        cursor = await self.conn.execute(
            "SELECT * FROM jobs WHERE article_id = ? AND stage = ?",
            (article_id, stage),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return JobRecord(
            id=row["id"],
            article_id=row["article_id"],
            stage=row["stage"],
            status=row["status"],
            output_path=row["output_path"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            cost_usd=row["cost_usd"],
            error=row["error"],
        )

    async def all_jobs(self) -> list[JobRecord]:
        cursor = await self.conn.execute("SELECT * FROM jobs ORDER BY id")
        rows = await cursor.fetchall()
        return [
            JobRecord(
                id=r["id"],
                article_id=r["article_id"],
                stage=r["stage"],
                status=r["status"],
                output_path=r["output_path"],
                started_at=r["started_at"],
                finished_at=r["finished_at"],
                cost_usd=r["cost_usd"],
                error=r["error"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------- api calls

    async def log_api_call(
        self,
        *,
        job_id: int | None,
        model: str,
        api: str,
        tokens_in: int | None,
        tokens_out: int | None,
        latency_ms: int,
        cost_usd: float,
        dry_run: bool,
    ) -> None:
        """Append-only log of every API call."""
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO api_calls
                (job_id, model, api, tokens_in, tokens_out, latency_ms,
                 cost_usd, called_at, dry_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    model,
                    api,
                    tokens_in,
                    tokens_out,
                    latency_ms,
                    cost_usd,
                    time.time(),
                    1 if dry_run else 0,
                ),
            )
            await self.conn.commit()

    # ------------------------------------------------------ cost accounting

    async def total_cost_usd(self) -> float:
        """Sum of all non-dry-run API calls so far."""
        cursor = await self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM api_calls WHERE dry_run = 0"
        )
        row = await cursor.fetchone()
        return float(row["total"])

    async def cost_by_stage(self) -> dict[str, float]:
        """Sum of costs grouped by stage (joined via jobs)."""
        cursor = await self.conn.execute(
            """
            SELECT j.stage AS stage, COALESCE(SUM(a.cost_usd), 0.0) AS total
            FROM api_calls a
            LEFT JOIN jobs j ON j.id = a.job_id
            WHERE a.dry_run = 0
            GROUP BY j.stage
            """
        )
        rows = await cursor.fetchall()
        return {r["stage"] or "<unattributed>": float(r["total"]) for r in rows}


@asynccontextmanager
async def open_state(db_path: Path) -> AsyncIterator[StateStore]:
    """Convenience context manager."""
    store = StateStore(db_path)
    async with store as s:
        yield s
