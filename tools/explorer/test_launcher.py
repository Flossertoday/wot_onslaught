import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def test_first_run_saves_a_valid_game_folder_with_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = root/'game with spaces'
            package = game/'res/packages/scripts.pkg'
            package.parent.mkdir(parents=True)
            package.write_bytes(b'fixture')
            config = root/'explorer.local.json'
            with patch.object(launcher, 'DEFAULT_CONFIG', config), \
                    patch.object(launcher, 'local_paths', return_value=(None, None)), \
                    patch.object(launcher.sys, 'argv', ['launcher.py']), \
                    patch.object(launcher.sys.stdin, 'isatty', return_value=True), \
                    patch('builtins.input', return_value=f'"{game}"'), \
                    patch.object(launcher.server, 'main', return_value=0) as start, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(), 0)
            self.assertEqual(json.loads(config.read_text())['game'], str(game.resolve()))
            start.assert_called_once_with(['--open-browser'])

    def test_demo_forwards_arguments_without_requesting_game_setup(self):
        with patch.object(launcher.sys, 'argv', ['launcher.py', '--demo', '--port', '8766']), \
                patch('builtins.input') as prompt, \
                patch.object(launcher.server, 'main', return_value=0) as start:
            self.assertEqual(launcher.main(), 0)
        prompt.assert_not_called()
        start.assert_called_once_with(['--open-browser', '--demo', '--port', '8766'])
