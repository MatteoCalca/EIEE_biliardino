"""Foosball Ladder — home page: record a match.

The most important screen, tuned for one-handed phone use: pick four players,
tap positions, enter the score, submit. Everything else lives in the pages/
folder (auto-listed in the sidebar).
"""

import pandas as pd
import streamlit as st

from foosball import db, service, stats
from foosball.config import ATTACKER, DEFENDER

service.page_config("Record a match")

st.title("⚽ Foosball Ladder")
st.caption("Record a 2v2 result — ratings update automatically.")

bundle = service.load()
players = bundle["players"]
eng = service.engine()

# --- add-player convenience -------------------------------------------------
with st.expander("➕ Add a new player"):
    with st.form("add_player", clear_on_submit=True):
        new_name = st.text_input("Name", placeholder="e.g. Giulia")
        if st.form_submit_button("Add player", use_container_width=True):
            try:
                db.add_player(eng, new_name)
                st.success(f"Added {new_name.strip()}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

labels, id_of = service.player_options(players)

if len(labels) < 4:
    st.info("Add at least **4 players** (above) to record a match. "
            f"Currently {len(labels)}.")
    st.stop()


def _sel(label, key, default_idx):
    return st.selectbox(label, labels, index=min(default_idx, len(labels) - 1), key=key)


# --- match entry form -------------------------------------------------------
with st.form("record_match"):
    st.subheader("🔵 Team A")
    a1, a2 = st.columns(2)
    with a1:
        a_att = _sel("⚔️ Attacker (front)", "a_att", 0)
    with a2:
        a_def = _sel("🛡️ Defender (back)", "a_def", 1)

    st.subheader("🔴 Team B")
    b1, b2 = st.columns(2)
    with b1:
        b_att = _sel("⚔️ Attacker (front)", "b_att", 2)
    with b2:
        b_def = _sel("🛡️ Defender (back)", "b_def", 3)

    st.subheader("🥅 Score")
    s1, s2 = st.columns(2)
    with s1:
        score_a = st.number_input("Team A", min_value=0, max_value=50, value=10, step=1)
    with s2:
        score_b = st.number_input("Team B", min_value=0, max_value=50, value=8, step=1)

    submitted = st.form_submit_button("✅ Save result", use_container_width=True, type="primary")

if submitted:
    try:
        new_id = db.add_match(
            eng,
            id_of[a_att], id_of[a_def], id_of[b_att], id_of[b_def],
            int(score_a), int(score_b),
        )
    except ValueError as exc:
        st.error(f"⚠️ {exc}")
    else:
        fresh = service.load()
        names = stats.name_map(fresh["players"])
        rec = next((r for r in fresh["history"] if r["match_id"] == new_id), None)
        winner = "Team A" if score_a > score_b else "Team B"
        st.success(f"Saved! **{winner}** won {int(score_a)}–{int(score_b)}.")
        st.balloons()
        if rec:
            pos_label = {ATTACKER: "attack", DEFENDER: "defense"}
            rows = [{
                "Player": names.get(pid, "?"),
                "Rating": pos_label[pos],
                "Change": f"{d:+.1f}",
                "New": f"{rec['post'][(pid, pos)]:.0f}",
            } for (pid, pos), d in rec["deltas"].items()]
            st.markdown("**Rating changes**")
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# --- footer quick stats -----------------------------------------------------
st.divider()
c1, c2 = st.columns(2)
c1.metric("Players", len(players))
c2.metric("Matches recorded", len(bundle["matches"]))
st.caption("⏳ = provisional rating (still settling). See the sidebar for the "
           "leaderboard, profiles, team balancer and stats.")
