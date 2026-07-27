"""Streamlit-facing glue: secrets bridge, cached data loading, UI helpers.

Keeping this here means the core modules (``db``, ``elo``, ``stats``) never
import Streamlit and stay unit-testable.
"""

from __future__ import annotations

import os

import streamlit as st

from . import db, elo, stats

APP_TITLE = "⚽ Foosball Ladder"


def _bridge_secrets_to_env() -> None:
    """Copy the DB URL from Streamlit secrets into the env for ``db.py``.

    Supports either ``[db] url = "..."`` or a bare ``FOOSBALL_DB_URL`` secret.
    Absent secrets → ``db`` falls back to the local SQLite file.
    """
    if os.environ.get("FOOSBALL_DB_URL"):
        return
    url = None
    try:
        if "db" in st.secrets and "url" in st.secrets["db"]:
            url = st.secrets["db"]["url"]
        elif "FOOSBALL_DB_URL" in st.secrets:
            url = st.secrets["FOOSBALL_DB_URL"]
    except Exception:
        url = None
    if url:
        os.environ["FOOSBALL_DB_URL"] = str(url)


def engine():
    _bridge_secrets_to_env()
    return db.get_engine()


@st.cache_data(show_spinner=False)
def _bundle(signature):
    eng = engine()
    players = db.get_players(eng)
    matches = db.get_matches(eng)
    states, history = elo.replay(matches)
    agg = stats.aggregate(players, matches)
    traj = stats.trajectories(matches, history)
    return {
        "players": players,
        "matches": matches,
        "states": states,
        "history": history,
        "agg": agg,
        "traj": traj,
        "signature": signature,
    }


def load():
    """Return the full derived data bundle, recomputed only when data changes."""
    eng = engine()
    sig = db.data_signature(eng)
    return _bundle(sig)


# --- small UI helpers ------------------------------------------------------
def page_config(subtitle: str, icon: str = "⚽") -> None:
    st.set_page_config(page_title=f"{subtitle} · Foosball Ladder",
                       page_icon=icon, layout="centered")


def prov_badge(is_prov: bool) -> str:
    return " ⏳" if is_prov else ""


def player_options(players, active_only: bool = True):
    """Return ``(labels, id_by_label)`` for select boxes."""
    ps = [p for p in players if p.get("active", True)] if active_only else list(players)
    labels = [p["name"] for p in ps]
    return labels, {p["name"]: p["id"] for p in ps}
