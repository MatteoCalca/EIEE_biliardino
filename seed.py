"""Seed the local database with fake players and matches for a demo.

Usage:
    python seed.py            # ~12 players, ~200 matches into the SQLite file
    python seed.py --reset    # wipe existing rows first

Each fake player has hidden per-position skills; match scores are drawn from
those skills so the recovered ELO ratings are actually meaningful to look at.
Uses only the local SQLite fallback unless FOOSBALL_DB_URL is set.
"""

from __future__ import annotations

import argparse
import random
import sys

from foosball import db

NAMES = [
    "Alice", "Bruno", "Chiara", "Dario", "Elena", "Franco",
    "Giulia", "Hassan", "Irene", "Jacopo", "Klara", "Luca",
]


def _score_from_strength(diff: float) -> tuple[int, int]:
    """Turn a strength difference into a plausible 0..10ish foosball score."""
    p = 1.0 / (1.0 + 10 ** (-diff / 300.0))  # win prob for side A
    if random.random() < p:
        win, lose = 10, min(9, int(abs(random.gauss(5, 2.5))))
    else:
        lose, win = min(9, int(abs(random.gauss(5, 2.5)))), 10
        return lose, win  # A lost
    # occasional overtime
    if random.random() < 0.10:
        margin = 2
        base = random.choice([9, 10, 11])
        return base + margin, base
    return win, lose


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="wipe rows first")
    ap.add_argument("--matches", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    engine = db.get_engine()

    if args.reset:
        with engine.begin() as conn:
            conn.execute(db.matches.delete())
            conn.execute(db.players.delete())

    # hidden skills: (attack, defence) offsets around 0
    skills = {}
    ids = {}
    for name in NAMES:
        pid = db.add_player(engine, name)
        ids[name] = pid
        skills[pid] = (random.gauss(0, 120), random.gauss(0, 120))

    all_ids = list(ids.values())
    made = 0
    for _ in range(args.matches):
        four = random.sample(all_ids, 4)
        aa, ad, ba, bd = four
        strength_a = skills[aa][0] + skills[ad][1]
        strength_b = skills[ba][0] + skills[bd][1]
        sa, sb = _score_from_strength(strength_a - strength_b)
        try:
            db.add_match(engine, aa, ad, ba, bd, sa, sb)
            made += 1
        except ValueError:
            pass

    print(f"Seeded {len(NAMES)} players and {made} matches "
          f"into {db.get_database_url()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
