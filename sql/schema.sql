-- Money vs. Manager: database schema (SQLite)
-- Every validation rule that can be expressed as a constraint lives here,
-- so bad data fails at load time instead of reaching the analysis.

PRAGMA foreign_keys = ON;

-- One row per club -------------------------------------------------------
CREATE TABLE teams (
    team_id            INTEGER PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,   -- canonical (football-data) name
    understat_name     TEXT NOT NULL UNIQUE,
    transfermarkt_name TEXT NOT NULL UNIQUE
);

-- One row per person who managed a PL match ----------------------------
CREATE TABLE managers (
    manager_id INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE
);

-- One row per match -------------------------------------------------------
CREATE TABLE matches (
    match_id             INTEGER PRIMARY KEY,
    season               TEXT    NOT NULL,
    date                 TEXT    NOT NULL,                  -- 'YYYY-MM-DD'
    home_team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    home_goals           INTEGER NOT NULL CHECK (home_goals >= 0),
    away_goals           INTEGER NOT NULL CHECK (away_goals >= 0),
    result               TEXT    NOT NULL CHECK (result IN ('H', 'D', 'A')),
    home_shots           INTEGER,
    away_shots           INTEGER,
    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,
    odds_home            REAL CHECK (odds_home > 1),
    odds_draw            REAL CHECK (odds_draw > 1),
    odds_away            REAL CHECK (odds_away > 1),
    understat_id         INTEGER UNIQUE,
    home_xg              REAL CHECK (home_xg >= 0),
    away_xg              REAL CHECK (away_xg >= 0),
    home_manager_id      INTEGER NOT NULL REFERENCES managers(manager_id),  -- matchday manager
    away_manager_id      INTEGER NOT NULL REFERENCES managers(manager_id),
    CHECK (home_team_id <> away_team_id),
    UNIQUE (season, home_team_id, away_team_id)             -- each fixture once per season
);

-- One row per managerial spell (stand-ins credited to the head coach) ---
CREATE TABLE spells (
    spell_id            INTEGER PRIMARY KEY,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id),
    manager_id          INTEGER NOT NULL REFERENCES managers(manager_id),
    spell_no            INTEGER NOT NULL CHECK (spell_no >= 1),
    start_date          TEXT    NOT NULL,
    end_date            TEXT    NOT NULL,
    matches             INTEGER NOT NULL CHECK (matches > 0),
    stand_in_matches    INTEGER NOT NULL DEFAULT 0,
    first_season        TEXT    NOT NULL,
    last_season         TEXT    NOT NULL,
    change_timing       TEXT CHECK (change_timing IN ('mid_season', 'between_seasons')),
    prev_departure      TEXT,
    position_at_vacancy TEXT,
    appointment_date    TEXT,
    wiki_verified       INTEGER NOT NULL CHECK (wiki_verified IN (0, 1)),
    appointment_type    TEXT CHECK (appointment_type IN
                            ('permanent', 'caretaker', 'caretaker_made_permanent', 'appointed_outside_pl')),
    CHECK (end_date >= start_date),
    UNIQUE (team_id, spell_no)
);

-- One row per move INTO a PL club -----------------------------------------
CREATE TABLE transfers (
    transfer_id      INTEGER PRIMARY KEY,
    season           TEXT    NOT NULL,
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    player_id        INTEGER NOT NULL,
    player_name      TEXT,
    transfer_date    TEXT    NOT NULL,
    from_club_name   TEXT,
    fee_eur          REAL CHECK (fee_eur >= 0),
    market_value_eur REAL,
    move_type        TEXT    NOT NULL CHECK (move_type IN
                         ('paid', 'free', 'undisclosed', 'loan_in', 'loan_return', 'youth_promotion'))
);

-- VIEW: one row per team per match (home and away stacked) ------------------
CREATE VIEW team_matches AS
SELECT match_id, season, date,
       home_team_id    AS team_id,
       away_team_id    AS opponent_id,
       1               AS is_home,
       home_goals      AS goals_for,
       away_goals      AS goals_against,
       home_xg         AS xg_for,
       away_xg         AS xg_against,
       CASE result WHEN 'H' THEN 3 WHEN 'D' THEN 1 ELSE 0 END AS points
FROM matches
UNION ALL
SELECT match_id, season, date,
       away_team_id, home_team_id, 0,
       away_goals, home_goals,
       away_xg, home_xg,
       CASE result WHEN 'A' THEN 3 WHEN 'D' THEN 1 ELSE 0 END
FROM matches;

-- VIEW: each team-match with the spell (head coach) it belongs to --------
CREATE VIEW team_match_spells AS
SELECT tm.*, s.spell_id, s.manager_id AS head_coach_id
FROM team_matches tm
JOIN spells s
  ON s.team_id = tm.team_id
 AND tm.date BETWEEN s.start_date AND s.end_date;