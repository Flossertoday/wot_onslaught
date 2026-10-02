import contextlib
import csv
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'replays').mkdir()
        (self.root/'replays/a.wotreplay').write_bytes(b'mocked extractor input')
        paths = patch.object(server, 'local_paths', return_value=(self.root/'game', None))
        paths.start()
        self.addCleanup(paths.stop)

    def test_refresh_passes_current_cutoff_and_reads_new_output(self):
        def run(command, **kwargs):
            output = Path(command[command.index('--output')+1])
            self.assertIn('--cutoff', command)
            self.assertIn('--data-only', command)
            self.assertTrue(command[command.index('--cutoff')+1].endswith('+08:00'))
            self.assertEqual(command[command.index('--replays')+1], str(self.root/'replays'))
            for name in ('audit.json', 'battles.csv', 'players.csv'):
                shutil.copy2(server.EVIDENCE/name, output/name)
            audit = json.loads((output/'audit.json').read_text(encoding='utf-8'))
            audit['cutoff'] = command[command.index('--cutoff')+1]
            (output/'audit.json').write_text(json.dumps(audit), encoding='utf-8')
            return subprocess.CompletedProcess(command, 0, '', '')

        with patch.object(server, 'ROOT', self.root), patch.object(server.subprocess, 'run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(source=None)
        self.assertIn('分析已更新', data['metadata']['startup_message'])
        self.assertEqual(len(data['records']), 431)
        self.assertEqual(len(list((self.root/'.drafts/explorer').iterdir())), 0)

    def test_verified_cache_skips_extractor_and_keeps_sync_message(self):
        cached = dict(metadata={}, records=[{}])
        report = dict(copied=0, existing=1, ignored=2, pending=0, conflicts=[], errors=[])
        with patch.object(server, 'ROOT', self.root), \
                patch.object(server, 'sync_replays', return_value=report), \
                patch.object(server, 'load_cached_data', return_value=cached), \
                patch.object(server.subprocess, 'run') as run, \
                contextlib.redirect_stdout(io.StringIO()):
            result = server.load_startup_data(source=self.root/'source')
        run.assert_not_called()
        self.assertIn('已有 1，已跳过非天梯 2', result['metadata']['startup_message'])
        self.assertIn('已校验并复用分析缓存', result['metadata']['startup_message'])

    def test_cache_write_failure_keeps_successful_analysis(self):
        def run(command, **kwargs):
            output = Path(command[command.index('--output')+1])
            for name in ('audit.json', 'battles.csv', 'players.csv'):
                shutil.copy2(server.EVIDENCE/name, output/name)
            return subprocess.CompletedProcess(command, 0, '', '')
        with patch.object(server, 'ROOT', self.root), \
                patch.object(server.subprocess, 'run', side_effect=run), \
                patch.object(server, 'save_cached_data', side_effect=OSError('disk full')), \
                contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(source=None)
        self.assertIn('分析已更新', data['metadata']['startup_message'])
        self.assertNotIn('历史快照', data['metadata']['startup_message'])
        self.assertEqual(len(data['records']), 431)

    def test_sync_message_marks_non_onslaught_as_skipped(self):
        report = dict(copied=69, existing=431, ignored=81, pending=1, conflicts=[], errors=[])
        data = dict(metadata={}, records=[{}] * 500)
        with patch.object(server, 'ROOT', self.root), \
                patch.object(server, 'sync_replays', return_value=report), \
                patch.object(server.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), \
                patch.object(server, 'build_data', return_value=data), \
                contextlib.redirect_stdout(io.StringIO()):
            result = server.load_startup_data(source=self.root/'source')
        message = result['metadata']['startup_message']
        self.assertIn('新增 69，已有 431，已跳过非天梯 81', message)
        self.assertIn('共 500 场录像', message)

    def test_failure_shows_no_other_persons_historical_data(self):
        with patch.object(server, 'ROOT', self.root), patch.object(server.subprocess, 'run', side_effect=OSError('missing Python')), contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(source=self.root/'missing')
        self.assertIn('错误 1', data['metadata']['startup_message'])
        self.assertIn('当前未加载对局', data['metadata']['startup_message'])
        self.assertEqual(data['records'], [])
        self.assertEqual(data['metadata']['data_mode'], 'local')

    def test_changed_replay_does_not_inherit_old_investigation(self):
        for name in ('audit.json', 'battles.csv', 'players.csv'):
            shutil.copy2(server.EVIDENCE/name, self.root/name)
        with (self.root/'battles.csv').open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        investigated = next(r for r in server.build_data()['records'] if r['result']=='unknown' and r['investigation'])
        next(r for r in rows if r['file']==investigated['file'])['sha256'] = 'changed'
        with (self.root/'battles.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        data = server.build_data(self.root, investigation_evidence=server.EVIDENCE)
        changed = next(r for r in data['records'] if r['id']=='changed')
        self.assertIsNone(changed['investigation'])
        self.assertEqual(changed['tags']['observed_death'], '未调查')
        self.assertEqual(changed['tags']['recording_end'], '假设提前离场 / 无战报')
        self.assertTrue(any(r['investigation'] for r in data['records']))


if __name__ == '__main__':
    unittest.main()
