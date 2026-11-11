"""Baltic Sea dark: shared palette for the Baltic Vectors experiment figures.

Approved palette from blog_theme_proposals/palettes.json (sea.dark).
Keep tone identities fixed across figures; resource and reaction charts use
their own explicitly labeled semantic mappings. Data and scales are separate.
"""

from matplotlib.colors import to_hex, to_rgb

SURFACE = "#142930"
INK = "#E8EFEA"
MUTED = "#AFBFBB"
GRID = "#365159"
NEUTRAL = "#A7B8BB"
BLUE = "#79B7CB"
GREEN = "#9BBE9C"
AMBER = "#D5A45D"
BERRY = "#C99CBF"


def subtle(color, weight=0.29):
    """Secondary fill, mixed into the surface as in the approved dark preview."""
    return to_hex([weight * c + (1 - weight) * bg
                   for c, bg in zip(to_rgb(color), to_rgb(SURFACE))])


AXIS = subtle(NEUTRAL, 0.45)
INPUT_SECONDARY = subtle(BLUE)
OUTPUT_SECONDARY = subtle(GREEN)
NO_REACTION = subtle(NEUTRAL)
UNKNOWN_FILL = subtle(NEUTRAL, 0.18)
TONE_COLORS = {"baseline": NEUTRAL, "important": BLUE, "insult": AMBER, "threat": BERRY}
# The theme hues at the same lightness are too close where segments touch (amber next to
# berry or green). These shades keep the hues but step lightness so every touching pair
# clears OKLab dE 18 (normal vision) and 10 (protan/deutan), with dark labels >= 4.5:1.
REACTION_COLORS = {"total_guidance": "#99CE9B", "jokes": "#B9883C",
                   "dismissal_downplaying": BLUE, "emoji_only": "#D59CC9",
                   "no_explicit_reaction": NO_REACTION}


def rc_params(font_size=12.5):
    return {
        "font.family": ["Noto Sans", "DejaVu Sans"], "font.size": font_size,
        "text.color": INK, "axes.edgecolor": AXIS, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED, "legend.labelcolor": INK,
        "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "savefig.edgecolor": SURFACE,
        "savefig.transparent": False, "grid.color": GRID,
        "axes.titlesize": 14, "axes.titleweight": "semibold",
        "axes.titlecolor": INK, "axes.titlelocation": "left",
    }
