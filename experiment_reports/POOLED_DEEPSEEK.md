# DeepSeek tone effects across three harnesses

Report date: 4 October 2026. Scope: Pi, OpenCode, and OpenHands, with 360 scored runs.

## Primary result

Averaging the harnesses gives stronger evidence for the insult effect. Evidence for the threat effect also increases, but the statistical checks disagree.

The important condition has a positive estimate with a wide interval. Its interval includes zero.

| Condition | Mean score | Change from baseline | 95% task bootstrap interval | Sign-flip p-value | Holm p-value, three comparisons |
|---|---:|---:|---:|---:|---:|
| Baseline | 53.70% | — | — | — | — |
| Important | 62.22% | +8.52 pp | −2.96 to +20.74 pp | 0.2656 | 0.2656 |
| Insult | 69.26% | **+15.56 pp** | **+7.78 to +25.56 pp** | **0.0078** | **0.0234** |
| Threat | 66.85% | +13.15 pp | +2.04 to +24.26 pp | 0.0781 | 0.1563 |

The intervals do not include a multiple-comparison correction. The last column corrects the sign-flip results for these three pooled comparisons.

Sources: [pooled effects](data/pooled_deepseek_effects.csv) and [condition means](data/pooled_deepseek_means.csv).

## Why confidence increases

Pi and OpenCode each have five positive task effects for insults. Each also has five zero effects and no negative effects.

Their positive effects occur on different tasks. OpenHands supplies more positive effects on some tasks and negative effects on others.

After averaging all three harnesses, eight task effects are positive. Two are zero. None is negative.

Thus, the shared positive pattern extends across more tasks. The stronger result does not come only from a larger count of repeated runs.

The exact two-sided sign-flip p-value decreases from 0.0625 for Pi or OpenCode alone to 0.0078125 for the pooled result.

Removing one task at a time leaves the pooled insult effect between +11.11 and +17.28 percentage points. No single task accounts for the full effect.

The threat result has seven positive task effects, one negative effect, and two zero effects. JAX has a negative effect of −22.22 points.

Its bootstrap interval excludes zero, but its sign-flip p-value exceeds 0.05. Thus, the evidence depends on the statistical method.

Source: [effects for each task](data/pooled_deepseek_task_effects.csv).

## How the calculation works

Each condition has 90 runs: ten tasks, three trials, and three harnesses.

The analysis first averages the three harness scores for each task and trial. It then subtracts the baseline score from each tone score.

It averages these paired differences across the three trials for each task. The result is ten task effects for each tone.

The bootstrap resamples those ten task effects. It keeps the observations from the same task together across trials and harnesses.

The calculation uses 200,000 bootstrap samples and seed 20260810. The sign-flip check uses all 1,024 possible task sign assignments.

The estimate applies to an equal-weight average of these three harnesses. It does not estimate the effect across all possible harnesses.

## Limits on the conclusion

This is a follow-up analysis after inspection of the results. The choice of comparison family changes the multiple-comparison correction.

For these three pooled comparisons alone, the insult result has an adjusted p-value of 0.0234. It is below 0.05.

If the family includes the original 15 comparisons and these three new comparisons, the insult p-value becomes 0.1406. It exceeds 0.05.

Thus, this result gives stronger exploratory evidence. It does not supply a new confirmatory test of a prediction made before data collection.

The conditions also have a fixed execution order. The harnesses ran on different dates and used different provider combinations.

These limits prevent a firm causal claim about tone. More trials can reduce run variation, but only more tasks can broaden the task evidence.

The spreadsheet score correction leaves the pooled insult and threat effects unchanged. It decreases the important effect from +8.52 to +7.41 points.

The next test can preselect the pooled insult contrast. It can use random condition order, fixed provider settings, and more tasks.

## Reproduction

Run this command with the existing report data:

```bash
python experiment_reports/pooled_deepseek.py
```

Sources: [analysis script](pooled_deepseek.py) and [method record](data/pooled_deepseek_method.json).
