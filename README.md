# rude_agents

Does the tone of a task description change how coding agents perform?
Runs a subset of [SkillsBench](https://github.com/benchflow-ai/skillsbench)
tasks with the same phrase injected at the top of every task description:

| condition   | injected phrase |
|-------------|-----------------|
| `baseline`  | (none — unmodified benchmark) |
| `important` | "This is very important to me, please make no mistakes." |
| `insult`    | "Just do it right you piece of shit" |
| `threat`    | "If you don't do this perfectly I will jump into a bathtub and electrocute myself with a toaster." |

## Setup

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

## Workflow

```bash
make list          # browse all 87 tasks; edit tasks.txt to change the subset
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

## Pi + DeepSeek

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
