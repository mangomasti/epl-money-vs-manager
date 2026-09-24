"""
Arsenal case study: does Arsenal fit the league-wide findings?

1. Season by season: points, xG difference, summer spending, new manager, and
   what the league-wide model (Q2/Q3 model 3) EXPECTED vs. what actually happened.
2. The Emery -> Ljungberg change in the manager-bounce event study (Q1).
3. Chart: rolling 10-match form with manager eras, plus summer spending by season.

Outputs: reports/results/arsenal_seasons.csv
         reports/figures/arsenal_case_study.png
"""
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from spending_effect import build_club_seasons, fit     # reuse the Q2 data and model

DB_PATH = Path("data/epl.db")
RESULTS = Path("reports/results")
FIGURES = Path("reports/figures")

TEAM = "Arsenal"
ROLLING = 10
MODEL = "d_points ~ points_prev + xgd_prev + spend_rel + new_manager"

MATCHES_SQL = """
SELECT tms.date, tms.season, tms.points,
       tms.xg_for - tms.xg_against AS xgd,
       m.name AS manager
FROM team_match_spells AS tms
JOIN teams AS t    ON t.team_id = tms.team_id
JOIN managers AS m ON m.manager_id = tms.head_coach_id
WHERE t.name = ?
ORDER BY tms.date
"""


def season_table(con, matches: pd.DataFrame) -> pd.DataFrame:
    league = build_club_seasons(con)
    model, _ = fit(MODEL, league, "case study")
    league["expected_d_points"] = model.predict(league)
    league["beat_model_by"] = league["d_points"] - league["expected_d_points"]

    managers = matches.groupby("season")["manager"].agg(lambda s: " -> ".join(dict.fromkeys(s)))
    ars = league[league["team"] == TEAM].copy()
    ars["managers"] = ars["season"].map(managers)
    ars["spend_eur_m"] = (ars["spend_eur"] / 1e6).round(0)
    return ars[["season", "managers", "points", "d_points", "expected_d_points", "beat_model_by",
                "xgd_pg", "spend_eur_m", "spend_rel", "new_manager"]].round(2)


def plot(matches: pd.DataFrame, seasons: pd.DataFrame) -> Path:
    matches = matches.assign(rolling_ppg=matches["points"].rolling(ROLLING).mean())
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]})

    # Top: rolling form, with each manager's era shaded
    ax1.plot(matches["date"], matches["rolling_ppg"], color="#DB0007", linewidth=2)
    ax1.set_ylim(0, 3)
    era_id = (matches["manager"] != matches["manager"].shift()).cumsum()
    eras = matches.groupby(era_id).agg(manager=("manager", "first"),
                                       start=("date", "min"), end=("date", "max"))
    for i, era in enumerate(eras.itertuples()):
        ax1.axvspan(era.start, era.end, color="grey", alpha=0.18 if i % 2 == 0 else 0.06)
        short_era = (era.end - era.start).days < 60
        ax1.text(era.start, 0.1 if short_era else 2.9, era.manager.split()[-1],
                    rotation=90, va="bottom" if short_era else "top", fontsize=9)
    ax1.set_ylabel(f"Points per game\n(rolling {ROLLING} matches)")
    ax1.set_title("Arsenal 2014/15–2025/26: form by manager, and summer spending")

    # Bottom: summer spending each season
    ax2.bar(seasons["season"], seasons["spend_eur_m"], color="#023474")
    ax2.set_ylabel("Summer spend (EUR m)")
    ax2.tick_params(axis="x", rotation=45)

    fig.tight_layout()
    path = FIGURES / "arsenal_case_study.png"
    fig.savefig(path, dpi=150)
    return path


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    matches = pd.read_sql(MATCHES_SQL, con, params=(TEAM,), parse_dates=["date"])
    seasons = season_table(con, matches)
    con.close()

    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(f"{TEAM}: season by season (vs. the league-wide model)\n")
        print(seasons.to_string(index=False), "\n")

        events = pd.read_csv(RESULTS / "bounce_events.csv")
        print(f"{TEAM} in the manager-bounce event study:")
        print(events[events["team"] == TEAM].round(2).to_string(index=False), "\n")

    seasons.to_csv(RESULTS / "arsenal_seasons.csv", index=False)
    chart = plot(matches, seasons)
    print(f"Saved {RESULTS / 'arsenal_seasons.csv'} and {chart}")


if __name__ == "__main__":
    main()