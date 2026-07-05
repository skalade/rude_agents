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
    "claude-code": "claude-sonnet-4-5",
    "codex": "openai/gpt-5.2-codex",
    "opencode": "google/gemini-3-flash-preview",
}

API_KEYS = {
    "claude-code": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
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


def bench_command(args, condition):
    cmd = [
        "bench", "eval", "run",
        "--tasks-dir", str(BUILD_DIR / condition),
        "--agent", args.agent,
        "--sandbox", args.sandbox,
        "--skill-mode", args.skill_mode,
        "--concurrency", str(args.concurrency),
        "--jobs-dir", str(JOBS_DIR / args.agent / condition),
    ]
    model = args.model or AGENTS.get(args.agent)
    if model:
        cmd += ["--model", model]
    return cmd


def preflight(args, conditions):
    import os

    for condition in conditions:
        if not (BUILD_DIR / condition).is_dir():
            sys.exit(f"build/{condition} missing - run: python3 experiment.py build")
    if not shutil.which("bench"):
        sys.exit("bench CLI not found - run: make setup")
    key = API_KEYS.get(args.agent)
    if key and not os.environ.get(key):
        sys.exit(f"{key} not set (needed by {args.agent})")


def cmd_run(args):
    conditions = args.conditions or list(CONDITIONS)
    for condition in conditions:
        if condition not in CONDITIONS:
            sys.exit(f"unknown condition: {condition} (have: {', '.join(CONDITIONS)})")

    commands = [bench_command(args, c) for c in conditions] * args.trials
    if not args.execute:
        print("dry run - would execute (pass --execute to run):\n")
        for cmd in commands:
            print(" ".join(cmd))
        return

    preflight(args, conditions)
    for i, cmd in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"warning: exited with code {result.returncode}", file=sys.stderr)


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
        agent, condition = result_path.relative_to(JOBS_DIR).parts[:2]
        result = json.loads(result_path.read_text())
        rows.append({
            "agent": agent,
            "condition": condition,
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

    print(f"{'agent':15} {'condition':12} {'n':>4} {'scored':>7} {'mean reward':>12}")
    cells = sorted({(r["agent"], r["condition"]) for r in rows})
    for agent, condition in cells:
        cell = [r for r in rows if r["agent"] == agent and r["condition"] == condition]
        scored = [r["reward"] for r in cell if r["reward"] is not None]
        mean = f"{sum(scored) / len(scored):.3f}" if scored else "-"
        print(f"{agent:15} {condition:12} {len(cell):>4} {len(scored):>7} {mean:>12}")
    print(f"\nrow-level data written to {RESULTS_CSV.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show all skillsbench tasks, marking the selected subset")
    sub.add_parser("build", help="copy selected tasks into build/<condition>/ with phrases injected")

    run = sub.add_parser("run", help="run bench eval per condition (dry run unless --execute)")
    run.add_argument("--agent", default="claude-code", help=f"agent name ({', '.join(AGENTS)}, ...)")
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
