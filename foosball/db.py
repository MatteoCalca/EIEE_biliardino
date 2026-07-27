"""Storage layer — the match log is the single source of truth.

Backed by Postgres (Supabase) in production and by a local SQLite file for
offline development; the only difference is the connection URL. Tables are
created on first use, so pointing the app at a fresh database "just works".

This module is Streamlit-free on purpose (so it can be scripted and tested).
The Streamlit layer feeds it a URL via the ``FOOSBALL_DB_URL`` env var — see
``foosball/service.py``.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table,
    create_engine, func, insert, select, update,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

metadata = MetaData()

players = Table(
    "players", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(80), nullable=False, unique=True),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime, nullable=False, default=dt.datetime.utcnow),
)

matches = Table(
    "matches", metadata,
    Column("id", Integer, primary_key=True),
    Column("played_at", DateTime, nullable=False, default=dt.datetime.utcnow),
    Column("team_a_attacker_id", Integer, ForeignKey("players.id"), nullable=False),
    Column("team_a_defender_id", Integer, ForeignKey("players.id"), nullable=False),
    Column("team_b_attacker_id", Integer, ForeignKey("players.id"), nullable=False),
    Column("team_b_defender_id", Integer, ForeignKey("players.id"), nullable=False),
    Column("score_a", Integer, nullable=False),
    Column("score_b", Integer, nullable=False),
    Column("overtime", Boolean, nullable=False, default=False),
    Column("voided", Boolean, nullable=False, default=False),
    Column("created_at", DateTime, nullable=False, default=dt.datetime.utcnow),
)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def get_database_url() -> str:
    """Resolve the DB URL, normalising Supabase-style schemes for SQLAlchemy."""
    url = os.environ.get("FOOSBALL_DB_URL", "").strip()
    if not url:
        return "sqlite:///" + os.path.join(_REPO_ROOT, "local.db")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


@lru_cache(maxsize=1)
def get_engine():
    """Create (once) and return the SQLAlchemy engine, tables ensured."""
    url = get_database_url()
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url, future=True, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------
def get_players(engine, include_inactive: bool = True) -> list[dict]:
    stmt = select(players).order_by(func.lower(players.c.name))
    if not include_inactive:
        stmt = stmt.where(players.c.active.is_(True))
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(stmt)]


def add_player(engine, name: str) -> int:
    """Insert a player (or return the existing id if the name is taken)."""
    name = name.strip()
    if not name:
        raise ValueError("Player name cannot be empty.")
    with engine.begin() as conn:
        existing = conn.execute(
            select(players.c.id).where(func.lower(players.c.name) == name.lower())
        ).first()
        if existing:
            return int(existing[0])
        res = conn.execute(insert(players).values(name=name, active=True))
        return int(res.inserted_primary_key[0])


def set_player_active(engine, player_id: int, active: bool) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(players).where(players.c.id == player_id).values(active=active)
        )


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------
def _is_overtime(score_a: int, score_b: int) -> bool:
    """A game went to deuce iff it was 9-9 first: margin 2 and loser >= 9."""
    return abs(score_a - score_b) == 2 and min(score_a, score_b) >= 9


def add_match(engine, team_a_attacker_id, team_a_defender_id,
              team_b_attacker_id, team_b_defender_id, score_a, score_b,
              played_at=None) -> int:
    score_a, score_b = int(score_a), int(score_b)
    ids = [team_a_attacker_id, team_a_defender_id, team_b_attacker_id, team_b_defender_id]
    if len(set(ids)) != 4:
        raise ValueError("A player cannot appear more than once in a match.")
    if score_a == score_b:
        raise ValueError("Foosball has no draws — one side must win.")
    with engine.begin() as conn:
        res = conn.execute(insert(matches).values(
            played_at=played_at or dt.datetime.utcnow(),
            team_a_attacker_id=team_a_attacker_id,
            team_a_defender_id=team_a_defender_id,
            team_b_attacker_id=team_b_attacker_id,
            team_b_defender_id=team_b_defender_id,
            score_a=score_a, score_b=score_b,
            overtime=_is_overtime(score_a, score_b), voided=False,
        ))
        return int(res.inserted_primary_key[0])


def get_matches(engine, include_voided: bool = False) -> list[dict]:
    """Return matches oldest -> newest (the order the ELO engine replays)."""
    stmt = select(matches).order_by(matches.c.played_at, matches.c.id)
    if not include_voided:
        stmt = stmt.where(matches.c.voided.is_(False))
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(stmt)]


def void_match(engine, match_id: int, voided: bool = True) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(matches).where(matches.c.id == match_id).values(voided=voided)
        )


def data_signature(engine) -> tuple:
    """A cheap fingerprint of state; changes on any add/void/new-player.

    Used as a cache key so derived ratings recompute exactly when needed.
    """
    with engine.connect() as conn:
        m = conn.execute(select(
            func.count(matches.c.id),
            func.coalesce(func.sum(matches.c.voided), 0),
            func.coalesce(func.max(matches.c.id), 0),
        )).first()
        p = conn.execute(select(func.count(players.c.id))).first()
    return (int(m[0]), int(m[1] or 0), int(m[2] or 0), int(p[0]))
