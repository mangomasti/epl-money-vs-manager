# Findings

## Q1: Is the "new manager bounce" real?

**Mostly not. About 86% of it happens anyway.**

![Event study chart](figures/bounce_event_study.png)

Teams that change manager mid-season are in relegation form (0.78 points per game over the previous 10 matches) and improve sharply afterwards (1.22 PPG). But teams in the **same** form, including a similar recent slump, that **kept** their manager improved almost as much.

| (61 mid-season changes) | Changed manager | Kept manager | Effect | 95% CI |
|---|---|---|---|---|
| Points per game | +0.44 | +0.38 | **+0.06** | −0.07 to +0.19 |
| Points vs. betting expectation | +0.45 | +0.36 | +0.09 | −0.02 to +0.20 |
| xG difference per game | +0.27 | +0.24 | +0.04 | −0.10 to +0.18 |
| Expected points (fixture difficulty) | −0.01 | +0.02 | −0.02 | −0.07 to +0.02 |

- **Results:** no reliable effect. The confidence interval includes zero. The recovery is mostly **regression to the mean**: clubs sack managers at an unusually bad moment, and unusually bad runs end regardless.
- **Fixtures** don't explain the recovery: expected points from betting odds barely change.
- **Caretakers vs. permanent managers:** both get a similar bump in results. Only permanent appointments show better **underlying performance** (xG difference +0.22 per game, 95% CI +0.01 to +0.42), while caretakers show none (−0.05). **Suggestive, not conclusive** (see limitations).

### Method

Event study with matched controls (`src/analysis/manager_bounce.py`):
- **Events:** mid-season changes with a settled predecessor and 10 matches before and after in the same season.
- **Controls:** windows where a team kept the same manager for 10 matches either side.
- **Matching:** each event is compared with controls within ±0.10 PPG over the previous 10 matches **and** within 1 point over the previous 3.
- **Effect:** the treated team's change minus the matched controls' average change.
- **Version history:** matching on 10-game form only (v1) gave +0.08 PPG; adding recent form (v2) gave +0.06. Better controls, smaller effect.

### Limitations

- Only 61 of 127 mid-season changes have full windows in the same season. Late-season changes and changes quickly followed by another are excluded.
- **16 comparisons** were run (4 metrics × 4 groups), so one borderline "significant" result could be chance.
- Control windows overlap (the same team in neighbouring weeks), so the confidence intervals are somewhat too narrow.
- Sacked teams' last 2 matches before the change were worse than their controls' (≈0.3 vs ≈0.5 PPG). If anything, this makes the estimated effect **too large**.
- Observational data: clubs choose *when* to sack, so no method fully removes that choice.