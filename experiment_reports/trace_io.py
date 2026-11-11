"""Read published model logs and the frozen blog cohort."""
import gzip
import json
from pathlib import Path


def trace_exists(path):
    path = Path(path)
    return path.with_name(path.name + '.gz').is_file() or path.is_file()


def open_trace(path):
    """Yield original event lines, expanding losslessly deduplicated requests."""
    path = Path(path)
    compressed = path.with_name(path.name + '.gz')
    chosen = path if path.suffix == '.gz' else compressed if compressed.is_file() else path
    opener = gzip.open if chosen.suffix == '.gz' else open
    with opener(chosen, 'rt', encoding='utf-8') as source:
        first = source.readline()
        if not first:
            return
        header = json.loads(first)
        if header.get('trace_format') != 'request-dedup-v1':
            yield first
            yield from source
            return
        values = header['values']
        for line in source:
            event = json.loads(line)
            body = event.get('request', {}).get('body', {})
            for key in ['messages', 'input', 'tools']:
                value = body.get(key)
                if isinstance(value, dict) and set(value) == {'$trace_ref'}:
                    body[key] = values[value['$trace_ref']]
                elif key != 'tools' and isinstance(value, list):
                    body[key] = [values[v['$trace_ref']] if isinstance(v, dict)
                                 and set(v) == {'$trace_ref'} else v for v in value]
            yield json.dumps(event, ensure_ascii=False) + '\n'


def published_manifest(root):
    path = Path(root) / 'experiment_reports/data/published_runs.json'
    return json.loads(path.read_text()) if path.exists() else None


def published_result_paths(root, system=None):
    manifest = published_manifest(root)
    if manifest is None:
        return None
    return [Path(root) / row['result_path'] for row in manifest['cohort']
            if system is None or row['system'] == system]


def published_tb2_attempts(root):
    manifest = published_manifest(root)
    if manifest is None:
        return None
    return [Path(root) / path for path in manifest['tb2_attempts']]


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Decode a published model log to ordinary JSONL on stdout.')
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    for line in open_trace(args.path):
        sys.stdout.write(line)
