"""
Clean Transfermarkt transfers into a table of moves INTO Premier League clubs.

Input:  data/raw/transfermarkt/transfers.csv.gz
        data/raw/transfermarkt/games.csv.gz     (which clubs were in the PL each season)
        data/reference/team_names.csv
Output: data/processed/transfers_in.csv

Rules (see reports/data_quality_report.md):
  1. Loan/youth flags are computed on each player's FULL transfer history, BEFORE filtering
  2. Drop moves dated after the snapshot (6 Jul 2026): scheduled, not completed
  3. Keep seasons 2014/15 to 2025/26, and only clubs that were IN the PL that season
  4. Join clubs by ID, not name (transfer names differ from every other source)
  5. Classify every move with a move_type
"""
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/transfermarkt")
TEAMS_PATH = Path("data/reference/team_names.csv")
OUT_PATH = Path("data/processed/transfers_in.csv")

SNAPSHOT_DATE = pd.Timestamp("2026-07-06")
FIRST_SEASON, LAST_SEASON = 2014, 2025
LOAN_MAX_DAYS = 750                      # loans of up to ~2 seasons
YOUTH_PATTERN = r"\bU\d{2}\b|\bYth\b|Youth|Academy|Reserves"


def pl_clubs_by_season() -> pd.DataFrame:
    """One row per (season, club) that played in the Premier League, with our canonical name."""
    games = pd.read_csv(RAW / "games.csv.gz")
    pl = games[(games["competition_id"] == "GB1") &
               games["season"].between(FIRST_SEASON, LAST_SEASON)]

    clubs = pl[["season", "home_club_id", "home_club_name"]].drop_duplicates()
    clubs.columns = ["season_start", "club_id", "transfermarkt_name"]

    names = pd.read_csv(TEAMS_PATH)
    clubs = clubs.merge(names[["transfermarkt_name", "team"]],
                        on="transfermarkt_name", how="left", validate="many_to_one")

    missing = clubs.loc[clubs["team"].isna(), "transfermarkt_name"].unique()
    if len(missing):
        raise ValueError(f"Add these to {TEAMS_PATH}: {sorted(missing)}")

    per_season = clubs.groupby("season_start").size()
    if (per_season != 20).any():
        raise ValueError(f"Expected 20 PL clubs per season, got:\n{per_season}")

    return clubs[["season_start", "club_id", "team"]]


def add_history_flags(t: pd.DataFrame) -> pd.DataFrame:
    """Look at each player's previous and next move to spot loans and returns."""
    t = t.sort_values(["player_id", "transfer_date"]).copy()
    by_player = t.groupby("player_id")

    prev_from = by_player["from_club_id"].shift()
    prev_date = by_player["transfer_date"].shift()
    next_to = by_player["to_club_id"].shift(-1)
    next_date = by_player["transfer_date"].shift(-1)

    no_fee = t["transfer_fee"].fillna(0) == 0

    t["is_loan_return"] = (no_fee & (t["to_club_id"] == prev_from) &
                           ((t["transfer_date"] - prev_date).dt.days <= LOAN_MAX_DAYS))
    t["is_loan_in"] = (no_fee & (t["from_club_id"] == next_to) &
                       ((next_date - t["transfer_date"]).dt.days <= LOAN_MAX_DAYS))

    youth_team = t["from_club_name"].str.contains(YOUTH_PATTERN, regex=True, na=False)
    parent_club = t["from_club_name"].str.replace(YOUTH_PATTERN, "", regex=True).str.strip()
    t["is_youth_promotion"] = youth_team & (parent_club == t["to_club_name"])
    return t


def classify(t: pd.DataFrame) -> pd.Series:
    """Later lines take priority over earlier ones."""
    fee = t["transfer_fee"]
    move = pd.Series("free", index=t.index)
    move[fee.isna()] = "undisclosed"
    move[fee > 0] = "paid"
    move[t["is_loan_in"]] = "loan_in"
    move[t["is_loan_return"]] = "loan_return"
    move[t["is_youth_promotion"]] = "youth_promotion"
    return move


def main() -> None:
    t = pd.read_csv(RAW / "transfers.csv.gz")
    t["transfer_date"] = pd.to_datetime(t["transfer_date"])

    # Rule 1: flags need full careers, so compute them BEFORE any filtering
    t = add_history_flags(t)

    # Rule 2: drop scheduled future moves
    future = t["transfer_date"] > SNAPSHOT_DATE
    print(f"Dropped {future.sum():,} moves dated after {SNAPSHOT_DATE.date()}")
    t = t[~future]

    # Rules 3 and 4: PL clubs only, in seasons they were in the PL, joined by ID
    t["season_start"] = pd.to_numeric("20" + t["transfer_season"].str[:2], errors="coerce")
    t = t.merge(pl_clubs_by_season(),
                left_on=["season_start", "to_club_id"],
                right_on=["season_start", "club_id"], how="inner")

    # Rule 5
    t["move_type"] = classify(t)

    t["season"] = t["season_start"].apply(lambda s: f"{s}/{str(s + 1)[-2:]}")
    out = (t[["season", "team", "player_id", "player_name", "transfer_date",
              "from_club_name", "transfer_fee", "market_value_in_eur", "move_type"]]
           .rename(columns={"transfer_fee": "fee_eur"})
           .sort_values(["season", "team", "transfer_date"]))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Saved {OUT_PATH}: {len(out):,} moves into PL clubs\n")

    print(pd.crosstab(out["season"], out["move_type"], margins=True).to_string())

    youth = out.loc[out["move_type"] == "youth_promotion", "from_club_name"].unique()
    print(f"\nYouth teams matched ({len(youth)}), please review:")
    print(sorted(youth))


if __name__ == "__main__":
    main()