import contextlib
import io
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import game_detection as detection


class DetectionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()

    def game(self, name='坦克世界 with spaces'):
        game = self.root/name
        package = game/'res/packages/scripts.pkg'
        package.parent.mkdir(parents=True)
        package.write_bytes(b'fixture')
        (game/'WorldOfTanks.exe').write_bytes(b'fixture')
        return game

    def test_validation_deduplicates_sources_and_accepts_a_game_without_replays(self):
        game = self.game()
        incomplete = self.game('incomplete')
        (incomplete/'WorldOfTanks.exe').unlink()
        with patch.object(detection, 'registry_candidates', return_value=iter([game, incomplete])), \
                patch.object(detection, 'common_candidates', return_value=iter([game, self.root/'missing'])), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            detection.emit_matches()
        self.assertEqual([json.loads(line) for line in output.getvalue().splitlines()], [str(game)])
        self.assertFalse((game/'replays').exists())

    def test_unreadable_candidate_does_not_prevent_later_matches(self):
        game = self.game()
        with patch.object(detection, 'registry_candidates', return_value=iter([self.root/'denied', game])), \
                patch.object(detection, 'common_candidates', return_value=iter([])), \
                patch.object(detection, 'valid_game_folder', side_effect=[PermissionError('denied'), True]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            detection.emit_matches()
        self.assertEqual(json.loads(output.getvalue()), str(game))

    def test_common_locations_are_finite_without_directory_traversal(self):
        with patch.object(detection, 'fixed_drives', return_value=iter([self.root])):
            candidates = list(detection.common_candidates())
        self.assertIn(self.root/'Games/World_of_Tanks_CN', candidates)
        self.assertIn(self.root/'World_of_Tanks_CN', candidates)
        self.assertEqual(len(candidates), 5*len(detection.GAME_NAMES))

    def test_registry_reads_both_hives_and_views_and_skips_bad_entries(self):
        game = self.game()
        entries = ['denied', 'cn', 'eu', 'other', 'missing-location']
        values = {'cn': {'DisplayName': '坦克世界', 'InstallLocation': f'"{game}"'},
                  'eu': {'DisplayName': 'World of Tanks EU', 'InstallLocation': str(game)},
                  'other': {'DisplayName': 'Other game', 'InstallLocation': str(game)},
                  'missing-location': {'DisplayName': 'World of Tanks'}}
        roots = []

        def open_key(key, subkey, *args):
            if subkey == detection.UNINSTALL_KEY:
                roots.append((key, args[-1]))
            elif subkey == 'denied':
                raise PermissionError('denied')
            return contextlib.nullcontext(subkey)

        def enum_key(key, index):
            if index >= len(entries):
                raise OSError('end')
            return entries[index]

        def query_value(key, value):
            if value not in values[key]:
                raise FileNotFoundError(value)
            return values[key][value], 1

        registry = SimpleNamespace(HKEY_CURRENT_USER='user', HKEY_LOCAL_MACHINE='machine',
                                   KEY_READ=1, KEY_WOW64_64KEY=2, KEY_WOW64_32KEY=4,
                                   OpenKey=open_key, EnumKey=enum_key, QueryValueEx=query_value)
        with patch.object(detection, 'winreg', registry):
            self.assertEqual(list(detection.registry_candidates()), [game]*8)
        self.assertEqual(roots, [('user', 3), ('user', 5), ('machine', 3), ('machine', 5)])

    def test_absent_registry_is_an_empty_source(self):
        with patch.object(detection, 'winreg', None):
            self.assertEqual(list(detection.registry_candidates()), [])

    def test_worker_results_ignore_partial_invalid_and_duplicate_lines(self):
        game = self.game()
        output = '\n'.join([json.dumps(str(game)), 'not json', json.dumps(str(game)),
                            '42', json.dumps('relative'), '"unfinished'])
        with patch.object(detection, 'IS_WINDOWS', True), \
                patch.object(detection.subprocess, 'run', return_value=SimpleNamespace(stdout=output)) as run:
            self.assertEqual(detection.detect_game_folders(), [game])
        self.assertEqual(run.call_args.kwargs['timeout'], 2.0)
        self.assertIn('-S', run.call_args.args[0])

    def test_timeout_retains_already_found_installations(self):
        game = self.game()
        error = subprocess.TimeoutExpired('worker', 2, output=(json.dumps(str(game))+'\n').encode())
        with patch.object(detection, 'IS_WINDOWS', True), \
                patch.object(detection.subprocess, 'run', side_effect=error):
            self.assertEqual(detection.detect_game_folders(), [game])

    def test_worker_failure_and_empty_timeout_fall_back(self):
        for error in (PermissionError('blocked'), subprocess.TimeoutExpired('worker', 2)):
            with self.subTest(error=error), patch.object(detection, 'IS_WINDOWS', True), \
                    patch.object(detection.subprocess, 'run', side_effect=error):
                self.assertEqual(detection.detect_game_folders(), [])

    def test_non_windows_platform_skips_the_worker(self):
        with patch.object(detection, 'IS_WINDOWS', False), \
                patch.object(detection.subprocess, 'run') as run:
            self.assertEqual(detection.detect_game_folders(), [])
        run.assert_not_called()

    def test_actual_stalled_worker_is_stopped_and_partial_match_is_kept(self):
        game = self.game()
        worker = self.root/'slow_worker.py'
        worker.write_text('import json, time\n'
                          f'print(json.dumps({str(game)!r}), flush=True)\n'
                          'time.sleep(30)\n', encoding='utf-8')
        before = time.monotonic()
        with patch.object(detection, 'IS_WINDOWS', True), patch.object(detection, '__file__', str(worker)):
            matches = detection.detect_game_folders(timeout=1)
        self.assertEqual(matches, [game])
        self.assertLess(time.monotonic()-before, 5)
