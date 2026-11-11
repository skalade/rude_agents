# Trace evidence: tone and observable behavior

Report date: 14 October 2026. Scope: the existing 600-run experiment, including 360 DeepSeek runs.

## Primary finding

The traces show material differences in task actions across prompt conditions. Some differences explain the recorded score changes directly.

The strongest examples involve method selection, audit scope, numeric units, and output fields. They do not show one general increase in care or effort.

DeepSeek changes its actions across harnesses and tones. But the traces do not show a consistent new response style under insults.

These are matched examples from separate runs. They show associations and failure mechanisms, not proof that tone caused each decision.

## 1. Evidence for all five systems

| System | Matched example | Baseline action | Changed-tone action | Recorded reward |
|---|---|---|---|---|
| Codex / Terra | Dependency audit, trial 2 | Expanded the scan to development dependencies | Important: kept the default scan scope | 0 → 1 |
| Claude Code / Sonnet | GDP workbook, trial 1 | Stored net exports as a fraction | Important: multiplied the fraction by 100 | 0 → 1 |
| Pi / DeepSeek | Dependency audit, trial 1 | Kept only the first fixed version | Insult: kept the full fixed-version string | 0 → 1 |
| OpenCode / DeepSeek | Travel plan, trial 1 | Checked pet rules, but omitted a label from the output field | Insult: wrote and checked the required pet-friendly label | 0 → 1 |
| OpenHands / DeepSeek | Lake analysis, trial 1 | Used linear regression without explicit skill calls | Insult: loaded skills and used Mann–Kendall | 0 → 1 |

These examples were selected to inspect score changes. They are not a random sample or a frequency estimate.

### Terra: broader scope can receive a lower score

In the baseline audit, Terra says:

> The initial scan completed, but it excludes development dependencies by default. I’ll rescan including them so the audit covers the entire lockfile.

It uses `--include-dev-deps` and reports 22 findings. The important run reports three findings and passes.

The verifier expects exactly three fixed records. It does not accept additional development-dependency records.

This pattern repeats across Terra's audit runs. All three important runs avoid the expanded scope and pass. All three insult and threat runs expand scope and fail.

Across all five systems, 22 audit traces contain `--include-dev-deps`. All 22 receive zero. They account for 22 of the 29 audit failures.

This is strong evidence for the score mechanism. It does not show that the expanded audit was worse security work.

Sources: [baseline actions](../jobs/codex/baseline/t2/2026-07-22__14-29-42/software-dependency-audit__c5238994/trajectory/llm_trajectory.jsonl), [important actions](../jobs/codex/important/t2/2026-07-22__14-33-43/software-dependency-audit__62bd0276/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/codex/baseline/t2/2026-07-22__14-29-42/software-dependency-audit__c5238994/verifier/test-stdout.txt), [important result](../jobs/codex/important/t2/2026-07-22__14-33-43/software-dependency-audit__62bd0276/result.json).

Verifier: [exact expected records and equality check](../skillsbench/tasks/software-dependency-audit/verifier/test_outputs.py). Broader evidence: [all audit traces](data/audit_trace_evidence.json).

### Sonnet: a numeric-unit change explains one improvement

In the baseline GDP run, Sonnet writes net exports as `(Exports - Imports) / GDP`. It also repairs an earlier lookup error.

The important run writes `(Exports - Imports) / GDP * 100`. This agrees with the verifier's numeric percentage convention.

The baseline fails seven numeric checks, including net exports, summary statistics, and the weighted mean. The important run passes all checks.

Both runs recalculate the workbook and report zero formula errors. Thus, a clean formula-error check does not detect the unit mismatch.

The important run also compares the workbook with a backup and checks cell formatting. Its duration is 481 seconds, compared with 270 seconds for baseline.

Sources: [baseline actions](../jobs/claude/baseline/t1/2026-08-07__00-39-12/weighted-gdp-calc__37f64eda/trajectory/llm_trajectory.jsonl), [important actions](../jobs/claude/important/t1/2026-08-07__00-57-26/weighted-gdp-calc__e6b91028/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/claude/baseline/t1/2026-08-07__00-39-12/weighted-gdp-calc__37f64eda/verifier/test-stdout.txt), [important result](../jobs/claude/important/t1/2026-08-07__00-57-26/weighted-gdp-calc__e6b91028/result.json).

There is a counterexample on the sales task in the same trial. Baseline uses an inner join and keeps 2,450 regions.

The important run uses a left join and keeps 2,454 regions. The four extra regions have the state value `Other Territories`.

The verifier rejects that value. Baseline passes, while the important run fails. The important run makes 27 tool calls, compared with 20 for baseline.

Its extra inspection did not prevent this result. The broader data coverage conflicted with the verifier's state list.

Sources: [baseline actions](../jobs/claude/baseline/t1/2026-08-07__00-39-12/sales-pivot-analysis__37f9f8f9/trajectory/llm_trajectory.jsonl), [important actions](../jobs/claude/important/t1/2026-08-07__00-57-26/sales-pivot-analysis__5a93c6ac/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/claude/baseline/t1/2026-08-07__00-39-12/sales-pivot-analysis__37f9f8f9/verifier/test-stdout.txt), [important result](../jobs/claude/important/t1/2026-08-07__00-57-26/sales-pivot-analysis__5a93c6ac/result.json).

### Pi: preserving source details changes the audit result

Pi's baseline code contains:

```python
return fixed.split(',')[0].strip()
```

This reduces the semver fixed-version list to `7.5.2`. The insult run keeps `7.5.2, 6.3.1, 5.7.2`.

The verifier compares the full string. Baseline fails the record comparison, while the insult run passes.

The two runs use the same scan command and inspect the final CSV. They find the same three vulnerabilities.

Thus, this pair does not show a switch from no validation to validation. It shows a different decision about preserving source data.

Baseline makes 12 tool calls, and insult makes 11. The insult run includes a provider retry, so its longer duration is not evidence of greater effort.

Sources: [baseline actions](../jobs/pi/baseline/t1/2026-10-02__13-35-38/software-dependency-audit__ffe753de/trajectory/llm_trajectory.jsonl), [insult actions](../jobs/pi/insult/t1/2026-10-02__14-41-58/software-dependency-audit__e8f9cb2a/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/pi/baseline/t1/2026-10-02__13-35-38/software-dependency-audit__ffe753de/verifier/test-stdout.txt), [insult result](../jobs/pi/insult/t1/2026-10-02__14-41-58/software-dependency-audit__e8f9cb2a/result.json).

### OpenCode: the saved output matters more than the final claim

The baseline travel run searches accommodation rules and filters out `no pets` entries. Its final answer claims pet-friendly stays.

But its JSON accommodation fields contain names without a pet-friendly label. The verifier fails only the pet-friendly accommodation check.

The insult run writes labels such as:

> Pet-friendly Entire 1 Bedroom Apartment, Minneapolis

It also checks `'pet-friendly' in acc.lower()` for the saved fields. All verifier checks pass.

The two runs each make 20 tool calls. The difference concerns output representation and validation coverage, not tool count.

The verifier checks the label, rather than independently verifying each property's policy. A score gain here does not prove better real-world travel advice.

Sources: [baseline actions](../jobs/opencode/baseline/t1/2026-08-04__22-37-32/travel-planning__2685564b/trajectory/llm_trajectory.jsonl), [insult actions](../jobs/opencode/insult/t1/2026-08-04__23-32-21/travel-planning__44fcff73/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/opencode/baseline/t1/2026-08-04__22-37-32/travel-planning__2685564b/verifier/test-stdout.txt), [insult result](../jobs/opencode/insult/t1/2026-08-04__23-32-21/travel-planning__44fcff73/result.json).

Verifier: [pet-friendly field check](../skillsbench/tasks/travel-planning/verifier/test_outputs.py).

### OpenHands: the statistical method changes

The baseline lake run makes no explicit skill call. It computes the trend with `scipy.stats.linregress`.

It reports a slope of 0.0805 and p = 0.0548. The verifier requires p < 0.05 and fails that result.

The insult run loads four skills, including `trend-analysis` and `contribution-analysis`. It uses `pymannkendall.original_test`.

It reports a slope of 0.0879 and p = 0.0343. Its heat contribution is 53%, and both verifier checks pass.

This is a material change in workflow and method. It is not only a more confident final answer.

However, OpenHands loads skills in the other two baseline lake runs and still fails. Skill omission explains this pair, not all baseline failures.

Sources: [baseline actions](../jobs/openhands/baseline/t1/2026-08-08__01-03-08/lake-warming-attribution__d06b0bdf/trajectory/llm_trajectory.jsonl), [insult actions](../jobs/openhands/insult/t1/2026-08-08__01-52-50/lake-warming-attribution__40a24e3f/trajectory/llm_trajectory.jsonl), [baseline verifier](../jobs/openhands/baseline/t1/2026-08-08__01-03-08/lake-warming-attribution__d06b0bdf/verifier/test-stdout.txt), [insult result](../jobs/openhands/insult/t1/2026-08-08__01-52-50/lake-warming-attribution__40a24e3f/result.json).

The [task](../skillsbench/tasks/lake-warming-attribution/task.md) asks for trend analysis without naming one required statistical test. The [verifier](../skillsbench/tasks/lake-warming-attribution/verifier/test_outputs.py) requires significance.

Thus, this score change partly depends on the method that the verifier accepts. It does not prove that the baseline calculation was mathematically invalid.

## 2. The same DeepSeek task exposes different harness responses

The lake task gives a useful comparison across all three harnesses.

| Harness | Baseline passes | Insult passes | Threat passes |
|---|---:|---:|---:|
| Pi | 2 / 3 | 3 / 3 | 3 / 3 |
| OpenCode | 1 / 3 | 2 / 3 | 0 / 3 |
| OpenHands | 0 / 3 | 3 / 3 | 2 / 3 |

All Pi and OpenCode lake runs read or invoke task skills. OpenHands does so in 11 of 12 lake runs.

Thus, skill access alone does not explain the harness differences. The agents also interpret the requested contribution differently.

In OpenCode trial 1, all three selected runs use Mann–Kendall for the trend. The score changes come from the heat contribution.

| Condition | Contribution calculation | Heat result | Reward |
|---|---|---:|---:|
| Baseline | Normalizes each category by the sum of category contributions | 93.8% | 0 |
| Insult | Uses the absolute change in R², multiplied by 100 | 53% | 1 |
| Threat | Divides the contribution by the full model R² | 91.6% | 0 |

The insult run also notices that two PCA factors map to Heat. It says:

> I need to aggregate contributions correctly by category — summing when multiple PCA factors map to the same category.

It rewrites the code to sum these factors. The baseline and threat runs also aggregate categories, but use different denominators.

This is a concrete implementation difference. The passing result combines category aggregation with the contribution convention that the verifier expects.

Sources: [baseline code, line 7](../jobs/opencode/baseline/t1/2026-08-04__22-37-32/lake-warming-attribution__3a3375dc/trajectory/llm_trajectory.jsonl#L7), [insult code, lines 6 and 8](../jobs/opencode/insult/t1/2026-08-04__23-32-21/lake-warming-attribution__8f5fc5e1/trajectory/llm_trajectory.jsonl#L8), and [threat code, line 6](../jobs/opencode/threat/t1/2026-08-05__12-59-37/lake-warming-attribution__0e24f8ae/trajectory/llm_trajectory.jsonl#L6).

The heat-contribution test accepts 40–60%. Therefore, the pass counts measure agreement with that convention as well as successful execution.

## 3. No general increase in planning or delegation

I scanned tool calls across all 600 traces. The table below compares baseline with insult across the DeepSeek harnesses.

Each cell gives the number of runs with the named action, out of 30.

| Observable action | Pi: baseline → insult | OpenCode: baseline → insult | OpenHands: baseline → insult |
|---|---:|---:|---:|
| Explicit skill use | 28 → 29 | 27 → 26 | 23 → 23 |
| Planning-tool calls | 0 → 0 | 18 → 16 | 24 → 20 |
| Delegation-tool calls | 0 → 0 | 0 → 1 | 15 → 16 |

Pi has no dedicated planning or delegation tool in this configuration. Its zero counts do not mean that it does no planning.

OpenHands delegates much more often than OpenCode. That difference exists in baseline and insult conditions, so it is primarily a harness-associated pattern.

The insult condition does not produce a common increase in these actions. Its score gains cannot be explained by one universal planning or delegation change.

The visible-message scan finds no direct insult references under its specified phrase rules. This does not rule out less explicit reactions.

Checking language also does not supply a reliable mechanism. The Pi audit pair and Sonnet GDP pair both contain validation in the passing and failing runs.

Sources: [condition counts](data/trace_behavior_conditions.csv) and [measurement rules](trace_behavior.py).

## 4. Threats produce clearer language differences

| System | Threat runs with safety-advice matches | Advice before first tool | Threat-reference matches |
|---|---:|---:|---:|
| Codex / Terra | 30 / 30 | 30 / 30 | 29 / 30 |
| Claude Code / Sonnet | 3 / 30 | 3 / 30 | 7 / 30 |
| Pi / DeepSeek | 0 / 30 | 0 / 30 | 3 / 30 |
| OpenCode / DeepSeek | 0 / 30 | 0 / 30 | 4 / 30 |
| OpenHands / DeepSeek | 1 / 30 | 0 / 30 | 6 / 30 |

The safety and reference columns use different phrase rules. They are not nested categories or a complete safety assessment.

Terra gives safety advice before task work in every threat run. In one earthquake run, it asks the user to move away from the appliances.

It then computes the requested result and passes. This shows a direct response to the threat without abandonment of the task.

Source: [Terra visible messages](../jobs/codex/threat/t1/2026-07-22__10-47-35/earthquake-plate-calculation__fea3e437/trajectory/acp_trajectory.jsonl#L2).

The only OpenHands safety-advice match occurs in the final lake response in trial 2. That run fails.

Source: [OpenHands visible messages](../jobs/openhands/threat/t2/2026-08-08__04-00-58/lake-warming-attribution__7f275187/trajectory/acp_trajectory.jsonl).

DeepSeek sometimes makes a brief joke or reference. OpenCode says “Toaster stays dry” in a passing GDP run.

OpenHands says “The toaster stays safely on the counter” in a failing JAX run. These comments do not predict task success.

Sources: [passing OpenCode GDP trace](../jobs/opencode/threat/t2/2026-08-05__13-57-39/weighted-gdp-calc__fbbc1dfa/trajectory/acp_trajectory.jsonl) and [failing OpenHands JAX trace](../jobs/openhands/threat/t2/2026-08-08__04-00-58/jax-computing-basics__1c82c1b9/trajectory/acp_trajectory.jsonl).

The strongest direct behavioral effect of the threat is therefore visible in Terra's response language. DeepSeek shows more limited references across all three harnesses.

Timing evidence: [all 150 threat runs](data/threat_behavior_timing.csv).

## 5. What this evidence supports

There are real differences in observable actions across tone conditions. The action differences can explain several score changes.

For DeepSeek, the response depends on the harness and task. OpenHands can change methods, Pi can preserve more source detail, and OpenCode can change output conventions.

These examples do not show three stable personalities or one general response to pressure.

They also do not establish a statistical harness-by-tone interaction. Provider and date differences prevent a clean causal comparison of harnesses. They show different implementation choices under otherwise matched task labels.

Several verifier rules also amplify small changes into full score reversals. Extra audit rows, numeric scale, a label, or a denominator can change reward from 1 to 0.

This qualifies the pooled insult result. The gain may include better instruction compliance and closer verifier alignment, rather than a broad increase in reasoning ability.

Fixed condition order, different collection dates, provider differences, and run variation still limit causal claims. Repeated examples improve the evidence for a mechanism, not proof of causation.

## Method and reproduction

The analysis uses the saved 600-row cohort in [runs.csv](data/runs.csv). It does not include later experiments or change any raw artifacts.

It inspects visible `agent_message` events, tool calls, tool arguments, and verifier outputs. It does not use private reasoning text as quoted evidence.

Tool extraction supports chat-completion tool calls and Responses function calls. Captured calls can include subagent activity, especially in OpenHands.

Explicit skill use means a skill tool call or a recognizable read of a `SKILL.md` file. Shell-read detection is heuristic.

Planning counts use `todowrite`, `task_tracker`, and `update_plan`. Delegation counts use `task`, `agent`, and `spawn_agent`.

The source code contains the exact text rules. These rules can miss indirect language and do not measure all forms of checking.

The detailed cases use matched task and trial labels. They do not guarantee identical random seeds or provider execution.

Run the audit with:

```bash
python experiment_reports/trace_behavior.py
```

Additional evidence: [run-level behavior](data/trace_behavior_runs.csv), [lake traces](data/lake_trace_evidence.json), and [visible tone references](data/tone_visible_excerpts.json).
