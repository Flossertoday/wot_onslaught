"""Disposable GUI snapshots, validated by content rather than timestamps."""
import collections
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

VERSION = 1
EVIDENCE_PATH = Path('DOCS/status/evidence/2026-09-30-replay-audit')
INPUTS = ('tools/explorer/server.py', 'tools/explorer/startup_cache.py',
          'tools/replay_analysis/audit.py', 'tools/replay_analysis/packed_xml.py',
          *(str(EVIDENCE_PATH / name) for name in
            ('audit.json', 'battles.csv', 'players.csv', 'missing-results.json')),
          'replays/ReplayCache.db')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dependency_stamp(root, game):
    """Refuse publication if dependencies changed while the extractor was running."""
    paths = [root / name for name in INPUTS] + [game / 'res/packages/scripts.pkg']
    return [(str(path), (path.stat().st_size, path.stat().st_mtime_ns)
             if path.exists() else None) for path in paths]


def fingerprint(root, game, entries):
    replays = root / 'replays'
    hashes = {path.relative_to(replays).as_posix(): digest(path)
              for path in sorted(replays.rglob('*.wotreplay'))}
    inputs = {name: digest(root / name) if (root / name).exists() else None
              for name in INPUTS}
    with zipfile.ZipFile(game / 'res/packages/scripts.pkg') as package:
        resources = {name: hashlib.sha256(package.read(name)).hexdigest()
                     for name in sorted(entries)}
    return dict(game=str(game.resolve()), replays=hashes, inputs=inputs, resources=resources)


def refresh_window(data, cutoff):
    start = cutoff - timedelta(days=7)
    for row in data['records']:
        row['in_window'] = start <= datetime.fromisoformat(row['started_at']) < cutoff
        for player in row['players']:
            player['in_window'] = row['in_window']
    recent = [row for row in data['records'] if row['in_window']]
    data['metadata'].update(cutoff=cutoff.isoformat(), window_start=start.isoformat(),
                            recent_count=len(recent),
                            recent_results=dict(collections.Counter(row['result'] for row in recent)))
    return data


def cache_path(root):
    return root / '.drafts/explorer-cache/snapshot.json'


def load_cached_data(root, game, cutoff):
    try:
        saved = json.loads(cache_path(root).read_text(encoding='utf-8'))
        if saved['version'] != VERSION:
            return None
        if fingerprint(root, game, saved['fingerprint']['resources']) != saved['fingerprint']:
            return None
        return refresh_window(saved['data'], cutoff)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile):
        return None


def save_cached_data(root, game, entries, replay_hashes, data):
    current = fingerprint(root, game, entries)
    if current['replays'] != replay_hashes or current['resources'] != entries:
        # A replay/resource changed during extraction: never cache a mixed snapshot.
        return
    target = cache_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(dict(version=VERSION, fingerprint=current, data=data),
                                    ensure_ascii=False, allow_nan=False))
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
