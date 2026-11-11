"""Render the six current post figures using the saved analysis and shared theme.

This command does not recalculate scores, bootstrap intervals, classifications,
or costs. Legacy, unreferenced figure functions stay outside this entry point.
"""

import argparse
import json
from pathlib import Path

if __package__:
    from . import figures, abuse_figures, harness_figure
else:
    import figures
    import abuse_figures
    import harness_figure


def render(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figures.POST = output_dir
    figures.fig_tone_scores()
    figures.fig_score_cost()
    figures.fig_generalize()
    saved = json.loads((Path(__file__).parent / "abuse_figure_data.json").read_text())
    abuse_figures.behavior_figure(saved["behavior"], output_dir)
    abuse_figures.threat_figure(saved["threat_responses"], output_dir)
    harness_figure.draw(output_dir)
    print("Rendered all six post figures to", output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=figures.POST)
    render(parser.parse_args().output_dir)
