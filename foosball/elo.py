"""Pure ELO rating engine for 2v2 foosball with per-position ratings.

Design notes
------------
* Every player carries TWO ratings: an attack rating and a defence rating.
  A game only touches, and is only predicted by, the rating for the position
  the player actually played.
* A team's strength is the attacker's attack rating blended with the
  defender's defence rating (a plain average keeps everything on one scale).
* Result uses win/loss (foosball has no draws) scaled by a margin-of-victory
  multiplier so that dominant wins move ratings more than nail-biters.
* This module is deliberately dependency-free (stdlib ``math`` only) so the
  maths can be unit-tested anywhere and reused outside Streamlit.

The single entry point is :func:`replay`, which takes the full match log in
chronological order and rebuilds every rating from scratch. Ratings are never
persisted — the match log is the source of truth — which makes edits/undo
trivially correct.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import config


# ---------------------------------------------------------------------------
# Per-player state
# ---------------------------------------------------------------------------
@dataclass
class PlayerState:
    """Live rating state for one player while replaying the match log."""

    atk: float = config.START_RATING
    dfn: float = config.START_RATING   # "def" is a keyword; use dfn
    n_atk: int = 0                     # games played as attacker
    n_dfn: int = 0                     # games played as defender

    @property
    def games(self) -> int:
        return self.n_atk + self.n_dfn

    def rating(self, position: str) -> float:
        return self.atk if position == config.ATTACKER else self.dfn

    def role_games(self, position: str) -> int:
        return self.n_atk if position == config.ATTACKER else self.n_dfn

    @property
    def overall(self) -> float:
        """Experience-weighted blend of the two ratings (headline number)."""
        if self.games == 0:
            return config.START_RATING
        return (self.atk * self.n_atk + self.dfn * self.n_dfn) / self.games

    def is_provisional(self, position: str | None = None) -> bool:
        """True while a rating hasn't yet settled.

        With ``position`` given, checks that specific role; otherwise the
        overall rating is provisional until *either* role has settled.
        """
        if position is None:
            return self.games < config.PROV_GAMES
        return self.role_games(position) < config.PROV_GAMES


# ---------------------------------------------------------------------------
# Core maths
# ---------------------------------------------------------------------------
def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that side A beats side B (logistic, scale 400)."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / config.SCALE))


def team_rating(attacker_atk: float, defender_dfn: float) -> float:
    """Combined strength of a team from its attacker and defender ratings."""
    return (attacker_atk + defender_dfn) / 2.0


def mov_multiplier(margin: int, winner_rating: float, loser_rating: float) -> float:
    """Margin-of-victory multiplier (FiveThirtyeight-style).

    ``ln(margin + 1)`` rewards blowouts; the damping term shrinks the reward
    when a favourite wins (``dR > 0``) and inflates it when an underdog wins
    (``dR < 0``). The denominator is floored so it can never flip sign.
    """
    diff = winner_rating - loser_rating
    denom = max(config.MOV_DENOM_FLOOR, config.MOV_DIFF_COEF * diff + config.MOV_DAMP)
    return math.log(margin + 1) * (config.MOV_DAMP / denom)


def k_factor(role_games: int) -> float:
    """Higher K while a rating is provisional, lower once it has settled."""
    return config.K_PROV if role_games < config.PROV_GAMES else config.K_BASE


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
# Each match is a mapping with these keys (player refs are any hashable id):
#   id, team_a_attacker_id, team_a_defender_id,
#       team_b_attacker_id, team_b_defender_id, score_a, score_b
# and is assumed already ordered oldest -> newest and free of voided rows.

def replay(matches):
    """Replay the whole match log and return ``(states, history)``.

    ``states``  : dict ``player_id -> PlayerState`` with final ratings.
    ``history`` : list of per-match records (pre/post ratings, deltas,
                  expected score, MoV multiplier) — used for charts and for
                  showing "what just changed" after a submission.
    """
    states: dict = {}

    def get(pid) -> PlayerState:
        st = states.get(pid)
        if st is None:
            st = states[pid] = PlayerState()
        return st

    history = []
    for m in matches:
        aa, ad = m["team_a_attacker_id"], m["team_a_defender_id"]
        ba, bd = m["team_b_attacker_id"], m["team_b_defender_id"]
        sa, sb = int(m["score_a"]), int(m["score_b"])

        s_aa, s_ad = get(aa), get(ad)
        s_ba, s_bd = get(ba), get(bd)

        r_a = team_rating(s_aa.atk, s_ad.dfn)
        r_b = team_rating(s_ba.atk, s_bd.dfn)

        e_a = expected_score(r_a, r_b)
        e_b = 1.0 - e_a

        if sa > sb:
            result_a = 1.0
        elif sa < sb:
            result_a = 0.0
        else:
            result_a = 0.5  # defensive; real foosball never ties
        result_b = 1.0 - result_a

        margin = abs(sa - sb)
        if result_a >= 0.5:
            winner_r, loser_r = r_a, r_b
        else:
            winner_r, loser_r = r_b, r_a
        mult = mov_multiplier(margin, winner_r, loser_r)

        err_a = result_a - e_a
        err_b = result_b - e_b

        # Per-player K depends on how many games they've played *in this role*.
        d_aa = k_factor(s_aa.n_atk) * mult * err_a
        d_ad = k_factor(s_ad.n_dfn) * mult * err_a
        d_ba = k_factor(s_ba.n_atk) * mult * err_b
        d_bd = k_factor(s_bd.n_dfn) * mult * err_b

        record = {
            "match_id": m.get("id"),
            "expected_a": e_a,
            "team_rating_a": r_a,
            "team_rating_b": r_b,
            "mov_multiplier": mult,
            "result_a": result_a,
            "margin": margin,
            # keyed by (player_id, position)
            "pre": {
                (aa, config.ATTACKER): s_aa.atk,
                (ad, config.DEFENDER): s_ad.dfn,
                (ba, config.ATTACKER): s_ba.atk,
                (bd, config.DEFENDER): s_bd.dfn,
            },
            "deltas": {
                (aa, config.ATTACKER): d_aa,
                (ad, config.DEFENDER): d_ad,
                (ba, config.ATTACKER): d_ba,
                (bd, config.DEFENDER): d_bd,
            },
        }

        # Apply updates.
        s_aa.atk += d_aa; s_aa.n_atk += 1
        s_ad.dfn += d_ad; s_ad.n_dfn += 1
        s_ba.atk += d_ba; s_ba.n_atk += 1
        s_bd.dfn += d_bd; s_bd.n_dfn += 1

        record["post"] = {
            (aa, config.ATTACKER): s_aa.atk,
            (ad, config.DEFENDER): s_ad.dfn,
            (ba, config.ATTACKER): s_ba.atk,
            (bd, config.DEFENDER): s_bd.dfn,
        }
        history.append(record)

    return states, history
