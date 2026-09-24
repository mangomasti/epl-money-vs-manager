"""
Export flat, Tableau-ready CSVs to data/tableau/.

Tableau works best with simple tables: one row per thing, readable names
instead of IDs, and categories spelled out ("Home"/"Away", "Yes"/"No").
"""
from pathlib import Path
import shutil
import sqlite3
import sys

import pandas as pd

sys.path.append("src/analysis")                          # so we can import the Q2 model code
from spending_effect import build_club_seasons, fit      # noqa: E402

DB_PATH = Path("data/epl.db")
RESULTS = Path("reports/results")
OUT = Path("data/tableau")
MODEL = "d_points ~ points_prev + xgd_prev + spend_rel + new_manager"

TEAM_MATCHES_SQL = """
SELECT tms.season, tms.date,
       t.name AS team, o.name AS opponent,
       CASE tms.is_home WHEN 1 THEN 'Home' ELSE 'Away' END AS venue,
       tms.goals_for, tms.goals_against, tms.points,
       ROUND(tms.xg_for, 2) AS xg_for, ROUND(tms.xg_against, 2) AS xg_against,
       m.name AS head_coach,
       COALESCE(s.appointment_type, 'first spell in data') AS appointment_type
FROM team_match_spells AS tms
JOIN teams AS t    ON t.team_id = tms.team_id
JOIN teams AS o    ON o.team_id = tms.opponent_id
JOIN managers AS m ON m.manager_id = tms.head_coach_id
JOIN spells AS s   ON s.spell_id = tms.spell_id
ORDER BY t.name, tms.date
"""

SPELLS_SQL = """
SELECT t.name AS team, m.name AS manager, s.spell_no,
       s.start_date, s.end_date, s.matches,
       ROUND(AVG(tms.points), 2)                    AS ppg,
       ROUND(AVG(tms.xg_for - tms.xg_against), 2)   AS xgd_per_game,
       COALESCE(s.appointment_type, 'first spell in data') AS appointment_type,
       s.change_timing, s.prev_departure, s.position_at_vacancy
FROM spells AS s
JOIN teams AS t    ON t.team_id = s.team_id
JOIN managers AS m ON m.manager_id = s.manager_id
JOIN team_match_spells AS tms ON tms.spell_id = s.spell_id
GROUP BY s.spell_id
ORDER BY t.name, s.spell_no
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)

    # 1. One row per team per match, with rolling form
    tm = pd.read_sql(TEAM_MATCHES_SQL, con)
    tm["rolling_ppg_10"] = (tm.groupby("team")["points"]
                              .transform(lambda s: s.rolling(10).mean()).round(2))

    # 2. One row per managerial spell
    spells = pd.read_sql(SPELLS_SQL, con)

    # 3. One row per club-season, with the model's expectation
    cs = build_club_seasons(con)
    baseline, _ = fit("d_points ~ points_prev + xgd_prev", cs, "baseline")
    cs["d_points_adjusted"] = (cs["d_points"] - baseline.predict(cs)).round(1)    
    model, _ = fit(MODEL, cs, "tableau")
    cs["expected_d_points"] = model.predict(cs).round(1)
    cs["beat_model_by"] = (cs["d_points"] - cs["expected_d_points"]).round(1)
    cs["spend_eur_m"] = (cs["spend_eur"] / 1e6).round(1)
    cs["new_manager"] = cs["new_manager"].map({1: "Yes", 0: "No"})
    cs = cs[["season", "team", "points", "points_prev", "d_points", "d_points_adjusted",
             "expected_d_points", "beat_model_by", "spend_eur_m", "spend_rel", "signings",
             "paid_signings", "new_manager", "xgd_pg"]].round({"spend_rel": 2, "xgd_pg": 2})
    
    con.close()

    outputs = {"team_matches.csv": tm, "manager_spells.csv": spells, "club_seasons.csv": cs}
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False)
        print(f"Saved {OUT / name}: {len(df):,} rows")

    # 4. The event study (already in Tableau-friendly shape)
    for name in ["bounce_events.csv", "bounce_paths.csv"]:
        shutil.copy(RESULTS / name, OUT / name)
        print(f"Copied {OUT / name}")


if __name__ == "__main__":
    main()