"""Verify GUI performance values against raw replay JSON; write anonymous coverage evidence."""
import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from audit import METRICS, read_blocks


def distribution(values):
    values = [v for v in values if v is not None]
    if not values:
        return {'count': 0, 'min': None, 'median': None, 'mean': None, 'max': None}
    return dict(count=len(values), min=min(values), median=statistics.median(values),
                mean=statistics.mean(values), max=max(values))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def inventory(root, evidence):
    battles = read_csv(evidence/'battles.csv')
    players = defaultdict(list)
    for row in read_csv(evidence/'players.csv'):
        players[row['file']].append(row)
    checked = []
    statuses = Counter()
    for battle in battles:
        path = root/'replays'/battle['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != battle['sha256']:
            raise ValueError('Snapshot hash mismatch: ' + battle['file'])
        blocks = read_blocks(path)
        statuses[battle['result_status']] += 1
        if battle['result_status'] != 'valid':
            if players[battle['file']] or any(battle.get(k) for k in METRICS):
                raise ValueError('Invalid result has promoted metrics: ' + battle['file'])
            continue
        h, result = blocks[0], blocks[1][0]
        entries = [v for group in result['vehicles'].values() for v in group]
        own = [v for v in entries if v.get('accountDBID') == h['playerID']]
        avatar = result['personal']['avatar']
        if len(entries) != 14 or len(own) != 1 or avatar['accountDBID'] != h['playerID']:
            raise ValueError('Identity or roster mismatch: ' + battle['file'])
        own = own[0]
        # Compare whole row multisets, retaining side and self identity. No names/IDs exported.
        raw_rows = Counter((v['team'], v['accountDBID'] == h['playerID'],
                            *(v.get(k) for k in METRICS)) for v in entries)
        csv_rows = Counter((int(p['team']), p['is_self'] == 'True',
                            *(float(p[k]) if p.get(k) else None for k in METRICS))
                           for p in players[battle['file']])
        if raw_rows != csv_rows:
            raise ValueError('Participant CSV differs from replay: ' + battle['file'])
        expected = {**{k: own.get(k) for k in METRICS},
                    'rating_before': avatar.get('comp7Rating'),
                    'rating_delta': avatar.get('comp7RatingDelta')}
        for key, value in expected.items():
            if (float(battle[key]) if battle.get(key) else None) != value:
                raise ValueError(f'Self CSV mismatch: {battle["file"]} {key}')
        checked.append(dict(file=battle['file'], in_window=battle['in_window'] == 'True',
                            outcome=battle['result'], own=own, avatar=avatar,
                            entries=entries, public_avatars=list(result['avatars'].values())))

    def summary(rows):
        entries = [v for r in rows for v in r['entries']]
        public = [v for r in rows for v in r['public_avatars']]
        return dict(
            battles=len(rows), participants=len(entries),
            participant_fields={k: dict(present=sum(v.get(k) is not None for v in entries),
                                       nonzero=sum(bool(v.get(k)) for v in entries),
                                       **distribution(v.get(k) for v in entries)) for k in METRICS},
            self_prestige=distribution(r['own'].get('comp7PrestigePoints') for r in rows),
            self_prestige_over_200=sum(r['own']['comp7PrestigePoints'] > 200 for r in rows),
            participants_prestige_over_200=sum(v['comp7PrestigePoints'] > 200 for v in entries),
            self_rating_delta=distribution(r['avatar'].get('comp7RatingDelta') for r in rows),
            rating_by_result={outcome: distribution(r['avatar'].get('comp7RatingDelta')
                                                   for r in rows if r['outcome'] == outcome)
                              for outcome in ('win', 'loss', 'draw')},
            public_rating_fields={k: sum(v.get(k) is not None for v in public)
                                  for k in ('comp7Rating', 'comp7RatingDelta')},
            delta_sign_violations=sum((r['outcome'] == 'win' and r['avatar']['comp7RatingDelta'] <= 0)
                                     or (r['outcome'] == 'loss' and r['avatar']['comp7RatingDelta'] >= 0)
                                     for r in rows),
            delta_outside_user_range=sum(abs(r['avatar']['comp7RatingDelta']) > 46 for r in rows))

    return dict(source='Raw JSON blocks cross-checked with SHA-256 and CSV snapshot',
                snapshot=evidence.name, files=len(battles), statuses=dict(statuses),
                all=summary(checked), recent=summary([r for r in checked if r['in_window']]),
                self_over_200_examples=[dict(file=r['file'], prestige=r['own']['comp7PrestigePoints'],
                                            rating_delta=r['avatar']['comp7RatingDelta'])
                                        for r in checked if r['own']['comp7PrestigePoints'] > 200])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.root, args.root/'DOCS/status/evidence/2026-09-30-replay-audit')
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('files', 'statuses')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
