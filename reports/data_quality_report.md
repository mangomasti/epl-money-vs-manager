# Data Quality Report

Log of every data issue found, and how it was handled.

## Source 1: football-data.co.uk (match results & odds)

**Raw files:** 12 seasons (2014/15–2025/26), `data/raw/football_data/E0_*.csv`

| # | Issue | Evidence | Resolution |
|---|-------|----------|------------|
| 1 | Blank trailing row | 2014/15 had 381 rows; row 380 entirely empty | Drop rows with missing `HomeTeam` |
| 2 | Inconsistent column counts | 62–132 columns across seasons (extra bookmaker odds added over time) | Keep only the 13 columns required; all 13 present in every season |
| 3 | Mixed date formats | 2014/15 and 2016/17 use `dd/mm/yy`; other seasons use `dd/mm/yyyy` | Standardise to 4-digit years, parse as day-first |
| 4 | Non-standard season start | 2020/21 began 12 Sep 2020 (COVID) | Not an error — validation rules must allow it |