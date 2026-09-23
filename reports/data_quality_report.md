# Data Quality Report

Log of every data issue found, and how it was handled.
| 5 | Impossible shot stats | Newcastle v West Ham (2021-08-15): West Ham 9 shots on target, 8 total shots | Flagged as known issue; to be cross-checked against Understat shot data |
| 6 | Outlier betting odds | Aston Villa v Arsenal (2023-02-18): Bet365 margin 16.7% vs. mean 4.35% (std 1.5%) — ~8 std devs | Kept; odds normalised to remove margin before analysis |
### Validation results

`src/validate/validate_matches.py` runs 14 automated checks on `data/processed/matches.csv`
(structure, completeness, logical consistency, dates, odds).
**Result: 14/14 pass**, with 2 documented exceptions (issues 5 & 6).
## Source 1: football-data.co.uk (match results & odds)
## Source 2: Understat (match-level xG)

**Raw files:** 12 seasons of JSON from Understat's internal endpoint, `data/raw/understat/epl_*.json`

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 7 | All values stored as text | Goals, xG and IDs returned as strings in the JSON | Converted to int/float/date during cleaning |
| 8 | Team names differ between sources | 7 of 35 teams named differently (e.g. `Man City` vs `Manchester City`) | Mapping table `data/reference/team_names.csv`; football-data names are canonical; cleaning fails loudly on any unmapped name |
| 9 | Understat dates off by one day | 26 matches (13 in 2015/16, 13 in 2016/17), all evening games between 31 Oct and 3 Mar; Understat date exactly +1 day with time `00:00:00` | Football-data dates kept as authoritative; not a join error (see below) |

### Joining the sources

`src/clean/build_match_table.py` joins both sources on **(season, home team, away team)**, a key proven unique by validation, rather than on date.

- **4,560 / 4,560 matches** paired, 0 unmatched
- **4,560 / 4,560 scores agree** across the two independent sources, confirming every match was paired correctly
- Joining on date would have silently dropped the 26 matches in issue 9

**Raw files:** 12 seasons (2014/15–2025/26), `data/raw/football_data/E0_*.csv`

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 1 | Blank trailing row | 2014/15 had 381 rows; row 380 entirely empty | Drop rows with missing `HomeTeam` |
| 2 | Inconsistent column counts | 62–132 columns across seasons (extra bookmaker odds added over time) | Keep only the 13 columns required; all 13 present in every season |
| 3 | Mixed date formats | 2014/15 and 2016/17 use `dd/mm/yy`; other seasons use `dd/mm/yyyy` | Standardise to 4-digit years, parse as day-first |
| 4 | Non-standard season start | 2020/21 began 12 Sep 2020 (COVID) | Not an error — validation rules must allow it |
## Source 3: Transfermarkt (transfers, managers)

**Raw files:** public `transfermarkt-datasets` project (CC0), `data/raw/transfermarkt/*.csv.gz`

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 10 | Frozen snapshot | Source updates stopped; last match 6 Jul 2026 | Covers full 2014/15–2025/26 window; raw snapshot committed in case the source disappears |
| 11 | Coverage grows over time (survivorship bias) | 220 incoming moves in 2014/15 vs 604 in 2023/24; Diego Costa → Chelsea (2014, ~€38m) missing entirely | Compare clubs **within** a season, not absolute spending across seasons |
| 12 | Future-dated moves | 520 moves dated after the snapshot (e.g. 2030-06-30): scheduled, not completed | Dropped, *after* history flags were computed |
| 13 | No loan/free flag; €0 is ambiguous | 59% of fees are €0, 11% missing | Every move classified from the player's career history (see below) |
| 14 | Clubs counted outside their PL seasons | Club IDs "ever in the PL" include second-division seasons | Join on (season, club ID) |
| 15 | Fourth naming convention | Transfers use `Man Utd`, `Sheff Utd` | Clubs joined by Transfermarkt ID, never by name |

### Move classification

| move_type | Rule | Count |
|---|---|---|
| `loan_return` | Back to a club the player left within 750 days, €0 | 1,449 |
| `youth_promotion` | From the same club's youth side (U18/U21/U23) | 220 |
| `paid` | Fee > 0 | 1,164 |
| `loan_in` | €0, player returns to his previous club within 750 days | 289 |
| `free` | €0, none of the above | 134 |
| `undisclosed` | Fee unknown | 58 |

**1,645 of 3,314 moves (50%) are real signings.** Loan returns and youth promotions are excluded from all signing analysis.

**Known limits of the rules:** loans longer than 750 days would be classed as `free`; a permanent €0 move back to a former club within 750 days would be classed as `loan_return`. Both are expected to be rare.
### Managers (from Transfermarkt `games`)

`src/clean/build_managers.py` attaches each team's manager to every match and builds managerial spells.

- **Third-source check:** all 4,560 matches joined to Transfermarkt; **4,560 / 4,560 scores agree** across football-data, Understat and Transfermarkt.

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 16 | Stand-in managers recorded as managerial changes | 6 runs of 1–3 matches with the same main manager on both sides, e.g. Stuivenberg for Arteta (Arsenal v Man City, 1 Jan 2022; Arteta had COVID) | Matches credited to the head coach; matchday manager kept; each spell records `stand_in_matches`. Removed 12 false changes |
| 17 | Separate jobs merged across a relegation gap | Heckingbottom (Sheffield United): caretaker spell in 2020/21 merged with a permanent appointment made in the Championship, returning to the PL in 2023/24 | Known issue: to be resolved in the Wikipedia cross-check |

**Result:** 210 spells, 140 managers, 175 managerial changes (127 mid-season, 48 between seasons). 41 spells of 5 matches or fewer (caretakers and very short permanent reigns) are kept, to be classified in the Wikipedia cross-check.
## Source 4: Wikipedia (managerial changes: cross-check)

**Raw files:** each season's Premier League page, `data/raw/wikipedia/pl_*.html`, parsed by `src/clean/clean_wikipedia_managers.py`; reconciled with Transfermarkt by `src/clean/reconcile_managers.py`

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 18 | Header text split by line breaks | 2015–16 onwards: `Manner of<br/>departure`; HTML parsers treat these as two separate text pieces | `<br>` tags replaced with spaces before parsing |
| 19 | Inconsistent departure wording | `End of interim spell` vs `End of caretaker spell`; `Signed by Tottenham` vs `Signed by Tottenham Hotspur` | Standardised into 7 categories; unknown wording would show as `other` |
| 20 | Caretakers mostly omitted; promoted caretakers dated after their first match | Ljungberg absent (Emery → Arteta); Carver first match 1 Jan 2015, appointed 26 Jan | Unmatched short spells classed as caretakers; appointment allowed any time up to a spell's last match |
| 21 | Name variants and joint caretakers | `Paddy McCarthy` = `Patrick McCarthy`; one cell lists "David Unsworth Joe Royle" | Manager alias table `data/reference/manager_aliases.csv`; name matched by containment after removing accents |
| 22 | Managers hired outside the PL | 9 promoted-club managers (e.g. Dean Smith, Kompany) appear only on Championship pages | Labelled `appointed_outside_pl`; excluded from bounce analysis |

### Reconciliation result

All 175 Transfermarkt managerial changes explained; **0 unverified**.

| appointment_type | Count |
|---|---|
| permanent (Wikipedia-verified) | 113 |
| caretaker | 47 |
| caretaker_made_permanent | 6 |
| appointed_outside_pl | 9 |

Wikipedia appointments with no Transfermarkt spell: 5, all explained (4 before our data starts; 1 caretaker who took no PL match).

**Issue 17 update:** Heckingbottom (Sheffield United) is now labelled `caretaker_made_permanent`. His 2021 caretaker stint and his 2023/24 permanent spell remain one merged spell. This affects one spell and is noted as a limitation.