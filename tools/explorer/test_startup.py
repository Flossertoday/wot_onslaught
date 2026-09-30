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

    def test_refresh_passes_current_cutoff_and_reads_new_output(self):
        def run(command, **kwargs):
            output = Path(command[command.index('--output')+1])
            self.assertIn('--cutoff', command)
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

    def test_failure_keeps_historical_data_and_visible_warning(self):
        with patch.object(server, 'ROOT', self.root), patch.object(server.subprocess, 'run', side_effect=OSError('missing Python')), contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(source=self.root/'missing')
        self.assertIn('错误 1', data['metadata']['startup_message'])
        self.assertIn('当前显示历史快照', data['metadata']['startup_message'])
        self.assertEqual(len(data['records']), 431)

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
        self.assertTrue(any(r['investigation'] for r in data['records']))


if __name__ == '__main__':
    unittest.main()
