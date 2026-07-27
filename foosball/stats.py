"""Derived statistics computed from the match log and the ELO replay.

All functions take plain data (lists of dicts, the replay outputs) and return
plain data, so this module stays dependency-free and unit-testable. The
Streamlit pages turn these into tables and charts.
"""

from __future__ import annotations

from collections import defaultdict

from . import config, elo


def name_map(players) -> dict:
    return {p["id"]: p["name"] for p in players}


# ---------------------------------------------------------------------------
# One-pass per-player aggregates
# ---------------------------------------------------------------------------
def aggregate(players, matches) -> dict:
    """Return ``pid -> aggregate dict`` with counting stats over all matches."""
    agg = {p["id"]: {
        "games": 0, "wins": 0, "losses": 0,
        "n_atk": 0, "n_dfn": 0, "wins_atk": 0, "wins_dfn": 0,
        "goals_for": 0, "goals_against": 0,
        "teammates": defaultdict(lambda: [0, 0]),   # partner -> [games, wins]
        "opponents": defaultdict(lambda: [0, 0]),    # opp -> [games, my wins]
        "results": [],                               # chronological win/loss bools
    } for p in players}

    for m in matches:
        aa, ad = m["team_a_attacker_id"], m["team_a_defender_id"]
        ba, bd = m["team_b_attacker_id"], m["team_b_defender_id"]
        sa, sb = m["score_a"], m["score_b"]
        a_won = sa > sb

        # (player_id, position, teammate, opponents, goals_for, goals_against, won)
        rows = [
            (aa, config.ATTACKER, ad, (ba, bd), sa, sb, a_won),
            (ad, config.DEFENDER, aa, (ba, bd), sa, sb, a_won),
            (ba, config.ATTACKER, bd, (aa, ad), sb, sa, not a_won),
            (bd, config.DEFENDER, ba, (aa, ad), sb, sa, not a_won),
        ]
        for pid, pos, mate, opps, gf, ga, won in rows:
            a = agg.get(pid)
            if a is None:
                continue
            a["games"] += 1
            a["goals_for"] += gf
            a["goals_against"] += ga
            a["results"].append(won)
            if pos == config.ATTACKER:
                a["n_atk"] += 1
                a["wins_atk"] += int(won)
            else:
                a["n_dfn"] += 1
                a["wins_dfn"] += int(won)
            a["wins" if won else "losses"] += 1
            tm = a["teammates"][mate]
            tm[0] += 1
            tm[1] += int(won)
            for opp in opps:
                op = a["opponents"][opp]
                op[0] += 1
                op[1] += int(won)

    # Drop the lambda-backed defaultdicts so the result is picklable
    # (st.cache_data serialises what it stores).
    for a in agg.values():
        a["teammates"] = dict(a["teammates"])
        a["opponents"] = dict(a["opponents"])
    return agg


def _win_pct(wins, games):
    return 100.0 * wins / games if games else 0.0


def _streaks(results):
    """Return (current_streak, longest_win_streak).

    current_streak is +n for n straight wins, -n for n straight losses.
    """
    if not results:
        return 0, 0
    longest = cur = 0
    for won in results:
        cur = cur + 1 if won else 0
        longest = max(longest, cur)
    # current run from the end
    last = results[-1]
    run = 0
    for won in reversed(results):
        if won == last:
            run += 1
        else:
            break
    return (run if last else -run), longest


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
def leaderboard(players, states, agg) -> list:
    rows = []
    for p in players:
        pid = p["id"]
        st = states.get(pid) or elo.PlayerState()
        a = agg.get(pid, {})
        games = a.get("games", 0)
        rows.append({
            "id": pid, "name": p["name"],
            "overall": round(st.overall, 1),
            "attack": round(st.atk, 1),
            "defense": round(st.dfn, 1),
            "games": games,
            "wins": a.get("wins", 0),
            "losses": a.get("losses", 0),
            "win_pct": round(_win_pct(a.get("wins", 0), games), 1),
            "n_atk": st.n_atk, "n_dfn": st.n_dfn,
            "prov_overall": st.is_provisional(),
            "prov_atk": st.is_provisional(config.ATTACKER),
            "prov_dfn": st.is_provisional(config.DEFENDER),
        })
    rows.sort(key=lambda r: r["overall"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ---------------------------------------------------------------------------
# ELO trajectories (for the history chart) — walks history once
# ---------------------------------------------------------------------------
def trajectories(matches, history) -> dict:
    """``pid -> [ {match_id, played_at, atk, dfn, overall}, ... ]`` after each
    match that player took part in. Rebuilt from the replay's post-ratings so
    it never re-derives the maths."""
    cur = defaultdict(lambda: [config.START_RATING, config.START_RATING, 0, 0])
    out = defaultdict(list)
    for m, rec in zip(matches, history):
        for (pid, pos), post in rec["post"].items():
            c = cur[pid]
            if pos == config.ATTACKER:
                c[0] = post
                c[2] += 1
            else:
                c[1] = post
                c[3] += 1
            games = c[2] + c[3]
            overall = (c[0] * c[2] + c[1] * c[3]) / games if games else config.START_RATING
            out[pid].append({
                "match_id": m.get("id"),
                "played_at": m.get("played_at"),
                "atk": round(c[0], 1),
                "dfn": round(c[1], 1),
                "overall": round(overall, 1),
            })
    return dict(out)


# ---------------------------------------------------------------------------
# Player profile
# ---------------------------------------------------------------------------
def player_report(pid, players, states, agg, history_traj) -> dict:
    names = name_map(players)
    st = states.get(pid) or elo.PlayerState()
    a = agg.get(pid, {})
    games = a.get("games", 0)
    cur_streak, longest = _streaks(a.get("results", []))

    def _top(mapping, key, min_games=3, best=True):
        items = [(pid2, gw) for pid2, gw in mapping.items() if gw[0] >= min_games]
        if not items:
            return None
        items.sort(key=lambda kv: key(kv[1]), reverse=best)
        pid2, gw = items[0]
        return {"name": names.get(pid2, "?"), "games": gw[0], "wins": gw[1],
                "win_pct": round(_win_pct(gw[1], gw[0]), 0)}

    teammates = a.get("teammates", {})
    opponents = a.get("opponents", {})
    return {
        "id": pid, "name": names.get(pid, "?"),
        "overall": round(st.overall, 1), "attack": round(st.atk, 1),
        "defense": round(st.dfn, 1),
        "prov_overall": st.is_provisional(),
        "prov_atk": st.is_provisional(config.ATTACKER),
        "prov_dfn": st.is_provisional(config.DEFENDER),
        "games": games, "wins": a.get("wins", 0), "losses": a.get("losses", 0),
        "win_pct": round(_win_pct(a.get("wins", 0), games), 1),
        "n_atk": a.get("n_atk", 0), "n_dfn": a.get("n_dfn", 0),
        "win_pct_atk": round(_win_pct(a.get("wins_atk", 0), a.get("n_atk", 0)), 1),
        "win_pct_dfn": round(_win_pct(a.get("wins_dfn", 0), a.get("n_dfn", 0)), 1),
        "goals_for": a.get("goals_for", 0), "goals_against": a.get("goals_against", 0),
        "avg_gf": round(a.get("goals_for", 0) / games, 2) if games else 0,
        "avg_ga": round(a.get("goals_against", 0) / games, 2) if games else 0,
        "current_streak": cur_streak, "longest_win_streak": longest,
        "best_teammate": _top(teammates, lambda gw: _win_pct(gw[1], gw[0]), best=True),
        "worst_teammate": _top(teammates, lambda gw: _win_pct(gw[1], gw[0]), best=False),
        "favorite_victim": _top(opponents, lambda gw: _win_pct(gw[1], gw[0]), best=True),
        "nemesis": _top(opponents, lambda gw: _win_pct(gw[1], gw[0]), best=False),
        "trajectory": history_traj.get(pid, []),
    }


# ---------------------------------------------------------------------------
# Global / fun stats
# ---------------------------------------------------------------------------
def _describe_match(m, names):
    return {
        "match_id": m.get("id"),
        "played_at": m.get("played_at"),
        "team_a": f"{names.get(m['team_a_attacker_id'], '?')} + {names.get(m['team_a_defender_id'], '?')}",
        "team_b": f"{names.get(m['team_b_attacker_id'], '?')} + {names.get(m['team_b_defender_id'], '?')}",
        "score": f"{m['score_a']}–{m['score_b']}",
        "score_a": m["score_a"], "score_b": m["score_b"],
        "margin": abs(m["score_a"] - m["score_b"]),
        "overtime": m.get("overtime", False),
    }


def global_stats(players, matches, history, top_n=8) -> dict:
    names = name_map(players)

    # Biggest upsets: winner's pre-game expected probability was lowest.
    upsets = []
    for m, rec in zip(matches, history):
        e_a = rec["expected_a"]
        a_won = m["score_a"] > m["score_b"]
        winner_expected = e_a if a_won else (1 - e_a)
        d = _describe_match(m, names)
        d["winner"] = d["team_a"] if a_won else d["team_b"]
        d["win_prob"] = round(100 * winner_expected, 1)
        upsets.append(d)
    upsets.sort(key=lambda d: d["win_prob"])

    blowouts = sorted((_describe_match(m, names) for m in matches),
                      key=lambda d: d["margin"], reverse=True)
    longest = sorted((_describe_match(m, names) for m in matches),
                     key=lambda d: d["score_a"] + d["score_b"], reverse=True)

    # Activity per ISO week.
    per_week = defaultdict(int)
    for m in matches:
        t = m.get("played_at")
        key = t.strftime("%G-W%V") if hasattr(t, "strftime") else str(t)[:10]
        per_week[key] += 1
    activity = [{"week": k, "matches": v} for k, v in sorted(per_week.items())]

    # Giant killers: most wins when your team was the underdog (<40% expected).
    killer = defaultdict(int)
    for m, rec in zip(matches, history):
        e_a = rec["expected_a"]
        a_won = m["score_a"] > m["score_b"]
        winners = ((m["team_a_attacker_id"], m["team_a_defender_id"]) if a_won
                   else (m["team_b_attacker_id"], m["team_b_defender_id"]))
        winner_expected = e_a if a_won else (1 - e_a)
        if winner_expected < 0.40:
            for pid in winners:
                killer[pid] += 1
    giant_killers = sorted(
        ({"name": names.get(pid, "?"), "upset_wins": c} for pid, c in killer.items()),
        key=lambda d: d["upset_wins"], reverse=True)

    return {
        "total_matches": len(matches),
        "biggest_upsets": upsets[:top_n],
        "blowouts": blowouts[:top_n],
        "longest_games": longest[:top_n],
        "activity": activity,
        "giant_killers": giant_killers[:top_n],
    }


def head_to_head(players, matches) -> dict:
    """Wins each player has over each other player (as direct opponents)."""
    names = name_map(players)
    wins = defaultdict(lambda: defaultdict(int))
    for m in matches:
        a = (m["team_a_attacker_id"], m["team_a_defender_id"])
        b = (m["team_b_attacker_id"], m["team_b_defender_id"])
        winners, losers = (a, b) if m["score_a"] > m["score_b"] else (b, a)
        for w in winners:
            for l in losers:
                wins[w][l] += 1
    return {"names": names, "wins": wins}
