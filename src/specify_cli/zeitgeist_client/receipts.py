"""Bounded identity-only delivery receipts; selection is never acknowledgement."""

from __future__ import annotations

import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from kernel.clock import now_epoch
from kernel.paths import get_runtime_state_root

MAX_RECEIPTS = 100_000
MAX_PENDING = 4096
MAX_ACKNOWLEDGED = MAX_RECEIPTS
PENDING_TTL_S = 86_400


class ReceiptStore:
    """Store scoped event digests and acknowledgement tokens, never event content.

    Exhaustion fails explicitly instead of evicting delivered identities and
    silently re-notifying them. SQLite transactions serialize concurrent writers.
    Pending tokens expire after one day; expiry does not mark anything read.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_runtime_state_root() / "zeitgeist-receipts.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5.0)
        db.execute("CREATE TABLE IF NOT EXISTS receipts (context TEXT, identity TEXT, shown REAL, event INTEGER, PRIMARY KEY(context, identity))")
        db.execute("CREATE TABLE IF NOT EXISTS pending (context TEXT, token TEXT PRIMARY KEY, identities TEXT, created REAL)")
        return db

    def known(self, context: str) -> set[str]:
        """Identities acknowledged in this exact consumer/filter/stream context."""
        db = self._connect()
        try:
            return {row[0] for row in db.execute("SELECT identity FROM receipts WHERE context = ?", (context,))}
        finally:
            db.close()

    @staticmethod
    def _budget_event_ids(db: sqlite3.Connection, context: str, now: float) -> set[str]:
        identities = {row[0] for row in db.execute("SELECT identity FROM receipts WHERE context = ? AND event = 1 AND shown > ?", (context, now - 60))}
        for row in db.execute("SELECT identities FROM pending WHERE context = ? AND created > ?", (context, now - 60)):
            identities.update(identity for identity, event in json.loads(row[0]) if event)
        return identities

    def budget_event_ids(self, context: str, *, now: float | None = None) -> set[str]:
        """Delivered or reserved event IDs in this rolling minute.

        A pending reservation spends quota, but is never a read receipt. It can
        be retransmitted without spending quota again; failed output becomes
        available for catch-up as the reservation ages out.
        """
        db = self._connect()
        try:
            return self._budget_event_ids(db, context, now_epoch() if now is None else now)
        finally:
            db.close()

    def prepare(self, context: str, identities: list[tuple[str, bool]], *, now: float | None = None, rate_limit: int | None = None) -> str | None:
        """Issue a receipt for a selected batch without marking it delivered."""
        if not identities:
            return None
        now = now_epoch() if now is None else now
        db = self._connect()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM pending WHERE created < ?", (now - PENDING_TTL_S,))
                if db.execute("SELECT count(*) FROM pending WHERE identities != '[]'").fetchone()[0] >= MAX_PENDING:
                    raise ValueError("Zeitgeist batch receipt capacity reached; wait for receipt-token expiry (one day).")
                if db.execute("SELECT count(*) FROM receipts").fetchone()[0] + len(identities) > MAX_RECEIPTS:
                    raise ValueError("Zeitgeist receipt capacity reached; use explicit replay to inspect retained activity.")
                if rate_limit is not None:
                    used = self._budget_event_ids(db, context, now)
                    additional = {identity for identity, event in identities if event} - used
                    if additional and len(used) + len(additional) > rate_limit:
                        raise ValueError("Zeitgeist rate budget changed during this read; retry or catch up after the rolling minute.")
                token = secrets.token_hex(24)
                db.execute("INSERT INTO pending VALUES (?, ?, ?, ?)", (context, token, json.dumps(identities), now))
                return token
        finally:
            db.close()

    def acknowledge(self, context: str, token: str, *, now: float | None = None) -> None:
        """Commit only an issued receipt belonging to this exact context."""
        now = now_epoch() if now is None else now
        db = self._connect()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT identities, created FROM pending WHERE context = ? AND token = ?", (context, token)).fetchone()
                if row is None or row[1] < now - PENDING_TTL_S:
                    raise ValueError("Unknown or expired Zeitgeist receipt for this consumer and scope.")
                identities: list[Any] = json.loads(row[0])
                if identities:
                    db.execute("DELETE FROM pending WHERE created < ?", (now - PENDING_TTL_S,))
                    acknowledged = db.execute("SELECT count(*) FROM pending WHERE identities = '[]'").fetchone()[0]
                    if acknowledged >= MAX_ACKNOWLEDGED:
                        raise ValueError("Zeitgeist acknowledgement token capacity reached; wait for token expiry (one day).")
                if db.execute("SELECT count(*) FROM receipts").fetchone()[0] + len(identities) > MAX_RECEIPTS:
                    raise ValueError("Zeitgeist receipt capacity reached; acknowledgement was not recorded.")
                db.executemany("INSERT OR IGNORE INTO receipts VALUES (?, ?, ?, ?)", [(context, identity, now, int(event)) for identity, event in identities])
                db.execute("UPDATE pending SET identities = ? WHERE token = ?", ("[]", token))
        finally:
            db.close()
