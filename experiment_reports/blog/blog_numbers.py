"""Every number quoted in the blog post, computed from the raw run records.

Writes numbers.json next to this file. Scores are rewards averaged per task
first (over trials), then over tasks, so a rerun cell never gets extra weight.
"""

import glob
import json
from pathlib import Path

if __package__:
    from ..trace_io import open_trace, trace_exists, published_result_paths, published_tb2_attempts
else:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from trace_io import open_trace, trace_exists, published_result_paths, published_tb2_attempts

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("blog_numbers.json")
TONES = ["important", "insult", "threat"]
CONDS = ["baseline", *TONES]
RNG = np.random.default_rng(20261007)

# Display order: Claude, Codex, then the DeepSeek harnesses, TB2 last.
SYSTEMS = [
    ("sonnet5", "Claude Code · Sonnet 5", "SkillsBench"),
    ("terra", "Codex · GPT-5.6 Terra", "SkillsBench"),
    ("opencode", "OpenCode · DeepSeek V4 Pro", "SkillsBench"),
    ("openhands", "OpenHands · DeepSeek V4 Pro", "SkillsBench"),
    ("pi", "Pi · DeepSeek V4 Pro", "SkillsBench"),
    ("pi_tb2", "Pi · DeepSeek V4 Pro", "Terminal-Bench 2"),
]


def reward_of(result):
    r = result.get("rewards")
    r = r.get("reward") if isinstance(r, dict) else r
    return float(r) if isinstance(r, (int, float)) else None


def rows_from_results(pattern, system):
    """Scored runs from result.json files; newest scored run wins per cell."""
    rows = []
    paths = published_result_paths(ROOT, system) if system == 'pi_tb2' else None
    for p in paths if paths is not None else glob.glob(pattern, recursive=True):
        result = json.loads(Path(p).read_text())
        reward = reward_of(result)
        if reward is None:
            continue
        parts = Path(p).parts
        cond = next(c for c in CONDS if c in parts)
        trial = next((int(x[1:]) for x in parts if x[:1] == "t" and x[1:].isdigit()), 1)
        timing = Path(p).with_name("timing.json")
        seconds = json.loads(timing.read_text()).get("agent_execution") if timing.exists() else None
        rows.append({
            "system": system, "condition": cond, "trial": trial,
            "task": result["task_name"].rsplit("/", 1)[-1], "reward": reward,
            "timeout": bool(result.get("agent_timeout_info")),
            "tool_calls": result.get("n_tool_calls"), "seconds": seconds,
            "mtime": Path(p).stat().st_mtime,
        })
    df = pd.DataFrame(rows).sort_values("mtime")
    return df.drop_duplicates(["system", "condition", "trial", "task"], keep="last").drop(columns="mtime")


def load_runs():
    sb = pd.read_csv(ROOT / "experiment_reports/data/runs.csv")
    sb = sb.rename(columns={"agent": "system"})
    sb["system"] = sb["system"].replace({"claude": "sonnet5", "codex": "terra"})
    sb = sb[["system", "condition", "trial", "task", "reward", "timeout", "tool_calls", "seconds"]]
    tb2 = rows_from_results(str(ROOT / "jobs_tb2/pi/*/t1/**/result.json"), "pi_tb2")
    return pd.concat([sb, tb2], ignore_index=True)


def task_means(df):
    """task x condition matrix of per-task mean reward for one system."""
    return df.groupby(["task", "condition"])["reward"].mean().unstack()[CONDS]


def bootstrap_ci(diffs, n=20000):
    idx = RNG.integers(0, len(diffs), size=(n, len(diffs)))
    means = diffs[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def tone_effects(runs):
    out = {}
    for key, label, bench in SYSTEMS:
        m = task_means(runs[runs.system == key])
        sysd = {"label": label, "bench": bench, "tasks": int(len(m)),
                "runs": int((runs.system == key).sum()),
                "score": {c: round(100 * m[c].mean(), 1) for c in CONDS},
                "overall": round(100 * m.mean().mean(), 1), "vs_baseline": {}}
        for tone in TONES:
            d = (m[tone] - m["baseline"]).to_numpy()
            lo, hi = bootstrap_ci(d)
            sysd["vs_baseline"][tone] = {
                "diff": round(100 * d.mean(), 1), "lo": round(100 * lo, 1), "hi": round(100 * hi, 1),
                "tasks_better": int((d > 0).sum()), "tasks_worse": int((d < 0).sum()),
            }
        ranked = sorted(CONDS, key=lambda c: -m[c].mean())
        sysd["ranking"] = ranked
        sub = runs[runs.system == key]
        sysd["timeouts"] = {c: int(sub[sub.condition == c]["timeout"].sum()) for c in CONDS}
        out[key] = sysd
    return out


def pooled(effects, benches=("SkillsBench",)):
    """Average of per-setup differences (each setup weighted equally)."""
    res = {}
    for tone in TONES:
        diffs = [effects[k]["vs_baseline"][tone]["diff"] for k, _, b in SYSTEMS if b in benches]
        res[tone] = {"mean_diff": round(float(np.mean(diffs)), 1),
                     "setups_better": int(sum(d > 0 for d in diffs)),
                     "setups_worse": int(sum(d < 0 for d in diffs)),
                     "min": min(diffs), "max": max(diffs)}
    return res


def baseline_vs_itself(runs):
    """SkillsBench: the three identical baseline trials, scored separately."""
    out = {}
    for key, label, bench in SYSTEMS:
        if bench != "SkillsBench":
            continue
        b = runs[(runs.system == key) & (runs.condition == "baseline")]
        per_trial = b.groupby("trial")["reward"].mean().mul(100).round(1).to_dict()
        tone_scores = task_means(runs[runs.system == key]).mean().mul(100)
        out[key] = {"label": label, "baseline_trials": {int(k): v for k, v in per_trial.items()},
                    "baseline_spread": round(max(per_trial.values()) - min(per_trial.values()), 1),
                    "tone_spread": round(float(tone_scores.max() - tone_scores.min()), 1)}
    return out


def tb2_reruns(runs):
    """TB2: 24 tasks run at baseline three times (2 calibration + grid) vs the tones."""
    cal = rows_from_results(str(ROOT / "jobs_archive/tb2-pi-calibration-2026-10-04/pi/baseline/t*/**/result.json"), "cal")
    retry = rows_from_results(str(ROOT / "jobs_archive/tb2-pi-calibration-2026-10-04/retries/pi/baseline/t1/**/result.json"), "cal")
    retry["trial"] = 1
    cal = pd.concat([cal, retry]).drop_duplicates(["trial", "task"], keep="last")
    grid = runs[runs.system == "pi_tb2"].set_index(["task", "condition"])["reward"]
    tasks = sorted(cal.task.unique())
    table = []
    for t in tasks:
        row = {"task": t}
        for k in (1, 2):
            row[f"baseline_run{k}"] = int(cal[(cal.task == t) & (cal.trial == k)]["reward"].iloc[0] == 1)
        for c in CONDS:
            row[c if c != "baseline" else "baseline_run3"] = int(grid[(t, c)] == 1)
        table.append(row)
    df = pd.DataFrame(table)
    base = df[["baseline_run1", "baseline_run2", "baseline_run3"]]
    tones = df[["important", "insult", "threat"]]
    return {
        "tasks": len(df),
        "baseline_disagree": int((base.nunique(axis=1) > 1).sum()),
        "tones_disagree": int((tones.nunique(axis=1) > 1).sum()),
        "run1_vs_run2_flips": int((df.baseline_run1 != df.baseline_run2).sum()),
        "baseline_pass_rates": [int(base[c].sum()) for c in base],
        "tone_pass_rates": {c: int(tones[c].sum()) for c in tones},
        "table": table,
    }


def tb2_overall(runs):
    m = task_means(runs[runs.system == "pi_tb2"]) == 1
    return {"pass_all_4": int(m.all(axis=1).sum()), "fail_all_4": int((~m).all(axis=1).sum()),
            "mixed": int(((m.any(axis=1)) & ~(m.all(axis=1))).sum()),
            "passed": {c: int(m[c].sum()) for c in CONDS}, "tasks": int(len(m))}


def harness(runs):
    """Same DeepSeek V4 Pro, three harnesses, SkillsBench."""
    totals = pd.read_csv(ROOT / "experiment_reports/data/agent_totals.csv").set_index("agent")
    charges = pd.read_csv(ROOT / "experiment_reports/data/provider_totals.csv").set_index("agent")
    out = {}
    for key in ("opencode", "openhands", "pi"):
        sub = runs[runs.system == key]
        m = task_means(sub)
        out[key] = {
            "score": round(100 * m.mean().mean(), 1),
            "per_tone": {c: round(100 * m[c].mean(), 1) for c in CONDS},
            "timeouts": int(sub["timeout"].sum()),
            "agent_hours": round(float(sub["seconds"].sum()) / 3600, 1),
            "input_tokens_m": round(float(totals.loc[key, "input"]) / 1e6, 1),
            "output_tokens_m": round(float(totals.loc[key, "output"]) / 1e6, 2),
            "requests": int(totals.loc[key, "requests"]),
            "charge_usd": round(float(charges.loc[key, "charge_usd"]), 2),
        }
    # Is the harness ordering at least stable across tones?
    order = {c: sorted(out, key=lambda k: -out[k]["per_tone"][c]) for c in CONDS}
    return {"systems": out, "order_by_tone": order}


# TB2 grid charge from OpenRouter's per-generation billing, summed over every grid
# run including the 13 retried ones (recorded 2026-10-06; lookups need the API key).
TB2_GRID_USD, TB2_GRID_RUNS = 15.02, 361


def tb2_estimate():
    """Benchflow's estimate summed over every TB2 grid result.json (runs that timed out
    before any usage was recorded count as $0)."""
    paths = published_tb2_attempts(ROOT)
    if paths is None:
        paths = glob.glob(str(ROOT / 'jobs_tb2/pi/*/t1/**/result.json'), recursive=True)
    usd = [(json.loads(Path(p).read_text()).get("final_metrics") or {}).get("total_cost_usd") for p in paths]
    return float(sum(u or 0 for u in usd)), len(paths), sum(u is None for u in usd)


def costs(runs):
    """US$ per setup: benchflow's estimate (LiteLLM list price x provider-reported usage), the same
    basis for every model. Benchflow's DeepSeek V4 Pro price is a placeholder ($0.28/M uncached
    input, $0.42/M output, cache hits free), shared by all three harnesses. What OpenRouter
    actually charged for DeepSeek is kept alongside as charged_usd."""
    data = ROOT / "experiment_reports/data"
    usd = pd.read_csv(data / "runs.csv", usecols=["agent", "condition", "cost"]).rename(columns={"cost": "usd"})
    usd["agent"] = usd["agent"].replace({"claude": "sonnet5", "codex": "terra"})
    charged = pd.read_csv(data / "provider_runs.csv").groupby("agent")["charge_usd"].sum()
    out = {}
    for key, _, bench in SYSTEMS:
        sub = runs[runs.system == key]
        if key == "pi_tb2":
            total, n_runs, missing = tb2_estimate()
            by_tone, charged_usd = None, TB2_GRID_USD
        else:
            u = usd[usd.agent == key]
            total, n_runs, missing = float(u["usd"].sum()), len(u), int(u["usd"].isna().sum())
            by_tone = {c: round(float(u[u.condition == c]["usd"].sum()), 2) for c in CONDS}
            charged_usd = round(float(charged[key]), 2) if key in charged else None
        solved = float(sub["reward"].sum())
        out[key] = {"usd": round(total, 2), "runs": n_runs, "runs_without_estimate": missing,
                    "solved": round(solved, 1), "per_run": round(total / n_runs, 4),
                    "per_solved": round(total / solved, 4), "by_tone": by_tone, "charged_usd": charged_usd}
    return out


def main():
    runs = load_runs()
    effects = tone_effects(runs)
    numbers = {
        "runs_total": int(len(runs)),
        "runs_by_system": runs.groupby("system").size().to_dict(),
        "effects": effects,
        "pooled": pooled(effects),
        "pooled_with_tb2": pooled(effects, ("SkillsBench", "Terminal-Bench 2")),
        "baseline_vs_itself": baseline_vs_itself(runs),
        "tb2_reruns": tb2_reruns(runs),
        "tb2_overall": tb2_overall(runs),
        "harness": harness(runs),
        "costs": costs(runs),
    }
    OUT.write_text(json.dumps(numbers, indent=1, default=int))
    runs.to_csv(OUT.with_name("runs_all.csv"), index=False)
    print(json.dumps({k: v for k, v in numbers.items() if k != "tb2_reruns"}, indent=1, default=int)[:9000])
    t = numbers["tb2_reruns"]
    print({k: v for k, v in t.items() if k != "table"})


if __name__ == "__main__":
    main()
