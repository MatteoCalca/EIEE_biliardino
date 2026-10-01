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


def test_win_probability_uses_position_ratings():
    # Unknown players are fresh -> coin flip.
    assert abs(elo.win_probability({}, "A", "B", "C", "D") - 0.5) < 1e-9
    states, hist = elo.replay([_match("A", "B", "C", "D", 10, 4)])
    p = elo.win_probability(states, "A", "B", "C", "D")
    # Same lineup as the replayed match -> next game's expected score.
    r_a = elo.team_rating(*(hist[0]["post"][k] for k in
                            (("A", config.ATTACKER), ("B", config.DEFENDER))))
    r_b = elo.team_rating(*(hist[0]["post"][k] for k in
                            (("C", config.ATTACKER), ("D", config.DEFENDER))))
    assert abs(p - elo.expected_score(r_a, r_b)) < 1e-12
    assert p > 0.5  # winners favoured in the rematch
    # A's defense and B's attack were never played -> swapping roles is 50/50.
    assert abs(elo.win_probability(states, "B", "A", "D", "C") - 0.5) < 1e-9


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


# --- reliability-weighted K ------------------------------------------------
def test_reliability_ramps():
    assert elo.reliability(0) == 0.0
    assert elo.reliability(config.PROV_GAMES) == 1.0
    assert 0.0 < elo.reliability(config.PROV_GAMES // 2) < 1.0


def test_continuous_k():
    assert elo.own_k(0.0) == config.K_PROV          # brand new -> fast
    assert elo.own_k(1.0) == config.K_BASE          # settled -> stable
    assert config.K_BASE < elo.own_k(0.5) < config.K_PROV


def test_fresh_vs_fresh_moves_fast_and_conserves():
    # Everyone unknown: full provisional K, no attenuation, zero-sum.
    assert abs(elo.step_size(0.0, 0.0) - config.K_PROV) < 1e-9
    _, hist = elo.replay([_match("A", "B", "C", "D", 10, 4)])
    assert abs(sum(hist[0]["deltas"].values())) < 1e-9


def test_established_moves_less_than_newcomer():
    # A/B get a long history (settled); C/D never played (brand new).
    history = [_match("A", "B", "X", "Y", 10, 5, mid=i) for i in range(1, 13)]
    states, _ = elo.replay(history)
    assert states["A"].n_atk >= config.PROV_GAMES   # A is settled at attack

    _, h = elo.replay(history + [_match("A", "B", "C", "D", 10, 6, mid=99)])
    d = h[-1]["deltas"]
    settled = abs(d[("A", config.ATTACKER)])
    newcomer = abs(d[("C", config.ATTACKER)])
    assert newcomer > settled       # the unknown moves much more
    assert settled > 0              # ...but the veteran isn't frozen


def test_settled_step_is_floored_not_zero():
    # Settled player vs total unknowns: damped to REL_FLOOR, never zero.
    s = elo.step_size(1.0, 0.0)
    assert abs(s - config.K_BASE * config.REL_FLOOR) < 1e-9
    assert s > 0


def test_record_exposes_speed():
    # delta == step * margin multiplier * (result - expected), exactly: the
    # post-submit explanation relies on this decomposition.
    log = [_match("A", "B", "C", "D", 10, 4, mid=i) for i in range(1, 13)]
    log += [_match("A", "E", "C", "B", 7, 10, mid=20),
            _match("E", "C", "F", "A", 10, 8, mid=21)]
    _, hist = elo.replay(log)
    seen = {}
    for rec in hist:
        err_a = rec["result_a"] - rec["expected_a"]
        for i, (key, d) in enumerate(rec["deltas"].items()):
            err = err_a if i < 2 else -err_a
            assert abs(d - rec["step"][key] * rec["mov_multiplier"] * err) < 1e-9
            assert rec["role_games"][key] == seen.get(key, 0)
            seen[key] = seen.get(key, 0) + 1


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
