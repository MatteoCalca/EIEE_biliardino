"""Balance Teams — pick 4 players, get the fairest 2v2 split + positions."""

import streamlit as st

from foosball import elo, service

service.page_config("Balance Teams", icon="⚖️")
st.title("⚖️ Balance Teams")
st.caption("Pick 4 players; we try every pairing and position and pick the "
           "matchup closest to a coin flip, using each player's attack and "
           "defense ratings.")

bundle = service.load()
players = bundle["players"]
states = bundle["states"]

labels, id_of = service.player_options(players, active_only=False)
if len(labels) < 4:
    st.info("Need at least 4 players. Add some on the **Record a match** page.")
    st.stop()

picked = st.multiselect("Who's playing? (choose exactly 4)", labels, max_selections=4)
if len(picked) != 4:
    st.info(f"Select 4 players — {len(picked)} chosen.")
    st.stop()


def rating(pid, pos):
    st_ = states.get(pid) or elo.PlayerState()
    return st_.rating(pos)


ids = [id_of[name] for name in picked]
name_of = {id_of[name]: name for name in picked}

# 3 ways to split 4 players into two pairs.
splits = [((ids[0], ids[1]), (ids[2], ids[3])),
          ((ids[0], ids[2]), (ids[1], ids[3])),
          ((ids[0], ids[3]), (ids[1], ids[2]))]

configs = []
for pair_a, pair_b in splits:
    for att_a, def_a in (pair_a, pair_a[::-1]):
        for att_b, def_b in (pair_b, pair_b[::-1]):
            r_a = elo.team_rating(rating(att_a, elo.config.ATTACKER),
                                  rating(def_a, elo.config.DEFENDER))
            r_b = elo.team_rating(rating(att_b, elo.config.ATTACKER),
                                  rating(def_b, elo.config.DEFENDER))
            p_a = elo.expected_score(r_a, r_b)
            configs.append({
                "att_a": att_a, "def_a": def_a, "att_b": att_b, "def_b": def_b,
                "r_a": r_a, "r_b": r_b, "p_a": p_a, "fairness": abs(p_a - 0.5),
            })

configs.sort(key=lambda c: c["fairness"])
best = configs[0]


def team_line(att, dfn):
    return f"⚔️ **{name_of[att]}**  +  🛡️ **{name_of[dfn]}**"


st.subheader("Fairest matchup")
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### 🔵 Team A")
    st.markdown(team_line(best["att_a"], best["def_a"]))
    st.metric("Team rating", f"{best['r_a']:.0f}", f"{best['p_a']*100:.0f}% to win")
with c2:
    st.markdown("#### 🔴 Team B")
    st.markdown(team_line(best["att_b"], best["def_b"]))
    st.metric("Team rating", f"{best['r_b']:.0f}", f"{(1-best['p_a'])*100:.0f}% to win")

gap = abs(best["p_a"] - 0.5) * 200  # percentage points from 50/50
st.progress(min(1.0, best["p_a"]),
            text=f"Predicted balance: {best['p_a']*100:.0f}% / {(1-best['p_a'])*100:.0f}%")
if gap < 6:
    st.success("Beautifully balanced. 🎯")
elif gap < 16:
    st.info("Reasonably balanced.")
else:
    st.warning("Best available split is still a bit lopsided.")

with st.expander("See all pairings"):
    for c in configs:
        st.markdown(
            f"- {name_of[c['att_a']]}/{name_of[c['def_a']]} "
            f"**{c['p_a']*100:.0f}% – {(1-c['p_a'])*100:.0f}%** "
            f"{name_of[c['att_b']]}/{name_of[c['def_b']]}")
