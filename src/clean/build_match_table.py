"""
Join football-data matches with Understat xG into one match table.

Join key: (season, home_team, away_team). Validation proved each fixture
occurs exactly once per season, so this key is unique and doesn't depend
on dates matching.

After joining, date and score are compared across sources as a check
that every match was paired correctly.

Output: data/processed/matches_with_xg.csv
"""
from pathlib import Path

import pandas as pd

FD_PATH = Path("data/processed/matches.csv")
US_PATH = Path("data/processed/understat_matches.csv")
OUT_PATH = Path("data/processed/matches_with_xg.csv")

KEY = ["season", "home_team", "away_team"]


def main() -> None:
    fd = pd.read_csv(FD_PATH, parse_dates=["date"])
    us = pd.read_csv(US_PATH, parse_dates=["date"])

    merged = fd.merge(
        us, on=KEY, how="outer",
        suffixes=("", "_us"),          # Understat's duplicate columns get '_us' on the end
        validate="one_to_one",         # crash if the key isn't unique on either side
        indicator=True,                # adds '_merge': which side(s) each row came from
    )

    # Check 1: every match found in both sources
    unmatched = merged[merged["_merge"] != "both"]
    print(f"Matched in both sources: {(merged['_merge'] == 'both').sum():,}")
    print(f"Unmatched:               {len(unmatched)}")
    if len(unmatched):
        print(unmatched[KEY + ["_merge"]].to_string())
        raise SystemExit("Join incomplete: fix before continuing.")

    # Check 2: do the dates agree?
    date_diff = merged[merged["date"] != merged["date_us"]]
    print(f"\nDate disagreements:  {len(date_diff)}")
    if len(date_diff):
        print(date_diff[KEY + ["date", "date_us"]].head(10).to_string())

    # Check 3: do the scores agree?
    goal_diff = merged[(merged["home_goals"] != merged["home_goals_us"]) |
                       (merged["away_goals"] != merged["away_goals_us"])]
    print(f"\nScore disagreements: {len(goal_diff)}")
    if len(goal_diff):
        print(goal_diff[KEY + ["home_goals", "away_goals",
                               "home_goals_us", "away_goals_us"]].to_string())

    # Keep football-data's date and score; drop the duplicates
    out = merged.drop(columns=["_merge", "date_us", "home_goals_us", "away_goals_us"])
    out.to_csv(OUT_PATH, index=False)
    print(f"\nSaved {OUT_PATH}: {len(out):,} rows, {out.shape[1]} columns")


if __name__ == "__main__":
    main()