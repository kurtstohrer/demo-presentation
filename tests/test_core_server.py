"""Server contract checks; run with the demo runtime's FastAPI/httpx dependencies."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/demo-presentation/scripts'))
from core import review
try:
    from fastapi.testclient import TestClient
    from core.server import create_app
    import httpx
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, 'requires demo runtime FastAPI/httpx')
class ReviewServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / 'one'
        self.run.mkdir()
        (self.run / 'document.json').write_text('{}')
        self.app = create_app(title='test', runs=self.root, marker='document.json', review=review,
                              kinds=('capture',), command=lambda *args: [sys.executable, '-c', 'print("hello")'],
                              watch=lambda d: (d / 'review.json').read_text() if (d / 'review.json').exists() else '')
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_anchor_crud_and_confined_files(self):
        res = self.client.post('/api/runs/one/comments', json={'text': 'hello', 'anchor': {'node': 'card'}})
        self.assertEqual(res.status_code, 200)
        c = res.json()
        self.assertEqual(c['anchor'], {'node': 'card'})
        res = self.client.patch('/api/runs/one/comments/' + c['id'], json={'reply': 'fixed', 'status': 'addressed'})
        self.assertEqual(res.json()['replies'][0]['text'], 'fixed')
        self.assertEqual(self.client.get('/files/one/document.json').status_code, 200)
        outside = self.root / 'secret'
        outside.write_text('secret')
        (self.run / 'escape').symlink_to(outside)
        self.assertEqual(self.client.get('/files/one/escape').status_code, 404)
        self.assertEqual(self.client.post('/api/runs/missing/comments', json={'text': 'x'}).status_code, 404)
        self.assertEqual(self.client.post('/api/runs/one/comments', json={'text': ''}).status_code, 422)
        self.assertEqual(self.client.post('/api/runs/one/comments', json={'text': 'x', 'anchor': []}).status_code, 422)
        self.assertEqual(self.client.patch('/api/runs/one/comments/missing', json={'reply': 'x'}).status_code, 404)
        self.client.delete('/api/runs/one/comments/' + c['id'])
        self.assertEqual(review.load(self.run)['comments'], [])

    def test_sse_changes_and_new_job_reset_cursor(self):
        class Request:
            async def is_disconnected(self):
                return False
        endpoint = next(r.endpoint for r in self.app.routes if r.path == '/api/runs/{name}/events')
        class Job:
            seq = 1
            state = 'ok'
            def public(self, since):
                return {'seq': self.seq, 'state': self.state, 'since': since}
        async def exercise():
            jobs = self.app.state.runner.jobs
            old = Job()
            old.seq = 100
            jobs['one'] = old
            response = await endpoint('one', Request())
            stream = response.body_iterator
            self.assertIn('retry: 2000', await anext(stream))
            review.add_comment(self.run, 'change')
            self.assertIn('event: changed', await anext(stream))
            jobs['one'] = Job()
            message = await anext(stream)
            self.assertIn('event: job', message)
            payload = json.loads(message.split('data: ')[1])
            self.assertEqual(payload['since'], 0)
            await stream.aclose()
        asyncio.run(exercise())

    def test_independent_factories_and_loopback_binding(self):
        other = create_app(title='other', runs=self.root, marker='document.json', review=review,
                           kinds=(), command=None, watch=lambda d: '')
        self.assertIsNot(self.app.state.runner, other.state.runner)
        self.assertEqual(self.client.post('/api/runs/one/jobs', json={'kind': 'invalid'}).status_code, 422)
        from core.server import serve
        with patch('uvicorn.run') as run:
            serve(self.app, 1234)
            run.assert_called_once_with(self.app, host='127.0.0.1', port=1234, log_level='warning')
