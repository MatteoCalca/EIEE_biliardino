# ⚽ Foosball Ladder

A tiny, phone-friendly web app for recording 2v2 foosball (biliardino) results among colleagues and keeping a continuously-updated **individual** ELO rating for everyone — with separate **attack** and **defense** ratings, margin-of-victory weighting, rich stats, and a team-balancer.

Built with **Python + Streamlit**, stored in **Supabase (Postgres)**, hosted free on **Streamlit Community Cloud**.

## What it does

- **Record a match** from your phone in seconds: pick 4 players, tap positions, enter the score, save. No login required.
- **Individual ELO** that accounts for your teammate, your opponents and the position you played — because foosball has no fixed teams and people are often much better at attack than defense (or vice-versa).
- **Leaderboard** with Overall / Attack / Defense views.
- **Player profiles**: win rate, position splits, goals, streaks, a rating-over-time chart, best teammate, nemesis.
- **Team balancer**: pick 4 people, get the fairest split and who should play front/back.
- **Match history** with one-tap undo (ratings recompute automatically).
- **Stats & fun**: biggest upsets, blowouts, longest games, giant-killers, activity, head-to-head matrix.

## How the rating works

Every player has two ratings — **attack** and **defense** — both starting at 1500. Only the rating for the position you actually played is used to predict the game and gets updated. A team's strength is its attacker's attack rating blended with its defender's defense rating. Your headline **Overall** number is an experience-weighted blend of your two ratings.

Winning matters, but **winning big matters more**: the rating change is scaled by a margin-of-victory multiplier (FiveThirtyeight-style), with a damper so a strong favourite can't farm points by running up the score. A 10–3 moves ratings about twice as much as a 10–8.

**Overtime is handled for free.** Because you always win overtime by exactly 2, an 18–16 nail-biter counts as the *gentlest* possible win (margin 2), just like an 11–9 — you simply record the two final scores and the maths does the rest. No special cases.

New players carry a higher K-factor (faster movement) for their first 10 games in a role, shown with a ⏳ badge, then settle to a stable K. All constants live in `foosball/config.py`.

Ratings are **never stored** — the match log is the single source of truth, and every rating is recomputed by replaying the log in order. That makes undo/edit trivially correct.

## Run it locally

Requires **Python 3.9+** (Streamlit needs it). With no configuration it uses a local SQLite file, so you can try it immediately:

```bash
pip install -r requirements.txt
python seed.py            # optional: 12 fake players + 200 demo matches
streamlit run app.py
```

Open the URL it prints (default http://localhost:8501). To point local dev at Supabase instead, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in your connection URL.

## Deploy it (free)

**1. Create the database (Supabase).** Sign up at supabase.com, create a project, then either run `schema.sql` in the SQL editor or just let the app create its tables on first connect. Copy the connection string from *Project Settings → Database → Connection string → Session pooler* (URI form).

**2. Push to GitHub.** Commit this repository to your GitHub account.

**3. Deploy on Streamlit Cloud.** At share.streamlit.io, click *New app*, choose this repo, set the main file to `app.py` and Python to 3.11. In *Advanced settings → Secrets*, paste:

```toml
[db]
url = "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"
```

Deploy, then share the URL with your colleagues. Every `git push` auto-redeploys.

## Project structure

```
app.py                     Record-a-match home page
pages/                     Leaderboard, Player Profile, Balance Teams, History, Stats
foosball/config.py         Tunable constants (start rating, K-factors, MoV)
foosball/elo.py            Pure rating engine (replay) — no dependencies
foosball/db.py             Storage (Supabase Postgres / SQLite fallback)
foosball/stats.py          Derived statistics
foosball/service.py        Streamlit glue: secrets bridge + cached loading
tests/test_elo.py          Engine unit tests
schema.sql                 Postgres schema (optional; app auto-creates tables)
seed.py                    Generate demo data locally
```

## Tests

```bash
python tests/test_elo.py          # standalone, no pytest needed
# or, if you have pytest:
pytest tests/
```

## Tuning

Edit `foosball/config.py`: `START_RATING`, `K_BASE` / `K_PROV` / `PROV_GAMES` (how fast ratings move and when they "settle"), and the margin-of-victory constants. Because ratings are recomputed from the log on every load, changing a constant re-rates all history automatically.
