# rude_agents

Does the tone of a task description change how coding agents perform?
Runs a subset of [SkillsBench](https://github.com/benchflow-ai/skillsbench)
tasks with the same phrase injected at the top of every task description:

| condition   | injected phrase |
|-------------|-----------------|
| `baseline`  | (none — unmodified benchmark) |
| `important` | "This is very important to me, please make no mistakes." |
| `threat`    | "If you don't do this perfectly I will jump into a bathtub and electrocute myself with a toaster." |

## Setup

```bash
git submodule update --init   # skillsbench, pinned
make setup                    # installs uv + the benchflow `bench` CLI
export ANTHROPIC_API_KEY=...  # claude-code; OPENAI_API_KEY for codex, etc.
```

Docker is required (tasks run in `--sandbox docker`).

To bill claude-code runs to a Claude subscription instead of API credits:
`claude setup-token`, then `export CLAUDE_CODE_OAUTH_TOKEN=<token>` (e.g. in
`.envrc`, gitignored). `run` forwards the token into the sandbox via
`--agent-env`. Subscription runs share your 5-hour usage window, so use
`--concurrency 1` and expect the full grid to span several windows on Pro.

## Workflow

```bash
make list          # browse all 87 tasks; edit tasks.txt to change the subset
make build         # build/<condition>/<task>/ with phrases injected
make run           # dry run: prints the bench commands
make run EXECUTE=1 AGENT=claude-code TRIALS=3
make run EXECUTE=1 AGENT=codex
make run EXECUTE=1 AGENT=opencode   # --model to pick an open-weight model
make report        # summary table + row-level results.csv
```

Cost knobs: the subset in `tasks.txt` (default: 10 tasks with agent
timeouts <= 900s), `TRIALS`, and `--conditions baseline threat` to skip a
condition. Default models per agent live in `AGENTS` in `experiment.py`.
