import copy
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from startup_cache import cache_path, load_cached_data, save_cached_data


class StartupCacheTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / 'game'
        self.package = self.game / 'res/packages/scripts.pkg'
        self.package.parent.mkdir(parents=True)
        self.write_resource(b'definition')
        self.replay = self.root / 'replays/map/a.wotreplay'
        self.replay.parent.mkdir(parents=True)
        self.replay.write_bytes(b'original')
        self.hashes = {'map/a.wotreplay': hashlib.sha256(b'original').hexdigest()}
        self.entries = {'scripts/map.xml': hashlib.sha256(b'definition').hexdigest()}
        self.data = dict(metadata={}, records=[dict(file='map/a.wotreplay',
            started_at='2026-09-24T12:00:00+08:00', result='unknown',
            in_window=True, players=[dict(in_window=True)],
            investigation=None, rating_delta=None)])
        self.cutoff = datetime.fromisoformat('2026-10-01T12:00:00+08:00')
        self.save()

    def write_resource(self, raw):
        with zipfile.ZipFile(self.package, 'w') as package:
            package.writestr('scripts/map.xml', raw)

    def save(self):
        save_cached_data(self.root, self.game, self.entries, self.hashes, self.data)

    def load(self, cutoff=None):
        return load_cached_data(self.root, self.game, cutoff or self.cutoff)

    def test_reuses_data_and_recomputes_exclusive_seven_day_window(self):
        original = copy.deepcopy(self.data)
        loaded = self.load()
        self.assertEqual(loaded['metadata']['recent_results'], {'unknown': 1})
        self.assertEqual(loaded['metadata']['recent_count'], 1)
        self.assertIsNone(loaded['records'][0]['rating_delta'])
        later = self.load(datetime.fromisoformat('2026-10-01T12:00:01+08:00'))
        self.assertEqual(later['metadata']['recent_count'], 0)
        self.assertFalse(later['records'][0]['players'][0]['in_window'])
        earlier = self.load(datetime.fromisoformat('2026-09-24T12:00:00+08:00'))
        self.assertFalse(earlier['records'][0]['in_window'])
        self.assertEqual(self.data, original)

    def test_same_size_replay_change_with_restored_mtime_invalidates(self):
        stat = self.replay.stat()
        self.replay.write_bytes(b'modified')
        os.utime(self.replay, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertIsNone(self.load())

    def test_added_and_deleted_replays_invalidate(self):
        extra = self.replay.with_name('new.wotreplay')
        extra.write_bytes(b'new')
        self.assertIsNone(self.load())
        extra.unlink()
        self.assertIsNotNone(self.load())
        self.replay.unlink()
        self.assertIsNone(self.load())

    def test_client_definition_change_invalidates(self):
        self.write_resource(b'changed')
        self.assertIsNone(self.load())

    def test_code_historical_evidence_and_game_cache_invalidate(self):
        for name in ('tools/explorer/server.py',
                     'DOCS/status/evidence/2026-09-30-replay-audit/missing-results.json',
                     'replays/ReplayCache.db'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'changed')
            with self.subTest(name=name):
                self.assertIsNone(self.load())
            path.unlink()
            self.assertIsNotNone(self.load())

    def test_corrupt_cache_or_missing_game_is_a_cache_miss(self):
        cache_path(self.root).write_text('{broken', encoding='utf-8')
        self.assertIsNone(self.load())
        self.save()
        self.package.unlink()
        self.assertIsNone(self.load())

    def test_old_version_and_invalid_cached_dates_are_cache_misses(self):
        target = cache_path(self.root)
        saved = json.loads(target.read_text(encoding='utf-8'))
        saved['version'] = -1
        target.write_text(json.dumps(saved), encoding='utf-8')
        self.assertIsNone(self.load())
        saved['version'] = 1
        saved['data']['records'][0]['started_at'] = 'invalid'
        target.write_text(json.dumps(saved), encoding='utf-8')
        self.assertIsNone(self.load())

    def test_changed_extraction_never_replaces_previous_cache(self):
        target = cache_path(self.root)
        original = target.read_bytes()
        self.replay.write_bytes(b'changed during extraction')
        self.save()
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(target.parent.glob('*.tmp')), [])
