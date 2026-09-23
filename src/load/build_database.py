"""
Build the SQLite database data/epl.db from the processed CSVs.

Schema (tables, keys, constraints, views): sql/schema.sql
The database is rebuilt from scratch on every run, so it always matches the CSVs.
"""
from pathlib import Path
import sqlite3

import pandas as pd

DB_PATH = Path("data/epl.db")
SCHEMA_PATH = Path("sql/schema.sql")
PROC = Path("data/processed")
TEAMS_PATH = Path("data/reference/team_names.csv")


def require_mapped(df: pd.DataFrame, columns: list, label: str) -> None:
    """Fail loudly if any name couldn't be turned into an ID."""
    for col in columns:
        missing = df[col].isna().sum()
        if missing:
            raise ValueError(f"{label}: {missing} rows have no {col}")


def main() -> None:
    DB_PATH.unlink(missing_ok=True)                        # start fresh every time
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")                # SQLite has foreign keys OFF by default
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # --- teams ---
    teams = pd.read_csv(TEAMS_PATH).rename(columns={"team": "name"})
    teams.insert(0, "team_id", range(1, len(teams) + 1))
    team_id = dict(zip(teams["name"], teams["team_id"]))

    matches = pd.read_csv(PROC / "matches_full.csv")
    spells = pd.read_csv(PROC / "manager_spells_verified.csv")
    transfers = pd.read_csv(PROC / "transfers_in.csv")

    # --- managers: everyone who was a matchday manager or a head coach ---
    names = sorted(set(matches["home_manager"]) | set(matches["away_manager"]) | set(spells["manager"]))
    managers = pd.DataFrame({"manager_id": range(1, len(names) + 1), "name": names})
    manager_id = dict(zip(managers["name"], managers["manager_id"]))

    # --- matches: names -> IDs ---
    matches_db = matches.assign(
        home_team_id=matches["home_team"].map(team_id),
        away_team_id=matches["away_team"].map(team_id),
        home_manager_id=matches["home_manager"].map(manager_id),
        away_manager_id=matches["away_manager"].map(manager_id),
    ).drop(columns=["home_team", "away_team", "home_manager", "away_manager"])
    require_mapped(matches_db, ["home_team_id", "away_team_id",
                                "home_manager_id", "away_manager_id"], "matches")

    # --- spells ---
    spells_db = spells.assign(
        team_id=spells["team"].map(team_id),
        manager_id=spells["manager"].map(manager_id),
        wiki_verified=spells["wiki_verified"].astype(int),
    ).drop(columns=["team", "manager", "wiki_row", "wiki_prev_manager"])
    spells_db.insert(0, "spell_id", range(1, len(spells_db) + 1))
    require_mapped(spells_db, ["team_id", "manager_id"], "spells")

    # --- transfers ---
    transfers_db = transfers.assign(team_id=transfers["team"].map(team_id)) \
                            .drop(columns=["team"]) \
                            .rename(columns={"market_value_in_eur": "market_value_eur"})
    transfers_db.insert(0, "transfer_id", range(1, len(transfers_db) + 1))
    require_mapped(transfers_db, ["team_id"], "transfers")

    # --- load: parents before children, so foreign keys always have a target ---
    for name, df in [("teams", teams), ("managers", managers), ("matches", matches_db),
                     ("spells", spells_db), ("transfers", transfers_db)]:
        df.to_sql(name, con, if_exists="append", index=False)
        print(f"Loaded {name:<10} {len(df):>6,} rows")
    con.commit()

    # --- checks ---
    print("\nChecks:")
    fk_problems = con.execute("PRAGMA foreign_key_check").fetchall()
    print(f"  Foreign-key violations: {len(fk_problems)}")

    rows, unique_rows = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT match_id || '-' || team_id) FROM team_match_spells"
    ).fetchone()
    expected = 2 * len(matches_db)
    print(f"  team_match_spells: {rows:,} rows, {unique_rows:,} unique (expected {expected:,} of each)")

    con.close()
    if fk_problems or rows != expected or unique_rows != expected:
        raise SystemExit("Database checks failed.")
    print(f"\nSaved {DB_PATH}")


if __name__ == "__main__":
    main()