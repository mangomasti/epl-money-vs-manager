-- First look: points per game in the 10 league matches before vs. after
-- each mid-season managerial change.
-- NOT yet a fair test: see the regression-to-the-mean note.

WITH seq AS (                       -- every team's matches, numbered in date order
    SELECT team_id, spell_id, date, points,
           ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY date) AS n
    FROM team_match_spells
),
changes AS (                        -- the match number where each new manager starts
    SELECT s.spell_id, s.team_id, s.appointment_type,
           MIN(seq.n) AS first_n
    FROM spells AS s
    JOIN seq ON seq.spell_id = s.spell_id
    WHERE s.change_timing = 'mid_season'
      AND s.appointment_type IN ('permanent', 'caretaker', 'caretaker_made_permanent')
    GROUP BY s.spell_id
),
windows AS (                        -- average points 10 before / 10 after each change
    SELECT c.spell_id, c.appointment_type,
           AVG(CASE WHEN seq.n BETWEEN c.first_n - 10 AND c.first_n - 1 THEN seq.points END) AS ppg_before,
           AVG(CASE WHEN seq.n BETWEEN c.first_n      AND c.first_n + 9 THEN seq.points END) AS ppg_after,
           COUNT(CASE WHEN seq.n BETWEEN c.first_n - 10 AND c.first_n - 1 THEN 1 END) AS n_before,
           COUNT(CASE WHEN seq.n BETWEEN c.first_n      AND c.first_n + 9 THEN 1 END) AS n_after
    FROM changes AS c
    JOIN seq ON seq.team_id = c.team_id
    GROUP BY c.spell_id
)
SELECT appointment_type,
       COUNT(*)                               AS changes,
       ROUND(AVG(ppg_before), 2)              AS ppg_before,
       ROUND(AVG(ppg_after), 2)               AS ppg_after,
       ROUND(AVG(ppg_after - ppg_before), 2)  AS avg_change
FROM windows
WHERE n_before = 10 AND n_after = 10          -- only changes with a full window on both sides
GROUP BY appointment_type
UNION ALL
SELECT 'ALL', COUNT(*),
       ROUND(AVG(ppg_before), 2), ROUND(AVG(ppg_after), 2), ROUND(AVG(ppg_after - ppg_before), 2)
FROM windows
WHERE n_before = 10 AND n_after = 10;