"""Methodology — how the ratings work, in plain words and in formulas.

Every number on this page is computed from ``config`` and the ``elo``
functions at render time, so it always matches the live engine.
"""

import pandas as pd
import streamlit as st

from foosball import config, elo, service, stats
from foosball.config import ATTACKER, DEFENDER

service.page_config("Methodology", icon="📖")
st.title("📖 Methodology")

S0, SCALE = config.START_RATING, config.SCALE
K_B, K_P, N_PROV = config.K_BASE, config.K_PROV, config.PROV_GAMES
FLOOR = config.REL_FLOOR
DAMP, COEF = config.MOV_DAMP, config.MOV_DIFF_COEF

# Handy reference numbers, straight from the engine.
BLOWOUT_VS_CLOSE = elo.mov_multiplier(8, 0, 0) / elo.mov_multiplier(2, 0, 0)  # 10-2 vs 10-8
TYPICAL = stats.TYPICAL_SWING  # even teams, 10-7: M * (S - E)

plain, maths = st.tabs(["💡 In plain words", "🧮 The maths"])

# ---------------------------------------------------------------------------
with plain:
    st.markdown(f"""
**Before every game, the app makes a prediction.** From the four players'
ratings it works out each team's chance of winning. After the game, ratings
move by how much the result *surprised* that prediction:

- beat a stronger team → big gain; beat a weaker team → small gain;
- lose to a weaker team → big loss; lose to a stronger team → small loss.

**Winning big counts more than scraping by.** A 10–2 moves ratings about
{BLOWOUT_VS_CLOSE:.0f}× as much as a 10–8. But a heavy favourite can't farm
points by running up the score: the margin bonus shrinks when the win was
expected. Overtime (say 18–16) is always won by 2, so it counts as the
narrowest possible win.

**You have two ratings: ⚔️ attack and 🛡️ defense.** Both start at {S0:.0f}.
A game only uses — and only updates — the rating for the position you actually
played. Your **Overall** rating blends the two, weighted by how often you play
each role.

**Your teammate matters.** The prediction uses both players on each team, so
winning with a weaker partner against strong opponents earns a lot. Both
teammates share the same surprise and margin; only their *speed* (next point)
can differ.

**New ratings move fast, settled ones move steadily.** A brand-new rating is
just a guess, so it moves at {K_P / K_B:g}× the normal speed and slows down
gradually over your first {N_PROV} games *in that role* (⏳ while settling).

**Games against newcomers count less for settled players.** Nobody knows yet
how good a newcomer is, so beating (or losing to) them says little about you:
settled players move less in those games. The newcomer still moves at full
speed — theirs is the rating that needs to find its level.

**Nothing is stored — everything is replayed.** Ratings are recomputed from
the full match log, in order, every time. Undoing a match re-rates all later
games exactly as if it had never been played.

**Badges:** ⏳ = fewer than {N_PROV} games in that role. 🎭 = all-rounder:
settled in both roles and at or above {S0:.0f} in both.
""")

# ---------------------------------------------------------------------------
with maths:
    st.subheader("1 · Team strength")
    st.latex(r"R_{\text{team}} = \tfrac{1}{2}\left(R^{\text{attack}}_{\text{attacker}}"
             r" + R^{\text{defense}}_{\text{defender}}\right)")

    st.subheader("2 · Win probability")
    st.latex(rf"E_A = \frac{{1}}{{1 + 10^{{(R_B - R_A)/{SCALE:g}}}}}, \qquad E_B = 1 - E_A")
    gaps = [0, 50, 100, 200, 300, 400]
    st.dataframe(pd.DataFrame({
        "Rating gap": [f"+{g}" if g else "0" for g in gaps],
        "Stronger team wins": [f"{elo.expected_score(g, 0):.0%}" for g in gaps],
    }), hide_index=True, use_container_width=True)

    st.subheader("3 · Rating update")
    st.latex(r"\Delta_i = K_i \cdot M \cdot (S - E)")
    st.markdown(f"""
- $S$ = 1 for a win, 0 for a loss; $E$ = your team's win probability, so
  $S - E$ is the **surprise** (small for an expected win, large for an upset).
- $M$ = **margin factor** (section 4), $K_i$ = your **speed** (section 5).
- $S - E$ and $M$ are the same for both teammates; only $K_i$ differs.

For scale: a *typical game* (evenly matched, 10–7) moves a settled player by
$\\pm${K_B * TYPICAL:.0f} points. After saving a match, the home page shows
“speed ×…” as $K_i / {K_B:g}$.
""")

    st.subheader("4 · Margin factor")
    st.latex(rf"M = \ln(m + 1) \cdot \frac{{{DAMP:g}}}{{{COEF:g}\,(R_W - R_L) + {DAMP:g}}}")
    st.markdown(f"""
$m$ = goal difference; $R_W - R_L$ = winning team's pre-game rating minus the
losing team's. The log rewards big wins with diminishing returns; the fraction
shrinks $M$ when a favourite wins ($R_W > R_L$) and grows it for an underdog
(denominator floored at {config.MOV_DENOM_FLOOR:g}).
""")
    margins = [2, 3, 4, 5, 6, 8, 10]
    st.dataframe(pd.DataFrame({
        "Margin": margins,
        "Even teams": [round(elo.mov_multiplier(m, 0, 0), 2) for m in margins],
        "Favourite (+200) wins": [round(elo.mov_multiplier(m, 200, 0), 2) for m in margins],
        "Underdog (−200) wins": [round(elo.mov_multiplier(m, 0, 200), 2) for m in margins],
    }), hide_index=True, use_container_width=True)

    st.subheader("5 · Speed")
    st.latex(rf"r = \min\!\left(1, \frac{{n}}{{{N_PROV}}}\right) \qquad "
             rf"K_{{\text{{own}}}} = {K_B:g} + ({K_P:g} - {K_B:g})(1 - r)")
    st.latex(rf"a = \max\!\left(1 - r,\ \bar r_{{\text{{opp}}}},\ {FLOOR:g}\right) \qquad "
             r"K_i = K_{\text{own}} \cdot a")
    st.markdown(f"""
$n$ = games you had already played **in this role**; $r$ = how reliable your
rating is (0 = brand new, 1 = settled); $\\bar r_{{\\text{{opp}}}}$ = average
reliability of your two opponents. You move at full $K_{{\\text{{own}}}}$ if
*you* are still new or your opponents are well known; only a settled player
facing unknowns is damped, and never below {FLOOR:.0%}.
""")
    cases = [(0, 0), (0, N_PROV), (N_PROV // 2, N_PROV), (N_PROV // 2, 0),
             (N_PROV, N_PROV), (N_PROV, N_PROV // 2), (N_PROV, 0)]
    rows = []
    for n_own, n_opp in cases:
        k = elo.step_size(elo.reliability(n_own), elo.reliability(n_opp))
        rows.append({"Your games in role": n_own, "Opponents' games": n_opp,
                     "K": round(k, 1), "Speed": f"×{k / K_B:.2f}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.subheader("6 · Worked example")
    # Team A: two settled players. Team B: a newcomer in attack + a settled
    # defender. Team B (the underdogs) wins 10-6.
    ex = [  # (name, position, rating, games already played in that role)
        ("Anna", ATTACKER, 1600.0, 20), ("Bruno", DEFENDER, 1500.0, 15),
        ("Carla", ATTACKER, 1450.0, 2), ("Dario", DEFENDER, 1500.0, 12),
    ]
    score_a, score_b = 6, 10
    rel = [elo.reliability(n) for *_, n in ex]
    r_a, r_b = elo.team_rating(ex[0][2], ex[1][2]), elo.team_rating(ex[2][2], ex[3][2])
    e_a = elo.expected_score(r_a, r_b)
    result_a = 1.0 if score_a > score_b else 0.0
    winner_r, loser_r = (r_a, r_b) if result_a else (r_b, r_a)
    mult = elo.mov_multiplier(abs(score_a - score_b), winner_r, loser_r)
    opp_rel = [(rel[2] + rel[3]) / 2] * 2 + [(rel[0] + rel[1]) / 2] * 2
    surprise = [result_a - e_a] * 2 + [(1 - result_a) - (1 - e_a)] * 2
    steps = [elo.step_size(rel[i], opp_rel[i]) for i in range(4)]
    deltas = [steps[i] * mult * surprise[i] for i in range(4)]

    st.markdown(f"""
Team A = Anna (⚔️ {ex[0][2]:.0f}) + Bruno (🛡️ {ex[1][2]:.0f}) → $R_A$ = {r_a:.0f}.
Team B = Carla (⚔️ {ex[2][2]:.0f}, only {ex[2][3]} attack games) + Dario
(🛡️ {ex[3][2]:.0f}) → $R_B$ = {r_b:.0f}. So $E_A$ = {e_a:.0%}, $E_B$ = {1 - e_a:.0%}.
Team B wins **{score_a}–{score_b}**: margin {abs(score_a - score_b)}, an
underdog win, so $M$ = {mult:.2f}.
""")
    st.dataframe(pd.DataFrame([{
        "Player": name, "Games in role": n,
        "K": round(steps[i], 1), "M": round(mult, 2),
        "S − E": round(surprise[i], 3), "Δ": f"{deltas[i]:+.1f}",
    } for i, (name, _, _, n) in enumerate(ex)]), hide_index=True, use_container_width=True)
    st.markdown(f"""
Anna and Bruno are settled, but half of their opposition (Carla) is unknown,
so their speed is damped to ×{steps[0] / K_B:.2f}. Carla is new, so she moves
fast (×{steps[2] / K_B:.2f}). Dario is settled and faced two settled
opponents: normal speed. What the home page would show after saving it:
""")
    rec = {
        "result_a": result_a, "expected_a": e_a, "mov_multiplier": mult,
        "margin": abs(score_a - score_b),
        "deltas": {(name, pos): deltas[i] for i, (name, pos, _, _) in enumerate(ex)},
        "post": {(name, pos): r + deltas[i] for i, (name, pos, r, _) in enumerate(ex)},
        "step": {(name, pos): steps[i] for i, (name, pos, _, _) in enumerate(ex)},
        "role_games": {(name, pos): n for name, pos, _, n in ex},
    }
    with st.container(border=True):
        st.markdown(service.rating_changes_md(rec, {name: name for name, *_ in ex}))

    st.subheader("7 · Overall rating and conservation")
    st.latex(r"\text{Overall} = \frac{n_{\text{att}}\,R^{\text{attack}}"
             r" + n_{\text{def}}\,R^{\text{defense}}}{n_{\text{att}} + n_{\text{def}}}")
    st.markdown("""
When all four players move at the same speed, the winners gain exactly what
the losers lose. When speeds differ (newcomers, damping) the total is not
conserved — by design: the newcomer's rating absorbs most of the correction,
instead of shifting points around among settled players.
""")

    st.subheader("🤔 Why these choices")
    with st.expander("Why do new ratings move faster, and for how long?"):
        st.markdown(f"""
A new rating starts at {S0:.0f} whatever your real level, so it is probably
wrong: big steps get it to the right place quickly. Once it is close, big steps
only add noise. In a typical game (evenly matched, 10–7) a settled player
moves ±{K_B * TYPICAL:.0f} points; at newcomer speed it would be
±{K_P * TYPICAL:.0f}, so a couple of lucky games would swing you by
{2 * K_P * TYPICAL:.0f} points and the leaderboard would reshuffle after almost
every game.
Hence speed ramps down linearly from {K_P:g} to {K_B:g} over the first
{N_PROV} games in each role.

We checked this with simulated 14-player offices (known true skills, games
played goal by goal to 10), comparing the 48 → 24 ramp with the two obvious
alternatives:

- **48 forever**: settled ratings jitter twice as much per game, predict later
  games worse, and rank players less accurately.
- **24 from day one**: a newcomer joining an established group is still about
  15% further from their true level after 10 games.
""")
    with st.expander("Why are settled players damped against newcomers?"):
        st.markdown(f"""
A newcomer's {S0:.0f} is a placeholder, so the pre-game prediction — and
therefore the surprise — is unreliable. A settled player's step is scaled by
how well known the opponents are, but never below {FLOOR:.0%}, so a genuine
upset still counts. The newcomer is not damped: theirs is the rating that
needs to move.
""")
    with st.expander("Why ln(margin + 1), and why the favourite damper?"):
        st.markdown("""
The margin carries information (10–1 says more than 10–9) but with diminishing
returns: going from a 2- to a 4-goal win means more than from 8 to 10. The log
captures that. Favourites win big more often anyway, so without the damper a
strong team could farm points by running up the score against weak ones; the
formula (from FiveThirtyEight's NFL Elo) shrinks the bonus for expected
blowouts and boosts it for underdog ones.
""")
