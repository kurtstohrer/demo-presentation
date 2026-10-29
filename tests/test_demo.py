"""demo-presentation's stdlib parts: script validation, the scene file server, the page driver (stdlib only)."""
import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/demo-presentation/scripts'
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402

spec = importlib.util.spec_from_file_location('demo_record', SCRIPTS / 'record.py')
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)
from core.page_driver import PageDriver  # noqa: E402

GOOD = {'title': 't', 'scenes': [{'id': 'a-1', 'type': 'card', 'beats': [{'say': 'hi', 'do': [{'wait': 1}]}]}]}


class ValidateScript(unittest.TestCase):
    def test_good_script(self):
        self.assertEqual(common.validate_script(GOOD), [])

    def test_problems(self):
        bad = {'scenes': [{'id': 'A', 'type': 'movie', 'beats': [{'say': 3, 'do': ['x']}]}, {'id': 'A', 'type': 'ui', 'beats': []}]}
        problems = common.validate_script(bad)
        for needle in ('title is required', 'id must be kebab-case', 'type must be one of', 'say must be a string',
                       'each action must be an object', 'duplicate id', 'ui scenes need url', 'beats must be a non-empty array'):
            self.assertTrue(any(needle in p for p in problems), needle)
        self.assertEqual(common.validate_script([]), ['script must be an object'])

    def test_cli_on_a_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'script.json').write_text(json.dumps(GOOD))
            r = subprocess.run([sys.executable, str(SCRIPTS / 'validate.py'), d], capture_output=True, text=True)
            self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {'ok': True, 'problems': []}))
            (Path(d) / 'script.json').write_text('{"title": ""}')
            r = subprocess.run([sys.executable, str(SCRIPTS / 'validate.py'), d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertFalse(json.loads(r.stdout)['ok'])

    def test_estimate(self):
        self.assertEqual(common.estimate_seconds(''), 0.0)
        self.assertAlmostEqual(common.estimate_seconds('one two three four five six seven eight nine ten eleven twelve thirteen'), 5.3)


class SceneFiles(unittest.TestCase):
    """The recorder's static server serves the skill and the project, and nothing outside them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'project'
        (self.root / 'brand').mkdir(parents=True)
        (self.root / 'brand' / 'logo.webp').write_bytes(b'RIFF')
        (Path(self.tmp.name) / 'secret.txt').write_text('no')
        self.server = record.start_server(self.root)
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, r.headers.get('content-type'), r.read()
        except urllib.error.HTTPError as e:
            return e.code, None, b''

    def test_mounts(self):
        status, ctype, body = self.get('/skill/scenes/runtime.js')
        self.assertEqual((status, ctype), (200, 'text/javascript'))
        self.assertIn(b'__scene', body)
        self.assertEqual(self.get('/project/brand/logo.webp')[:2], (200, 'image/webp'))
        self.assertEqual(self.get('/skill/vendor/fonts/Inter-Regular.ttf')[0], 200)

    def test_outside_the_mounts_is_404(self):
        for path in ('/project/../secret.txt', '/project/%2e%2e/secret.txt', '/secret.txt', '/nm/x', '/skill/../../../etc/passwd'):
            self.assertEqual(self.get(path)[0], 404, path)


class FakeMouse:
    def __init__(self, log): self.log = log
    async def move(self, x, y, steps=1): self.log.append(('move', round(x), round(y)))
    async def click(self, x, y, click_count=1, button='left'): self.log.append(('click', round(x), round(y), click_count, button))


class FakeKeyboard:
    def __init__(self, log): self.log = log
    async def press(self, key): self.log.append(('press', key))
    async def type(self, text, delay=0): self.log.append(('type', text))


class FakePage:
    def __init__(self):
        self.log = []
        self.mouse, self.keyboard = FakeMouse(self.log), FakeKeyboard(self.log)
    async def evaluate(self, js, arg=None): self.log.append(('overlay', arg[1]) if arg else ('eval', js))
    async def goto(self, url, wait_until=None): self.log.append(('goto', url))


class PageDriverActions(unittest.TestCase):
    def run_actions(self, *actions):
        page = FakePage()
        driver = PageDriver(page, viewport={'width': 200, 'height': 100}, speed=1000, base_url='http://app.test/', overlay='__o')
        for a in actions:
            asyncio.run(driver.apply(a))
        return page.log

    def test_click_on_a_point_and_goto(self):
        log = self.run_actions({'goto': '/x'}, {'goto': 'https://other.test/'}, {'click': {'x': 10, 'y': 20}})
        self.assertEqual([e for e in log if e[0] in ('goto', 'click')],
                         [('goto', 'http://app.test/x'), ('goto', 'https://other.test/'), ('click', 10, 20, 1, 'left')])
        self.assertIn(('overlay', 'ripple'), log)

    def test_unknown_action(self):
        with self.assertRaises(ValueError):
            self.run_actions({'teleport': 1})


if __name__ == '__main__':
    unittest.main()
