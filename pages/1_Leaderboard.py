"""Leaderboard — ranked ratings with Overall / Attack / Defense views."""

import pandas as pd
import streamlit as st

from foosball import service, stats

service.page_config("Leaderboard", icon="🏆")
st.title("🏆 Leaderboard")

bundle = service.load()
rows = stats.leaderboard(bundle["players"], bundle["states"], bundle["agg"])

if not rows:
    st.info("No players yet — add some on the **Record a match** page.")
    st.stop()

view = st.radio("Rank by", ["Overall", "Attack", "Defense"],
                horizontal=True, index=0)
rating_key = {"Overall": "overall", "Attack": "attack", "Defense": "defense"}[view]
prov_key = {"Overall": "prov_overall", "Attack": "prov_atk", "Defense": "prov_dfn"}[view]

ranked = sorted(rows, key=lambda r: r[rating_key], reverse=True)

# Top 3 cards.
medals = ["🥇", "🥈", "🥉"]
cols = st.columns(min(3, len(ranked)))
for i, col in enumerate(cols):
    r = ranked[i]
    col.metric(f"{medals[i]} {r['name']}{service.prov_badge(r[prov_key])}",
               f"{r[rating_key]:.0f}", f"{r['win_pct']:.0f}% wins")

st.divider()

df = pd.DataFrame([{
    "#": i + 1,
    "Player": r["name"] + service.prov_badge(r[prov_key]),
    "Rating": r[rating_key],
    "Games": r["games"],
    "W–L": f"{r['wins']}–{r['losses']}",
    "Win %": r["win_pct"],
} for i, r in enumerate(ranked)])

st.dataframe(
    df, hide_index=True, use_container_width=True,
    column_config={
        "Rating": st.column_config.NumberColumn(format="%.0f"),
        "Win %": st.column_config.ProgressColumn(
            format="%.0f%%", min_value=0, max_value=100),
    },
)
st.caption("⏳ = provisional (fewer than 10 games in that role). "
           "Attack / Defense are separate ratings; Overall blends them by "
           "how often you play each position.")
