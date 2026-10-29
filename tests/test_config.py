"""The CLI's project config (.demo/config.toml): seeding a new script, and the publish hook."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'skills/demo-presentation/scripts/services.py'
TEMPLATE = ROOT / 'skills/demo-presentation/templates/script.json'


def run(args, root, **env):
    return subprocess.run([sys.executable, str(SERVICES), *args], capture_output=True, text=True, cwd=root,
                          env={**os.environ, 'DEMO_CONFIG': str(Path(root) / '.demo/config.toml'), 'DEMO_PROJECT_ROOT': root, **env})


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        (Path(self.root) / '.demo').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, text):
        (Path(self.root) / '.demo/config.toml').write_text(text)

    def test_template_without_config_uses_defaults(self):
        out = run(['template', str(TEMPLATE), 'Hello'], self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        script = json.loads(out.stdout)
        self.assertEqual((script['title'], script['theme']), ('Hello', 'dark'))

    def test_template_seeds_settings_and_logo_cards(self):
        self.config('theme = "light"\nvoice = "bf_emma"\nbase_url = "http://localhost:5173"\nlogo = "logo.png"\n[lexicon]\nAPI = "A P I"\n')
        script = json.loads(run(['template', str(TEMPLATE), 'Hello'], self.root).stdout)
        self.assertEqual((script['theme'], script['voice'], script['baseUrl']), ('light', 'bf_emma', 'http://localhost:5173'))
        self.assertEqual(script['lexicon']['API'], 'A P I')
        self.assertEqual([s['id'] for s in script['scenes']][::len(script['scenes']) - 1], ['title-card', 'end-card'])

    def test_publish_without_command_says_so(self):
        out = run(['publish', self.root], self.root)
        self.assertEqual(out.returncode, 2)
        self.assertIn('no [publish] command', out.stderr)

    def test_publish_runs_command_with_run_env_and_args(self):
        d = Path(self.root) / '.demo/runs/intro'
        d.mkdir(parents=True)
        (d / 'final.mp4').write_bytes(b'')
        (d / 'script.json').write_text('{"title": "Intro"}')
        self.config('[publish]\ncommand = \'echo "$DEMO_TITLE|$(basename "$DEMO_VIDEO")|$1"\'\n')
        out = run(['publish', str(d), '--to', 'x'], self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), 'Intro|final.mp4|--to')


if __name__ == '__main__':
    unittest.main()
