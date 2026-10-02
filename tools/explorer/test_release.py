"""Exercise release startup and downloads without the author's installation or replays."""
import contextlib
import hashlib
import io
import json
import os
import struct
import tempfile
import threading
import time
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

import server


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.game = self.root/'game with spaces'
        self.source = self.game/'replays'
        self.source.mkdir(parents=True)
        package = self.game/'res/packages/scripts.pkg'
        package.parent.mkdir(parents=True)
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('scripts/arena_defs/04_himmelsdorf.xml',
                             '<root><gameplayTypes><comp7><teamSpawnPoints><team1>'
                             '<point>1 2 3</point></team1></teamSpawnPoints></comp7></gameplayTypes></root>')

    def replay(self):
        header = dict(gameplayID='comp7', battleType=43, mapName='04_himmelsdorf',
                      mapDisplayName='Test map', playerVehicle='ussr-Test', playerName='Test',
                      playerID=1, vehicles={'0': {'name': 'Test', 'team': 1}},
                      clientVersionFromExe='test',
                      dateTime=(datetime.now(timezone(timedelta(hours=8)))-timedelta(minutes=1)).strftime('%d.%m.%Y %H:%M:%S'))
        raw = json.dumps(header).encode()
        path = self.source/'test.wotreplay'
        path.write_bytes(struct.pack('<III', 0x11343212, 1, len(raw)) + raw + b'events')
        os.utime(path, (time.time()-60, time.time()-60))
        return path

    def test_unconfigured_fresh_checkout_has_no_historical_records(self):
        with patch.object(server, 'ROOT', self.root), \
                patch.object(server, 'local_paths', return_value=(None, None)), \
                patch.object(server.subprocess, 'run') as extractor:
            data = server.load_startup_data()
        extractor.assert_not_called()
        self.assertEqual(data['records'], [])
        self.assertIn('尚未配置', data['metadata']['startup_message'])

    def test_configured_game_without_replays_is_an_empty_local_explorer(self):
        with patch.object(server, 'ROOT', self.root), contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(self.source, self.game)
        self.assertEqual(data['records'], [])
        self.assertIn('尚无天梯录像', data['metadata']['startup_message'])

    def test_real_extraction_from_a_relocated_game_without_site_packages(self):
        source = self.replay()
        original = source.read_bytes()
        # Use the actual extractor in a different working tree, with no third-party packages.
        import subprocess
        actual_run = subprocess.run
        code_root = server.ROOT

        def run(command, **kwargs):
            command[1] = str(code_root/'tools/replay_analysis/audit.py')
            command.insert(1, '-S')
            return actual_run(command, **kwargs)

        with patch.object(server, 'ROOT', self.root), \
                patch.object(server.subprocess, 'run', side_effect=run), \
                contextlib.redirect_stdout(io.StringIO()):
            data = server.load_startup_data(self.source, self.game)
        self.assertEqual(len(data['records']), 1, data['metadata']['startup_message'])
        record = data['records'][0]
        self.assertEqual(record['result'], 'unknown')
        self.assertIsNone(record.get('rating_delta'))
        self.assertTrue(record['replay_available'])
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(Path(record['replay_path']).read_bytes(), original)
        self.assertEqual(data['metadata']['data_mode'], 'local')

    def test_missing_changed_and_outside_archive_downloads_return_http_errors(self):
        archive = self.root/'replays'
        archive.mkdir()
        (archive/'changed.wotreplay').write_bytes(b'changed')
        (self.root/'outside.txt').write_bytes(b'private')
        records = [dict(id='missing', file='missing.wotreplay', sha256='missing'),
                   dict(id='changed', file='changed.wotreplay', sha256=hashlib.sha256(b'original').hexdigest()),
                   dict(id='outside', file='../outside.txt', sha256=hashlib.sha256(b'private').hexdigest())]
        with patch.object(server, 'ROOT', self.root):
            http = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler({'records': records}))
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                for name, status in (('missing', 404), ('changed', 409), ('outside', 404)):
                    with self.subTest(name=name), self.assertRaises(HTTPError) as raised:
                        urlopen(f'http://127.0.0.1:{http.server_port}/replay/{name}', timeout=3)
                    self.assertEqual(raised.exception.code, status)
                    raised.exception.close()
            finally:
                http.shutdown()
                http.server_close()
                thread.join()
