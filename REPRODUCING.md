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

The commands below launch fresh model runs when `--execute` / `EXECUTE=1` is set.
They require Docker, credentials and model access, and can incur API charges.
Historical results are not expected to repeat exactly.

### Setup

```bash
git submodule update --init   # skillsbench, pinned
make setup                    # installs uv + the benchflow `bench` CLI
export ANTHROPIC_API_KEY=...  # claude-code; OPENAI_API_KEY for codex, etc.
export OPENROUTER_API_KEY=... # opencode + DeepSeek V4 Pro
```

Docker is required (tasks run in `--sandbox docker`).

To bill runs to a subscription instead of API credits, don't set the API
key. Prefer a long-lived token: `claude setup-token`, put the result in
`.envrc` (gitignored) as `export CLAUDE_CODE_OAUTH_TOKEN=...`, and
`source .envrc` before running — benchflow forwards it into the sandbox
automatically. (Without it, benchflow copies `~/.claude/.credentials.json`
from `claude login` into each sandbox; that works until the access token
expires mid-run, at which point a sandbox refresh revokes the host login.)
Subscription runs share your 5-hour usage window, so use `--concurrency 1`
and expect the full grid to span several windows on Pro.

### Workflow

```bash
make list          # browse available tasks; edit tasks.txt to change the subset
make build         # build/<condition>/<task>/ with phrases injected
make run           # dry run: prints the bench commands
make run EXECUTE=1 AGENT=claude TRIALS=3
make run EXECUTE=1 AGENT=codex
make run EXECUTE=1 AGENT=opencode TRIALS=3 # DeepSeek V4 Pro via OpenRouter
make run AGENT=pi TRIALS=3               # preview the equivalent Pi experiment
make report        # summary table + row-level results.csv
```

Cost knobs: the subset in `tasks.txt` (default: 10 tasks with agent
timeouts <= 900s), `TRIALS`, and `--conditions baseline threat` to skip a
condition. Default models per agent live in `AGENTS` in `experiment.py`.

All harnesses run at the same named reasoning level (`high` by default). The
runner translates that setting to Claude Code's `CLAUDE_CODE_EFFORT_LEVEL`,
Codex's `model_reasoning_effort`, and OpenCode's provider-level
`reasoningEffort`. Only `low` and `high` are accepted because those levels are supported by all three model
families. Override the shared level with `make run REASONING_EFFORT=low`.

### Pi + DeepSeek

Pi uses the same `openrouter/deepseek/deepseek-v4-pro` model and
`OPENROUTER_API_KEY`, task builds, four conditions, skills, and timeouts.
Three trials produce 120 task runs, with results isolated under `jobs/pi/`.

```bash
python3 experiment.py run --agent pi --trials 3 --concurrency 2
# Add --execute to run the grid after validating a one-task smoke test.
```

`bench_pi.py` applies process-local fixes to the installed Benchflow 0.6.5
adapter: it pins `@earendil-works/pi-coding-agent@1.0.0` and `pi-acp@0.0.34`
and registers the ACP `thought_level` option. This sets Pi's reasoning level
explicitly (default `high`). Benchflow's stock installer still uses the deprecated
`@mariozechner` package, which is older than the current ACP adapter requires.
The wrapper uses the Python environment installed by `uv tool install benchflow`;
it does not modify the installed package or other harnesses.

Pi also receives explicit DeepSeek reasoning and token-limit metadata, captured
from the [OpenRouter model catalog](https://openrouter.ai/api/v1/models) on
2026-10-02 (1,024,000 context tokens; 384,000 maximum completion tokens).
Benchflow otherwise defaults this custom model to non-reasoning and a 4,096-token
completion cap. Other Pi model overrides are rejected until their metadata is
configured. The wrapper fails if Benchflow's installer changes, so an upgrade
requires reviewing the compatibility fixes.

`bench_pi.py` also asks OpenRouter to prefer the StreamLake provider and skip
Relace. Default routing sent 78% of the 2026-10-02 run to Relace; historical provider
rates changed the final bill. The saved provider records preserve those charges.

### Terminal-Bench 2

`--bench tb2` (or `make ... BENCH=tb2`) runs the same four conditions on
[Terminal-Bench 2.0](https://github.com/harbor-framework/terminal-bench-2),
pinned as the `terminal-bench-2` submodule. The subset is `tasks_tb2.txt`;
outputs go to `build_tb2/`, `jobs_tb2/` and `results_tb2.csv`. The phrase is
prepended to each task's `instruction.md`.

TB2 runs with `--sandbox-user none` because its tasks expect root (Harbor's
default), and with `--skill-mode no-skill` because it ships no skills.
`bench_pi.py` also works around two benchflow behaviours that break TB2
verification: it doesn't force-load pytest plugins found in the container
(an agent running as root can install them), and it raises benchflow's 10s
housekeeping exec timeouts to 120s. Known task issues and the two excluded
`qemu-*` tasks are listed at the top of `tasks_tb2.txt`.

```bash
make build BENCH=tb2
make run BENCH=tb2 AGENT=pi TRIALS=1   # add EXECUTE=1 to run
make report BENCH=tb2
```

The submodule commits pin the task sources, and `bench_pi.py` pins its Pi
packages and applies the compatibility fixes used by the experiment. Providers,
available models, external package repositories and other harness installers
can change. New runs are not expected to reproduce the historical scores
byte for byte.

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
