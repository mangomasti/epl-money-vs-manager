"""
Q2: Does summer transfer spending improve a club's results?
Q3 (first look): how does it compare with changing manager in the same summer?

Unit: club-season, for clubs in the PL in both the previous and current season.
Outcome: change in points vs. the previous season (and change in xG difference per game).
Spending: summer (May-Sep) fees on paid transfers, relative to the league average that
          summer (1.0 = average). Summer only: January spending partly REACTS to results.
Controls: previous season's points and xG difference (regression to the mean).
new_manager: different head coach at the start of the season than at the end of the last one.

Outputs: reports/results/spending_club_seasons.csv
         reports/results/spending_models.csv
         reports/figures/spending_effect.png
"""
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

DB_PATH = Path("data/epl.db")
RESULTS = Path("reports/results")
FIGURES = Path("reports/figures")

SIGNING_TYPES = ["paid", "free", "undisclosed", "loan_in"]

SEASON_SQL = """
SELECT tm.team_id, t.name AS team, tm.season,
       SUM(tm.points)                   AS points,
       AVG(tm.xg_for - tm.xg_against)   AS xgd_pg
FROM team_matches AS tm
JOIN teams AS t ON t.team_id = tm.team_id
GROUP BY tm.team_id, tm.season
"""
COACH_SQL = "SELECT team_id, season, date, head_coach_id FROM team_match_spells"
TRANSFERS_SQL = "SELECT team_id, season, transfer_date, fee_eur, move_type FROM transfers"


def build_club_seasons(con) -> pd.DataFrame:
    seasons = pd.read_sql(SEASON_SQL, con)
    seasons["start"] = seasons["season"].str[:4].astype(int)

    # --- summer signings ---
    tr = pd.read_sql(TRANSFERS_SQL, con, parse_dates=["transfer_date"])
    tr["start"] = tr["season"].str[:4].astype(int)
    summer = tr[(tr["transfer_date"].dt.year == tr["start"]) &
                tr["transfer_date"].dt.month.between(5, 9) &
                tr["move_type"].isin(SIGNING_TYPES)]
    spend = summer.groupby(["team_id", "start"]).agg(
        spend_eur=("fee_eur", "sum"),                       # free/loan = 0, undisclosed = missing (skipped)
        signings=("move_type", "size"),
        paid_signings=("move_type", lambda s: (s == "paid").sum()),
    ).reset_index()
    seasons = seasons.merge(spend, on=["team_id", "start"], how="left")
    seasons[["spend_eur", "signings", "paid_signings"]] = \
        seasons[["spend_eur", "signings", "paid_signings"]].fillna(0)
    seasons["spend_rel"] = seasons["spend_eur"] / seasons.groupby("start")["spend_eur"].transform("mean")

    # --- head coach at the start and end of each season ---
    coach = pd.read_sql(COACH_SQL, con).sort_values("date")
    by = coach.groupby(["team_id", "season"])["head_coach_id"]
    ends = pd.DataFrame({"first_coach": by.first(), "last_coach": by.last()}).reset_index()
    ends["start"] = ends["season"].str[:4].astype(int)
    seasons = seasons.merge(ends[["team_id", "start", "first_coach", "last_coach"]],
                            on=["team_id", "start"], how="left")

    # --- previous season (inner join = only clubs in the PL both seasons) ---
    prev = seasons[["team_id", "start", "points", "xgd_pg", "last_coach"]].rename(columns={
        "points": "points_prev", "xgd_pg": "xgd_prev", "last_coach": "prev_last_coach"})
    prev["start"] += 1
    df = seasons.merge(prev, on=["team_id", "start"], how="inner")

    df["d_points"] = df["points"] - df["points_prev"]
    df["d_xgd"] = df["xgd_pg"] - df["xgd_prev"]
    df["new_manager"] = (df["first_coach"] != df["prev_last_coach"]).astype(int)
    return df


def fit(formula: str, df: pd.DataFrame, label: str):
    model = smf.ols(formula, data=df).fit(cov_type="HC1")    # robust standard errors
    ci = model.conf_int()
    table = pd.DataFrame({
        "model": label, "term": model.params.index, "coef": model.params.values,
        "ci_low": ci[0].values, "ci_high": ci[1].values, "p_value": model.pvalues.values,
    })
    return model, table


def plot(df: pd.DataFrame, baseline) -> Path:
    df = df.assign(resid=baseline.resid)
    labels = ["Lowest 20%", "20-40%", "40-60%", "60-80%", "Highest 20%"]
    df["spend_group"] = pd.qcut(df["spend_rel"].rank(method="first"), 5, labels=labels)
    g = df.groupby("spend_group", observed=True)["resid"]
    mean, sem = g.mean(), g.sem()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, mean.values, yerr=1.96 * sem.values, capsize=5)
    ax.axhline(0, color="grey", linewidth=1)
    ax.set_xlabel("Summer spending relative to the league that summer")
    ax.set_ylabel("Points change vs. expected\n(after regression to the mean)")
    ax.set_title("Does summer spending buy points? (PL clubs, 2015/16–2025/26)")
    fig.tight_layout()
    path = FIGURES / "spending_effect.png"
    fig.savefig(path, dpi=150)
    return path


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    df = build_club_seasons(con)
    con.close()
    df["log_spend"] = np.log1p(df["spend_rel"])     # log(1 + x): compresses huge summers

    print(f"Club-seasons: {len(df)}  ({df['season'].nunique()} seasons, promoted clubs excluded)")
    print(f"Summer manager changes: {df['new_manager'].sum()} of {len(df)} club-seasons")
    print("League-average summer spend (EUR m):")
    print((df.groupby("season")["spend_eur"].mean() / 1e6).round(0).to_string(), "\n")

    top = df.nlargest(5, "spend_rel")[["season", "team", "spend_eur", "spend_rel", "d_points"]]
    top["spend_eur"] = (top["spend_eur"] / 1e6).round(0)
    print("Biggest relative spenders (spend in EUR m):")
    print(top.to_string(index=False), "\n")

    trimmed = df[df["spend_rel"] <= df["spend_rel"].quantile(0.95)]
    specs = [
        ("1 baseline",          "d_points ~ points_prev + xgd_prev", df),
        ("2 + spending",        "d_points ~ points_prev + xgd_prev + spend_rel", df),
        ("3 + new manager",     "d_points ~ points_prev + xgd_prev + spend_rel + new_manager", df),
        ("4 xG outcome",        "d_xgd ~ points_prev + xgd_prev + spend_rel + new_manager", df),
        ("5 robust: log spend", "d_points ~ points_prev + xgd_prev + log_spend + new_manager", df),
        ("6 robust: top 5% spenders removed",
                                "d_points ~ points_prev + xgd_prev + spend_rel + new_manager", trimmed),
    ]

    models, tables = [], []
    for label, formula, data in specs:
        model, table = fit(formula, data, label)
        models.append(model)
        tables.append(table)
        print(f"Model {label}   (R-squared {model.rsquared:.2f}, n={int(model.nobs)})")
        for _, r in table[table["term"] != "Intercept"].iterrows():
            print(f"  {r['term']:<12} {r['coef']:+7.3f}   [95% CI {r['ci_low']:+.3f}, {r['ci_high']:+.3f}]"
                  f"   p={r['p_value']:.3f}")
        print()

    df.to_csv(RESULTS / "spending_club_seasons.csv", index=False)
    pd.concat(tables).to_csv(RESULTS / "spending_models.csv", index=False)
    chart = plot(df, models[0])
    print(f"Saved results to {RESULTS} and chart to {chart}")




if __name__ == "__main__":
    main()