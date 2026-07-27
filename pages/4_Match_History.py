"""Match History — browse recent results and undo mistakes.

Undo is a soft-delete (``voided``): the row stays but is skipped by the ELO
replay, so every rating recomputes as if the match never happened. Restore
puts it back the same way.
"""

import streamlit as st

from foosball import db, service, stats

service.page_config("Match History", icon="📜")
st.title("📜 Match History")

eng = service.engine()
players = db.get_players(eng)
names = stats.name_map(players)

show_voided = st.toggle("Show undone matches", value=False)
limit = st.slider("How many to show", 10, 100, 30, step=10)

all_matches = db.get_matches(eng, include_voided=True)
all_matches.sort(key=lambda m: (m["played_at"], m["id"]), reverse=True)
matches = [m for m in all_matches if show_voided or not m["voided"]][:limit]

if not matches:
    st.info("No matches recorded yet.")
    st.stop()


def team(att_id, def_id):
    return f"{names.get(att_id, '?')} + {names.get(def_id, '?')}"


for m in matches:
    a_won = m["score_a"] > m["score_b"]
    a = team(m["team_a_attacker_id"], m["team_a_defender_id"])
    b = team(m["team_b_attacker_id"], m["team_b_defender_id"])
    a_txt = f"**{a}**" if a_won else a
    b_txt = f"**{b}**" if not a_won else b
    ot = " · OT" if m["overtime"] else ""
    when = m["played_at"].strftime("%d %b %H:%M") if hasattr(m["played_at"], "strftime") else ""

    row, action = st.columns([5, 1])
    with row:
        strike_open, strike_close = ("~~", "~~") if m["voided"] else ("", "")
        st.markdown(f"{strike_open}🔵 {a_txt}  &nbsp;`{m['score_a']}–{m['score_b']}`  "
                    f"{b_txt} 🔴{strike_close}")
        st.caption(f"{when}{ot}" + ("  · undone" if m["voided"] else ""))
    with action:
        if m["voided"]:
            if st.button("↩︎", key=f"restore_{m['id']}", help="Restore"):
                db.void_match(eng, m["id"], voided=False)
                st.rerun()
        else:
            if st.button("🗑️", key=f"void_{m['id']}", help="Undo this match"):
                db.void_match(eng, m["id"], voided=True)
                st.rerun()
    st.divider()
