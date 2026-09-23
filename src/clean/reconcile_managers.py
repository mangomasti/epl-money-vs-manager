"""
Cross-check Transfermarkt managerial spells against Wikipedia's managerial-changes tables.

Inputs:  data/processed/manager_spells.csv        (Transfermarkt)
         data/processed/wiki_manager_changes.csv  (Wikipedia)
         data/reference/manager_aliases.csv       (name variants)
Output:  data/processed/manager_spells_verified.csv

A Transfermarkt spell (spell 2 onwards) matches a Wikipedia appointment when:
  1. Same team
  2. Same manager: names normalised (aliases applied, accents removed, lower case).
     The Transfermarkt name may be CONTAINED in the Wikipedia cell, which
     sometimes lists joint caretakers ("David Unsworth Joe Royle").
  3. Appointment date between 150 days before the spell's first match and its
     last match. An appointment after the first match means a caretaker who
     was promoted to permanent.

appointment_type for every change:
  permanent                 matched, not interim
  caretaker                 matched as interim (one season), or unmatched and <= 10 matches
  caretaker_made_permanent  started as caretaker, then given the job
  appointed_outside_pl      unmatched, between seasons: hired while the club was outside the PL
  unverified                anything else: needs manual review
"""
from pathlib import Path
import unicodedata

import pandas as pd

SPELLS_PATH = Path("data/processed/manager_spells.csv")
WIKI_PATH = Path("data/processed/wiki_manager_changes.csv")
ALIASES_PATH = Path("data/reference/manager_aliases.csv")
OUT_PATH = Path("data/processed/manager_spells_verified.csv")

MAX_GAP_DAYS = 150
PROMOTION_TOLERANCE_DAYS = 3
CARETAKER_MAX_MATCHES = 10


def normalise_name(name, aliases: dict):
    """Apply alias, remove accents, lower case: 'Arsène Wenger' -> 'arsene wenger'."""
    if pd.isna(name):
        return name
    name = str(name).strip()
    name = aliases.get(name, name)
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def match_spells(changes: pd.DataFrame, wiki: pd.DataFrame) -> pd.DataFrame:
    """Every same-team pair, filtered by name and date, then the closest one kept."""
    pairs = changes.merge(wiki, on="team", how="inner")

    name_ok = [isinstance(tm, str) and isinstance(wk, str) and tm in wk
               for tm, wk in zip(pairs["name_key"], pairs["wiki_name_key"])]
    pairs = pairs[name_ok]

    window_start = pairs["start_date"] - pd.Timedelta(days=MAX_GAP_DAYS)
    pairs = pairs[pairs["appointment_date"].between(window_start, pairs["end_date"])].copy()

    pairs["gap_days"] = (pairs["start_date"] - pairs["appointment_date"]).dt.days.abs()
    return (pairs.sort_values("gap_days")
                 .drop_duplicates("spell_idx")
                 .drop_duplicates("wiki_row"))


def classify(spells: pd.DataFrame) -> pd.Series:
    """Later lines take priority over earlier ones."""
    is_change = spells["spell_no"] > 1
    verified = spells["wiki_verified"]
    wiki_caretaker = spells["incoming_is_caretaker"].eq(True)
    promoted = spells["appointment_date"] > spells["start_date"] + pd.Timedelta(days=PROMOTION_TOLERANCE_DAYS)
    multi_season = spells["first_season"] != spells["last_season"]
    short = spells["matches"] <= CARETAKER_MAX_MATCHES
    between = spells["change_timing"] == "between_seasons"

    t = pd.Series(None, index=spells.index, dtype="object")
    t[is_change & verified & ~wiki_caretaker] = "permanent"
    t[is_change & verified & wiki_caretaker] = "caretaker"
    t[is_change & verified & ((wiki_caretaker & multi_season) | (~wiki_caretaker & promoted))] = "caretaker_made_permanent"
    t[is_change & ~verified] = "unverified"
    t[is_change & ~verified & short] = "caretaker"
    t[is_change & ~verified & ~short & between] = "appointed_outside_pl"
    return t


def main() -> None:
    spells = pd.read_csv(SPELLS_PATH, parse_dates=["start_date", "end_date"])
    wiki = pd.read_csv(WIKI_PATH, parse_dates=["vacancy_date", "appointment_date"])
    aliases = dict(pd.read_csv(ALIASES_PATH).values)

    spells["name_key"] = spells["manager"].map(lambda n: normalise_name(n, aliases))
    wiki["wiki_name_key"] = wiki["incoming"].map(lambda n: normalise_name(n, aliases))
    wiki["wiki_row"] = range(len(wiki))

    changes = spells[spells["spell_no"] > 1].reset_index(names="spell_idx")
    pairs = match_spells(changes, wiki)

    matched = pairs.set_index("spell_idx")[[
        "wiki_row", "outgoing", "departure_type", "position",
        "appointment_date", "incoming_is_caretaker"]].rename(columns={
        "outgoing": "wiki_prev_manager",
        "departure_type": "prev_departure",
        "position": "position_at_vacancy",
    })
    spells = spells.join(matched)
    spells["wiki_row"] = spells["wiki_row"].astype("Int64")
    spells["wiki_verified"] = spells["wiki_row"].notna()
    spells["appointment_type"] = classify(spells)

    # Wikipedia rows no spell used, with a reason
    first_spells = set(zip(spells.loc[spells["spell_no"] == 1, "team"],
                           spells.loc[spells["spell_no"] == 1, "name_key"]))
    wiki_only = wiki[~wiki["wiki_row"].isin(spells["wiki_row"].dropna())].copy()
    wiki_only["reason"] = [
        "team's first spell in our data (appointed before it starts)"
        if (team, key) in first_spells else "no PL match found: check"
        for team, key in zip(wiki_only["team"], wiki_only["wiki_name_key"])
    ]

    spells = spells.drop(columns=["name_key", "incoming_is_caretaker"])
    spells.to_csv(OUT_PATH, index=False)
    print(f"Saved {OUT_PATH}\n")

    is_change = spells["spell_no"] > 1
    print("Transfermarkt changes by appointment type:")
    print(spells.loc[is_change, "appointment_type"].value_counts().to_string(), "\n")

    cols = ["team", "manager", "start_date", "matches"]
    for label in ["unverified", "caretaker_made_permanent", "appointed_outside_pl"]:
        rows = spells[spells["appointment_type"] == label]
        print(f"{label}: {len(rows)}")
        print(rows[cols].to_string(index=False), "\n")

    print(f"Wikipedia appointments with no Transfermarkt spell: {len(wiki_only)}")
    print(wiki_only[["season", "team", "incoming", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()