"""Copy completed Onslaught replays into map folders without changing source files."""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import time
from pathlib import Path

from audit import read_blocks

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path('C:/Games/World_of_Tanks_CN/replays')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def signature(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def sync_replays(source=DEFAULT_SOURCE, destination=ROOT / 'replays', min_age=10):
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
            header = read_blocks(path)[0]
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
                same = digest(path) == digest(target)
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
                if digest(temporary) == digest(target):
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
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--destination', type=Path, default=ROOT / 'replays')
    args = parser.parse_args()
    report = sync_replays(args.source, args.destination)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report['errors'] or report['conflicts'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
