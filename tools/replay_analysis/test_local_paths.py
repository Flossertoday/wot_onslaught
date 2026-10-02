import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_paths import local_paths


class LocalPathTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = self.root/'explorer.local.json'
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_no_settings_does_not_assume_the_authors_game_location(self):
        self.assertEqual(local_paths(config=self.config), (None, None))

    def test_relative_settings_are_anchored_to_the_config_not_current_directory(self):
        self.config.write_text(json.dumps({'game': 'game with spaces', 'replay_source': 'saved replays'}))
        self.assertEqual(local_paths(config=self.config),
                         (self.root/'game with spaces', self.root/'saved replays'))

    def test_cli_game_override_uses_its_own_replays_not_saved_old_game(self):
        self.config.write_text(json.dumps({'game': 'old', 'replay_source': 'old/replays'}))
        game, source = local_paths(game=self.root/'new', config=self.config)
        self.assertEqual((game, source), (self.root/'new', self.root/'new/replays'))

    def test_environment_and_cli_override_saved_paths(self):
        self.config.write_text(json.dumps({'game': 'old', 'replay_source': 'old/replays'}))
        os.environ.update(WOT_GAME_DIR=str(self.root/'env game'), WOT_REPLAY_SOURCE=str(self.root/'env replays'))
        self.assertEqual(local_paths(config=self.config), (self.root/'env game', self.root/'env replays'))
        self.assertEqual(local_paths(self.root/'cli game', self.root/'cli replays', self.config),
                         (self.root/'cli game', self.root/'cli replays'))

    def test_bad_config_reports_an_actionable_error(self):
        for value in ('[]', '{"game": 1}', '{"game": ""}', '{bad'):
            with self.subTest(value=value):
                self.config.write_text(value)
                with self.assertRaises(ValueError):
                    local_paths(config=self.config)

    def test_explicit_game_can_recover_from_broken_saved_settings(self):
        self.config.write_text('{broken')
        game, source = local_paths(game=self.root/'recovered', config=self.config)
        self.assertEqual((game, source), (self.root/'recovered', self.root/'recovered/replays'))
