# epl-money-vs-manager
# Money vs. Manager: What Actually Changes a Premier League Club's Trajectory?

When a club wants to improve, what moves the needle more: **changing the manager** or **spending in the transfer window**?

This project builds a multi-source dataset of every Premier League match, transfer and managerial change from **2014/15 to 2025/26**, then tests:

1. Is the "new manager bounce" real, or just regression to the mean?
2. Does transfer spending predict improvement, and does *how* a club spends matter?
3. Which effect is bigger, and which lasts longer?
4. **Case study:** Arsenal, from Wenger to Emery to Arteta.

## 📊 [Interactive dashboard on Tableau Public](https://public.tableau.com/app/profile/karan.goyal4817/viz/MoneyvsManager/MoneyvsManager)

## Key findings

- **The "new manager bounce" is mostly an illusion.** Teams in the same bad form that kept their manager recovered almost as much. About 86% of the bounce is regression to the mean.
- **Summer decisions matter more than mid-season ones.** A new manager hired in the summer is linked to about +5 points; summer spending to about +2–3 points per league-average budget, with diminishing returns.
- **Arsenal under Arteta beat the league-wide model by about 70 points over six seasons.** The improvement was gradual, not a bounce.

Full write-up: [`reports/findings.md`](reports/findings.md)

## Data

| Source | What it provides | Method |
|---|---|---|
| [football-data.co.uk](https://www.football-data.co.uk) | 4,560 match results, shots, pre-match betting odds | CSV download |
| [Understat](https://understat.com) | Expected goals (xG) for every match | Scraped from an internal JSON endpoint |
| [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) | Transfers, fees, the manager for every match | Public dataset (CC0) |
| Wikipedia | Managerial changes, manner of departure | Scraped HTML tables |

## Data quality

Real data is messy. **22 issues** were found, fixed and documented in [`reports/data_quality_report.md`](reports/data_quality_report.md). Highlights:

- **Scores agree across three independent sources** for all 4,560 matches
- **Half of all "incoming transfers" aren't signings**: 1,449 loan returns and 220 youth promotions, detected from each player's career history
- **Stand-in managers** (e.g. Arteta's COVID absence) were being counted as managerial changes; removing them eliminated 12 false events
- **Every one of 175 managerial changes** is verified against Wikipedia or explained

## Reproduce it

```bash
git clone https://github.com/mangomasti/epl-money-vs-manager.git
cd epl-money-vs-manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run_pipeline.py              # rebuild everything from the saved raw data
python run_pipeline.py --download   # re-download raw data first
```

## Repository structure

```
data/
  raw/          untouched source files (never edited)
  reference/    hand-maintained lookup tables (team names, manager aliases)
  processed/    cleaned outputs
src/
  scrape/       one script per data source
  clean/        cleaning, joining, classification
  validate/     automated data checks
notebooks/      exploration
reports/        data quality report, findings
run_pipeline.py rebuilds everything in dependency order
```