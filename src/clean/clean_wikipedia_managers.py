"""  0.
 <br> line breaks replaced with spaces before parsing (they split header text)
Parse the "Managerial changes" table from each saved Wikipedia season page.

Input:  data/raw/wikipedia/pl_*.html
        data/reference/team_names.csv
Output: data/processed/wiki_manager_changes.csv

Rules:
  1. Exactly one table containing "Manner of departure" per page, with 7 columns (else stop)
  2. Strip footnote markers like [a] and flag country codes like "ESP "
  3. Team names looked up across ALL known aliases in the mapping table
  4. "(interim)" / "(caretaker)" becomes a separate True/False column
  5. Unparseable dates are reported, not silently dropped
"""
from io import StringIO
from pathlib import Path
import re

import pandas as pd

RAW_DIR = Path("data/raw/wikipedia")
TEAMS_PATH = Path("data/reference/team_names.csv")
OUT_PATH = Path("data/processed/wiki_manager_changes.csv")

COLUMNS = ["team", "outgoing", "departure", "vacancy_date",
           "position", "incoming", "appointment_date"]
CARETAKER = r"\s*\([^)]*(?:interim|caretaker)[^)]*\)"
MATCH = r"Manner\s*of\s*departure"


def load_alias_map() -> dict:
    """Any name used by any source -> canonical team name."""
    names = pd.read_csv(TEAMS_PATH)
    alias = {}
    for col in ["team", "understat_name", "transfermarkt_name"]:
        alias.update(dict(zip(names[col], names["team"])))
    return alias


def clean_text(value):
    if pd.isna(value):
        return value
    value = re.sub(r"\[.*?\]", "", str(value))     # footnotes: [a], [12]
    value = re.sub(r"^[A-Z]{3}\s+", "", value)     # flag codes: "ESP Unai Emery"
    return value.strip()


def parse_season(path: Path, alias: dict) -> pd.DataFrame:
    year = int(path.stem.split("_")[1])
    html = path.read_text(encoding="utf-8")
    html = re.sub(r"<br[^>]*>", " ", html)      # <br> splits text into pieces: turn it into a space
    try:
        tables = pd.read_html(StringIO(html), match=MATCH)
    except ValueError as err:
        raise ValueError(f"{path.name}: {err}") from err

    # Rule 1
    if len(tables) != 1:
        raise ValueError(f"{path.name}: expected 1 managerial-changes table, found {len(tables)}")
    df = tables[0]
    if df.shape[1] != 7:
        raise ValueError(f"{path.name}: unexpected columns {list(df.columns)}")
    df.columns = COLUMNS

    # Rule 2
    df = df.map(clean_text)

    # Rule 3
    df["season"] = f"{year}/{str(year + 1)[-2:]}"
    df["team_canonical"] = df["team"].map(alias)
    unknown = sorted(df.loc[df["team_canonical"].isna(), "team"].unique())
    if unknown:
        raise ValueError(f"{path.name}: unknown team names {unknown}. Add them to {TEAMS_PATH}")

    # Rule 4
    df["incoming_is_caretaker"] = df["incoming"].str.contains(CARETAKER, case=False, regex=True, na=False)
    df["incoming"] = df["incoming"].str.replace(CARETAKER, "", case=False, regex=True)

    # Rule 5
    for col in ["vacancy_date", "appointment_date"]:
        df[col] = pd.to_datetime(df[col], format="%d %B %Y", errors="coerce")
    return df

def standardise_departure(text) -> str:
    """Collapse editors' wording into a few categories."""
    t = str(text).strip().lower()
    if t.startswith("signed by"):
        return "left_for_new_job"
    if "interim" in t or "caretaker" in t:
        return "end_of_caretaker"
    return {
        "sacked": "sacked",
        "mutual consent": "mutual_consent",
        "resigned": "resigned",
        "end of contract": "end_of_contract",
        "retired": "retired",
    }.get(t, "other")
def main() -> None:
    alias = load_alias_map()
    wiki = pd.concat([parse_season(p, alias) for p in sorted(RAW_DIR.glob("pl_*.html"))],
                     ignore_index=True)
    wiki = wiki[["season", "team_canonical", "outgoing", "departure", "vacancy_date",
                 "position", "incoming", "incoming_is_caretaker", "appointment_date"]] \
               .rename(columns={"team_canonical": "team"})
    wiki["departure_type"] = wiki["departure"].map(standardise_departure)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wiki.to_csv(OUT_PATH, index=False)
    print(f"Saved {OUT_PATH}: {len(wiki)} managerial changes\n")

    print("Changes per season:")
    print(wiki.groupby("season").size().to_string(), "\n")

    print("Departure type (standardised):")
    print(wiki["departure_type"].value_counts().to_string(), "\n")

    bad_dates = wiki[wiki["vacancy_date"].isna() | wiki["appointment_date"].isna()]
    print(f"Rows with an unparseable date: {len(bad_dates)}")
    if len(bad_dates):
        print(bad_dates[["season", "team", "outgoing", "incoming"]].to_string(index=False))

    print("\nArsenal changes (sanity check):")
    print(wiki[wiki["team"] == "Arsenal"][["season", "outgoing", "departure",
                                           "incoming", "appointment_date"]].to_string(index=False))


if __name__ == "__main__":
    main()