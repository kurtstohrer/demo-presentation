"""Persistence and packaging regression tests (stdlib only)."""
import importlib.util
import io
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/demo-presentation/scripts'))
from core import review, services
from core.jobs import JobRunner

spec = importlib.util.spec_from_file_location('demo_review', ROOT / 'skills/demo-presentation/scripts/reviewlib.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def append_comments(run, count):
    for i in range(count):
        review.add_comment(Path(run), str(i), anchor={'node': 'card'})


class ReviewState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.legacy = json.loads((ROOT / 'tests/fixtures/review-legacy.json').read_text())
        review.write_json(self.run / 'review.json', self.legacy)

    def test_read_lock_never_publishes_derived_state(self):
        path = self.run / 'review.json'
        path.write_text(json.dumps(self.legacy, separators=(',', ':')))
        before = path.read_bytes()
        with patch.object(review, 'write_json', side_effect=AssertionError('read wrote')):
            with review.locked(self.run, write=False) as state:
                state['status'] = 'derived only'
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_load_save_is_lossless(self):
        self.assertEqual(review.load(self.run), self.legacy)
        self.assertEqual(demo.load(self.run), self.legacy)
        with review.locked(self.run) as state:
            self.assertEqual(state, self.legacy)
        self.assertEqual(review.load(self.run), self.legacy)
        self.assertNotIn('anchor', review.load(self.run)['comments'][0])
        self.assertEqual(review.comment_anchor(self.legacy['comments'][0])['t'], 1.234567)

    def test_legacy_reply_preserves_every_other_field(self):
        review.update_comment(self.run, 'cold', reply=' New reply ', status='addressed')
        actual = review.load(self.run)
        added = actual['comments'][0]['replies'].pop()
        self.assertEqual(added['text'], 'New reply')
        actual['comments'][0]['status'] = 'open'
        self.assertEqual(actual, self.legacy)
        review.close_decision(self.run, 'dold', ' fixed ')
        decision = review.load(self.run)['decisions'][0]
        self.assertEqual(decision['custom'], 42)
        self.assertEqual((decision['state'], decision['reply']), ('done', 'fixed'))

    def test_anchor_only_roundtrip_and_ui_projection(self):
        anchor = {'node': 'button', 'page': 'home', 'region': self.legacy['comments'][0]['region'], 'custom': {'a': [1]}}
        c = review.add_comment(self.run, ' note ', anchor=anchor)
        anchor['custom']['a'].append(2)
        self.assertNotIn('t', c)
        self.assertEqual(c['anchor']['custom'], {'a': [1]})
        review.update_comment(self.run, c['id'], reply='yes')
        stored = review.load(self.run)['comments'][-1]
        self.assertEqual(stored['anchor'], c['anchor'])
        shown = demo.load(self.run)['comments'][-1]
        self.assertIsNone(shown['t'])
        self.assertEqual(shown['region'], c['anchor']['region'])
        self.assertNotIn('t', review.load(self.run)['comments'][-1])

    def test_demo_legacy_and_anchor_inputs(self):
        review.write_json(self.run / 'final.json', {'scenes': [{'start': 0, 'end': 5, 'beats': [{'start': 0, 'key': 'intro.0'}]}]})
        region = self.legacy['comments'][0]['region']
        for kwargs in ({'t': 1.234, 'region': region}, {'anchor': {'t': 1.234, 'region': region, 'extra': 7}}):
            c = demo.add_comment(self.run, 'pin', **kwargs)
            self.assertEqual((c['t'], c['key'], c['region']), (1.23, 'intro.0', region))
            for field in ('t', 'key', 'region'):
                self.assertEqual(c[field], c['anchor'][field])
        self.assertEqual(c['anchor']['extra'], 7)

    def test_new_region_validation_does_not_migrate_old_pins(self):
        for region in ({'x': -1, 'y': 0, 'w': 1, 'h': 1}, {'x': 0.8, 'y': 0, 'w': 0.3, 'h': 1},
                       {'x': float('nan'), 'y': 0, 'w': 1, 'h': 1}, {}):
            with self.assertRaises(ValueError):
                review.add_comment(self.run, 'bad', region=region)
        self.assertEqual(review.load(self.run), self.legacy)

    def test_transaction_failure_and_atomic_write_failure_preserve_original(self):
        before = (self.run / 'review.json').read_bytes()
        with self.assertRaises(RuntimeError):
            with review.locked(self.run) as state:
                state['comments'].clear()
                raise RuntimeError('abort')
        with self.assertRaises(TypeError):
            review.write_json(self.run / 'review.json', {'bad': object()})
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                review.write_json(self.run / 'review.json', {'bad': 1})
        self.assertEqual((self.run / 'review.json').read_bytes(), before)
        self.assertEqual(list(self.run.glob('*.tmp')), [])
        review.add_comment(self.run, 'lock released')

    def test_atomic_writers_never_expose_partial_json(self):
        path = self.run / 'atomic.json'
        review.write_json(path, {'n': 0, 'text': 'a' * 1000})
        def writer(n):
            for _ in range(20):
                review.write_json(path, {'n': n, 'text': str(n) * 1000})
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(writer, n) for n in range(4)]
            while not all(f.done() for f in futures):
                value = review.read_json(path)
                self.assertEqual(len(value['text']), 1000)
            for f in futures:
                f.result()
        self.assertEqual(list(self.run.glob('*.tmp')), [])

    def test_lock_serializes_processes_and_threads(self):
        ctx = multiprocessing.get_context('spawn')
        procs = [ctx.Process(target=append_comments, args=(str(self.run), 12)) for _ in range(3)]
        for p in procs:
            p.start()
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: append_comments(str(self.run), 12), range(3)))
        for p in procs:
            p.join(15)
            if p.is_alive():
                p.kill()
            self.assertEqual(p.exitcode, 0)
        state = review.load(self.run)
        self.assertEqual(len(state['comments']), 73)
        self.assertEqual(state['comments'][0], self.legacy['comments'][0])

    def test_versions_and_demo_workflow_preserve_old_state(self):
        review.write_json(self.run / 'script.json', {'title': 'before'})
        review.write_json(self.run / 'final.json', {'duration': 12})
        self.assertEqual(demo.snapshot_version(self.run), 3)
        review.write_json(self.run / 'script.json', {'title': 'after'})
        self.assertEqual(demo.snapshot_version(self.run), 4)
        self.assertEqual([p.name for p in review.list_versions(self.run)], ['3', '4'])
        self.assertEqual(review.load_version(self.run, 3, ('script.json',))['script.json']['title'], 'before')
        state = review.load(self.run)
        self.assertEqual(state['comments'], self.legacy['comments'])
        self.assertEqual(state['versions'][:2], self.legacy['versions'])
        with self.assertRaises(KeyError):
            review.load_version(self.run, 9, ('script.json',))
        demo.add_decision(self.run, 'run', None, 'approve')
        self.assertEqual(review.load(self.run)['status'], 'done')
        demo.snapshot_version(self.run)
        self.assertEqual(review.load(self.run)['status'], 'video-review')

    def test_snapshot_copy_failure_does_not_publish_version(self):
        review.write_json(self.run / 'script.json', {})
        with patch.object(review.shutil, 'copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                demo.snapshot_version(self.run)
        self.assertEqual(review.load(self.run), self.legacy)
        self.assertFalse((self.run / 'versions/3').exists())
        self.assertEqual(demo.snapshot_version(self.run), 3)

    def test_snapshot_save_failure_can_retry_without_overwriting_existing_versions(self):
        with patch.object(review, 'write_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                demo.snapshot_version(self.run)
        self.assertEqual(review.load(self.run), self.legacy)
        self.assertFalse((self.run / 'versions/3').exists())
        (self.run / 'versions/3').mkdir()
        (self.run / 'versions/3/keep').write_text('immutable')
        with self.assertRaises(FileExistsError):
            demo.snapshot_version(self.run)
        self.assertEqual((self.run / 'versions/3/keep').read_text(), 'immutable')

    def test_custom_snapshot_files_and_concurrent_versions(self):
        review.write_json(self.run / 'document.json', {'nodes': []})
        with ThreadPoolExecutor(max_workers=3) as pool:
            versions = list(pool.map(lambda _: review.snapshot_version(self.run, ('document.json',)), range(3)))
        self.assertEqual(sorted(versions), [3, 4, 5])
        for version in versions:
            self.assertEqual(review.load_version(self.run, version, ('document.json',)), {'document.json': {'nodes': []}})

    def test_decision_supersession_and_custom_scope(self):
        d = review.add_decision(self.run, 'node', 'card', 'changes', 'resize')
        review.add_decision(self.run, 'node', 'card', 'approve')
        self.assertEqual(review.load(self.run)['decisions'][-2]['state'], 'superseded')
        review.close_decision(self.run, d['id'], 'handled')
        with self.assertRaises(ValueError):
            demo.add_decision(self.run, 'node', 'card', 'approve')


class JobsAndServices(unittest.TestCase):
    def wait_job(self, job):
        job.proc.wait(timeout=10)
        deadline = time.monotonic() + 5
        while job.state in ('running', 'cancelling') and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertNotIn(job.state, ('running', 'cancelling'))

    def test_single_job_across_concurrent_launches_and_cancel(self):
        runner = JobRunner(('capture',), lambda *args: [sys.executable, '-c', 'import time; print("ready", flush=True); time.sleep(30)'])
        barrier = threading.Barrier(4)
        def start(i):
            barrier.wait()
            try:
                return runner.start(str(i), 'capture', [])
            except RuntimeError:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [j for j in pool.map(start, range(4)) if j]
        self.assertEqual(len(jobs), 1)
        runner.cancel(jobs[0].name)
        self.wait_job(jobs[0])
        self.assertEqual(jobs[0].state, 'cancelled')

    def test_job_output_cursor_failure_and_restart(self):
        runner = JobRunner(('capture',), lambda *args: [sys.executable, '-c', 'for i in range(2100): print(i)'])
        job = runner.start('one', 'capture', ['a'])
        self.wait_job(job)
        self.assertEqual(job.public(since=2098)['lines'], ['2098', '2099'])
        self.assertEqual(len(job.public(since=0)['lines']), 2000)
        self.assertEqual(job.public()['state'], 'ok')
        self.assertEqual(job.public()['scenes'], ['a'])
        runner.command = lambda *args: [sys.executable, '-c', 'raise SystemExit(3)']
        failed = runner.start('one', 'capture', [])
        self.wait_job(failed)
        self.assertEqual((failed.state, failed.code), ('failed', 3))
        with self.assertRaises(ValueError):
            runner.start('one', 'bad', [])

    def test_services_start_in_root_and_log_under_demo(self):
        svcs = [{'name': 'api', 'start': 'start-it', 'stop': 'stop-it', 'ready': 'check-it'}]
        with tempfile.TemporaryDirectory() as root, patch.object(services, 'is_ready', side_effect=[False, True, True]), patch.object(services.subprocess, 'Popen') as start:
            self.assertEqual(services.up(root, svcs), 0)
            self.assertEqual(start.call_args.args, ('start-it',))
            self.assertEqual(start.call_args.kwargs['cwd'], root)
            self.assertTrue((Path(root) / '.demo/local/services/api.log').exists())
        with patch.object(services.subprocess, 'run') as stop:
            stop.return_value.returncode = 0
            self.assertEqual(services.down('/project', svcs), 0)
            stop.assert_called_once_with('stop-it', shell=True, cwd='/project')


if __name__ == '__main__':
    unittest.main()
