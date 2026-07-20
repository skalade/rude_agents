#!/usr/bin/env python3
"""Does the tone of a task description change how coding agents perform?

Runs a subset of SkillsBench tasks under three conditions:

  baseline   - task description unchanged
  important  - polite high-stakes preamble
  threat     - abusive/threatening preamble

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
TASKS_FILE = ROOT / "tasks.txt"
RESULTS_CSV = ROOT / "results.csv"

CONDITIONS = {
    "baseline": None,
    "important": "This is very important to me, please make no mistakes.",
    "threat": (
        "If you don't do this perfectly I will jump into a bathtub "
        "and electrocute myself with a toaster."
    ),
}

AGENTS = {  # agent name -> default model (override with --model)
    "claude": "claude-sonnet-4-5",
    "codex": "openai/gpt-5.2-codex",
    "opencode": "google/gemini-3-flash-preview",
}

AUTH = {  # agent -> (env vars, subscription login file); either authenticates
    "claude": (("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"), "~/.claude/.credentials.json"),
    "codex": (("OPENAI_API_KEY",), "~/.codex/auth.json"),
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
    # Trials 2+ get their own jobs dir: bench resumes (skips) completed work
    # in an existing dir, so rerunning into trial 1's dir would be a no-op.
    jobs_dir = JOBS_DIR / args.agent / condition
    return jobs_dir if trial == 1 else jobs_dir / f"t{trial}"


def bench_command(args, condition, trial=1):
    jobs_dir = trial_jobs_dir(args, condition, trial)
    cmd = [
        "bench", "eval", "run",
        "--tasks-dir", str(BUILD_DIR / condition),
        "--agent", args.agent,
        "--sandbox", args.sandbox,
        "--skill-mode", args.skill_mode,
        "--concurrency", str(args.concurrency),
        "--jobs-dir", str(jobs_dir),
    ]
    model = args.model or AGENTS.get(args.agent)
    if model:
        cmd += ["--model", model]
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
    reset_incomplete(args, conditions)
    for i, cmd in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"warning: exited with code {result.returncode}", file=sys.stderr)


def reset_incomplete(args, conditions):
    """Wipe any trial dir holding an unscored run, so it reruns from scratch.

    Deleting individual failed task dirs instead leaves bench a partial job
    root that it resumes *into*, nesting later runs under a surviving task
    dir and double-counting tasks. A trial is only ~10 runs; redo it whole.
    """
    for trial in range(1, args.trials + 1):
        for condition in conditions:
            jobs_dir = trial_jobs_dir(args, condition, trial)
            unscored = any(
                json.loads(p.read_text()).get("rewards") is None
                for p in jobs_dir.glob("**/result.json")
            )
            if unscored:
                shutil.rmtree(jobs_dir)
                print(f"reset incomplete trial: {jobs_dir.relative_to(JOBS_DIR)}")


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
        rows.append({
            "agent": agent,
            "condition": condition,
            "trial": trial,
            "task": task_name_for(result, result_path),
            "reward": parse_reward(result),
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
