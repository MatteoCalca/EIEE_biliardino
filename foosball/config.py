"""Tunable constants for the foosball ELO engine.

Everything a maintainer might want to adjust lives here so the rating maths in
``elo.py`` reads cleanly. Values are deliberately conservative for a small,
occasionally-played office ladder.
"""

# --- Base rating -----------------------------------------------------------
START_RATING = 1500.0     # every new player starts here, for both roles
SCALE = 400.0             # logistic scale for the expected-score curve

# --- K-factor (how fast ratings move) --------------------------------------
K_BASE = 24.0             # established players
K_PROV = 48.0             # provisional players (their first PROV_GAMES in a role)
PROV_GAMES = 10           # games *in a role* before that rating is "established"

# Opponent-reliability weighting: a game's rating change is scaled by how
# well-known the players are. A brand-new rating is "unreliable" (0) and ramps
# to fully "reliable" (1) over PROV_GAMES games in a role. A settled player
# still moves at least REL_FLOOR of the normal amount against an unknown (so a
# real upset is never fully ignored), while a newcomer always moves fast.
REL_FLOOR = 0.25

# --- Margin-of-victory multiplier (FiveThirtyeight-style) ------------------
# multiplier = ln(margin + 1) * (MOV_DAMP / (MOV_DIFF_COEF * dR + MOV_DAMP))
# The ln term rewards blowouts; the second term damps a strong favourite from
# farming points by running up the score (and boosts underdog blowouts).
MOV_DAMP = 2.2
MOV_DIFF_COEF = 0.001
MOV_DENOM_FLOOR = 0.20    # keep the damper denominator strictly positive

# --- Roles -----------------------------------------------------------------
ATTACKER = "attacker"     # "front"
DEFENDER = "defender"     # "back"
POSITIONS = (ATTACKER, DEFENDER)
