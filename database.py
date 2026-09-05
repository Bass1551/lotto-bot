# -*- coding: utf-8 -*-
"""SQLite database layer for storing sent lottery results (prevent duplicates)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Optional

from utils import setup_logging

logger = setup_logging()


class Database:
    """Simple SQLite wrapper focused on duplicate-send prevention."""

    def __init__(self, db_path: str = "lottery_results.db") -> None:
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_name TEXT NOT NULL,
                    result_date  TEXT NOT NULL,
                    top3         TEXT NOT NULL,
                    bottom2      TEXT NOT NULL,
                    full_result  TEXT,
                    sent_at      TEXT NOT NULL,
                    UNIQUE(lottery_name, result_date)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lottery_date
                ON results (lottery_name, result_date)
                """
            )
        logger.info("Database initialized at %s", self.db_path)

    def already_sent(self, lottery_name: str, result_date: Optional[date] = None) -> bool:
        """Check whether a result for this lottery on this date was already sent.

        Args:
            lottery_name: Name of the lottery (must match config).
            result_date: Date of the draw. Defaults to today.

        Returns:
            True if already recorded as sent.
        """
        if result_date is None:
            result_date = date.today()
        date_str = result_date.isoformat()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM results
                WHERE lottery_name = ? AND result_date = ?
                LIMIT 1
                """,
                (lottery_name, date_str),
            ).fetchone()
        return row is not None

    def save_result(
        self,
        lottery_name: str,
        top3: str,
        bottom2: str,
        full_result: str = "",
        result_date: Optional[date] = None,
    ) -> bool:
        """Save a sent result. Returns False if already exists (duplicate).

        Args:
            lottery_name: Name of the lottery.
            top3: 3-digit top.
            bottom2: 2-digit bottom.
            full_result: Optional raw full number string.
            result_date: Draw date. Defaults to today.

        Returns:
            True if inserted successfully, False if duplicate.
        """
        if result_date is None:
            result_date = date.today()
        date_str = result_date.isoformat()
        sent_at = datetime.now().isoformat(timespec="seconds")

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO results
                        (lottery_name, result_date, top3, bottom2, full_result, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (lottery_name, date_str, top3, bottom2, full_result, sent_at),
                )
            logger.info(
                "Saved result: %s | %s | top3=%s bottom2=%s",
                lottery_name,
                date_str,
                top3,
                bottom2,
            )
            return True
        except sqlite3.IntegrityError:
            logger.warning(
                "Duplicate prevented: %s already sent for %s",
                lottery_name,
                date_str,
            )
            return False

    def get_last_result(self, lottery_name: str) -> Optional[dict]:
        """Return the most recent result for a lottery (for debugging)."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM results
                WHERE lottery_name = ?
                ORDER BY result_date DESC, sent_at DESC
                LIMIT 1
                """,
                (lottery_name,),
            ).fetchone()
        return dict(row) if row else None

    def get_daily_results(self, result_date: Optional[date] = None) -> list[dict]:
        """Return all recorded results for a specific date."""
        if result_date is None:
            result_date = date.today()
        date_str = result_date.isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM results
                WHERE result_date = ?
                ORDER BY id ASC
                """,
                (date_str,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_history_results(
        self,
        lottery_name: str,
        limit: int = 15,
        before_date: Optional[date] = None,
        include_today: bool = False,
    ) -> list[dict]:
        """Return the most recent `limit` historical results for a lottery strictly before today, sorted chronologically."""
        if before_date is None:
            before_date = date.today()
        date_str = before_date.isoformat()

        op = "<=" if include_today else "<"
        query = f"""
            SELECT * FROM results
            WHERE (lottery_name = ? OR lottery_name LIKE ?)
              AND result_date {op} ?
            ORDER BY result_date DESC
            LIMIT ?
        """

        with self._connect() as conn:
            rows = conn.execute(
                query,
                (lottery_name, f"%{lottery_name}%", date_str, limit),
            ).fetchall()
        results = [dict(r) for r in rows]
        results.reverse()  # Chronological order (oldest to newest)
        return results


