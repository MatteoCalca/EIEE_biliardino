"""Player Profile — one player's ratings, form, splits and history chart."""

import altair as alt
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

if rep["versatile"]:
    st.markdown(":violet[🎭 **All-rounder**] — settled and above 1500 in both attack and defense.")

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
# A static figure (no zoom/pan/tooltips, which fight page scrolling on a
# phone): one point per day = the rating after that day's last match.
SERIES = {"overall": "Overall", "atk": "Attack", "dfn": "Defense"}
hist = pd.DataFrame(rep["trajectory"])
hist["day"] = pd.to_datetime(hist["played_at"]).dt.normalize()
daily = hist.groupby("day", as_index=False)[list(SERIES)].last()

st.subheader("Rating over time")
if len(daily) >= 2:
    first, last = daily["day"].min(), daily["day"].max()
    step = max(1, -(-(last - first).days // 5))   # at most 6 date labels
    ticks = [alt.DateTime(year=d.year, month=d.month, date=d.day)
             for d in pd.date_range(first, last, freq=f"{step}D")]
    fmt = "%-d %b" if first.year == last.year else "%-d %b %y"

    long = daily.melt("day", var_name="rating", value_name="value")
    long["rating"] = long["rating"].map(SERIES)
    chart = alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("day:T", title=None,
                axis=alt.Axis(values=ticks, format=fmt, labelAngle=0,
                              labelOverlap="greedy")),
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
        color=alt.Color("rating:N", title=None,
                        scale=alt.Scale(domain=list(SERIES.values())),
                        legend=alt.Legend(orient="top")),
    ).properties(height=280)
    st.altair_chart(chart, use_container_width=True)
else:
    st.caption("The chart appears once there are matches on two different days.")

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
