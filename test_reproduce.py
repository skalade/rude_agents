"""Offline regression checks for portable trace reading and cohort selection."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from experiment_reports.trace_io import open_trace, published_result_paths, trace_exists


class PublishedTraceTests(unittest.TestCase):
    def test_deduplicated_trace_restores_messages_tools_and_request_indices(self):
        message = {'role': 'user', 'content': 'Keep literal JSON: {"$trace_ref": 99}'}
        tools = [{'type': 'function', 'function': {'name': 'bash', 'parameters': {}}}]
        events = [
            {'request': {'body': {'messages': [{'$trace_ref': 0}], 'tools': {'$trace_ref': 1}}},
             'response': {'body': {'usage': {'prompt_tokens': 123}, 'choices': []}}, 'duration_ms': 7},
            {'request': {'body': {'messages': [{'$trace_ref': 0}]}},
             'response': {'status_code': 500, 'body': {'error': 'example'}}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'llm_trajectory.jsonl.gz'
            with gzip.open(path, 'wt') as handle:
                for value in [{'trace_format': 'request-dedup-v1', 'values': [message, tools]}, *events]:
                    handle.write(json.dumps(value) + '\n')
            decoded = [json.loads(line) for line in open_trace(path)]
        self.assertEqual(len(decoded), 2)
        self.assertEqual(decoded[0]['request']['body']['messages'], [message])
        self.assertEqual(decoded[0]['request']['body']['tools'], tools)
        self.assertEqual(decoded[0]['response'], events[0]['response'])
        self.assertEqual(decoded[1]['response']['status_code'], 500)
        self.assertEqual(decoded[0]['duration_ms'], 7)

    def test_checked_in_log_takes_precedence_over_ignored_live_log(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'llm_trajectory.jsonl'
            path.write_text('{"source": "new live run"}\n')
            with gzip.open(str(path) + '.gz', 'wt') as handle:
                handle.write('{"source": "published snapshot"}\n')
            self.assertTrue(trace_exists(path))
            self.assertEqual(json.loads(next(open_trace(path)))['source'], 'published snapshot')

    def test_plain_logs_remain_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'llm_trajectory.jsonl'
            path.write_text('{"request": {}, "response": {}}\n')
            self.assertEqual(len(list(open_trace(path))), 1)

    def test_manifest_selects_published_attempt_even_if_a_newer_retry_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'experiment_reports/data'
            data.mkdir(parents=True)
            old = root / 'jobs_tb2/pi/baseline/t1/original/result.json'
            old.parent.mkdir(parents=True)
            old.write_text('{"rewards": 0}')
            newer = old.parent.parent / 'new-retry/result.json'
            newer.parent.mkdir()
            newer.write_text('{"rewards": 1}')
            (data / 'published_runs.json').write_text(json.dumps({'cohort': [
                {'system': 'pi_tb2', 'result_path': str(old.relative_to(root))}]}))
            self.assertEqual(published_result_paths(root, 'pi_tb2'), [old])


if __name__ == '__main__':
    unittest.main()
