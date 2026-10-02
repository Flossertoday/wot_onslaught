"""Copy completed Onslaught replays into map folders without changing source files."""
import argparse
import json
import os
import re
import shutil
import struct
import tempfile
import time
from pathlib import Path

from audit import read_blocks
from local_paths import DEFAULT_CONFIG, local_paths

ROOT = Path(__file__).resolve().parents[2]


def same_content(left, right):
    # Synchronization only needs exact equality; computing two hashes adds CPU work.
    # Read every byte, including events, and never infer equality from timestamps.
    with left.open('rb') as source, right.open('rb') as target:
        while True:
            block = source.read(256 * 1024)
            if block != target.read(256 * 1024):
                return False
            if not block:
                return True


def signature(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def sync_replays(source=None, destination=ROOT / 'replays', min_age=10):
    if source is None:
        _, source = local_paths()
    if source is None:
        raise ValueError('Set --source or configure a game folder in explorer.local.json')
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Source and destination must differ')
    report = dict(copied=0, existing=0, ignored=0, pending=0, conflicts=[], errors=[])
    try:
        candidates = sorted(source.iterdir())
    except OSError as error:
        report['errors'].append(f'{source}: {error}')
        return report
    for path in candidates:
        if path.suffix.lower() != '.wotreplay':
            continue
        temporary = None
        try:
            before = signature(path)
            if path.name.lower() == 'temp.wotreplay' or time.time() - path.stat().st_mtime < min_age:
                report['pending'] += 1
                continue
            header = read_blocks(path, header_only=True)[0]
            if not isinstance(header, dict):
                raise ValueError('invalid replay header')
            if header.get('gameplayID') != 'comp7' or header.get('battleType') != 43:
                report['ignored'] += 1
                continue
            map_id = header.get('mapName')
            if not isinstance(map_id, str) or not re.fullmatch(r'\d+_[A-Za-z0-9_]+', map_id):
                raise ValueError('invalid mapName')
            target = destination / map_id.replace('_', '-', 1) / path.name
            if target.exists():
                same = same_content(path, target)
                if signature(path) != before:
                    report['pending'] += 1
                elif same:
                    report['existing'] += 1
                else:
                    report['conflicts'].append(path.name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.part', delete=False) as temp:
                temporary = Path(temp.name)
            shutil.copy2(path, temporary)
            if signature(path) != before or temporary.stat().st_size != before[0]:
                report['pending'] += 1
                continue
            read_blocks(temporary)
            # Publish a complete file atomically and never replace an existing replay.
            try:
                os.link(temporary, target)
                report['copied'] += 1
            except FileExistsError:
                if same_content(temporary, target):
                    report['existing'] += 1
                else:
                    report['conflicts'].append(path.name)
        except (OSError, ValueError, TypeError, IndexError, struct.error) as error:
            report['errors'].append(f'{path.name}: {error}')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--game', type=Path)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--destination', type=Path, default=ROOT / 'replays')
    args = parser.parse_args()
    try:
        _, source = local_paths(args.game, args.source, args.config)
        if source is None:
            parser.error('Set --source, --game, or configure explorer.local.json')
        report = sync_replays(source, args.destination)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report['errors'] or report['conflicts'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
