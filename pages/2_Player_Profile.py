"""Player Profile — one player's ratings, form, splits and history chart."""

import pandas as pd
import streamlit as st

from foosball import service, stats

service.page_config("Player Profile", icon="👤")
st.title("👤 Player Profile")

bundle = service.load()
players = bundle["players"]
if not players:
    st.info("No players yet — add some on the **Record a match** page.")
    st.stop()

labels, id_of = service.player_options(players, active_only=False)
choice = st.selectbox("Player", labels)
pid = id_of[choice]

rep = stats.player_report(pid, players, bundle["states"], bundle["agg"], bundle["traj"])

if rep["games"] == 0:
    st.info(f"**{rep['name']}** hasn't played any matches yet.")
    st.stop()

# --- headline ratings -------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Overall" + service.prov_badge(rep["prov_overall"]), f"{rep['overall']:.0f}")
c2.metric("⚔️ Attack" + service.prov_badge(rep["prov_atk"]), f"{rep['attack']:.0f}")
c3.metric("🛡️ Defense" + service.prov_badge(rep["prov_dfn"]), f"{rep['defense']:.0f}")

# --- record -----------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Games", rep["games"])
c2.metric("Record", f"{rep['wins']}–{rep['losses']}")
c3.metric("Win rate", f"{rep['win_pct']:.0f}%")

streak = rep["current_streak"]
streak_txt = (f"🔥 {streak} wins" if streak > 0
              else f"❄️ {abs(streak)} losses" if streak < 0 else "—")
c1, c2, c3 = st.columns(3)
c1.metric("Current streak", streak_txt)
c2.metric("Longest win streak", rep["longest_win_streak"])
c3.metric("Goals /game", f"{rep['avg_gf']:.1f} – {rep['avg_ga']:.1f}")

# --- position split ---------------------------------------------------------
st.subheader("By position")
c1, c2 = st.columns(2)
c1.metric(f"⚔️ As attacker ({rep['n_atk']} games)", f"{rep['win_pct_atk']:.0f}% wins")
c2.metric(f"🛡️ As defender ({rep['n_dfn']} games)", f"{rep['win_pct_dfn']:.0f}% wins")

# --- ELO history chart ------------------------------------------------------
traj = rep["trajectory"]
if len(traj) >= 2:
    st.subheader("Rating over time")
    hist = pd.DataFrame(traj)
    hist["game"] = range(1, len(hist) + 1)
    chart = hist.set_index("game")[["overall", "atk", "dfn"]].rename(
        columns={"overall": "Overall", "atk": "Attack", "dfn": "Defense"})
    st.line_chart(chart, height=280)

# --- relationships ----------------------------------------------------------
st.subheader("Chemistry & rivalries")


def _line(label, entry, emoji):
    if entry:
        st.markdown(f"{emoji} **{label}:** {entry['name']} "
                    f"({entry['wins']}/{entry['games']}, {entry['win_pct']:.0f}%)")
    else:
        st.markdown(f"{emoji} **{label}:** _not enough games yet_")


_line("Best teammate", rep["best_teammate"], "🤝")
_line("Toughest teammate", rep["worst_teammate"], "😬")
_line("Favourite victim", rep["favorite_victim"], "🎯")
_line("Nemesis", rep["nemesis"], "😈")
st.caption("Chemistry/rivalry needs ≥3 games together/against to show.")
