import json
import os
import shutil
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sync_replays import sync_replays


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'game'
        self.source.mkdir()
        self.destination = self.root/'replays'

    def replay(self, name='battle.wotreplay', **fields):
        header = dict(gameplayID='comp7', battleType=43, mapName='115_sweden_comp7_nb')
        header.update(fields)
        raw = json.dumps(header).encode()
        path = self.source/name
        path.write_bytes(struct.pack('<III', 0x11343212, 1, len(raw)) + raw + b'events')
        os.utime(path, (time.time()-60, time.time()-60))
        return path

    def sync(self):
        return sync_replays(self.source, self.destination)

    def test_copy_preserves_bytes_and_is_idempotent(self):
        source = self.replay()
        raw, modified = source.read_bytes(), source.stat().st_mtime_ns
        self.assertEqual(self.sync()['copied'], 1)
        target = self.destination/'115-sweden_comp7_nb'/source.name
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(target.stat().st_mtime_ns, modified)
        self.assertEqual(self.sync()['existing'], 1)
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(len(list(self.destination.rglob('*.wotreplay'))), 1)

    def test_filter_by_header_not_filename(self):
        self.replay('Onslaught_regular.wotreplay', gameplayID='ctf', battleType=1)
        self.replay('renamed.wotreplay')
        report = self.sync()
        self.assertEqual((report['copied'], report['ignored']), (1, 1))
        self.assertTrue((self.source/'Onslaught_regular.wotreplay').exists())

    def test_conflicting_file_is_never_overwritten(self):
        self.replay()
        self.sync()
        target = next(self.destination.rglob('*.wotreplay'))
        target.write_bytes(b'local original')
        report = self.sync()
        self.assertEqual(report['conflicts'], ['battle.wotreplay'])
        self.assertEqual(target.read_bytes(), b'local original')

    def test_temp_recent_and_malformed_are_skipped(self):
        self.replay('temp.wotreplay')
        recent = self.replay('recent.wotreplay')
        os.utime(recent, None)
        broken = self.replay('broken.wotreplay')
        broken.write_bytes(b'bad')
        os.utime(broken, (time.time()-60, time.time()-60))
        self.replay('valid.wotreplay')
        report = self.sync()
        self.assertEqual((report['pending'], len(report['errors']), report['copied']), (2, 1, 1))

    def test_source_changing_during_copy_is_not_published(self):
        self.replay()
        real_copy = shutil.copy2

        def changing_copy(source, target):
            real_copy(source, target)
            with source.open('ab') as stream:
                stream.write(b'new events')

        with patch('sync_replays.shutil.copy2', side_effect=changing_copy):
            self.assertEqual(self.sync()['pending'], 1)
        self.assertEqual(list(self.destination.rglob('*.wotreplay')), [])
        self.assertEqual(list(self.destination.rglob('*.part')), [])

    def test_concurrent_publication_does_not_clobber(self):
        self.replay()

        def publish_elsewhere(temp, target):
            target.write_bytes(b'other launch')
            raise FileExistsError()

        with patch('sync_replays.os.link', side_effect=publish_elsewhere):
            self.assertEqual(self.sync()['conflicts'], ['battle.wotreplay'])
        self.assertEqual(next(self.destination.rglob('*.wotreplay')).read_bytes(), b'other launch')
        self.assertEqual(list(self.destination.rglob('*.part')), [])

    def test_invalid_map_cannot_escape_destination(self):
        self.replay(mapName='../escape')
        self.assertEqual(len(self.sync()['errors']), 1)
        self.assertFalse(self.destination.exists())

    def test_missing_source_and_same_directory(self):
        report = sync_replays(self.root/'absent', self.destination)
        self.assertEqual(len(report['errors']), 1)
        with self.assertRaises(ValueError):
            sync_replays(self.source, self.source)


if __name__ == '__main__':
    unittest.main()
