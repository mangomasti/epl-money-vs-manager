"""
Clean the raw football-data.co.uk files into ONE tidy match table.

Input:  data/raw/football_data/E0_*.csv   (12 season files)
Output: data/processed/matches.csv        (one row per match)

Rules applied (see reports/data_quality_report.md):
  1. Drop blank rows (no HomeTeam)
  2. Keep only the 13 columns we need, with readable names
  3. Standardise dates to 4-digit years, parse as day/month/year
"""
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw/football_data")
OUT_PATH = Path("data/processed/matches.csv")

# Original column name -> our readable name
KEEP = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "B365H": "odds_home",
    "B365D": "odds_draw",
    "B365A": "odds_away",
}

COUNT_COLUMNS = ["home_goals", "away_goals", "home_shots", "away_shots",
                 "home_shots_on_target", "away_shots_on_target"]


def season_label(code: str) -> str:
    """'1415' -> '2014/15'"""
    return f"20{code[:2]}/{code[2:]}"


def clean_season(path: Path) -> pd.DataFrame:
    """Clean one season's raw file."""
    code = path.stem.split("_")[1]          # 'E0_1415' -> '1415'
    df = pd.read_csv(path)

    # Rule 1: drop blank rows
    df = df.dropna(subset=["HomeTeam"])

    # Rule 2: keep and rename our 13 columns
    df = df[list(KEEP)].rename(columns=KEEP)

    # Rule 3: '16/08/14' -> '16/08/2014', then parse day-first
    four_digit = df["date"].str.replace(r"/(\d{2})$", r"/20\1", regex=True)
    df["date"] = pd.to_datetime(four_digit, format="%d/%m/%Y")

    # Goals and shots are whole numbers
    df[COUNT_COLUMNS] = df[COUNT_COLUMNS].astype("Int64")

    df.insert(0, "season", season_label(code))
    return df


def main() -> None:
    frames = [clean_season(p) for p in sorted(RAW_DIR.glob("E0_*.csv"))]
    matches = pd.concat(frames, ignore_index=True)

    matches = matches.sort_values(["date", "home_team"]).reset_index(drop=True)
    matches.insert(0, "match_id", range(1, len(matches) + 1))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(OUT_PATH, index=False)

    print(f"Saved {OUT_PATH}: {len(matches):,} matches, {matches.shape[1]} columns\n")
    print(matches.groupby("season").size().to_string())


if __name__ == "__main__":
    main()