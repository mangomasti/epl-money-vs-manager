"""
Validate data/processed/matches.csv against rules that MUST be true
for Premier League match data. Prints PASS/FAIL for each check.
"""
from pathlib import Path
import sys

import pandas as pd

MATCHES_PATH = Path("data/processed/matches.csv")
# Rows we've investigated and documented in reports/data_quality_report.md.
# Keyed by (date, home team, away team), NOT match_id — IDs could shift if data changes.
KEY = ["date", "home_team", "away_team"]
KNOWN_ISSUES = {
    ("2021-08-15", "Newcastle", "West Ham"):
        "Source lists 9 away shots on target but only 8 away shots. Cross-check with Understat.",
    ("2023-02-18", "Aston Villa", "Arsenal"):
        "Bet365 margin 16.7% (~8 std devs above mean 4.35%). Kept; odds normalised in analysis.",
}
def run_check(name: str, bad: pd.DataFrame) -> bool:
    """A check passes if every problem row is a documented known issue."""
    known = bad.iloc[0:0]
    if set(KEY).issubset(bad.columns):
        keys = zip(bad["date"].dt.strftime("%Y-%m-%d"), bad["home_team"], bad["away_team"])
        is_known = pd.Series([k in KNOWN_ISSUES for k in keys], index=bad.index, dtype=bool)
        known, bad = bad[is_known], bad[~is_known]

    if len(bad) == 0:
        if len(known) == 0:
            print(f"✅ PASS  {name}")
        else:
            print(f"⚠️  PASS  {name}  ({len(known)} documented exception)")
            for _, row in known.iterrows():
                key = (row["date"].strftime("%Y-%m-%d"), row["home_team"], row["away_team"])
                print(f"        {key[1]} v {key[2]} ({key[0]}): {KNOWN_ISSUES[key]}")
        return True

    print(f"❌ FAIL  {name}  ({len(bad)} problem rows)")
    print(bad.head().to_string(), "\n")
    return False



def main() -> None:
    m = pd.read_csv(MATCHES_PATH, parse_dates=["date"])
    results = []

    # --- Structure: is the season complete? ---
    per_season = m.groupby("season").size()
    results.append(run_check("Every season has 380 matches",
                             per_season[per_season != 380].to_frame("matches")))

    teams = m.groupby("season")["home_team"].nunique()
    results.append(run_check("Every season has 20 teams",
                             teams[teams != 20].to_frame("teams")))

    home = m.groupby(["season", "home_team"]).size()
    results.append(run_check("Every team plays 19 home games per season",
                             home[home != 19].to_frame("home_games")))

    away = m.groupby(["season", "away_team"]).size()
    results.append(run_check("Every team plays 19 away games per season",
                             away[away != 19].to_frame("away_games")))

    # --- Completeness and uniqueness ---
    missing = m.isna().sum()
    results.append(run_check("No missing values",
                             missing[missing > 0].to_frame("missing_count")))

    results.append(run_check("Each fixture appears once per season",
                             m[m.duplicated(["season", "home_team", "away_team"], keep=False)]))

    results.append(run_check("No team plays itself",
                             m[m["home_team"] == m["away_team"]]))

    # --- Logic: do the numbers agree with each other? ---
    expected = pd.Series("D", index=m.index)
    expected[m["home_goals"] > m["away_goals"]] = "H"
    expected[m["home_goals"] < m["away_goals"]] = "A"
    results.append(run_check("Result (H/D/A) matches the score",
                             m[m["result"] != expected]))

    counts = ["home_goals", "away_goals", "home_shots", "away_shots",
              "home_shots_on_target", "away_shots_on_target"]
    results.append(run_check("No negative goals or shots",
                             m[(m[counts] < 0).any(axis=1)]))

    results.append(run_check("Shots on target never exceed total shots",
                             m[(m["home_shots_on_target"] > m["home_shots"]) |
                               (m["away_shots_on_target"] > m["away_shots"])]))

    # --- Dates ---
    start_year = m["season"].str[:4].astype(int)
    window_start = pd.to_datetime(start_year.astype(str) + "-08-01")
    window_end = pd.to_datetime((start_year + 1).astype(str) + "-07-31")
    results.append(run_check("Every date falls inside its season (1 Aug - 31 Jul)",
                             m[(m["date"] < window_start) | (m["date"] > window_end)]))

    team_days = pd.concat([
        m[["date", "home_team"]].rename(columns={"home_team": "team"}),
        m[["date", "away_team"]].rename(columns={"away_team": "team"}),
    ])
    results.append(run_check("No team plays twice on the same day",
                             team_days[team_days.duplicated(keep=False)]))

    # --- Betting odds ---
    odds = m[["odds_home", "odds_draw", "odds_away"]]
    results.append(run_check("All odds are greater than 1.0",
                             m[(odds <= 1).any(axis=1)]))

    margin = (1 / odds).sum(axis=1)
    results.append(run_check("Bookmaker margin is realistic (implied probabilities sum to 1.00-1.15)",
                             m[(margin < 1.0) | (margin > 1.15)]))

    # --- Summary ---
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()