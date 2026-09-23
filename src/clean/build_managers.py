"""
Build manager data from Transfermarkt's games table.

Outputs:
  data/processed/matches_full.csv     matches_with_xg + each team's matchday manager
  data/processed/manager_spells.csv   one row per continuous managerial spell

Rules:
  1. Join Transfermarkt games to our match table on (season, home_team, away_team),
     then cross-check the score: a third independent source.
  2. Stand-ins: a run of <= 3 matches with the SAME main manager on both sides
     (illness, COVID, touchline ban) is not a managerial change. Those matches
     are credited to that head coach. The matchday manager is still kept.
  3. A spell = consecutive PL matches for a team under the same head coach.
     A relegation gap does NOT end a spell if the same manager comes back.
  4. Spell 1 for each team is where our data starts, not a managerial change.
     Later spells are labelled mid_season or between_seasons.
"""
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/transfermarkt")
TEAMS_PATH = Path("data/reference/team_names.csv")
MATCHES_PATH = Path("data/processed/matches_with_xg.csv")
MATCHES_OUT = Path("data/processed/matches_full.csv")
SPELLS_OUT = Path("data/processed/manager_spells.csv")

KEY = ["season", "home_team", "away_team"]
SHORT_SPELL = 5     # flagged as possible caretakers; also the "main manager" threshold
STAND_IN_MAX = 3    # runs this short between the same manager are stand-ins


def load_tm_games() -> pd.DataFrame:
    games = pd.read_csv(RAW / "games.csv.gz")
    pl = games[(games["competition_id"] == "GB1") & games["season"].between(2014, 2025)].copy()

    name_map = pd.read_csv(TEAMS_PATH).set_index("transfermarkt_name")["team"]
    pl["home_team"] = pl["home_club_name"].map(name_map)
    pl["away_team"] = pl["away_club_name"].map(name_map)
    unmapped = set(pl.loc[pl["home_team"].isna(), "home_club_name"]) | \
               set(pl.loc[pl["away_team"].isna(), "away_club_name"])
    if unmapped:
        raise ValueError(f"Add these to {TEAMS_PATH}: {sorted(unmapped)}")

    pl["season"] = pl["season"].apply(lambda s: f"{s}/{str(s + 1)[-2:]}")
    return pl[KEY + ["home_club_goals", "away_club_goals",
                     "home_club_manager_name", "away_club_manager_name"]].rename(columns={
        "home_club_manager_name": "home_manager",
        "away_club_manager_name": "away_manager",
    })


def number_runs(long: pd.DataFrame, column: str) -> pd.Series:
    """Number each run of identical values in `column`, separately per team."""
    changed = long[column] != long.groupby("team")[column].shift()
    return changed.astype(int).groupby(long["team"]).cumsum()


def mark_head_coach(long: pd.DataFrame) -> pd.DataFrame:
    """Rule 2: credit stand-in matches to the surrounding head coach."""
    long = long.copy()
    long["run"] = number_runs(long, "manager")

    runs = long.groupby(["team", "run"]).agg(
        manager=("manager", "first"),
        matches=("match_id", "count"),
        start_date=("date", "min"),
    ).reset_index()
    runs["prev"] = runs.groupby("team")["manager"].shift()
    runs["next"] = runs.groupby("team")["manager"].shift(-1)

    # How many matches each manager had at each club in total
    total = long.groupby(["team", "manager"]).size()
    prev_total = pd.Series([total.get((t, p), 0) for t, p in zip(runs["team"], runs["prev"])],
                           index=runs.index)

    stand_in = ((runs["matches"] <= STAND_IN_MAX) &
                (runs["prev"] == runs["next"]) &
                (prev_total > SHORT_SPELL))
    runs["head_coach"] = runs["manager"].where(~stand_in, runs["prev"])

    print(f"Stand-ins found: {stand_in.sum()}")
    print(runs.loc[stand_in, ["team", "manager", "head_coach", "start_date", "matches"]]
          .rename(columns={"manager": "stand_in"}).to_string(index=False), "\n")

    long = long.merge(runs[["team", "run", "head_coach"]], on=["team", "run"], how="left")
    long["is_stand_in"] = long["manager"] != long["head_coach"]
    return long


def build_spells(full: pd.DataFrame) -> pd.DataFrame:
    # One row per team per match ("long" format)
    home = full[["match_id", "season", "date", "home_team", "home_manager"]]
    away = full[["match_id", "season", "date", "away_team", "away_manager"]]
    home.columns = away.columns = ["match_id", "season", "date", "team", "manager"]
    long = (pd.concat([home, away], ignore_index=True)
              .sort_values(["team", "date"]).reset_index(drop=True))

    long = mark_head_coach(long)
    long["spell_no"] = number_runs(long, "head_coach")

    spells = long.groupby(["team", "spell_no"]).agg(
        manager=("head_coach", "first"),
        start_date=("date", "min"),
        end_date=("date", "max"),
        matches=("match_id", "count"),
        stand_in_matches=("is_stand_in", "sum"),
        first_season=("season", "first"),
        last_season=("season", "last"),
    ).reset_index()

    # Rule 4: label real changes by timing
    prev_last_season = spells.groupby("team")["last_season"].shift()
    spells["change_timing"] = None
    is_change = spells["spell_no"] > 1
    spells.loc[is_change & (prev_last_season == spells["first_season"]), "change_timing"] = "mid_season"
    spells.loc[is_change & (prev_last_season != spells["first_season"]), "change_timing"] = "between_seasons"
    return spells


def main() -> None:
    matches = pd.read_csv(MATCHES_PATH, parse_dates=["date"])
    tm = load_tm_games()

    # Rule 1: join + third-source score check
    merged = matches.merge(tm, on=KEY, how="outer", validate="one_to_one", indicator=True)
    unmatched = merged[merged["_merge"] != "both"]
    print(f"Matched with Transfermarkt: {(merged['_merge'] == 'both').sum():,} | unmatched: {len(unmatched)}")
    if len(unmatched):
        print(unmatched[KEY + ["_merge"]].to_string())
        raise SystemExit("Join incomplete: fix before continuing.")

    score_diff = merged[(merged["home_goals"] != merged["home_club_goals"]) |
                        (merged["away_goals"] != merged["away_club_goals"])]
    print(f"Score disagreements vs Transfermarkt: {len(score_diff)}\n")

    full = merged.drop(columns=["_merge", "home_club_goals", "away_club_goals"])
    full.to_csv(MATCHES_OUT, index=False)

    # Rules 2 to 4: spells
    spells = build_spells(full)
    spells.to_csv(SPELLS_OUT, index=False)
    print(f"Saved {SPELLS_OUT}: {len(spells)} spells, {spells['manager'].nunique()} different managers")
    print(spells["change_timing"].value_counts(dropna=False).to_string(), "\n")

    # Flags for review
    cols = ["team", "manager", "start_date", "end_date", "matches"]
    short = spells[(spells["matches"] <= SHORT_SPELL) & (spells["spell_no"] > 1)]
    print(f"Short spells (<= {SHORT_SPELL} matches): {len(short)}")
    print(short[cols].to_string(index=False), "\n")

    prev_mgr = spells.groupby("team")["manager"].shift()
    next_mgr = spells.groupby("team")["manager"].shift(-1)
    aba = spells[prev_mgr.notna() & (prev_mgr == next_mgr)]
    print(f"Remaining A-B-A patterns: {len(aba)}")
    print(aba[cols].to_string(index=False))


if __name__ == "__main__":
    main()