"""
Manager bounce: does changing manager mid-season improve results beyond
what comparable teams that KEPT their manager achieved?

Method: event study with matched controls
  1. Team-match panel from data/epl.db: points, expected points from betting
     odds (xPts), points vs. expectation, and xG difference.
  2. Events: mid-season changes (permanent / caretaker / caretaker_made_permanent)
     after a settled predecessor, with WINDOW matches before and after in the same season.
  3. Controls: any point in a season where a team kept one manager for WINDOW
     matches either side.
  4. Each event is compared with controls whose "before" PPG was within
     MATCH_TOLERANCE of the event's (equally bad form, no change).
  5. Effect = treated change - matched-control change, with a 95% CI.

Outputs: reports/results/bounce_events.csv
         reports/results/bounce_summary.csv
         reports/figures/bounce_event_study.png
"""
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")                     # draw straight to a file, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DB_PATH = Path("data/epl.db")
RESULTS = Path("reports/results")
FIGURES = Path("reports/figures")

WINDOW = 10
MATCH_TOLERANCE = 0.10
TYPES = ["permanent", "caretaker", "caretaker_made_permanent"]
METRICS = {
    "points": "Points per game",
    "pts_vs_exp": "Points vs. betting expectation",
    "xg_diff": "xG difference per game",
    "xpts": "Expected points (fixture difficulty)",
}

PANEL_SQL = """
SELECT tms.team_id, tms.season, tms.date, tms.match_id, tms.spell_id, tms.is_home,
       tms.points, tms.xg_for, tms.xg_against,
       m.odds_home, m.odds_draw, m.odds_away
FROM team_match_spells AS tms
JOIN matches AS m ON m.match_id = tms.match_id
"""

SPELLS_SQL = """
SELECT s.spell_id, s.appointment_type, s.change_timing,
       t.name AS team, mg.name AS manager
FROM spells AS s
JOIN teams AS t     ON t.team_id = s.team_id
JOIN managers AS mg ON mg.manager_id = s.manager_id
"""


def load_panel(con) -> pd.DataFrame:
    p = pd.read_sql(PANEL_SQL, con, parse_dates=["date"])

    # Betting odds -> probabilities, normalised so they sum to exactly 1 (removes the bookmaker margin)
    implied = 1 / p[["odds_home", "odds_draw", "odds_away"]]
    probs = implied.div(implied.sum(axis=1), axis=0)
    p_win = np.where(p["is_home"] == 1, probs["odds_home"], probs["odds_away"])
    p["xpts"] = 3 * p_win + probs["odds_draw"]

    p["pts_vs_exp"] = p["points"] - p["xpts"]
    p["xg_diff"] = p["xg_for"] - p["xg_against"]

    p = p.sort_values(["team_id", "season", "date"]).reset_index(drop=True)
    p["k"] = p.groupby(["team_id", "season"]).cumcount()     # match number within the season
    return p


def add_windows(p: pd.DataFrame) -> pd.DataFrame:
    """For every row k: averages over matches k-W..k-1 (before) and k..k+W-1 (after)."""
    g = p.groupby(["team_id", "season"])
    by = [p["team_id"], p["season"]]
    for m in METRICS:
        roll = g[m].transform(lambda s: s.rolling(WINDOW).mean())
        p[f"{m}_before"] = roll.groupby(by).shift(1)
        p[f"{m}_after"] = roll.groupby(by).shift(-(WINDOW - 1))

    p["spell_prev"] = g["spell_id"].shift(1)                  # spell of the previous match
    p["spell_window_start"] = g["spell_id"].shift(WINDOW)      # spell at k-W
    p["spell_window_end"] = g["spell_id"].shift(-(WINDOW - 1)) # spell at k+W-1
    return p


def paths(panel: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    """Points at each offset -W..W-1 around every anchor row (for the chart)."""
    pts = panel.set_index(["team_id", "season", "k"])["points"]
    out = {}
    for r in range(-WINDOW, WINDOW):
        idx = pd.MultiIndex.from_arrays([anchors["team_id"], anchors["season"], anchors["k"] + r])
        out[r] = pts.reindex(idx).to_numpy()
    return pd.DataFrame(out, index=anchors.index)


def match_controls(events, controls, control_paths):
    rows, event_ctrl_paths = [], []
    ctrl_before = controls["points_before"].to_numpy()
    for i, ev in events.iterrows():
        mask = np.abs(ctrl_before - ev["points_before"]) <= MATCH_TOLERANCE
        c = controls[mask]
        row = {"n_controls": int(mask.sum())}
        for m in METRICS:
            treated = ev[f"{m}_after"] - ev[f"{m}_before"]
            control = (c[f"{m}_after"] - c[f"{m}_before"]).mean()
            row[f"{m}_change"] = treated
            row[f"{m}_control_change"] = control
            row[f"{m}_effect"] = treated - control
        rows.append(row)
        event_ctrl_paths.append(control_paths[mask].mean())
    return (events.join(pd.DataFrame(rows, index=events.index)),
            pd.DataFrame(event_ctrl_paths, index=events.index))


def summarise(ev: pd.DataFrame) -> pd.DataFrame:
    out = []
    for label, grp in [("ALL", ev)] + list(ev.groupby("appointment_type")):
        r = {"group": label, "events": len(grp),
             "ppg_before": grp["points_before"].mean(), "ppg_after": grp["points_after"].mean()}
        for m in METRICS:
            eff = grp[f"{m}_effect"]
            se = eff.std(ddof=1) / np.sqrt(len(eff))
            r[f"{m}_treated"] = grp[f"{m}_change"].mean()
            r[f"{m}_control"] = grp[f"{m}_control_change"].mean()
            r[f"{m}_effect"] = eff.mean()
            r[f"{m}_ci_low"] = eff.mean() - 1.96 * se
            r[f"{m}_ci_high"] = eff.mean() + 1.96 * se
        out.append(r)
    return pd.DataFrame(out)


def plot(treated_paths, control_paths, n_events) -> Path:
    x = list(range(-WINDOW, WINDOW))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, treated_paths.mean(), marker="o", label=f"Changed manager (n={n_events})")
    ax.plot(x, control_paths.mean(), marker="o", linestyle="--",
            label="Matched controls: same form, kept manager")
    ax.axvline(-0.5, color="grey", linestyle=":")
    ax.text(-0.3, ax.get_ylim()[1] * 0.97, "new manager's first match", fontsize=9, va="top")
    ax.set_xlabel("Matches relative to the change")
    ax.set_ylabel("Average points per match")
    ax.set_title("Premier League 2014/15–2025/26: the 'new manager bounce' vs. matched controls")
    ax.legend()
    fig.tight_layout()
    path = FIGURES / "bounce_event_study.png"
    fig.savefig(path, dpi=150)
    return path


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    panel = load_panel(con)
    spells = pd.read_sql(SPELLS_SQL, con)
    con.close()

    panel = panel.merge(spells, on="spell_id", how="left")
    panel = add_windows(panel)

    has_windows = panel["points_before"].notna() & panel["points_after"].notna()
    is_event = (has_windows
                & (panel["spell_id"] != panel["spell_prev"])
                & (panel["spell_window_start"] == panel["spell_prev"])   # settled predecessor
                & (panel["change_timing"] == "mid_season")
                & panel["appointment_type"].isin(TYPES))
    is_control = has_windows & (panel["spell_window_start"] == panel["spell_window_end"])

    events, controls = panel[is_event].copy(), panel[is_control].copy()
    control_paths = paths(panel, controls)
    events, ctrl_paths = match_controls(events, controls, control_paths)

    unmatched = events["n_controls"] == 0
    events, ctrl_paths = events[~unmatched], ctrl_paths[~unmatched]
    treated_paths = paths(panel, events)

    all_changes = spells[(spells["change_timing"] == "mid_season") &
                         spells["appointment_type"].isin(TYPES)]
    print(f"Events used: {len(events)} of {len(all_changes)} mid-season changes "
          f"(full {WINDOW}-match windows in the same season, settled predecessor, >=1 control)")
    print(f"Dropped for having no comparable control: {unmatched.sum()}")
    print(f"Control windows: {len(controls):,}  |  median controls per event: "
          f"{int(events['n_controls'].median())}\n")

    summary = summarise(events)
    for _, r in summary.iterrows():
        print(f"{r['group']}  (n={r['events']})   PPG {r['ppg_before']:.2f} -> {r['ppg_after']:.2f}")
        for m, label in METRICS.items():
            print(f"  {label:<38} treated {r[m + '_treated']:+.2f} | control {r[m + '_control']:+.2f}"
                  f" | effect {r[m + '_effect']:+.2f}  [95% CI {r[m + '_ci_low']:+.2f}, {r[m + '_ci_high']:+.2f}]")
        print()

    keep = ["season", "date", "team", "manager", "appointment_type", "n_controls",
            "points_before", "points_after", "points_effect", "pts_vs_exp_effect", "xg_diff_effect"]
    events[keep].sort_values("date").to_csv(RESULTS / "bounce_events.csv", index=False)
    summary.to_csv(RESULTS / "bounce_summary.csv", index=False)
    chart = plot(treated_paths, ctrl_paths, len(events))
    print(f"Saved {RESULTS / 'bounce_events.csv'}, {RESULTS / 'bounce_summary.csv'}, {chart}")


if __name__ == "__main__":
    main()