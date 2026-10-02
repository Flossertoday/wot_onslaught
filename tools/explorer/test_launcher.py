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
                    patch.object(launcher, 'detect_game_folders', return_value=[]), \
                    patch('builtins.input', return_value=f'"{game}"'), \
                    patch.object(launcher.server, 'main', return_value=0) as start, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(), 0)
            self.assertEqual(json.loads(config.read_text())['game'], str(game.resolve()))
            start.assert_called_once_with(['--open-browser'])

    def test_demo_forwards_arguments_without_requesting_game_setup(self):
        with patch.object(launcher.sys, 'argv', ['launcher.py', '--demo', '--port', '8766']), \
                patch.object(launcher, 'detect_game_folders') as detect, \
                patch('builtins.input') as prompt, \
                patch.object(launcher.server, 'main', return_value=0) as start:
            self.assertEqual(launcher.main(), 0)
        prompt.assert_not_called()
        detect.assert_not_called()
        start.assert_called_once_with(['--open-browser', '--demo', '--port', '8766'])

    def test_single_detected_installation_is_confirmed_and_replay_override_is_kept(self):
        from local_paths import local_paths
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            game = root/'坦克世界 with spaces'
            package = game/'res/packages/scripts.pkg'
            package.parent.mkdir(parents=True)
            package.write_bytes(b'fixture')
            config = root/'explorer.local.json'
            config.write_text(json.dumps({'replay_source': 'saved replays'}))
            with patch.object(launcher, 'DEFAULT_CONFIG', config), \
                    patch.object(launcher, 'local_paths', side_effect=lambda: local_paths(config=config)), \
                    patch.object(launcher.sys, 'argv', ['launcher.py']), \
                    patch.object(launcher.sys.stdin, 'isatty', return_value=True), \
                    patch.object(launcher, 'detect_game_folders', return_value=[game]), \
                    patch('builtins.input', return_value='') as prompt, \
                    patch.object(launcher.server, 'main', return_value=0), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(launcher.main(), 0)
            prompt.assert_called_once()
            self.assertEqual(json.loads(config.read_text()),
                             {'game': str(game), 'replay_source': 'saved replays'})
            self.assertIn(str(root/'saved replays'), output.getvalue())
            self.assertFalse((game/'replays').exists())

    def test_multiple_matches_require_a_choice_and_invalid_numbers_can_be_retried(self):
        games = [Path('/game one'), Path('/game two')]
        with patch.object(launcher, 'detect_game_folders', return_value=games), \
                patch('builtins.input', side_effect=['9', '2']), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.select_game_folder(), games[1])

    def test_detection_can_be_overridden_with_a_manual_path(self):
        with tempfile.TemporaryDirectory() as folder:
            manual = Path(folder).resolve()
            with patch.object(launcher, 'detect_game_folders', return_value=[Path('/detected')]), \
                    patch('builtins.input', return_value=f'"{manual}"'), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.select_game_folder(), manual)

    def test_user_can_decline_detection_and_open_an_empty_explorer(self):
        with patch.object(launcher, 'detect_game_folders', return_value=[Path('/detected')]), \
                patch('builtins.input', side_effect=['0', '']), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(launcher.select_game_folder())

    def test_no_match_can_fall_back_to_an_empty_explorer(self):
        with patch.object(launcher, 'detect_game_folders', return_value=[]), \
                patch('builtins.input', return_value=''), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(launcher.select_game_folder())
        self.assertIn('No installation found', output.getvalue())

    def test_configured_or_noninteractive_startup_never_searches_or_prompts(self):
        for game, interactive in ((Path('/configured'), True), (None, False)):
            with self.subTest(game=game, interactive=interactive), \
                    patch.object(launcher, 'local_paths', return_value=(game, None)), \
                    patch.object(launcher.sys, 'argv', ['launcher.py']), \
                    patch.object(launcher.sys.stdin, 'isatty', return_value=interactive), \
                    patch.object(launcher, 'detect_game_folders') as detect, \
                    patch('builtins.input') as prompt, \
                    patch.object(launcher.server, 'main', return_value=0):
                self.assertEqual(launcher.main(), 0)
            detect.assert_not_called()
            prompt.assert_not_called()

    def test_invalid_manual_folder_is_not_saved_or_started(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'explorer.local.json'
            with patch.object(launcher, 'DEFAULT_CONFIG', config), \
                    patch.object(launcher, 'local_paths', return_value=(None, None)), \
                    patch.object(launcher.sys, 'argv', ['launcher.py']), \
                    patch.object(launcher.sys.stdin, 'isatty', return_value=True), \
                    patch.object(launcher, 'detect_game_folders', return_value=[]), \
                    patch('builtins.input', return_value=folder), \
                    patch.object(launcher.server, 'main') as start, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(launcher.main(), 1)
            start.assert_not_called()
            self.assertFalse(config.exists())
