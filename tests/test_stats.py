"""Unit tests for the post-submit explanation (``stats.explain_changes``).

Runs under pytest *or* standalone: ``python tests/test_stats.py``.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foosball import config, elo, stats  # noqa: E402


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


def test_explain_fresh_players():
    _, hist = elo.replay([_match("A", "B", "C", "D", 10, 4)])
    headline, reasons = stats.explain_changes(hist[0])
    assert headline.startswith("Team A were evenly matched (50% to win)")
    assert set(reasons) == set(hist[0]["deltas"])
    assert "first attack game" in reasons[("A", config.ATTACKER)]
    assert "first defense game" in reasons[("B", config.DEFENDER)]
    assert f"×{config.K_PROV / config.K_BASE:.1f}" in reasons[("A", config.ATTACKER)]


def test_explain_settled_vs_newcomers():
    log = [_match("A", "B", "X", "Y", 10, 5, mid=i) for i in range(1, 13)]
    _, hist = elo.replay(log + [_match("A", "B", "C", "D", 6, 10, mid=99)])
    headline, reasons = stats.explain_changes(hist[-1])
    assert headline.startswith("Team B were underdogs")
    assert "moved more than in a typical game" in headline
    settled = reasons[("A", config.ATTACKER)]
    assert "settled attack rating" in settled and "damped" in settled
    assert "first attack game" in reasons[("C", config.ATTACKER)]
    assert "damped" not in reasons[("C", config.ATTACKER)]


def test_explain_provisional_count():
    log = [_match("A", "B", "C", "D", 10, 8, mid=i) for i in range(1, 4)]
    _, hist = elo.replay(log)
    _, reasons = stats.explain_changes(hist[-1])
    assert f"2/{config.PROV_GAMES} attack games" in reasons[("A", config.ATTACKER)]


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
