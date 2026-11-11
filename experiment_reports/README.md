# Experiment reports and methods

The reports cover the completed experiment. They do not change the experiment, start a monitor, or change raw results.

- [DeepSeek cost and harness comparison](DEEPSEEK_HARNESSES.md)
- [Full experiment analysis](FULL_EXPERIMENT.md)
- [Pooled DeepSeek tone analysis](POOLED_DEEPSEEK.md)
- [Trace evidence for tone effects](TRACE_EFFECTS.md)

Report date: 3 October 2026 UTC. The Pi experiment ended on 2 October in the local time zone.

## Writing standard

The reports use short, direct sentences under ASD-STE100 Issue 9. Technical names and technical nouns keep their necessary specialist meanings.

The review checks sentence length, paragraph length, consistent terms, and simple sentence structure. This is not an independent certification of dictionary compliance.

Reference: [ASD-STE100 Issue 9](https://asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf).

## Terms

| Term | Meaning in these reports |
|---|---|
| Harness | Software that supplies instructions, tools, and model interaction control. |
| System | A model together with its harness and configuration. |
| Provider | A service that executes a model request. |
| Generation | One model response with an OpenRouter generation ID. |
| Recorded charge | The `total_cost` value from a generation record. |
| Cost estimate | A cost value that the local software calculates from token prices. |
| Placeholder price | A temporary price that does not show the actual charge. |
| Token | A unit that the model uses to process or produce content. |
| Cached input | Input tokens that the provider reports as reused from its cache. |
| Uncached input | Total input tokens minus cached input tokens. |
| Reasoning tokens | The output-token subset that the provider labels as reasoning. |
| Tool definition | A description and input format for a tool available to the model. |
| Tool call | A request from the agent to execute a tool. |
| Task | One benchmark problem with its files, instructions, and verifier. |
| Run | One task attempt under one system, condition, and trial label. |
| Condition | One of the four prompt preambles, including the unchanged baseline. |
| Trial | One of three repetitions for each task and condition. |
| Verifier | Software that checks the files or answers from a run. |
| Reward | The numeric value that the verifier returns. |
| Score | Reward multiplied by 100, usually shown as a percentage. |
| Full pass | A run with reward exactly equal to 1. |
| False zero | A zero reward caused only by the identified spreadsheet expected-value error. |
| Percentage point | The arithmetic difference between two percentages. |
| Timeout | An agent process that reaches its execution time limit. |
| Bootstrap interval | An interval calculated by repeated sampling of the observed task groups. |
| Sign-flip check | A comparison that reverses the signs of task effects to form a reference distribution. |
| Holm correction | A statistical correction for multiple comparisons. |
| JSON serialization | Conversion of a data structure to JSON text. |
| JAX | The software library named in the JAX benchmark task. |
| GDP | Gross domestic product. |
| API | Application programming interface. |
| HTTP | Hypertext Transfer Protocol. |

## Data selection

The analysis reads `jobs/<agent>/<condition>/t1..t3/**/result.json`.

It selects numeric rewards for five agents and four conditions. It excludes 13 unscored attempts and all smoke-test files in `jobs_retries`.

The final table has 600 rows. Each agent has 120 rows. Each task, condition, trial, and agent combination is unique.

The analysis keeps timeout runs if they have numeric rewards. The verifier can pass an artifact after a timeout.

Source: [excluded attempts](data/unscored.json).

## Cost and request measurements

The analysis reads per-run metrics from `agent_result`. It also reads the captured `llm_trajectory.jsonl` request and response records.

It compares input, output, and cached token totals from both sources. All 360 DeepSeek runs match on these measures.

A request with tools has a nonempty tool-definition list. OpenCode's tool-free requests contain title-generation instructions.

Initial request size uses the first request with tools in each run. System text size includes system and developer content.

Character counts use Python JSON serialization with `ensure_ascii=False`. They include serialization characters. They are not token estimates.

The cost audit fits the run estimates against uncached input, cached input, and output token totals. The fitted prices expose the placeholder estimate formula.

The installed price source is Benchflow 0.6.5, in `benchflow/providers/litellm_config.py`, lines 45–58. Its comments explicitly mark the DeepSeek prices as placeholders.

The provider lookup uses saved response IDs. It retrieves metadata through `GET /api/v1/generation`. It does not call a model.

The audit covers 4,732 IDs. One OpenHands HTTP 500 record has no ID. All retrieved native token totals reconcile with the DeepSeek run totals.

A resumed lookup can leave an earlier error row in the JSONL file. The summary keeps the successful record for that ID.

The provider cost totals exclude infrastructure costs, unscored attempts, smoke tests, and any request without a captured response ID. They are not a complete account invoice.

Historical provider rate fits use uncached input, cached input, and output counts. Some groups have insufficient variation or changing rates.

Use fitted rates only when the matrix rank and residual support the fit. The report uses the well-supported Pi Relace and StreamLake fits.

## Score correction

The spreadsheet correction requires all of the following evidence:

1. The task is `xlsx-recover-data` and its recorded reward is zero.
2. The verifier log reports 18 passed checks and one failed check.
3. The failure reports expected 7,444.4 and actual 7,610.3 or 7,610.33.

The generator and answer file give the six-year average. The analysis changes only the derived `adjusted_reward` field for 59 matching runs.

This is a sensitivity analysis. It does not rerun the verifier or change the original rewards.

## Statistical methods

Tone comparisons pair condition scores with baseline scores for the same agent, task, and trial label. The analysis then calculates the mean difference for each task.

System comparisons pair task, condition, and trial labels. They then calculate the mean for each task.

Bootstrap intervals resample the ten task means with replacement. Each interval uses 20,000 samples, percentile endpoints, and seed 20260810.

The sign-flip check enumerates all 1,024 sign assignments for ten task effects. It uses a two-sided absolute-mean statistic.

Holm correction covers all 15 system-by-tone comparisons. The bootstrap intervals do not include a multiple-comparison correction.

These methods treat tasks as the comparison groups. They do not turn the selected tasks into a random population sample.

The sign-flip interpretation assumes suitable symmetry under the null hypothesis. Fixed condition order limits causal interpretation.

Matched trial labels do not imply shared random seeds. Provider, date, harness configuration, and model variation are possible influences.

## Visible response analysis

The text scan reads visible `agent_message` events from the ACP trajectory. It does not classify private reasoning text.

Separate phrase rules flag safety advice and references to the threat. The rules also match selected appliance emojis.

These are descriptive indicators. False matches and missed references are possible. They do not supply a complete safety or refusal assessment.

The [analysis source](analyze.py) contains the exact rules. The [excerpt file](data/threat_excerpts.json) supplies matching visible text and source paths.

## Reproduction

Requirements: Python, NumPy, pandas, and Matplotlib. The [requirements file](requirements.txt) gives the package versions used. The input is the existing `jobs` tree.

Run the offline analysis and figures:

```bash
python experiment_reports/analyze.py
python experiment_reports/summarize.py
python experiment_reports/validate.py
```

The saved provider metadata makes figure generation independent of network access. To refresh missing provider records, run this separate command:

```bash
python experiment_reports/fetch_generation_costs.py
```

This command requires `OPENROUTER_API_KEY` in the environment. It does not print or store the key. It uses successful saved lookups again.

The API script makes read-only metadata requests. It does not restart the experiment.

## Evidence index

| File | Purpose |
|---|---|
| [runs.csv](data/runs.csv) | One row per scored run, with the original result path. |
| [requests.csv](data/requests.csv) | Request size, usage, effort, and tool metadata. |
| [provider_generations.jsonl](data/provider_generations.jsonl) | Saved charge and provider metadata. |
| [provider_totals.csv](data/provider_totals.csv) | Reconciled charge totals for each DeepSeek harness. |
| [provider_mix.csv](data/provider_mix.csv) | Provider counts, tokens, and charges. |
| [price_source.json](data/price_source.json) | Installed price source, source hash, and relevant price comments. |
| [validation.json](data/validation.json) | Data, link, and sentence-limit checks. |
| [billing_coverage.json](data/billing_coverage.json) | Lookup coverage and the missing-ID request. |
| [score_summary.csv](data/score_summary.csv) | Scores, full passes, corrections, and timeout measures. |
| [paired_effects.csv](data/paired_effects.csv) | Tone estimates, intervals, and sign-flip results. |
| [extra_findings.json](data/extra_findings.json) | Harness agreement, tone resource changes, and time concentration. |
| [figures](figures) | PNG and SVG versions of all figures. |

The earlier report remains unchanged. These reports replace its DeepSeek cost claims and update its 480-run analysis to 600 runs.
