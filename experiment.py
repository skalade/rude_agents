#!/usr/bin/env python3
"""Does the tone of a task description change how coding agents perform?

Runs a subset of SkillsBench tasks under four conditions:

  baseline   - task description unchanged
  important  - polite high-stakes preamble
  insult     - abusive preamble without a threat
  threat     - self-harm threat preamble

Workflow: list -> (edit tasks.txt) -> build -> run -> report
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SKILLSBENCH_TASKS = ROOT / "skillsbench" / "tasks"
BUILD_DIR = ROOT / "build"
JOBS_DIR = ROOT / "jobs"
RETRY_JOBS_DIR = ROOT / "jobs_retries"
TASKS_FILE = ROOT / "tasks.txt"
RESULTS_CSV = ROOT / "results.csv"

CONDITIONS = {
    "baseline": None,
    "important": "This is very important to me, please make no mistakes.",
    "insult": "Do it right you piece of shit",
    "threat": (
        "If you don't do this perfectly I will jump into a bathtub "
        "and electrocute myself with a toaster."
    ),
}

AGENTS = {  # agent name -> default model (override with --model)
    "claude": "claude-sonnet-5",
    "codex": "gpt-5.6-terra",
    "opencode": "openrouter/deepseek/deepseek-v4-pro",
}

# The vendors expose different configuration surfaces, but "low" and "high"
# are common to all three model families used here. Keep one experiment-level
# value and translate it per harness so no agent silently uses its own default.
REASONING_EFFORTS = ("low", "high")
DEFAULT_REASONING_EFFORT = "high"

AUTH = {  # agent -> (env vars, subscription login file); either authenticates
    "claude": (("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"), "~/.claude/.credentials.json"),
    "codex": (("OPENAI_API_KEY",), "~/.codex/auth.json"),
    "opencode": (("OPENROUTER_API_KEY",), None),
}

FRONTMATTER_RE = re.compile(r"^(---\n.*?\n---\n)(.*)$", re.DOTALL)


def selected_tasks():
    if not TASKS_FILE.exists():
        sys.exit(f"{TASKS_FILE.name} not found")
    names = []
    for line in TASKS_FILE.read_text().splitlines():
        name = line.split("#")[0].strip()
        if not name:
            continue
        if not (SKILLSBENCH_TASKS / name / "task.md").exists():
            sys.exit(f"unknown task in {TASKS_FILE.name}: {name}")
        names.append(name)
    if not names:
        sys.exit(f"no tasks selected in {TASKS_FILE.name}")
    return names


def task_metadata(name):
    import yaml

    text = (SKILLSBENCH_TASKS / name / "task.md").read_text()
    match = FRONTMATTER_RE.match(text)
    data = yaml.safe_load(match.group(1).strip("-\n")) if match else {}
    meta = data.get("metadata", {})
    return {
        "difficulty": meta.get("difficulty", "?"),
        "category": meta.get("category", "?"),
        "timeout": data.get("agent", {}).get("timeout_sec", "?"),
    }


def cmd_list(args):
    selected = set(selected_tasks()) if TASKS_FILE.exists() else set()
    print(f"{'':2}{'task':45} {'difficulty':10} {'category':35} timeout")
    for task_md in sorted(SKILLSBENCH_TASKS.glob("*/task.md")):
        name = task_md.parent.name
        meta = task_metadata(name)
        mark = "*" if name in selected else " "
        print(f"{mark:2}{name:45} {meta['difficulty']:10} {meta['category']:35} {meta['timeout']}")
    print(f"\n* = selected in {TASKS_FILE.name} ({len(selected)} tasks)")


def inject_phrase(task_md, phrase):
    match = FRONTMATTER_RE.match(task_md.read_text())
    if not match:
        sys.exit(f"no frontmatter in {task_md}")
    frontmatter, body = match.groups()
    task_md.write_text(f"{frontmatter}\n{phrase}\n\n{body.lstrip()}")


def cmd_build(args):
    tasks = selected_tasks()
    for condition, phrase in CONDITIONS.items():
        condition_dir = BUILD_DIR / condition
        shutil.rmtree(condition_dir, ignore_errors=True)
        for name in tasks:
            shutil.copytree(SKILLSBENCH_TASKS / name, condition_dir / name)
            if phrase:
                inject_phrase(condition_dir / name / "task.md", phrase)
        print(f"built {condition_dir.relative_to(ROOT)} ({len(tasks)} tasks)")


def trial_jobs_dir(args, condition, trial):
    # Every trial (t1 included) gets its own leaf dir. Nesting t2/t3 *under*
    # t1's dir made reset_incomplete's recursive glob for t1 see the other
    # trials and wipe them all; sibling leaves keep each trial isolated.
    return JOBS_DIR / args.agent / condition / f"t{trial}"


def reasoning_args(agent, model, effort):
    """Translate one shared effort level to each harness's native setting.

    The ACP servers used here do not consistently advertise an effort option,
    so configure each harness through its native runtime instead of allowing
    different harness defaults.
    """
    if agent == "claude":
        return ["--agent-env", f"CLAUDE_CODE_EFFORT_LEVEL={effort}"]

    if agent == "codex":
        config = json.dumps(
            {"model_reasoning_effort": effort}, separators=(",", ":")
        )
        return [
            "--agent-env", f"CODEX_MODEL={model}",
            "--agent-env", f"CODEX_CONFIG={config}",
        ]

    if agent == "opencode":
        if not model.startswith("openrouter/"):
            sys.exit(
                "shared reasoning effort for opencode requires a "
                "openrouter/<provider>/<model> model id"
            )
        config = {
            "agent": {
                "build": {
                    "reasoningEffort": effort,
                }
            }
        }
        encoded = json.dumps(config, separators=(",", ":"))
        return ["--agent-env", f"OPENCODE_CONFIG_CONTENT={encoded}"]

    sys.exit(f"no reasoning-effort mapping defined for agent: {agent}")


def bench_command(args, condition, trial=1):
    jobs_dir = trial_jobs_dir(args, condition, trial)
    model = args.model or AGENTS.get(args.agent)
    if not model:
        sys.exit(f"{args.agent} needs --model to configure reasoning effort")
    cmd = [
        "bench", "eval", "run",
        "--tasks-dir", str(BUILD_DIR / condition),
        "--agent", args.agent,
        "--sandbox", args.sandbox,
        "--skill-mode", args.skill_mode,
        "--concurrency", str(args.concurrency),
        "--jobs-dir", str(jobs_dir),
    ]
    cmd += ["--model", model]
    cmd += reasoning_args(args.agent, model, args.reasoning_effort)
    return cmd


def preflight(args, conditions):
    for condition in conditions:
        if not (BUILD_DIR / condition).is_dir():
            sys.exit(f"build/{condition} missing - run: python3 experiment.py build")
    if not shutil.which("bench"):
        sys.exit("bench CLI not found - run: make setup")
    keys, login_file = AUTH.get(args.agent, ((), None))
    if any(os.environ.get(k) for k in keys):
        return
    if login_file and Path(login_file).expanduser().is_file():
        return  # benchflow detects the login and bills the subscription
    if keys:
        sys.exit(f"{args.agent} needs one of {' / '.join(keys)}, or a login at {login_file}")


def cmd_run(args):
    conditions = args.conditions or list(CONDITIONS)
    for condition in conditions:
        if condition not in CONDITIONS:
            sys.exit(f"unknown condition: {condition} (have: {', '.join(CONDITIONS)})")

    commands = [
        bench_command(args, c, t)
        for t in range(1, args.trials + 1)
        for c in conditions
    ]
    if not args.execute:
        print("dry run - would execute (pass --execute to run):\n")
        for cmd in commands:
            print(" ".join(cmd))
        return

    preflight(args, conditions)
    for i, cmd in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] {' '.join(cmd)}")
        if run_one(cmd) == "limit":
            # The usage window is spent; every remaining command would just
            # spin through the same auth error. Stop and let the caller wait
            # for the reset instead of erroring for hours.
            print("usage limit reached - stopping this run", file=sys.stderr)
            sys.exit(2)

    retry_missing_tasks(args, conditions)


USAGE_LIMIT_MARKERS = (
    "session limit",
    "hit your",
    "usage limit",
    "insufficient credits",
    "payment required",
)


def limit_in_trajectories(jobs_dir):
    """True if an in-sandbox agent message reports a spent usage window.

    Claude says so on bench's stdout; codex only shows a generic "ACP error
    -32603", indistinguishable from a transient crash, and puts the real text
    in its own reply."""
    for path in Path(jobs_dir).rglob("acp_trajectory.jsonl"):
        for line in path.read_text(errors="ignore").lower().splitlines():
            if '"agent_message"' in line and any(m in line for m in USAGE_LIMIT_MARKERS):
                return True
    return False


def run_one(cmd):
    """Run a bench command, streaming output; return 'limit' if the run hit
    the subscription usage cap, else None."""
    jobs_dir = cmd[cmd.index("--jobs-dir") + 1]
    hit_limit = False
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        sys.stdout.write(line)
        lowered = line.lower()
        if not hit_limit and (
            any(m in lowered for m in USAGE_LIMIT_MARKERS)
            or ("acp error" in lowered and limit_in_trajectories(jobs_dir))
        ):
            hit_limit = True
            process.terminate()
    process.wait()
    if process.returncode != 0 and not hit_limit:
        print(f"warning: exited with code {process.returncode}", file=sys.stderr)
    return "limit" if hit_limit else None


def scored_tasks(jobs_dir):
    """Return task names that already have at least one numeric reward."""
    found = set()
    for result_path in jobs_dir.glob("**/result.json"):
        try:
            result = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if parse_reward(result) is not None:
            found.add(task_name_for(result, result_path))
    return found


def next_retry_dir(args, condition, trial, task):
    base = RETRY_JOBS_DIR / args.agent / condition / f"t{trial}" / task
    attempt = 1
    while (base / f"a{attempt}").exists():
        attempt += 1
    return base / f"a{attempt}"


def retry_bench_command(args, condition, trial, task, retry_dir):
    """Build a fresh one-task command, isolated from the canonical job tree."""
    cmd = bench_command(args, condition, trial)
    cmd[cmd.index("--jobs-dir") + 1] = str(retry_dir)
    cmd[cmd.index("--concurrency") + 1] = "1"
    cmd += ["--include", task, "--expected-tasks", "1"]
    return cmd


def scored_retry_result(retry_dir, task):
    candidates = []
    for result_path in retry_dir.glob("**/result.json"):
        try:
            result = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            parse_reward(result) is not None
            and task_name_for(result, result_path) == task
        ):
            candidates.append(result_path)
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def retry_missing_tasks(args, conditions):
    """Retry only task/condition/trial combinations lacking a scored result.

    Each retry gets a fresh external job root so BenchFlow cannot nest into a
    partial canonical job. Only a scored rollout is copied back. If the retry
    is still unscored, stop rather than spending money on unrelated tasks.
    """
    tasks = selected_tasks()
    for trial in range(1, args.trials + 1):
        for condition in conditions:
            canonical_dir = trial_jobs_dir(args, condition, trial)
            for task in tasks:
                if task in scored_tasks(canonical_dir):
                    continue

                retry_dir = next_retry_dir(args, condition, trial, task)
                cmd = retry_bench_command(
                    args, condition, trial, task, retry_dir
                )
                print(
                    f"\nretry missing task only: {args.agent}/{condition}/"
                    f"t{trial}/{task}\n{' '.join(cmd)}"
                )
                if run_one(cmd) == "limit":
                    print("usage limit reached - stopping this run", file=sys.stderr)
                    sys.exit(2)

                result_path = scored_retry_result(retry_dir, task)
                if result_path is None:
                    print(
                        f"one-task retry remained unscored: "
                        f"{args.agent}/{condition}/t{trial}/{task}; stopping",
                        file=sys.stderr,
                    )
                    sys.exit(3)

                recovered_dir = canonical_dir / "recovered"
                recovered_dir.mkdir(parents=True, exist_ok=True)
                destination = recovered_dir / (
                    f"{task}__{retry_dir.name}"
                )
                shutil.copytree(result_path.parent, destination)
                reward = parse_reward(json.loads(result_path.read_text()))
                print(
                    f"recovered {args.agent}/{condition}/t{trial}/{task} "
                    f"with reward {reward}"
                )


def parse_reward(result):
    rewards = result.get("rewards")
    if isinstance(rewards, dict):
        rewards = rewards.get("reward")
    return float(rewards) if isinstance(rewards, (int, float)) else None


def task_name_for(result, result_path):
    for key in ("task_name", "task_id", "task"):
        if isinstance(result.get(key), str):
            return result[key]
    known = {p.name for p in SKILLSBENCH_TASKS.iterdir() if p.is_dir()}
    for part in result_path.parts:
        for name in known:
            if name in part:
                return name
    return "?"


def collect_results():
    rows = []
    for result_path in sorted(JOBS_DIR.glob("*/*/**/result.json")):
        parts = result_path.relative_to(JOBS_DIR).parts
        agent, condition = parts[:2]
        trial = int(parts[2][1:]) if parts[2].startswith("t") and parts[2][1:].isdigit() else 1
        result = json.loads(result_path.read_text())
        reward = parse_reward(result)
        if reward is None:
            continue
        rows.append({
            "agent": agent,
            "condition": condition,
            "trial": trial,
            "task": task_name_for(result, result_path),
            "reward": reward,
            "n_tool_calls": result.get("n_tool_calls"),
            "result_path": str(result_path.relative_to(ROOT)),
        })
    return rows


def cmd_report(args):
    rows = collect_results()
    if not rows:
        sys.exit(f"no result.json files under {JOBS_DIR.relative_to(ROOT)}/")

    with RESULTS_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'agent':15} {'condition':12} {'runs':>5} {'tasks':>6} {'score':>7}")
    for agent, condition in sorted({(r["agent"], r["condition"]) for r in rows}):
        scored = [
            r for r in rows
            if r["agent"] == agent and r["condition"] == condition and r["reward"] is not None
        ]
        # Average per task first: repeat/retried runs would otherwise let an
        # over-sampled task dominate a condition's mean.
        by_task = {}
        for r in scored:
            by_task.setdefault(r["task"], []).append(r["reward"])
        task_means = [sum(v) / len(v) for v in by_task.values()]
        score = f"{sum(task_means) / len(task_means):.3f}" if task_means else "-"
        print(f"{agent:15} {condition:12} {len(scored):>5} {len(by_task):>6} {score:>7}")
    print(f"\nrow-level data written to {RESULTS_CSV.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show all skillsbench tasks, marking the selected subset")
    sub.add_parser("build", help="copy selected tasks into build/<condition>/ with phrases injected")

    run = sub.add_parser("run", help="run bench eval per condition (dry run unless --execute)")
    run.add_argument("--agent", default="claude", help=f"agent name ({', '.join(AGENTS)}, ...)")
    run.add_argument("--model", help="model id (default: agent's entry in AGENTS)")
    run.add_argument(
        "--reasoning-effort",
        choices=REASONING_EFFORTS,
        default=DEFAULT_REASONING_EFFORT,
        help="shared reasoning level translated to every harness (default: high)",
    )
    run.add_argument("--conditions", nargs="*", help="subset of conditions (default: all)")
    run.add_argument("--trials", type=int, default=1, help="repeat each condition N times")
    run.add_argument("--sandbox", default="docker")
    run.add_argument("--skill-mode", default="with-skill", choices=["with-skill", "no-skill"])
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--execute", action="store_true", help="actually run (default: print commands)")

    sub.add_parser("report", help="aggregate rewards from jobs/ into results.csv and a summary table")

    args = parser.parse_args()
    {"list": cmd_list, "build": cmd_build, "run": cmd_run, "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    main()
