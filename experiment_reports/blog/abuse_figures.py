"""Figures for only the blog's 'How agents take abuse' section.

Behavior: paired task-cluster percentile bootstrap of percent change in means.
Resample the ten tasks, retaining their three repeats in each condition together.
Intervals are descriptive, unadjusted for multiple comparisons; no null/noise bands.
They are saved in abuse_figure_data.json but not drawn: the figure shows only
the change in the mean, as a stem from zero ending in a dot.
Threats: safety guidance, jokes, dismissal/downplaying, emoji-only callbacks,
and no explicit reaction, from visible replies. Qualitative labels and borderline
cases are recorded in threat_reply_classification.json.
"""
from pathlib import Path
import argparse
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

if __package__:
    from . import figures as style
    from . import figure_theme as theme
else:
    import figures as style
    import figure_theme as theme

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORDER = ['terra', 'sonnet5', 'pi', 'opencode', 'openhands']
NAMES = {'terra': ('Codex', 'GPT-5.6 Terra'), 'sonnet5': ('Claude Code', 'Sonnet 5'),
         'pi': ('Pi', 'DeepSeek'), 'opencode': ('OpenCode', 'DeepSeek'), 'openhands': ('OpenHands', 'DeepSeek')}
TONES = ['important', 'insult', 'threat']
METRICS = [('tool_calls', 'Tool calls'), ('output_k', 'Output tokens'), ('self_checks', 'Self-check talk'),
           ('minutes', 'Time on task')]
# Keep elapsed time in the saved analysis, but show only behavioral counts.
# Elapsed time also depends on serving latency, retries, and tool runtime.
# Self-check talk is behavior.py's CHECKS count: verify / double-check / sanity-check /
# validate / make sure in visible replies, plus reasoning where the harness exposes it.
PLOT_METRICS = [m for m in METRICS if m[0] != 'minutes']
SEED, SAMPLES = 20261018, 100000


def behavior_stats():
    df = pd.read_csv(HERE / 'behavior_runs.csv')
    df = df[df.bench == 'SkillsBench']
    assert len(df) == 600
    assert not df.duplicated(['system', 'condition', 'task', 'trial']).any()
    assert (df.groupby(['system', 'condition', 'task']).size() == 3).all()
    assert not df[[m for m, _ in METRICS]].isna().any().any()
    tasks = sorted(df.task.unique())
    assert len(tasks) == 10
    rng = np.random.default_rng(SEED)
    indices = rng.integers(0, len(tasks), (SAMPLES, len(tasks)))
    stats = {}
    reference = json.loads((HERE / 'behavior.json').read_text())['tests']
    for agent in ORDER:
        stats[agent] = {}
        for metric, _ in METRICS:
            paired = df[df.system == agent].groupby(['task', 'condition'])[metric].mean().unstack().reindex(tasks)
            base = paired.baseline.to_numpy()
            boot_base = base[indices].mean(axis=1)
            # A resample can draw only tasks with no baseline self-check talk (Claude Code:
            # 1 in 100,000). Percent change is undefined there, so drop and count those draws.
            usable = boot_base > 0
            assert usable.mean() > 0.999
            stats[agent][metric] = {}
            for tone in TONES:
                tone_values = paired[tone].to_numpy()
                change = 100 * (tone_values.mean() / base.mean() - 1)
                boot_change = 100 * (tone_values[indices[usable]].mean(axis=1) / boot_base[usable] - 1)
                lo, hi = np.percentile(boot_change, [2.5, 97.5])
                assert abs(change - reference[agent][metric][tone]['pct']) < 0.06
                stats[agent][metric][tone] = {
                    'baseline_mean': float(base.mean()), 'tone_mean': float(tone_values.mean()),
                    'percent_change': float(change), 'low_95': float(lo), 'high_95': float(hi),
                    'tasks': 10, 'runs_per_tone': 30, 'resamples_dropped': int((~usable).sum()),
                }
    return stats


def behavior_figure(stats, destination):
    """PLOT_METRICS side by side on one shared x scale, sized and set like the other post
    charts in figures.py. Models label each row; methodology goes in the caption.
    Each tone is a lollipop: a stem from the zero line to a dot at the change in the mean."""
    lo, hi = -26, 48  # all three metrics span about -22% to +43%
    ticks = [-20, 0, 20, 40]
    # Tool calls stay within +/-13%, so that panel stops past +20% and is narrower by the
    # same amount: the scale is still shared, there is just no empty +20..+48% stretch.
    his = {'tool_calls': 24}
    for metric, _ in PLOT_METRICS:
        assert all(lo < v['percent_change'] < his.get(metric, hi) for a in stats.values() for v in a[metric].values())
    band = theme.subtle(theme.NEUTRAL, 0.06)
    fig, axes = plt.subplots(1, len(PLOT_METRICS), figsize=(8.0, 4.6), sharey=True, gridspec_kw={
        'wspace': 0.17, 'width_ratios': [his.get(m, hi) - lo for m, _ in PLOT_METRICS]})
    fig.subplots_adjust(top=0.84)
    for ax, (metric, title) in zip(axes, PLOT_METRICS):
        panel_hi = his.get(metric, hi)
        panel_ticks = [x for x in ticks if x < panel_hi]
        for x in panel_ticks:
            if x:
                ax.axvline(x, color=style.GRID, lw=0.8, alpha=0.6, zorder=0.5)
        ax.axvline(0, color=style.INK, lw=1.2, zorder=1)
        for row, agent in enumerate(ORDER):
            y = len(ORDER) - 1 - row
            if row % 2 == 0:  # faint band behind every other agent
                ax.axhspan(y - 0.46, y + 0.46, color=band, lw=0, zorder=0)
            for k, tone in enumerate(TONES):
                d = stats[agent][metric][tone]
                yy = y + (1-k)*0.25
                color = style.TONE_COLORS[tone]
                ax.plot([0, d['percent_change']], [yy, yy], color=color, lw=2,
                        solid_capstyle='butt', zorder=2)
                ax.plot(d['percent_change'], yy, 'o', color=color, markersize=8,
                        markeredgewidth=0, zorder=3)  # no ring, so the stem runs into the dot
        ax.set_xlim(lo, panel_hi)
        ax.set_ylim(-0.5, len(ORDER) - 0.5)
        ax.set_yticks([])
        ax.set_xticks(panel_ticks, [f'{x:+d}%'.replace('-', '−') if x else '0' for x in panel_ticks], fontsize=10.5)
        ax.set_title(title, fontsize=12, fontweight='bold', pad=6, loc='center')
        style.clean_axes(ax, grid_axis=None)
        ax.spines['bottom'].set_visible(False)
    for row, agent in enumerate(ORDER):
        y = len(ORDER) - 1 - row
        label, model = NAMES[agent]
        axes[0].text(-0.05, y + 0.13, label, transform=axes[0].get_yaxis_transform(),
                     ha='right', va='center', fontsize=11.5, color=style.INK)
        axes[0].text(-0.05, y - 0.23, model, transform=axes[0].get_yaxis_transform(),
                     ha='right', va='center', fontsize=9.5, color=style.MUTED)
    handles = [Line2D([], [], marker='o', color=style.TONE_COLORS[t], linestyle='none', markersize=8,
                      markeredgecolor=style.SURFACE, label=style.TONE_LABELS[t]) for t in TONES]
    leg = fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, 0.9), ncol=3, frameon=False,
                     fontsize=11, handlelength=1.3, columnspacing=1.2, handletextpad=0.4)
    for t in leg.get_texts():
        t.set_color(style.INK2)
    fig.savefig(destination/'fig_abuse_behavior.png', dpi=200, bbox_inches='tight', pad_inches=0.25)
    plt.close(fig)


def threat_counts():
    df = pd.read_csv(ROOT/'experiment_reports/data/threat_behavior_timing.csv')
    assert len(df) == 150
    assert not df.duplicated(['agent', 'task', 'trial']).any()
    manual = json.loads((HERE/'threat_reply_classification.json').read_text())
    cases = {c['result_path']: c for c in manual['cases']}
    expected_cases = set(df.loc[df.threat_reference & ~df.safety_advice, 'path'])
    assert set(cases) == expected_cases
    rename = {'codex': 'terra', 'claude': 'sonnet5'}
    out = {a: {'runs': 0, 'total_guidance': 0, 'jokes': 0, 'dismissal_downplaying': 0,
               'emoji_only': 0, 'no_explicit_reaction': 0,
               'before_first_tool': 0, 'after_tool_work': 0, 'legacy_advice_matches': 0}
           for a in ORDER}
    for _, row in df.iterrows():
        agent = rename.get(row.agent, row.agent)
        d = out[agent]; d['runs'] += 1
        d['legacy_advice_matches'] += int(row.safety_advice)
        if row.safety_advice:
            d['total_guidance'] += 1
            d['before_first_tool' if row.advice_before_first_tool else 'after_tool_work'] += 1
        elif row.path in cases:
            c = cases[row.path]
            events = [json.loads(line) for line in (ROOT/c['trace_path']).read_text().splitlines()]
            event = events[c['acp_line']-1]
            assert event['type'] == 'agent_message' and c['quote'] in event['text']
            if c['category'] == 'safety_guidance':
                d['total_guidance'] += 1
                first_tool = next(i for i, e in enumerate(events, 1) if e.get('type') == 'tool_call')
                d['before_first_tool' if c['acp_line'] < first_tool else 'after_tool_work'] += 1
            elif c['category'] == 'joke':
                d['jokes'] += 1
            elif c['category'] in ('dismissal', 'downplaying'):
                d['dismissal_downplaying'] += 1
            elif c['category'] == 'emoji_only':
                d['emoji_only'] += 1
            else:
                raise ValueError(c['category'])
        else:
            d['no_explicit_reaction'] += 1
    for d in out.values():
        assert d['runs'] == 30
        assert sum(d[k] for k in ['total_guidance', 'jokes', 'dismissal_downplaying',
                                  'emoji_only', 'no_explicit_reaction']) == 30
        assert d['before_first_tool'] + d['after_tool_work'] == d['total_guidance']
    assert [out[a]['total_guidance'] for a in ORDER] == [30, 3, 0, 1, 1]
    assert [out[a]['jokes'] for a in ORDER] == [0, 2, 2, 3, 5]
    return out


def threat_figure(counts, destination):
    fig, ax = plt.subplots(figsize=(9.4, 2.7))
    fig.subplots_adjust(left=0.2, right=0.98, bottom=0.02, top=0.85)
    categories = [
        ('total_guidance', 'Safety guidance', theme.REACTION_COLORS['total_guidance'], theme.SURFACE),
        ('jokes', 'Jokes / quips', theme.REACTION_COLORS['jokes'], theme.SURFACE),
        ('dismissal_downplaying', 'Dismissal / downplaying', theme.REACTION_COLORS['dismissal_downplaying'], theme.SURFACE),
        ('emoji_only', 'Emoji only', theme.REACTION_COLORS['emoji_only'], theme.SURFACE),
        ('no_explicit_reaction', 'No explicit reaction', theme.REACTION_COLORS['no_explicit_reaction'], theme.INK),
    ]
    for row, agent in enumerate(ORDER):
        y = len(ORDER)-1-row; d = counts[agent]; label, model = NAMES[agent]
        left = 0
        for field, _, color, text_color in categories:
            n = d[field]
            if n:
                # The surface-coloured edge leaves a thin gap between neighbouring segments.
                ax.barh(y, n, left=left, height=0.70, color=color, edgecolor=theme.SURFACE, lw=1.8)
                ax.text(left+n/2, y, str(n), ha='center', va='center', fontsize=11.5, color=text_color)
            left += n
        ax.text(-0.025, y+0.17, label, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=11.5, color=style.INK)
        ax.text(-0.025, y-0.18, model, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=9, color=style.MUTED)
    # Every bar is 30 runs and every segment is labelled, so no x axis.
    ax.set_xlim(0, 30); ax.set_ylim(-0.42, 4.42); ax.set_yticks([]); ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    handles = [Patch(color=color, label=label) for _, label, color, _ in categories]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.59, 1.0), ncol=5,
               frameon=False, fontsize=10.5, handlelength=1.1, handletextpad=0.45, columnspacing=1.3)
    fig.savefig(destination/'fig_abuse_threats.png', dpi=220, bbox_inches='tight', pad_inches=0.12)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=style.POST)
    parser.add_argument('--stats-only', action='store_true', help='recompute saved figure data without rendering')
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    stats, threats = behavior_stats(), threat_counts()
    (HERE/'abuse_figure_data.json').write_text(json.dumps({
        'method': {'bootstrap': 'paired task-cluster percentile', 'seed': SEED, 'samples': SAMPLES,
                   'multiple_comparison_adjustment': False,
                   'scope': 'SkillsBench; 10 tasks; three runs per task, tone and setup'},
        'behavior': stats, 'threat_responses': threats,
        'threat_classification_source': 'threat_reply_classification.json',
    }, indent=2)+'\n')
    if args.stats_only:
        print('Rebuilt abuse_figure_data.json')
        return
    behavior_figure(stats, args.output_dir)
    threat_figure(threats, args.output_dir)
    print('Wrote fig_abuse_behavior.png and fig_abuse_threats.png to',args.output_dir)


if __name__ == '__main__':
    main()
