"""Stats & Fun — global insights: upsets, blowouts, rivalries, activity."""

import pandas as pd
import streamlit as st

from foosball import service, stats

service.page_config("Stats", icon="📊")
st.title("📊 Stats & Fun")

bundle = service.load()
players, matches, history = bundle["players"], bundle["matches"], bundle["history"]

if not matches:
    st.info("No matches yet — record a few to unlock the stats.")
    st.stop()

g = stats.global_stats(players, matches, history)

c1, c2, c3 = st.columns(3)
c1.metric("Matches", g["total_matches"])
c2.metric("Players", len(players))
c3.metric("Overtime games", sum(1 for m in matches if m.get("overtime")))

# --- activity ---------------------------------------------------------------
st.subheader("📈 Activity")
act = pd.DataFrame(g["activity"])
if not act.empty:
    st.bar_chart(act.set_index("week")["matches"], height=220)

# --- leaderboards of fun ----------------------------------------------------
st.subheader("😱 Biggest upsets")
st.caption("Wins by the least-favoured team (lower % = bigger shock).")
st.dataframe(pd.DataFrame([{
    "Winner": u["winner"], "Score": u["score"],
    "Win chance": u["win_prob"],
} for u in g["biggest_upsets"]]), hide_index=True, use_container_width=True,
    column_config={"Win chance": st.column_config.NumberColumn(format="%.0f%%")})

col1, col2 = st.columns(2)
with col1:
    st.subheader("💥 Blowouts")
    st.dataframe(pd.DataFrame([{
        "Match": f"{b['team_a']} vs {b['team_b']}",
        "Score": b["score"], "Margin": b["margin"],
    } for b in g["blowouts"]]), hide_index=True, use_container_width=True)
with col2:
    st.subheader("⏱️ Longest games")
    st.dataframe(pd.DataFrame([{
        "Match": f"{l['team_a']} vs {l['team_b']}",
        "Score": l["score"], "Points": l["score_a"] + l["score_b"],
    } for l in g["longest_games"]]), hide_index=True, use_container_width=True)

# --- giant killers ----------------------------------------------------------
st.subheader("🗡️ Giant killers")
st.caption("Most wins as the underdog (team given under 40% chance).")
if g["giant_killers"]:
    st.dataframe(pd.DataFrame(g["giant_killers"]).rename(
        columns={"name": "Player", "upset_wins": "Upset wins"}),
        hide_index=True, use_container_width=True)

# --- head to head -----------------------------------------------------------
st.subheader("⚔️ Head-to-head")
st.caption("Rows = wins scored against the column player (as direct opponents).")
h2h = stats.head_to_head(players, matches)
name_by_id = h2h["names"]
order = [p["id"] for p in sorted(players, key=lambda p: p["name"])]
matrix = pd.DataFrame(
    [[h2h["wins"].get(r, {}).get(c, 0) if r != c else None for c in order] for r in order],
    index=[name_by_id[i] for i in order],
    columns=[name_by_id[i] for i in order],
)
st.dataframe(matrix, use_container_width=True)
