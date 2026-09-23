-- Every Arsenal managerial spell, with points per game.
SELECT s.spell_no,
       m.name                        AS manager,
       s.start_date,
       s.end_date,
       s.matches,
       ROUND(AVG(tms.points), 2)     AS points_per_game,
       s.appointment_type,
       s.prev_departure              AS how_predecessor_left
FROM spells AS s
JOIN managers AS m          ON m.manager_id = s.manager_id
JOIN teams AS t             ON t.team_id = s.team_id
JOIN team_match_spells AS tms ON tms.spell_id = s.spell_id
WHERE t.name = 'Arsenal'
GROUP BY s.spell_id
ORDER BY s.spell_no;