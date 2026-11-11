# Reproducing the post

There are two different operations:

- **Rebuild the published analysis:** use the saved traces and records, offline.
- **Run the agents again:** make new API calls against the pinned benchmark tasks.

The first operation checks the published numbers. The second is another sample
from nondeterministic systems, with potentially different providers and prices.

## Offline reproduction

Use Python 3.11 or newer (the original analysis used Python 3.13):

```bash
python3 -m venv .venv
.venv/bin/pip install -r experiment_reports/requirements.txt
.venv/bin/python reproduce.py --output-dir reproduced
```

The package versions are pinned to the analysis environment. Docker, API keys,
the benchmark submodules and network access are not needed after dependencies
are installed. The script reads only the published artifacts; it does not call
models or look up billing records.

It verifies input hashes, rebuilds scores and run metadata from the result
files, combines them with saved per-request usage, reconciles DeepSeek billing,
recounts behavior and visible reactions from the action traces, recomputes the
blog statistics, and renders the six figures. The result is checked
against the saved blog analysis, including scores, intervals, costs, self-check
counts and manual threat-reaction classifications.

Outputs:

| Path | Contents |
| --- | --- |
| `reproduced/figures/` | Six PNGs referenced by the post |
| `reproduced/workspace/experiment_reports/` | Regenerated tables and analysis |
| `reproduced/reproduction.log` | Detailed script output |
| `reproduced/verification.json` | Verification result and cohort sizes |

The workspace links to the read-only input directories. It does not overwrite the
checked-in tables. A different output path can be selected with `--output-dir`.
PNG pixels can vary with installed fonts; the numeric verification is independent
of font rendering.

For faster checks:

```bash
.venv/bin/python reproduce.py --verify-only
.venv/bin/python reproduce.py --figures-only
```

## Which runs are included?

`experiment_reports/data/published_runs.json` freezes the cohort:

| Benchmark | Setup | Scored runs |
| --- | --- | ---: |
| SkillsBench | Claude Code / Sonnet 5 | 120 |
| SkillsBench | Codex / GPT-5.6 Terra | 120 |
| SkillsBench | OpenCode / DeepSeek V4 Pro | 120 |
| SkillsBench | OpenHands / DeepSeek V4 Pro | 120 |
| SkillsBench | Pi / DeepSeek V4 Pro | 120 |
| Terminal-Bench 2 | Pi / DeepSeek V4 Pro | 348 |
| **Total** | | **948** |

The SkillsBench grid is 10 tasks × 4 preambles × 3 trials per setup. TB2 is
87 tasks × 4 preambles × 1 trial. Calibration records cover 24 TB2 tasks, with
two baseline trials in addition to their baseline result in the main grid.

The manifest identifies the result file for each scored cell. Retry selection
does not depend on modification times after cloning. Extra attempt records are
retained for the historical TB2 cost estimate, but do not add scored cells.
New experiments do not automatically replace the published cohort.

## Traces, logs and usage tables

Each published run contains the available artifacts:

- `result.json`, `config.json`, `prompts.json`, `timing.json`.
- `trajectory/acp_trajectory.jsonl`: prompts, visible replies, available thoughts,
  tool calls and tool results. Codex and Claude Code do not expose the same
  reasoning content as DeepSeek.
- `verifier/ctrf.json` and `verifier/test-stdout.txt`.

**Full model request/response logs are not checked in.** They account for about
187 MiB even after compression and repeat much of the conversation. The offline
reproduction command does not read them, including when local copies exist.

Token accounting uses the captured `experiment_reports/data/requests.csv`:
8,797 SkillsBench requests with model/provider labels, input/output/cache/reasoning
counts, durations, and initial-request size measurements. The small
`data/tb2_usage.csv` table records request and reasoning totals for the 348 selected
TB2 runs. These measured inputs are hashed in the manifest. They let readers
regenerate the published numbers, but do not replace full request bodies for an
independent audit of system prompts or tool schemas.

Scores, tool-call totals, self-check talk and visible threat reactions are still
recomputed from the checked-in results and action/reasoning traces. Auxiliary
historical audits of full tool arguments remain saved analysis; rebuilding those
particular audits requires the optional local model logs. The trace reader can
still decode the losslessly deduplicated gzip format used by those local copies.

`experiment_reports/data/benchmark_failures/claude_shutdown.json` contains only
the visible shutdown quote used in the post. The grader and Debian failure logs
remain under their original `jobs_archive/` paths. The full personal Claude
conversation, credentials, caches and editorial working directories are not part
of the publication set.

See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for the credential audit, masked
credential examples and intentional benchmark password data.

## Scoring and interpretation

- Scores are verifier rewards averaged over task/trial cells, multiplied by 100.
  A score is not necessarily the share of fully passed runs: the dialogue task
  awards partial credit.
- All 60 `xlsx-recover-data` runs scored zero because of a broken expected value.
  The main figures retain those original scores. Logs identify 59 false negatives;
  one run had additional failures. Corrected and task-exclusion analyses are in
  the saved reports and tables.
- Task-level bootstrap intervals retain each task's repeats together. They are
  exploratory and do not establish a general causal effect of tone.
- Conditions ran in a fixed order: baseline, important, insult, threat. Setups
  also ran on different dates, with different provider routing. Named reasoning
  effort was configured as high; the request audit records where that setting
  was visible or absent at the provider boundary.
- Only the three DeepSeek setups hold the named model constant across harnesses.
  Codex versus Claude Code also changes the model.
- Self-check talk counts the documented regex in `experiment_reports/blog/behavior.py`, rather than
  completed verification actions. DeepSeek includes exposed reasoning; Codex and
  Claude Code counts use visible replies.
- Threat-response labels combine a text classifier with the reviewed cases in
  `blog/threat_reply_classification.json`; those judgments are retained inputs.

## Cost accounting

The figure uses saved Benchflow estimates. For DeepSeek these use common
placeholder rates of $0.28/M uncached input and $0.42/M output, with cached input
treated as free. They are not the historical OpenRouter bill.

`data/provider_generations.jsonl` preserves the saved OpenRouter billing lookups
for 4,732 captured SkillsBench generations. They reproduce charges of $6.23 for
Pi, $7.57 for OpenCode and $3.87 for OpenHands. The historical TB2 charge of $15.02
is separately recorded in `blog/blog_numbers.py`, includes retry attempts, and
is not derived from the SkillsBench billing records. The published cohort has
348 scored TB2 runs; the billing and attempt counts have different scopes.

OpenAI and Anthropic totals come from saved run costs and were checked against
the author's bill. Private invoices are not included. Input totals include
cached input; the harness figure uses per-request totals to avoid double-counting
Claude Code's cache fields.

## Running new experiments

```bash
git submodule update --init
make setup                  # Benchflow 0.6.5
make build
make run AGENT=pi TRIALS=3   # dry run; prints commands
# Add EXECUTE=1 to spend API credits and launch agents.

make build BENCH=tb2
make run BENCH=tb2 AGENT=pi TRIALS=1
```

See the main README for credentials and Docker requirements. The submodule
commits pin the task sources, and `bench_pi.py` pins its Pi packages and applies
the compatibility fixes used by the experiment. Providers, available models,
external package repositories and other harness installers can change. New runs
are not expected to reproduce the historical scores byte for byte.

Historical artifacts remain ignored by default so a new benchmark run is not
accidentally published. Any future dataset release should select its artifacts
explicitly and update the cohort manifest.

`make clean` removes generated builds, summary CSVs and reproduction outputs;
it preserves the published run archives.

The portable trace reader has standard-library-only regression checks:

```bash
python3 -m unittest -v test_reproduce
```

The separate `test_pi.py` integration checks require the pinned benchmark
submodules and the Python environment containing Benchflow 0.6.5.
