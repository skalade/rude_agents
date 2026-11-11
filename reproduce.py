#!/usr/bin/env python3
"""Rebuild the published analysis and six blog figures without model/API calls.

Inputs stay untouched. Intermediate tables and logs go under --output-dir.
The frozen manifest determines the scored cohort, independent of file mtimes.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / 'experiment_reports'
FIGURES = ['fig_tone_scores.png', 'fig_score_cost.png', 'fig_generalize.png',
           'fig_abuse_behavior.png', 'fig_abuse_threats.png', 'fig_harness.png']


def verify_inputs():
    manifest = json.loads((REPORTS / 'data/published_runs.json').read_text())
    rows = manifest['cohort']
    counts = collections.Counter(row['system'] for row in rows)
    expected = {'terra': 120, 'sonnet5': 120, 'pi': 120,
                'opencode': 120, 'openhands': 120, 'pi_tb2': 348}
    if counts != expected:
        raise ValueError(f'Unexpected cohort: {dict(counts)}')
    keys = {(r['system'], r['condition'], r['trial'], r['task']) for r in rows}
    if len(keys) != 948:
        raise ValueError('Duplicate experiment cells in the published cohort')
    inputs = manifest['artifacts'] + manifest.get('analysis_inputs', [])
    for item in inputs:
        path = ROOT / item['path']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item['sha256']:
            raise ValueError(f'Published input changed: {item["path"]}')
    for row in rows:
        result = json.loads((ROOT / row['result_path']).read_text())
        reward = result['rewards']
        reward = reward.get('reward') if isinstance(reward, dict) else reward
        if reward != row['reward']:
            raise ValueError(f'Reward mismatch: {row["result_path"]}')
    print(f'Verified {len(rows)} scored runs and {len(inputs)} artifact hashes.', flush=True)
    return manifest


def check_analysis(work):
    expected = json.loads((REPORTS / 'blog/blog_numbers.json').read_text())
    actual = json.loads((work / 'experiment_reports/blog/blog_numbers.json').read_text())
    # These cover every published score, tone difference, rerun summary and cost.
    for key in ['runs_total', 'runs_by_system', 'effects', 'pooled',
                'baseline_vs_itself', 'tb2_reruns', 'tb2_overall', 'harness', 'costs']:
        if actual[key] != expected[key]:
            raise ValueError(f'Regenerated analysis differs from the snapshot: {key}')
    expected_abuse = json.loads((REPORTS / 'blog/abuse_figure_data.json').read_text())
    actual_abuse = json.loads((work / 'experiment_reports/blog/abuse_figure_data.json').read_text())
    for key in ['behavior', 'threat_responses']:
        if actual_abuse[key] != expected_abuse[key]:
            raise ValueError(f'Regenerated trace analysis differs: {key}')
    print('Published scores, intervals, costs, behavior metrics and threat classifications match.', flush=True)
    return {'scored_runs': actual['runs_total'], 'runs_by_system': actual['runs_by_system'],
            'analysis_matches_saved_snapshot': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reproduced')
    parser.add_argument('--verify-only', action='store_true', help='check hashes and the frozen cohort without rebuilding')
    parser.add_argument('--figures-only', action='store_true', help='render the six figures from saved analysis tables')
    args = parser.parse_args()
    verify_inputs()
    if args.verify_only:
        return
    output = args.output_dir.resolve()
    if output == ROOT or output in ROOT.parents or any(output.is_relative_to(ROOT / p)
            for p in ['experiment_reports', 'jobs', 'jobs_tb2', 'jobs_archive']):
        parser.error('Choose an output directory outside the checked-in input directories.')
    output.mkdir(parents=True, exist_ok=True)
    work = output / 'workspace'
    work.mkdir(exist_ok=True)
    shutil.copytree(REPORTS, work / 'experiment_reports', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ['jobs', 'jobs_tb2', 'jobs_archive']:
        link = work / name
        if link.is_symlink():
            if link.resolve() != (ROOT / name).resolve():
                raise ValueError(f'Unexpected input link: {link}')
        elif link.exists():
            raise ValueError(f'Expected a link to the input artifacts, found a directory: {link}')
        else:
            link.symlink_to(ROOT / name, target_is_directory=True)
    env = os.environ.copy()
    env['MPLCONFIGDIR'] = str(output / 'matplotlib-cache')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    steps = [] if args.figures_only else [
        ('run records and saved request usage', ['experiment_reports/analyze.py', '--requests-csv', 'experiment_reports/data/requests.csv']),
        ('provider accounting and summaries', ['experiment_reports/summarize.py']),
        ('visible threat reactions', ['experiment_reports/trace_behavior.py', '--reactions-only']),
        ('blog numbers and task bootstrap', ['experiment_reports/blog/blog_numbers.py']),
        ('behavior counts and permutation checks', ['experiment_reports/blog/behavior.py', '--tb2-usage-csv', 'experiment_reports/data/tb2_usage.csv']),
        ('behavior bootstrap and manual reaction labels', ['experiment_reports/blog/abuse_figures.py', '--stats-only']),
    ]
    log = output / 'reproduction.log'
    with log.open('w') as handle:
        for label, command in steps:
            print('Rebuilding:', label, flush=True)
            result = subprocess.run([sys.executable, *command], cwd=work, env=env,
                                    stdout=handle, stderr=subprocess.STDOUT)
            if result.returncode:
                raise SystemExit(f'{label} failed; see {log}')
        summary = check_analysis(work) if not args.figures_only else {'saved_analysis_used': True}
        print('Rendering the six blog figures.', flush=True)
        result = subprocess.run([sys.executable, 'experiment_reports/blog/render_post_figures.py',
                                 '--output-dir', str(output / 'figures')], cwd=work, env=env,
                                stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit(f'Figure rendering failed; see {log}')
    for name in FIGURES:
        path = output / 'figures' / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Missing figure: {name}')
    summary['token_accounting_source'] = 'saved_usage_tables'
    summary['figures'] = FIGURES
    (output / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('Done. Figures:', output / 'figures', flush=True)
    print('Verification:', output / 'verification.json', flush=True)


if __name__ == '__main__':
    main()
