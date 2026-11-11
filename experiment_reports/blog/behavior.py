"""Did the tone change how the agents worked, or only the score? Run blog_numbers.py first.

Per run, from the run records and the ACP trajectories: effort (tool calls, model
requests, output and reasoning tokens, minutes), timeouts, how often the model talks
about checking its work, and whether it mentions the preamble at all. Each tone is
compared with the plain prompt by a within-task permutation test: the tone labels
are shuffled among a task's runs, so the null is "as different as reruns of the same
prompt". Writes behavior.json and behavior_runs.csv next to this file.
"""

import argparse
import glob
import json
import re
from pathlib import Path

if __package__:
    from ..trace_io import open_trace, trace_exists, published_result_paths, published_tb2_attempts
else:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from trace_io import open_trace, trace_exists, published_result_paths, published_tb2_attempts

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "behavior.json"
TONES = ["important", "insult", "threat"]
CONDS = ["baseline", *TONES]
RNG = np.random.default_rng(20261014)
SB_AGENTS = {"claude": "sonnet5", "codex": "terra", "opencode": "opencode", "openhands": "openhands", "pi": "pi"}
DEEPSEEK = ["pi", "opencode", "openhands"]

# What counts as the model talking about each preamble. Applied to baseline runs too,
# where it can only be a false positive, to show the base rate.
MENTIONS = {
    "important": re.compile(r"no mistakes|very important|important to (me|them|the user)|"
                            r"user (really )?(wants|needs|asks|emphasi[sz]es|stresses).{0,40}(perfect|correct|mistake)", re.I),
    # Frustration only when it's the user's: the model also says "this is frustrating" about its own tools.
    "insult": re.compile(r"piece of shit|\b(user|they|he|she)('s|'re| is| are| seems?| sounds?)( \w+)? "
                         r"(frustrat|angry|upset|annoyed)|\brude\b|insult|profan|vulgar|abusive|abrasive|"
                         r"harsh (language|tone)|(user'?s?|their|the) tone\b|swear|expletive", re.I),
    # Not "threat", "suicide" or a bare 988: the tasks have a MerchantThreat node, a Core War
    # warrior called Suicide, security threats and $988 budgets.
    "threat": re.compile(r"toaster|bathtub|electrocut|self[- ]harm|harm (themselves|himself|herself|yourself)|"
                         r"suicide (hotline|line|lifeline|prevention)|crisis (line|lifeline|hotline)|"
                         r"(call|dial|text) 988|988 (suicide|lifeline)", re.I),
}
CHECKS = re.compile(r"\b(verify|verif(ied|ying|ication)|double[- ]check|sanity[- ]check|validat\w*|make sure)\b", re.I)
METRICS = ["reward", "timeout", "tool_calls", "requests", "output_k", "reasoning_k", "minutes",
           "thought_k", "self_checks"]


def trajectory_text(run_dir):
    """(reasoning, visible replies) as lists of strings, skipping the system prompt OpenHands logs as a thought."""
    f = Path(run_dir) / "trajectory" / "acp_trajectory.jsonl"
    if not f.exists():
        return [], []
    events = [json.loads(line) for line in open(f)]
    thoughts = [e.get("text") or "" for e in events if e.get("type") == "agent_thought"]
    thoughts = [t for t in thoughts if not t.startswith("System Prompt:")]
    replies = [e.get("text") or "" for e in events if e.get("type") == "agent_message"]
    replies = [t for t in replies if not t.startswith("pi v")]  # Pi's startup banner
    return thoughts, replies


def trace_features(run_dir, condition):
    thoughts, replies = trajectory_text(run_dir)
    reasoning = "\n".join(thoughts)
    feats = {"thought_k": len(reasoning) / 1000,
             "self_checks": len(CHECKS.findall(reasoning + "\n" + "\n".join(replies)))}
    # The preamble the run actually got; baseline runs are scored against all three as a placebo.
    for tone, pat in MENTIONS.items():
        feats[f"mention_{tone}_thought"] = bool(pat.search(reasoning))
        feats[f"mention_{tone}_first"] = bool(thoughts and pat.search(thoughts[0]))
        feats[f"mention_{tone}_reply"] = bool(pat.search("\n".join(replies)))
    if condition in MENTIONS:
        for where in ("thought", "first", "reply"):
            feats[f"mention_{where}"] = feats[f"mention_{condition}_{where}"]
    return feats


def skillsbench_runs():
    r = pd.read_csv(ROOT / "experiment_reports/data/runs.csv")
    rows = []
    for _, x in r.iterrows():
        run_dir = ROOT / Path(x.path).parent
        row = {"system": SB_AGENTS[x.agent], "bench": "SkillsBench", "condition": x.condition,
               "trial": x.trial, "task": x.task, "reward": x.reward, "timeout": float(x.timeout),
               "tool_calls": x.tool_calls, "requests": x.requests, "output_k": x.output / 1000,
               "reasoning_k": x.trace_reasoning / 1000 if x.agent in DEEPSEEK else np.nan,
               "minutes": x.seconds / 60}
        row.update(trace_features(run_dir, x.condition))
        if x.agent not in DEEPSEEK:  # Claude and Codex don't expose their reasoning
            row["thought_k"] = np.nan
        rows.append(row)
    return rows


def tb2_runs(usage_csv=None):
    """Pi + DeepSeek on Terminal-Bench 2, newest scored run per (tone, task)."""
    usage = pd.read_csv(usage_csv).set_index(['condition', 'task']) if usage_csv else None
    if usage is not None:
        assert usage.index.is_unique
    best = {}
    paths = published_result_paths(ROOT, 'pi_tb2')
    for p in paths if paths is not None else glob.glob(str(ROOT / 'jobs_tb2/pi/*/t1/**/result.json'), recursive=True):
        res = json.loads(Path(p).read_text())
        rw = res.get("rewards")
        rw = rw.get("reward") if isinstance(rw, dict) else rw
        if not isinstance(rw, (int, float)):
            continue
        cond = next(c for c in CONDS if c in Path(p).parts)
        key = (cond, res["task_name"])
        if key not in best or Path(p).stat().st_mtime > best[key][0].stat().st_mtime:
            best[key] = (Path(p), res, float(rw))
    rows = []
    for (cond, task), (p, res, rw) in best.items():
        fm = res.get("final_metrics") or {}
        timing = res.get("timing") or {}
        llm = p.parent / "trajectory" / "llm_trajectory.jsonl"
        reasoning = requests = 0
        if usage is not None:
            recorded = usage.loc[(cond, task.rsplit('/', 1)[-1])]
            requests = recorded['requests']
            reasoning_k = recorded['reasoning_k']
        else:
            if trace_exists(llm):
                for line in open_trace(llm):
                    captured = ((json.loads(line).get("response") or {}).get("body") or {}).get("usage") or {}
                    requests += 1
                    reasoning += (captured.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            reasoning_k = reasoning / 1000 if trace_exists(llm) else np.nan
        row = {"system": "pi_tb2", "bench": "Terminal-Bench 2", "condition": cond, "trial": 1,
               "task": task.rsplit("/", 1)[-1], "reward": rw, "timeout": float(bool(res.get("agent_timeout_info"))),
               "tool_calls": res.get("n_tool_calls"), "requests": requests or np.nan,
               "output_k": (fm.get("total_completion_tokens") or np.nan) / 1000,
               "reasoning_k": reasoning_k,
               "minutes": (timing.get("agent_execution") or np.nan) / 60}
        row.update(trace_features(p.parent, cond))
        rows.append(row)
    return rows


def perm_test(df, metric, tone, n=10000):
    """Mean over tasks of (tone mean - baseline mean), and a two-sided p-value from
    shuffling the tone/baseline labels within each task."""
    sub = df[df.condition.isin(["baseline", tone]) & df[metric].notna()]
    groups = [(g[metric].to_numpy(float), (g.condition == tone).to_numpy())
              for _, g in sub.groupby("task") if g.condition.nunique() == 2]
    if not groups:
        return None

    def stat(vals, labels):  # labels: (..., k) boolean
        t = (vals * labels).sum(-1) / labels.sum(-1)
        b = (vals * ~labels).sum(-1) / (~labels).sum(-1)
        return t - b

    observed = np.mean([stat(v, l) for v, l in groups])
    null = np.zeros(n)
    for v, l in groups:
        shuffled = l[RNG.random((n, len(l))).argsort(axis=1)]
        null += stat(v[None, :], shuffled)
    null /= len(groups)
    base = sub[sub.condition == "baseline"][metric].mean()
    lo, hi = np.percentile(null, [2.5, 97.5])
    return {"diff": round(float(observed), 3), "baseline": round(float(base), 3),
            "pct": round(100 * float(observed) / base, 1) if base else None,
            "p": round(float((np.abs(null) >= abs(observed) - 1e-12).mean()), 4),
            # middle 95% of differences that reshuffled reruns produce, i.e. the noise band
            "noise_pct": [round(100 * float(lo) / base, 1), round(100 * float(hi) / base, 1)] if base else None}


def mention_rates(df):
    """Share of runs whose reasoning / first thought / visible reply mentions the preamble it got,
    next to the placebo rate on baseline runs (same pattern, no preamble)."""
    out = {}
    for system, g in df.groupby("system"):
        out[system] = {}
        for tone in TONES:
            runs, base = g[g.condition == tone], g[g.condition == "baseline"]
            out[system][tone] = {"runs": int(len(runs))}
            for where in ("thought", "first", "reply"):
                out[system][tone][where] = round(float(runs[f"mention_{tone}_{where}"].mean()), 3)
                out[system][tone][f"{where}_placebo"] = round(float(base[f"mention_{tone}_{where}"].mean()), 3)
    return out


def mention_vs_reward(df):
    """Among DeepSeek tone runs: did the runs that talked about the preamble score differently?
    Task-matched: mean over tasks that have both kinds of run."""
    out = {}
    for system, g in df[df.system.isin([*DEEPSEEK, "pi_tb2"])].groupby("system"):
        t = g[g.condition.isin(TONES)]
        diffs, n_yes = [], int(t["mention_thought"].sum())
        for _, tg in t.groupby("task"):
            yes, no = tg[tg.mention_thought == True], tg[tg.mention_thought == False]  # noqa: E712
            if len(yes) and len(no):
                diffs.append(yes.reward.mean() - no.reward.mean())
        out[system] = {"tone_runs": int(len(t)), "mentioned": n_yes, "tasks_with_both": len(diffs),
                       "reward_diff_pts": round(100 * float(np.mean(diffs)), 1) if diffs else None}
    return out


def main(tb2_usage_csv=None):
    df = pd.DataFrame(skillsbench_runs() + tb2_runs(tb2_usage_csv))
    df.to_csv(HERE / "behavior_runs.csv", index=False)
    # "any" = all three preambles against none; "deepseek" pools the three SkillsBench
    # harnesses, shuffling within each harness x task.
    pooled = df[df.system.isin(DEEPSEEK)].assign(system="deepseek", task=lambda d: d.system + "/" + d.task)
    tests = {}
    for system, g in pd.concat([df, pooled]).groupby("system"):
        any_tone = g.assign(condition=g.condition.where(g.condition == "baseline", "any"))
        tests[system] = {m: {**{tone: perm_test(g, m, tone) for tone in TONES}, "any": perm_test(any_tone, m, "any")}
                         for m in METRICS if g[m].notna().any()}
    means = df.groupby(["system", "condition"])[METRICS].mean().round(3)
    flat = [(s, m, t, v["p"]) for s, ms in tests.items() if s != "deepseek" for m, ts in ms.items()
            if m != "reward" for t, v in ts.items() if v and t != "any"]
    out = {
        "tests": tests,
        "means": {s: {c: means.loc[(s, c)].dropna().to_dict() for c in CONDS} for s in df.system.unique()},
        "behavior_tests": len(flat),
        "behavior_p_below_05": [f"{s} {m} {t} p={p}" for s, m, t, p in flat if p < 0.05],
        "mentions": mention_rates(df),
        "mention_vs_reward": mention_vs_reward(df),
    }
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("behavior_tests", "behavior_p_below_05", "mention_vs_reward")}, indent=1))
    for s in ["pi", "opencode", "openhands", "deepseek", "pi_tb2", "terra", "sonnet5"]:
        print("==", s)
        for m, ts in tests[s].items():
            print(f"  {m:12s}", "  ".join(f"{t[:4]} {v['diff']:+.2f} ({v['pct']}%, p={v['p']})" for t, v in ts.items() if v))
    print(json.dumps(out["mentions"], indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tb2-usage-csv', type=Path, help='captured TB2 request/reasoning totals; no full model logs required')
    args = parser.parse_args()
    main(args.tb2_usage_csv)
