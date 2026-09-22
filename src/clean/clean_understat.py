"""
Clean raw Understat JSON into one tidy match table with xG.

Input:  data/raw/understat/epl_*.json
        data/reference/team_names.csv   (team-name mapping)
Output: data/processed/understat_matches.csv

Rules applied:
  1. Keep only played matches (isResult = True)
  2. Convert text to proper types (ints, floats, dates)
  3. Translate Understat team names to our canonical names
  4. Fail loudly if any team name is missing from the mapping
"""
from pathlib import Path
import json

import pandas as pd

RAW_DIR = Path("data/raw/understat")
TEAMS_PATH = Path("data/reference/team_names.csv")
OUT_PATH = Path("data/processed/understat_matches.csv")


def load_name_map() -> dict:
    """Understat name -> canonical name."""
    teams = pd.read_csv(TEAMS_PATH)
    return dict(zip(teams["understat_name"], teams["team"]))


def clean_season(path: Path, name_map: dict) -> pd.DataFrame:
    year = int(path.stem.split("_")[1])            # 'epl_2014' -> 2014
    raw = json.loads(path.read_text(encoding="utf-8"))
    df = pd.json_normalize(raw["dates"])

    # Rule 1: played matches only
    unplayed = (~df["isResult"]).sum()
    if unplayed:
        print(f"  {path.name}: dropping {unplayed} unplayed match(es)")
    df = df[df["isResult"]]

    # Rules 2 and 3: proper types + canonical names
    out = pd.DataFrame({
        "season": f"{year}/{str(year + 1)[-2:]}",
        "understat_id": df["id"].astype(int),
        "date": pd.to_datetime(df["datetime"]).dt.normalize(),
        "home_team": df["h.title"].map(name_map),
        "away_team": df["a.title"].map(name_map),
        "home_goals": df["goals.h"].astype(int),
        "away_goals": df["goals.a"].astype(int),
        "home_xg": df["xG.h"].astype(float),
        "away_xg": df["xG.a"].astype(float),
    })

    # Rule 4: any name not in the mapping becomes blank -> stop and say which
    unmapped = set(df.loc[out["home_team"].isna(), "h.title"]) | \
               set(df.loc[out["away_team"].isna(), "a.title"])
    if unmapped:
        raise ValueError(f"Add these to {TEAMS_PATH}: {sorted(unmapped)}")

    return out


def main() -> None:
    name_map = load_name_map()
    frames = [clean_season(p, name_map) for p in sorted(RAW_DIR.glob("epl_*.json"))]
    matches = pd.concat(frames, ignore_index=True)
    matches = matches.sort_values(["date", "home_team"]).reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(OUT_PATH, index=False)

    print(f"Saved {OUT_PATH}: {len(matches):,} matches\n")
    print(matches.groupby("season").size().to_string())


if __name__ == "__main__":
    main()