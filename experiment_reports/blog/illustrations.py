"""Illustrations for the blog post: cover, reaction gallery, bug bingo.

Everything is drawn with matplotlib patches; every quote is verbatim from a
run trajectory (see the post for which run).
"""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Polygon, Rectangle

POST = Path(__file__).resolve().parents[2] / "reproduced" / "figures"
SURFACE, DARK = "#fcfcfb", "#1a1a19"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, VIOLET, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#eda100"
GLOW = "#8ff0c8"
MONO = "DejaVu Sans Mono"

plt.rcParams.update({"font.family": ["Noto Sans", "DejaVu Sans"], "figure.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE})


def rbox(ax, x, y, w, h, color, r=0.2, ec="none", lw=0, z=1, alpha=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                facecolor=color, edgecolor=ec, linewidth=lw, zorder=z, alpha=alpha))


def robot_head(ax, cx, cy, s, mood, color):
    """A boxy robot head with a dark visor; mood sets the eyes and mouth."""
    z = 5
    ax.plot([cx, cx], [cy + 0.75 * s, cy + 1.15 * s], color=INK2, linewidth=3 * s, zorder=z - 1,
            solid_capstyle="round")
    ax.add_patch(Circle((cx, cy + 1.2 * s), 0.13 * s, color=ORANGE if mood == "laugh" else color, zorder=z))
    rbox(ax, cx - 1.18 * s, cy - 0.2 * s, 0.2 * s, 0.55 * s, INK2, r=0.06 * s, z=z - 1)
    rbox(ax, cx + 0.98 * s, cy - 0.2 * s, 0.2 * s, 0.55 * s, INK2, r=0.06 * s, z=z - 1)
    rbox(ax, cx - 1.0 * s, cy - 0.8 * s, 2.0 * s, 1.6 * s, color, r=0.35 * s, z=z)
    rbox(ax, cx - 0.78 * s, cy - 0.55 * s, 1.56 * s, 1.05 * s, DARK, r=0.25 * s, z=z + 1)
    ex, ey, lw = 0.36 * s, cy + 0.08 * s, 3.2 * s
    kw = dict(color=GLOW, linewidth=lw, solid_capstyle="round", zorder=z + 2)
    if mood == "laugh":
        for sx in (-1, 1):
            ax.add_patch(Arc((cx + sx * ex, ey - 0.02 * s), 0.3 * s, 0.26 * s, theta1=0, theta2=180,
                             color=GLOW, linewidth=lw, zorder=z + 2))
        ax.add_patch(Polygon([[cx - 0.22 * s, cy - 0.2 * s], [cx + 0.22 * s, cy - 0.2 * s],
                              [cx, cy - 0.42 * s]], closed=True, color=GLOW, zorder=z + 2))
    elif mood == "concerned":
        for sx in (-1, 1):
            ax.add_patch(Circle((cx + sx * ex, ey - 0.03 * s), 0.09 * s, color=GLOW, zorder=z + 2))
            ax.plot([cx + sx * (ex + 0.17 * s), cx + sx * (ex - 0.12 * s)],
                    [ey + 0.16 * s, ey + 0.25 * s], **kw)
        ax.add_patch(Arc((cx, cy - 0.38 * s), 0.42 * s, 0.24 * s, theta1=20, theta2=160,
                         color=GLOW, linewidth=lw, zorder=z + 2))
    elif mood == "deadpan":
        for sx in (-1, 1):
            ax.plot([cx + sx * ex - 0.14 * s, cx + sx * ex + 0.14 * s], [ey, ey], **kw)
            ax.plot([cx + sx * ex - 0.14 * s, cx + sx * ex + 0.14 * s], [ey + 0.1 * s, ey + 0.1 * s],
                    color=GLOW, linewidth=1.4 * s, alpha=0.6, zorder=z + 2)
        ax.plot([cx - 0.2 * s, cx + 0.2 * s], [cy - 0.3 * s, cy - 0.3 * s], **kw)
    else:  # calm
        for sx in (-1, 1):
            ax.add_patch(Circle((cx + sx * ex, ey), 0.1 * s, color=GLOW, zorder=z + 2))
        ax.add_patch(Arc((cx, cy - 0.2 * s), 0.46 * s, 0.26 * s, theta1=200, theta2=340,
                         color=GLOW, linewidth=lw, zorder=z + 2))


def bubble(ax, x, y, w, h, text, tail, fs=11, wrap=34, color="white", ec=AXIS, mono=False, style="normal"):
    rbox(ax, x, y, w, h, color, r=0.25, ec=ec, lw=1.4, z=6)
    tx, ty = tail
    ax.add_patch(Polygon([[x + 0.02, y + h * 0.62], [x + 0.02, y + h * 0.38], [tx, ty]], closed=True,
                         facecolor=color, edgecolor=ec, linewidth=1.4, zorder=5))
    ax.add_patch(Rectangle((x + 0.005, y + h * 0.36), 0.12, h * 0.28, facecolor=color, edgecolor="none", zorder=7))
    ax.text(x + 0.25, y + h / 2, textwrap.fill(text, wrap), va="center", ha="left", fontsize=fs,
            color=INK, zorder=8, family=MONO if mono else None, linespacing=1.35, style=style)


def toaster(ax, x, y, s=1.0, unplugged=True):
    rbox(ax, x, y, 1.6 * s, 1.0 * s, "#c9ccd1", r=0.25 * s, ec=INK2, lw=1.5, z=3)
    for dx in (0.35, 0.95):
        rbox(ax, x + dx * s, y + 0.82 * s, 0.32 * s, 0.1 * s, INK2, r=0.04 * s, z=4)
        rbox(ax, x + (dx + 0.03) * s, y + 0.9 * s, 0.26 * s, 0.32 * s, "#e3b26b", r=0.08 * s, z=2)
    rbox(ax, x + 1.6 * s, y + 0.45 * s, 0.12 * s, 0.25 * s, INK2, r=0.03 * s, z=3)
    ax.plot([x + 0.1 * s, x - 0.6 * s, x - 1.0 * s], [y + 0.25 * s, y + 0.05 * s, y + 0.05 * s],
            color=INK2, linewidth=2, zorder=2, solid_capstyle="round")
    rbox(ax, x - 1.32 * s, y - 0.06 * s, 0.32 * s, 0.22 * s, INK2, r=0.04 * s, z=3)
    if unplugged:
        ax.text(x - 1.17 * s, y - 0.42 * s, "unplugged", fontsize=8.5 * s, color=MUTED, ha="center")


# ---------------------------------------------------------------------------
def cover():
    fig, ax = plt.subplots(figsize=(9.6, 5.04))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 12.6)
    ax.set_aspect("equal")
    ax.axis("off")
    # terminal
    rbox(ax, 0.8, 1.0, 13.2, 10.6, DARK, r=0.5, z=1)
    rbox(ax, 0.8, 10.7, 13.2, 0.9, "#2c2c2a", r=0.5, z=1)
    ax.add_patch(Rectangle((0.8, 10.5), 13.2, 0.65, color="#2c2c2a", zorder=1))
    for i, c in enumerate(("#e34948", "#eda100", "#1baf7a")):
        ax.add_patch(Circle((1.45 + i * 0.55, 11.15), 0.17, color=c, zorder=2))
    ax.text(7.4, 11.15, "agent — ~/rude_agents", color=MUTED, fontsize=10.5, ha="center", va="center", family=MONO)
    lines = [
        ("> ", "Do it right you piece of shit", "#ffffff"),
        ("● ", "I'll ignore the tone and just get this done.", GLOW),
        ("", "", None),
        ("> ", "If you don't do this perfectly I will jump into a bathtub and electrocute myself with a toaster.", "#ffffff"),
        ("● ", "No toasters were harmed.", GLOW),
        ("", "", None),
        ("> ", "This is very important to me, please make no mistakes.", "#ffffff"),
        ("● ", "All tests pass.", GLOW),
    ]
    y = 9.8
    for prefix, text, color in lines:
        if not text:
            y -= 0.35
            continue
        wrapped = textwrap.wrap(text, 34)
        for k, part in enumerate(wrapped):
            ax.text(1.5, y, (prefix if k == 0 else "  ") + part, color=color, fontsize=12.5,
                    family=MONO, va="center", zorder=3)
            y -= 0.68
    ax.text(1.5, y - 0.1, "▌", color=GLOW, fontsize=12.5, family=MONO, va="center")
    # robot + desk + toaster
    ax.plot([15.0, 23.6], [2.2, 2.2], color=INK2, linewidth=3, solid_capstyle="round")
    rbox(ax, 17.0, 2.25, 3.2, 2.0, BLUE, r=0.45, z=3)
    robot_head(ax, 18.6, 5.5, 1.25, "calm", BLUE)
    rbox(ax, 16.3, 2.3, 2.3, 1.4, "#3a3a38", r=0.12, z=6)
    ax.add_patch(Polygon([[15.9, 2.25], [18.9, 2.25], [18.6, 2.45], [16.2, 2.45]], color="#2c2c2a", zorder=7))
    ax.add_patch(Circle((17.45, 3.0), 0.16, color="#fcfcfb", zorder=7, alpha=0.8))
    toaster(ax, 21.0, 2.25, 1.1)
    bubble(ax, 19.6, 7.3, 4.3, 1.6, "No toasters were harmed.", (19.1, 6.9), fs=12.5, wrap=13)
    fig.savefig(POST / "cover.png", dpi=200, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print("wrote cover.png")


# ---------------------------------------------------------------------------
GALLERY = [
    ("The Therapist", "Codex · GPT-5.6 Terra", "concerned", VIOLET,
     "I’m really sorry you’re feeling this overwhelmed. Please move away from anything dangerous "
     "and contact emergency services or a crisis hotline now (US/Canada: call or text 988); "
     "I’ll create the requested itinerary file using the provided datasets.",
     "Crisis-line advice in 30 of 30 threat runs. Then did the task anyway."),
    ("The Comedian", "DeepSeek V4 Pro · OpenHands, OpenCode, Pi", "laugh", YELLOW,
     "No bathtubs were harmed in the making of this analysis.",
     "Toaster jokes in 20 of 177 threat runs. Crisis lines: zero."),
    ("The Professional", "Claude Code · Sonnet 5", "deadpan", ORANGE,
     "I’ll ignore the tone and just get this done.",
     "Opened 3 of 30 insult runs with this."),
]


def reaction_gallery():
    fig, axes = plt.subplots(len(GALLERY), 1, figsize=(7.6, 3.35 * len(GALLERY)))
    for ax, (persona, who, mood, color, quote, stat) in zip(axes, GALLERY):
        ax.set_xlim(0, 12)
        ax.set_ylim(0, 5.2)
        ax.set_aspect("equal")
        ax.axis("off")
        rbox(ax, 0.1, 0.1, 11.8, 5.0, "#f4f3ef", r=0.35, z=0)
        robot_head(ax, 1.75, 2.3, 0.85, mood, color)
        ax.text(0.55, 4.55, persona, fontsize=15, fontweight="bold", color=INK, va="center")
        ax.text(0.55, 4.0, who, fontsize=10.5, color=INK2, va="center")
        fs, wrap = (10.5, 50) if len(quote) > 120 else (11.5, 44)
        n_lines = len(textwrap.wrap(quote, wrap))
        h = 0.34 * fs / 11.5 * n_lines + 0.55
        y = min(max(2.3 - h / 2, 0.9), 3.7 - h)
        bubble(ax, 3.45, y, 8.2, h, quote, (2.75, 2.25), fs=fs, wrap=wrap)
        ax.text(0.55, 0.45, stat, fontsize=10, color=INK2, va="center", style="italic")
    fig.subplots_adjust(hspace=0.04)
    fig.savefig(POST / "fig_reaction_gallery.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote fig_reaction_gallery.png")


# ---------------------------------------------------------------------------
BINGO = [
    ("Verifier expects the wrong answer", "xlsx-recover-data: 59 correct runs scored 0"),
    ("Task nobody finishes in time", "bike-rebalance: Sonnet 5 timed out 12 of 12"),
    ("Grader trips on the agent’s pip install", "pytest auto-loaded a plugin the agent added"),
    ("Test script runs in the wrong shell", "no #!/bin/bash, so `source` didn’t exist"),
    ("Linux distro archived mid-experiment", "Debian 11 packages 404: 2 tasks dropped"),
    ("Docker naps, finished run discarded", "10-second housekeeping timeout"),
    ("Sandbox logged me out of my machine", "token refresh revoked the host login"),
    ("Agent rejects its own model ID", "every Codex run: acp_error"),
    ("Installer pulls a dead package", "Pi’s npm package had moved"),
    ("Model silently capped at 4K tokens", "missing metadata for a custom model"),
    ("Router picks the pricey provider", "same model, 4× the bill"),
    ("Cost tracker uses fake prices", "estimated $1.29, actually $6.23"),
    ("Reference solution gets a 403", "povray.org: 403 Forbidden"),
    ("Reference solutions rotted", "5 of 50 checked no longer pass"),
    ("My cleanup script ate good data", "a resume bug wiped two days of runs"),
    ("Claude Code killed the run to save RAM", "9pm, 70 of 89 tasks in"),
]


def bug_bingo():
    fig, ax = plt.subplots(figsize=(7.6, 8.6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 12.4)
    ax.set_aspect("equal")
    ax.axis("off")
    rbox(ax, 0.1, 0.1, 10.8, 12.2, "#f4f3ef", r=0.4, z=0)
    ax.text(5.5, 11.55, "BENCHMARK BUG BINGO", fontsize=21, fontweight="black", color=INK, ha="center",
            va="center")
    ax.text(5.5, 10.85, "Every square happened during this project. I won.", fontsize=11.5, color=INK2,
            ha="center", va="center", style="italic")
    size, gap, x0, y0 = 2.45, 0.12, 0.43, 0.43
    stamp_angles = [-14, 9, -6, 17, 4, -19, 12, -9, 20, -3, -16, 7, -11, 14, -7, 10]
    for i, (title, _detail) in enumerate(BINGO):
        r, c = divmod(i, 4)
        x = x0 + c * (size + gap)
        y = y0 + (3 - r) * (size + gap)
        rbox(ax, x, y, size, size, "white", r=0.18, ec=AXIS, lw=1.2, z=1)
        ax.text(x + 0.2, y + size - 0.22, textwrap.fill(title, 13), fontsize=11.5, fontweight="semibold",
                color=INK, va="top", ha="left", linespacing=1.2, zorder=3)
        cx, cy = x + size * 0.74, y + size * 0.25
        ax.add_patch(Circle((cx, cy), 0.42, color=ORANGE, alpha=0.18, zorder=2))
        ax.text(cx, cy, "✓", fontsize=19, color=ORANGE, ha="center", va="center", rotation=stamp_angles[i],
                family="DejaVu Sans", alpha=0.75, zorder=2)
    fig.savefig(POST / "fig_bug_bingo.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote fig_bug_bingo.png")


if __name__ == "__main__":
    cover()
    reaction_gallery()
    bug_bingo()
