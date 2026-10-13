from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Self

Kind = Literal["job", "phd"]
Status = Literal["new", "shortlisted", "applied", "interview", "rejected", "ignored"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    company_or_lab TEXT NOT NULL,
    location TEXT,
    url TEXT NOT NULL,
    description TEXT,
    posted_at TEXT,
    fetched_at TEXT NOT NULL,
    score REAL,
    flags TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT,
    cv_variant TEXT,
    dedup_key TEXT NOT NULL UNIQUE
)
"""


@dataclass
class Offer:
    source: str
    kind: Kind
    title: str
    company_or_lab: str
    url: str
    location: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    fetched_at: datetime = field(default_factory=datetime.now)
    score: float | None = None
    flags: list[str] = field(default_factory=list)
    status: Status = "new"
    notes: str | None = None
    cv_variant: str | None = None
    id: int | None = None


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _dedup_key(title: str, company_or_lab: str, url: str) -> str:
    return "|".join(_normalize(v) for v in (title, company_or_lab, url))


class Store:
    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def add_offer(self, offer: Offer) -> int:
        dedup_key = _dedup_key(offer.title, offer.company_or_lab, offer.url)
        self._conn.execute(
            """
            INSERT OR IGNORE INTO offers
                (source, kind, title, company_or_lab, location, url, description,
                 posted_at, fetched_at, score, flags, status, notes, cv_variant, dedup_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer.source,
                offer.kind,
                offer.title,
                offer.company_or_lab,
                offer.location,
                offer.url,
                offer.description,
                offer.posted_at.isoformat() if offer.posted_at else None,
                offer.fetched_at.isoformat(),
                offer.score,
                json.dumps(offer.flags),
                offer.status,
                offer.notes,
                offer.cv_variant,
                dedup_key,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM offers WHERE dedup_key = ?", (dedup_key,)
        ).fetchone()
        return row["id"]

    def get_offer(self, offer_id: int) -> Offer | None:
        row = self._conn.execute(
            "SELECT * FROM offers WHERE id = ?", (offer_id,)
        ).fetchone()
        return _row_to_offer(row) if row else None

    def list_offers(self) -> list[Offer]:
        rows = self._conn.execute("SELECT * FROM offers ORDER BY id").fetchall()
        return [_row_to_offer(row) for row in rows]


def _row_to_offer(row: sqlite3.Row) -> Offer:
    return Offer(
        id=row["id"],
        source=row["source"],
        kind=row["kind"],
        title=row["title"],
        company_or_lab=row["company_or_lab"],
        location=row["location"],
        url=row["url"],
        description=row["description"],
        posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        score=row["score"],
        flags=json.loads(row["flags"]),
        status=row["status"],
        notes=row["notes"],
        cv_variant=row["cv_variant"],
    )
