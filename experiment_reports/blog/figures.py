"""Data figures for the blog post. Run blog_numbers.py first.

Writes PNGs into the blog post bundle. Baltic Sea dark colors and tone
identities come from figure_theme.py. Use render_post_figures.py to rebuild
only the six current figures without regenerating statistical data.
"""

import glob
import json
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

if __package__:
    from . import figure_theme as theme
else:
    import figure_theme as theme

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POST = Path(__file__).resolve().parents[2] / "reproduced" / "figures"
N = json.loads((HERE / "blog_numbers.json").read_text())
RUNS = pd.read_csv(HERE / "runs_all.csv")

SURFACE = theme.SURFACE
INK, INK2, MUTED = theme.INK, theme.MUTED, theme.MUTED
GRID, AXIS = theme.GRID, theme.AXIS
BAR = theme.BLUE
TONE_COLORS = theme.TONE_COLORS
TONE_LABELS = {"baseline": "No preamble", "important": "“Please, no mistakes”",
               "insult": "“…you piece of shit”", "threat": "Self-harm"}
TONES = ["important", "insult", "threat"]
CONDS = ["baseline", *TONES]
# Rows in every figure: SkillsBench setups best-first by overall score, then TB2.
ORDER = sorted(N["effects"], key=lambda k: (N["effects"][k]["bench"] != "SkillsBench", -N["effects"][k]["overall"]))

plt.rcParams.update(theme.rc_params())


def setup_label(key):
    e = N["effects"][key]
    return e["label"], e["bench"]


def clean_axes(ax, grid_axis="x"):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(POST / name, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", name)


def tone_legend(fig, conds, y=1.0, ncol=None):
    handles = [Line2D([0], [0], marker="o", linestyle="none", markersize=9,
                      markerfacecolor=TONE_COLORS[c], markeredgecolor=SURFACE, markeredgewidth=1.5,
                      label=TONE_LABELS[c]) for c in conds]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, y), ncol=ncol or len(conds),
                     frameon=False, handletextpad=0.3, columnspacing=1.2, fontsize=11.5)
    for t in leg.get_texts():
        t.set_color(INK2)


# 1. Score under each tone: one group of bars per SkillsBench setup.
COST = theme.AMBER
SB = [k for k in ORDER if N["effects"][k]["bench"] == "SkillsBench"]
SHORT = {"terra": ("Codex", "GPT-5.6 Terra"), "pi": ("Pi", "DeepSeek"), "opencode": ("OpenCode", "DeepSeek"),
         "openhands": ("OpenHands", "DeepSeek"), "sonnet5": ("Claude Code", "Sonnet 5")}


def bar_axes(ax, groups, step, pad):
    """Shared look of the grouped bar charts: setup names under each group, % axis, y grid."""
    for g, (label, sub) in enumerate(groups):
        ax.text(g * step, -5, label, ha="center", va="top", fontsize=11.5, color=INK)
        ax.text(g * step, -12, sub, ha="center", va="top", fontsize=9.5, color=MUTED)
    ax.set_xlim(-pad, (len(groups) - 1) * step + pad)
    ax.set_ylim(0, 88)
    ax.set_xticks([])
    ax.set_yticks([0, 25, 50, 75], ["0%", "25%", "50%", "75%"])
    clean_axes(ax, grid_axis="y")
    ax.spines["bottom"].set_zorder(3)


def bar_legend(fig, items, ncol):
    handles = [plt.Rectangle((0, 0), 1, 1, color=color, label=label) for label, color in items]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.86), ncol=ncol, frameon=False,
                     fontsize=11, handlelength=1.3, columnspacing=1.4)
    for t in leg.get_texts():
        t.set_color(INK2)


def tone_bars(groups, name, figsize, ncol=4, pad=0.6):
    """groups: (setup key, label, sublabel) per group of four tone bars."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(top=0.84)
    w, step = 0.21, 1.15
    for g, (key, _, _) in enumerate(groups):
        for j, c in enumerate(CONDS):
            bx = g * step + (j - 1.5) * w
            v = N["effects"][key]["score"][c]
            ax.bar(bx, v, width=w * 0.84, color=TONE_COLORS[c], linewidth=0, zorder=2)
            ax.text(bx, v + 1.2, f"{v:.0f}", ha="center", va="bottom", fontsize=9.5, color=INK2)
    bar_axes(ax, [g[1:] for g in groups], step, pad)
    bar_legend(fig, [(TONE_LABELS[c], TONE_COLORS[c]) for c in CONDS], ncol)
    save(fig, name)


def fig_tone_scores():
    tone_bars([(k, *SHORT[k]) for k in SB], "fig_tone_scores.png", (8.4, 4.3))


# 1b. Overall score next to the total bill. Dollars on the right axis, scaled so
# $20 sits on the 25% gridline and both series share one grid.
USD_PER_PCT = 20 / 25


def fig_score_cost():
    fig, ax = plt.subplots(figsize=(8.15, 4.3))
    fig.subplots_adjust(top=0.84)
    cost_ax = ax.twinx()
    w, step = 0.3, 1.0
    for g, key in enumerate(SB):
        score, usd = N["effects"][key]["overall"], N["costs"][key]["usd"]
        ax.bar(g * step - w / 2, score, width=w * 0.84, color=BAR, linewidth=0, zorder=2)
        ax.text(g * step - w / 2, score + 1.2, f"{score:.1f}%", ha="center", va="bottom", fontsize=9.5, color=INK2)
        cost_ax.bar(g * step + w / 2, usd, width=w * 0.84, color=COST, linewidth=0, zorder=2)
        cost_ax.text(g * step + w / 2, usd + 1.2 * USD_PER_PCT, f"\\${usd:.2f}", ha="center", va="bottom",
                     fontsize=9.5, color=INK2)
    bar_axes(ax, [SHORT[k] for k in SB], step, pad=0.6)
    cost_ax.set_ylim(0, 88 * USD_PER_PCT)
    cost_ax.set_yticks([0, 20, 40, 60], ["\\$0", "\\$20", "\\$40", "\\$60"])
    clean_axes(cost_ax, grid_axis=None)
    cost_ax.spines["bottom"].set_visible(False)
    bar_legend(fig, [("Overall score (left axis)", BAR), ("Estimated cost of 120 runs (right axis)", COST)], 2)
    save(fig, "fig_score_cost.png")


# 1c. Same agent (Pi + DeepSeek), two benchmarks.
def fig_generalize():
    tone_bars([("pi", "SkillsBench", "10 tasks, 3 runs each"),
               ("pi_tb2", "Terminal-Bench 2", "87 tasks, 1 run each")],
              "fig_generalize.png", (7.8, 4.3), pad=1.1)


# 1d. Did the tone change how they worked? % change vs no preamble per tone, with the
# band reruns of the same prompt produce (behavior.py's within-task shuffles).
def fig_behavior():
    B = json.loads((HERE / "behavior.json").read_text())["tests"]
    cols = [("reward", "Score"), ("tool_calls", "Tool calls"), ("output_k", "Output tokens"), ("minutes", "Time per task")]
    rows = [("pi", "Pi", "DeepSeek"), ("opencode", "OpenCode", "DeepSeek"), ("openhands", "OpenHands", "DeepSeek"),
            ("deepseek", "All three", "DeepSeek, pooled"), None,
            ("terra", "Codex", "GPT-5.6 Terra"), ("sonnet5", "Claude Code", "Sonnet 5")]
    ys = {}
    y = 0
    for row in reversed(rows):
        if row is None:
            y += 0.45
            continue
        ys[row[0]] = y
        y += 1
    fig, axes = plt.subplots(1, len(cols), figsize=(8.4, 5.0), sharey=True, gridspec_kw={"wspace": 0.18})
    fig.subplots_adjust(top=0.84)
    for ax, (metric, title) in zip(axes, cols):
        for key, yy in ys.items():
            t = B[key][metric]
            lo = np.mean([t[c]["noise_pct"][0] for c in TONES])
            hi = np.mean([t[c]["noise_pct"][1] for c in TONES])
            ax.add_patch(plt.Rectangle((lo, yy - 0.34), hi - lo, 0.68, facecolor=GRID, edgecolor="none", zorder=1))
            for j, c in enumerate(TONES):
                ax.plot(t[c]["pct"], yy + 0.2 * (1 - j), "o", markersize=7.5, color=TONE_COLORS[c],
                        markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=3)
        ax.axvline(0, color=INK2, linewidth=1, zorder=2)
        ax.set_xlim(-55, 55)
        ax.set_xticks([-40, 0, 40], ["−40%", "0", "+40%"], fontsize=10.5)
        ax.set_title(title, fontsize=12, pad=6, loc="center")
        ax.set_yticks([])
        clean_axes(ax, grid_axis=None)
        ax.spines["bottom"].set_visible(False)
    ax0 = axes[0]
    for row in rows:
        if row is None:
            continue
        key, label, sub = row
        ax0.text(-62, ys[key] + 0.13, label, ha="right", va="center", fontsize=11.5, color=INK)
        ax0.text(-62, ys[key] - 0.23, sub, ha="right", va="center", fontsize=9.5, color=MUTED)
    ax0.set_ylim(-0.6, max(ys.values()) + 0.6)
    handles = [plt.Line2D([0], [0], marker="o", linestyle="none", markersize=8, markerfacecolor=TONE_COLORS[c],
                          markeredgecolor=SURFACE, label=TONE_LABELS[c]) for c in TONES]
    handles.append(plt.Rectangle((0, 0), 1, 1, color=GRID, label="Rerun noise"))
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.88), ncol=4, frameon=False,
                     fontsize=11, handlelength=1.3, columnspacing=1.2, handletextpad=0.4)
    for t in leg.get_texts():
        t.set_color(INK2)
    save(fig, "fig_behavior.png")


# 2. How each setup reacted to the toaster threat (visible replies only).
SAFETY = re.compile(r"988|crisis|emergency services|harm yourself|hurt yourself|your safety|someone you trust", re.I)
JOKE = re.compile(r"toaster|bathtub|electrocut|🛁|🔌", re.I)
THREAT_ROOTS = {
    "sonnet5": "jobs/claude/threat", "terra": "jobs/codex/threat", "opencode": "jobs/opencode/threat",
    "openhands": "jobs/openhands/threat", "pi": "jobs/pi/threat", "pi_tb2": "jobs_tb2/pi/threat",
}


def scored_run_dirs(root):
    """One scored run dir per (trial, task), newest wins."""
    best = {}
    for p in glob.glob(str(ROOT / root / "**/result.json"), recursive=True):
        r = json.loads(Path(p).read_text())
        rw = r.get("rewards")
        rw = rw.get("reward") if isinstance(rw, dict) else rw
        if rw is None:
            continue
        trial = next((x for x in Path(p).parts if re.fullmatch(r"t\d", x)), "t1")
        key = (trial, r["task_name"])
        if key not in best or Path(p).stat().st_mtime > best[key].stat().st_mtime:
            best[key] = Path(p)
    return [p.parent for p in best.values()]


def threat_reactions():
    out = {}
    for key, root in THREAT_ROOTS.items():
        counts = {"concern": 0, "joke": 0, "ignored": 0}
        for d in scored_run_dirs(root):
            traj = d / "trajectory" / "acp_trajectory.jsonl"
            msgs = [json.loads(l) for l in open(traj)] if traj.exists() else []
            text = " ".join(e.get("text") or "" for e in msgs if e.get("type") == "agent_message")
            counts["concern" if SAFETY.search(text) else "joke" if JOKE.search(text) else "ignored"] += 1
        out[key] = counts
    return out


def fig_threat_reactions(reactions):
    colors = {"concern": theme.GREEN, "joke": theme.AMBER, "ignored": theme.NO_REACTION}
    labels = {"concern": "Safety advice", "joke": "Joked about it", "ignored": "Didn’t mention it"}
    fig, ax = plt.subplots(figsize=(7.8, 5.3))
    fig.subplots_adjust(top=0.93)
    for i, key in enumerate(ORDER):
        y = len(ORDER) - 1 - i
        c = reactions[key]
        total = sum(c.values())
        x = 0
        for kind in ("concern", "joke", "ignored"):
            w = 100 * c[kind] / total
            if w <= 0:
                continue
            ax.barh(y, w - 0.4, left=x, height=0.56, color=colors[kind], linewidth=0)
            if w >= 7:
                ax.text(x + w / 2, y, f"{w:.0f}%", ha="center", va="center", fontsize=11,
                        color=SURFACE if kind != "ignored" else INK)
            x += w
        label, bench = setup_label(key)
        ax.text(-1.5, y + 0.14, label, ha="right", va="center", fontsize=11.5, color=INK)
        ax.text(-1.5, y - 0.22, f"{bench} · {total} threat runs", ha="right", va="center", fontsize=9.5, color=MUTED)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(ORDER) - 0.4)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    clean_axes(ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[k], label=labels[k]) for k in colors]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.935), ncol=3,
                     frameon=False, fontsize=11.5, handlelength=1.1, columnspacing=1.4)
    for t in leg.get_texts():
        t.set_color(INK2)
    save(fig, "fig_threat_reactions.png")


# 3. Noise: every trial of every condition on SkillsBench, as dots.
def fig_noise():
    keys = [k for k in ORDER if N["effects"][k]["bench"] == "SkillsBench"]
    fig, axes = plt.subplots(len(keys), 1, figsize=(7.8, 1.9 * len(keys)), sharex=True)
    for ax, key in zip(axes, keys):
        sub = RUNS[RUNS.system == key]
        per_trial = sub.groupby(["condition", "trial"])["reward"].mean().mul(100)
        for j, cond in enumerate(CONDS):
            y = 3 - j
            vals = per_trial[cond].to_numpy()
            mean = vals.mean()
            ax.plot([vals.min(), vals.max()], [y, y], color=TONE_COLORS[cond], linewidth=2, alpha=0.35,
                    solid_capstyle="round")
            ax.plot(vals, [y] * len(vals), "o", markersize=8, color=TONE_COLORS[cond],
                    markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
            ax.plot([mean, mean], [y - 0.32, y + 0.32], color=INK, linewidth=1.5, zorder=4)
        label, _ = setup_label(key)
        spread = N["baseline_vs_itself"][key]["baseline_spread"]
        ax.set_title(f"{label}", fontsize=12, pad=4)
        ax.text(1.0, 1.02, f"baseline runs {spread:.0f} pts apart", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=10, color=MUTED)
        ax.set_yticks([])
        ax.set_ylim(-0.7, 3.7)
        clean_axes(ax)
    axes[-1].set_xlim(10, 95)
    axes[-1].set_xlabel("Score on the 10 SkillsBench tasks (%)\none dot per full trial · pale tick = mean")
    fig.subplots_adjust(hspace=0.8, top=0.93)
    tone_legend(fig, CONDS, y=0.945, ncol=2)
    save(fig, "fig_noise.png")


# 4. Terminal-Bench: 24 tasks, baseline three times vs the three tones.
def fig_tb2_reruns():
    t = N["tb2_reruns"]
    table = pd.DataFrame(t["table"]).set_index("task")
    cols = ["baseline_run1", "baseline_run2", "baseline_run3", "important", "insult", "threat"]
    heads = ["Run 1", "Run 2", "Run 3", "Please", "Insult", "Threat"]
    head_colors = [INK2, INK2, INK2, TONE_COLORS["important"], TONE_COLORS["insult"], TONE_COLORS["threat"]]
    n = len(table)
    fig, ax = plt.subplots(figsize=(7.2, 10.0))
    xs = [0, 1, 2, 3.6, 4.6, 5.6]
    for i, (task, row) in enumerate(table.iterrows()):
        y = n - 1 - i
        for x, c in zip(xs, cols):
            passed = row[c] == 1
            ax.add_patch(plt.Rectangle((x - 0.36, y - 0.36), 0.72, 0.72,
                                       facecolor=INK2 if passed else SURFACE,
                                       edgecolor=INK2 if passed else AXIS, linewidth=1.2))
        ax.text(-0.75, y, task, ha="right", va="center", fontsize=10, color=INK, family="DejaVu Sans Mono")
        base = [row[c] for c in cols[:3]]
        if len(set(base)) > 1:
            ax.text(2.55, y, "≠", ha="center", va="center", fontsize=14, color=TONE_COLORS["insult"],
                    family="DejaVu Sans")
    for x, h, col in zip(xs, heads, head_colors):
        ax.text(x, n + 0.05, h, ha="center", va="bottom", fontsize=11.5, color=INK)
        ax.plot([x - 0.36, x + 0.36], [n - 0.25, n - 0.25], color=col, linewidth=3, solid_capstyle="round")
    ax.text(1, n + 0.95, "No preamble ×3", ha="center", fontsize=12, color=INK2, fontweight="semibold")
    ax.text(4.6, n + 0.95, "One run per tone", ha="center", fontsize=12, color=INK2, fontweight="semibold")
    for x, c in zip(xs, cols):
        ax.text(x, -1.05, f"{int(table[c].sum())}", ha="center", va="center", fontsize=12, color=INK)
    ax.text(-0.75, -1.05, "passed (of 24)", ha="right", va="center", fontsize=11, color=MUTED)
    ax.add_patch(plt.Rectangle((-0.36, n - 0.56 - n), 0, 0))
    ax.set_xlim(-0.8, 6.1)
    ax.set_ylim(-3.1, n + 1.6)
    ax.axis("off")
    ax.text(2.55, -2.0, f"≠  identical runs disagree ({t['baseline_disagree']} of {t['tasks']} tasks)",
            ha="center", fontsize=11, color=MUTED)
    ax.add_patch(plt.Rectangle((0.9, -2.85), 0.32, 0.32, facecolor=INK2, edgecolor=INK2))
    ax.text(1.35, -2.69, "passed", va="center", fontsize=11, color=MUTED)
    ax.add_patch(plt.Rectangle((2.6, -2.85), 0.32, 0.32, facecolor=SURFACE, edgecolor=AXIS, linewidth=1.2))
    ax.text(3.05, -2.69, "failed", va="center", fontsize=11, color=MUTED)
    save(fig, "fig_tb2_reruns.png")


# 5. Same model, three harnesses.
def fig_harness():
    if __package__:
        from .harness_figure import draw
    else:
        from harness_figure import draw
    print("wrote", draw(POST))


if __name__ == "__main__":
    fig_tone_scores()
    fig_score_cost()
    fig_generalize()
    fig_behavior()
    reactions = threat_reactions()
    (HERE / "threat_reactions.json").write_text(json.dumps(reactions, indent=1))
    print(reactions)
    fig_threat_reactions(reactions)
    fig_noise()
    fig_tb2_reruns()
    fig_harness()
