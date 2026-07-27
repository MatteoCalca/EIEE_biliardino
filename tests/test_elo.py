"""Unit tests for the pure ELO engine (``foosball.elo``).

Runs under pytest *or* standalone: ``python tests/test_elo.py``.
Depends only on the standard library, so it works on the local Python 3.8.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foosball import config, elo  # noqa: E402


def _match(aa, ad, ba, bd, sa, sb, mid=1):
    return {
        "id": mid,
        "team_a_attacker_id": aa,
        "team_a_defender_id": ad,
        "team_b_attacker_id": ba,
        "team_b_defender_id": bd,
        "score_a": sa,
        "score_b": sb,
    }


# --- expected score --------------------------------------------------------
def test_expected_score_symmetry():
    assert abs(elo.expected_score(1500, 1500) - 0.5) < 1e-9
    e = elo.expected_score(1700, 1500)
    assert abs(e + elo.expected_score(1500, 1700) - 1.0) < 1e-9
    assert e > 0.5  # higher-rated side favoured


# --- zero-sum --------------------------------------------------------------
def test_zero_sum_for_fresh_players():
    # All four players are brand new -> identical K -> ratings are conserved.
    states, hist = elo.replay([_match("A", "B", "C", "D", 10, 4)])
    total = sum(hist[0]["deltas"].values())
    assert abs(total) < 1e-9
    # Winners gained, losers lost, by equal-and-opposite amounts.
    assert states["A"].atk > config.START_RATING
    assert states["B"].dfn > config.START_RATING
    assert states["C"].atk < config.START_RATING
    assert states["D"].dfn < config.START_RATING


# --- margin of victory -----------------------------------------------------
def test_bigger_margin_moves_more():
    _, blowout = elo.replay([_match("A", "B", "C", "D", 10, 2)])
    _, squeak = elo.replay([_match("A", "B", "C", "D", 10, 8)])
    assert blowout[0]["deltas"][("A", config.ATTACKER)] > \
        squeak[0]["deltas"][("A", config.ATTACKER)] > 0


def test_overtime_is_the_gentlest_win():
    # 18-16 (overtime, margin 2) should move ratings like a 10-8, and far
    # less than a 10-2 blowout -- this is the whole point of using margin.
    _, ot = elo.replay([_match("A", "B", "C", "D", 18, 16)])
    _, close = elo.replay([_match("A", "B", "C", "D", 10, 8)])
    _, blowout = elo.replay([_match("A", "B", "C", "D", 10, 2)])
    d_ot = ot[0]["deltas"][("A", config.ATTACKER)]
    d_close = close[0]["deltas"][("A", config.ATTACKER)]
    d_blow = blowout[0]["deltas"][("A", config.ATTACKER)]
    assert abs(d_ot - d_close) < 1e-9   # identical: both margin 2
    assert d_ot < d_blow


# --- upsets ----------------------------------------------------------------
def test_upset_moves_more_than_expected_win():
    # Build a big gap: give A/B a strong history, then compare a favourite
    # win vs an underdog win of the same margin.
    strong = [_match("A", "B", "C", "D", 10, 0, mid=i) for i in range(15)]
    base_states, _ = elo.replay(strong)
    fav = base_states["A"].atk  # A is now highly rated

    # Favourite (A/B) beats weak (C/D) 10-6.
    _, fav_hist = elo.replay(strong + [_match("A", "B", "C", "D", 10, 6, mid=99)])
    fav_gain = fav_hist[-1]["deltas"][("A", config.ATTACKER)]

    # Underdog (C/D) beats favourite (A/B) 10-6 -> big upset.
    _, ups_hist = elo.replay(strong + [_match("A", "B", "C", "D", 6, 10, mid=99)])
    ups_gain = ups_hist[-1]["deltas"][("C", config.ATTACKER)]

    assert fav > config.START_RATING
    assert ups_gain > fav_gain > 0


# --- team symmetry ---------------------------------------------------------
def test_team_swap_symmetry():
    _, normal = elo.replay([_match("A", "B", "C", "D", 10, 5)])
    _, swapped = elo.replay([_match("C", "D", "A", "B", 5, 10)])
    for key in normal[0]["deltas"]:
        assert abs(normal[0]["deltas"][key] - swapped[0]["deltas"][key]) < 1e-9


# --- provisional K ---------------------------------------------------------
def test_provisional_k():
    assert elo.k_factor(0) == config.K_PROV
    assert elo.k_factor(config.PROV_GAMES - 1) == config.K_PROV
    assert elo.k_factor(config.PROV_GAMES) == config.K_BASE


# --- position independence -------------------------------------------------
def test_positions_are_tracked_separately():
    # A only ever attacks; their defence rating must stay untouched.
    states, _ = elo.replay([
        _match("A", "B", "C", "D", 10, 3, mid=1),
        _match("A", "X", "Y", "Z", 10, 7, mid=2),
    ])
    assert states["A"].n_atk == 2
    assert states["A"].n_dfn == 0
    assert states["A"].dfn == config.START_RATING
    assert states["A"].atk != config.START_RATING


# --- determinism -----------------------------------------------------------
def test_replay_is_deterministic():
    log = [
        _match("A", "B", "C", "D", 10, 6, mid=1),
        _match("C", "A", "B", "D", 10, 9, mid=2),
        _match("D", "B", "A", "C", 8, 10, mid=3),
    ]
    s1, _ = elo.replay(log)
    s2, _ = elo.replay(log)
    for pid in s1:
        assert abs(s1[pid].atk - s2[pid].atk) < 1e-12
        assert abs(s1[pid].dfn - s2[pid].dfn) < 1e-12


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
