"""Plot tokens and calls for five setups, with a DeepSeek/model boundary.

Use per-request prompt totals for all setups. Sonnet's result summaries add
cache reads and cache writes to an input total that already contains them.
Its normalized traces do not supply a usable reasoning-token breakdown.
See blog_review_2026-10-25/harness_all_models for the trace accounting audit.
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import pandas as pd

if __package__:
    from . import figure_theme as theme
else:
    import figure_theme as theme

HERE = Path(__file__).resolve().parent
POST = Path(__file__).resolve().parents[2] / "reproduced" / "figures"
BG, INK, MUTED, GRID = theme.SURFACE, theme.INK, theme.MUTED, theme.GRID
NAMES = {"pi": "Pi", "opencode": "OpenCode", "openhands": "OpenHands",
         "codex": "Codex", "claude": "Claude Code"}
MODELS = {"codex": "GPT-5.6 Terra", "claude": "Sonnet 5"}
ROWS = {"pi": 5.15, "opencode": 4.15, "openhands": 3.15, "codex": 1.15, "claude": .15}


def load_data():
    data = pd.read_csv(HERE.parent / "data/agent_totals.csv").set_index("agent").loc[list(NAMES)].copy()
    # Per-request normalized prompt_tokens already include cache reads/writes.
    data["input"] = data["trace_input"]
    data["cached"] = data["trace_cached"]
    data["uncached"] = data["input"] - data["cached"]
    assert (data["uncached"] >= 0).all()
    assert (data["output"] == data["trace_output"]).all()
    assert ((data["trace_reasoning"] >= 0) & (data["trace_reasoning"] <= data["output"])).all()
    return data


def draw(output_dir=POST):
    data = load_data()
    with plt.rc_context(theme.rc_params(font_size=11)):
        fig = plt.figure(figsize=(11.0, 7.8))
        fig.text(.045, .963, "Tokens and calls", fontsize=24, fontweight="bold", color=INK, va="top")
        fig.text(.045, .902, "10 SkillsBench tasks · 120 runs per setup · all four tones", fontsize=11.5, color=MUTED)

        # All panels share the same row positions and model-group boundary.
        panels = [
            (.205, .18, "Input tokens", "input", "uncached", theme.BLUE, theme.INPUT_SECONDARY, 170, [0, 50, 100, 150]),
            (.425, .18, "Output tokens", "output", "trace_reasoning", theme.GREEN, theme.OUTPUT_SECONDARY, 2.9, [0, 1, 2]),
            (.650, .13, "Tool calls", "tool_calls", None, theme.AMBER, None, 2900, [0, 1000, 2000]),
            (.825, .13, "Model API calls", "requests", None, theme.BERRY, None, 2900, [0, 1000, 2000]),
        ]
        axes = []
        for left, width, title, field, base_field, dark, pale, xmax, ticks in panels:
            ax = fig.add_axes([left, .195, width, .555])
            axes.append(ax)
            ax.set_xlim(0, xmax)
            ax.set_ylim(-.55, 6.25)
            fig.text(left, .845, title, fontsize=13, fontweight="bold", color=INK)
            if base_field:
                labels = ("Uncached", "Cached") if field == "input" else ("Reasoning", "Other output")
                for j, (color, label) in enumerate(zip([dark, pale], labels)):
                    yy = .811 - j * .029
                    fig.patches.append(Rectangle((left, yy - .002), .011, .012,
                                                 transform=fig.transFigure, facecolor=color, edgecolor="none"))
                    fig.text(left + .017, yy + .004, label, fontsize=9.5, color=INK, va="center")
            for key, y in ROWS.items():
                value = data.loc[key, field] / (1e6 if base_field else 1)
                unknown_split = key == "claude" and field == "output"
                if unknown_split:
                    ax.barh(y + .08, value, height=.28, color=theme.UNKNOWN_FILL, edgecolor=theme.NEUTRAL,
                            hatch="////", linewidth=.6, zorder=3)
                    ax.text(0, y - .25, "Split unavailable", fontsize=9.5, color=MUTED, va="center")
                elif base_field:
                    base = data.loc[key, base_field] / 1e6
                    ax.barh(y + .08, base, height=.28, color=dark, zorder=3)
                    ax.barh(y + .08, value - base, left=base, height=.28, color=pale, zorder=3)
                    suffix = "uncached" if field == "input" else "reasoning"
                    ax.text(0, y - .25, f"{base:.2f}M {suffix}", fontsize=9.5, color=dark, va="center")
                else:
                    ax.barh(y + .08, value, height=.28, color=dark, zorder=3)
                label = f"{value:.2f}M" if base_field else f"{value:,.0f}"
                ax.text(value + xmax * .022, y + .08, label, fontsize=10.5,
                        color=INK, va="center", ha="left", clip_on=False)
            ax.set_yticks([])
            tick_labels = ["0" if v == 0 else f"{v:g}M" if base_field else f"{v / 1000:g}k" for v in ticks]
            ax.set_xticks(ticks, tick_labels, fontsize=9, color=MUTED)
            ax.tick_params(length=0, pad=7)
            # Segmented grids stop at the gap between model families.
            for x in ticks:
                for low, high in [(-.48, 1.65), (2.68, 5.68)]:
                    ax.plot([x, x], [low, high], color=GRID, linewidth=.65, zorder=0)
            for side, spine in ax.spines.items():
                spine.set_visible(side == "bottom")
                spine.set_color(GRID)

        def fig_y(y):
            return fig.transFigure.inverted().transform(axes[0].transData.transform((0, y)))[1]

        for key, y in ROWS.items():
            fig.text(.045, fig_y(y + .08), NAMES[key], fontsize=12,
                     fontweight="semibold", color=INK, va="center")
            if key in MODELS:
                fig.text(.045, fig_y(y - .24), MODELS[key], fontsize=10, color=MUTED, va="center")
        fig.text(.045, fig_y(5.97), "DeepSeek V4 Pro · open-source harnesses", fontsize=12,
                 fontweight="bold", color=INK, va="center")
        boundary = fig_y(2.48)
        fig.lines.append(Line2D([.045, .96], [boundary, boundary], transform=fig.transFigure,
                               color=theme.AXIS, linewidth=1.0, linestyle=(0, (4, 4))))
        fig.text(.045, fig_y(1.98), "Proprietary models", fontsize=12,
                 fontweight="bold", color=INK, va="center")

        input_reduction = 100 * (1 - data.loc["pi", "uncached"] / data.loc["openhands", "uncached"])
        output_reduction = 100 * (1 - data.loc["pi", "output"] / data.loc["openhands", "output"])
        fig.lines.append(Line2D([.045, .96], [.133, .133], transform=fig.transFigure, color=GRID, linewidth=1))
        fig.text(.045, .102, "Within DeepSeek: Pi compared with OpenHands", fontsize=10.5, color=MUTED)
        fig.text(.045, .066, f"{input_reduction:.0f}% less uncached input · {output_reduction:.0f}% less output",
                 fontsize=14, color=INK, fontweight="semibold")
        fig.text(.045, .025, "Sonnet’s output is hatched because its reasoning split is unavailable.", fontsize=9.5, color=MUTED)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "fig_harness.png"
        fig.savefig(path, dpi=220)
        plt.close(fig)
        return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=POST)
    print(draw(parser.parse_args().output_dir))
