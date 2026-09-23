-- Final league table for one season, calculated from match results.
-- Validation: compare with the official table.
SELECT t.name                                AS team,
       COUNT(*)                              AS played,
       SUM(tm.points = 3)                    AS won,
       SUM(tm.points = 1)                    AS drawn,
       SUM(tm.points = 0)                    AS lost,
       SUM(tm.goals_for)                     AS gf,
       SUM(tm.goals_against)                 AS ga,
       SUM(tm.goals_for - tm.goals_against)  AS gd,
       SUM(tm.points)                        AS pts
FROM team_matches AS tm
JOIN teams AS t ON t.team_id = tm.team_id
WHERE tm.season = '2019/20'
GROUP BY t.name
ORDER BY pts DESC, gd DESC, gf DESC;