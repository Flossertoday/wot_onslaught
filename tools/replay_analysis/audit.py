"""Read-only replay feasibility audit. Unknown results never become losses.

Only the length-prefixed JSON blocks are parsed; binary battle events are untouched.
Python 3 + scipy (for exploratory Fisher tests). No game process is launched.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import sqlite3
import struct
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

from packed_xml import unpack

TZ = timezone(timedelta(hours=8))
METRICS = ('damageDealt', 'damageAssistedRadio', 'damageAssistedTrack',
           'damageAssistedStun', 'damageAssistedInspire', 'damageBlockedByArmor',
           'damageReceived', 'kills', 'shots', 'directHits', 'piercings',
           'lifeTime', 'health', 'maxHealth', 'capturePoints', 'droppedCapturePoints',
           'comp7PrestigePoints', 'roleSkillUsed', 'poiCapturedByOwnTeam')


def read_blocks(path):
    with path.open('rb') as f:
        def read(n):
            data = f.read(n)
            if len(data) != n:
                raise ValueError('truncated replay JSON area')
            return data
        magic, count = struct.unpack('<II', read(8))
        if magic != 0x11343212 or not 1 <= count <= 8:
            raise ValueError('unsupported replay header')
        blocks = []
        for _ in range(count):
            size, = struct.unpack('<I', read(4))
            if size > 32 * 1024 * 1024:
                raise ValueError('oversized JSON block')
            blocks.append(json.loads(read(size)))
        return blocks


def win_interval(wins, total):
    if not total:
        return None, None
    z = 1.959963984540054
    p = wins / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total))/denom
    radius = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denom
    return center-radius, center+radius


def bh_adjust(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [1.] * len(values)
    bound = 1.
    for rank in range(len(order), 0, -1):
        i = order[rank-1]
        bound = min(bound, values[i]*len(values)/rank)
        result[i] = bound
    return result


class ClientDefinitions:
    def __init__(self, game):
        self.package = zipfile.ZipFile(game / 'res/packages/scripts.pkg')
        self.sources = {}
        self.maps = {}
        self.nations = {}

    def xml(self, name):
        raw = self.package.read(name)
        self.sources[name] = hashlib.sha256(raw).hexdigest()
        return unpack(raw)

    def spawns(self, map_id):
        if map_id not in self.maps:
            root = self.xml('scripts/arena_defs/' + map_id + '.xml')
            teams = {}
            for team in (1, 2):
                node = root.find(f'gameplayTypes/comp7/teamSpawnPoints/team{team}')
                teams[str(team)] = ([list(map(float, p.text.split())) for p in node]
                                    if node is not None else [])
            self.maps[map_id] = teams
        return self.maps[map_id]

    def vehicle(self, name):
        if not name or ':' not in name:
            return {}
        nation, tank = name.split(':', 1)
        if nation not in self.nations:
            root = self.xml(f'scripts/item_defs/vehicles/{nation}/list.xml')
            self.nations[nation] = {
                child.tag: {'vehicle_class': next((t for t in (child.findtext('tags') or '').split()
                            if t in ('heavyTank', 'mediumTank', 'lightTank', 'AT-SPG', 'SPG')), None),
                            'level': child.findtext('level')}
                for child in root if child.find('id') is not None}
        return self.nations[nation].get(tank, {})


def cache_rows(root):
    path = root / 'ReplayCache.db'
    if not path.exists():
        return {}
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        # Do not request localized columns: the cache stores some text as GBK.
        rows = db.execute('SELECT szRplyFilePath,iIsWinner,uiReplayFileSize FROM WotReplayInfo')
        result = {}
        for row in rows:
            name = PureWindowsPath(row['szRplyFilePath']).name
            if name in result:
                raise ValueError('ambiguous cache basename: ' + name)
            result[name] = dict(row)
        return result


def extract(path, root, cutoff, client, cache):
    blocks = read_blocks(path)
    h = blocks[0]
    started = datetime.strptime(h['dateTime'], '%d.%m.%Y %H:%M:%S').replace(tzinfo=TZ)
    if h.get('gameplayID') != 'comp7' or h.get('battleType') != 43:
        raise ValueError('non-Onslaught replay')
    header_vehicle = h['playerVehicle'].replace('-', ':', 1)
    own_headers = [v for v in h['vehicles'].values() if v.get('name') == h['playerName']]
    header_team = own_headers[0]['team'] if len(own_headers) == 1 else None
    cached = cache.get(path.name, {})
    row = dict(file=path.relative_to(root).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               bytes=path.stat().st_size, started_at=started.isoformat(),
               in_window=cutoff-timedelta(days=7) <= started < cutoff,
               map_id=h['mapName'], map_name=h['mapDisplayName'],
               client_version=h['clientVersionFromExe'], json_blocks=len(blocks),
               header_vehicle=header_vehicle, header_team=header_team,
               team=header_team, team_source='header.name_unique_match' if header_team else None,
               result='unknown', result_status='no_result_block',
               cache_outcome=cached.get('iIsWinner'),
               cache_size_matches=cached.get('uiReplayFileSize') == path.stat().st_size)
    row['spawn_points'] = client.spawns(row['map_id']).get(str(header_team), [])
    if len(blocks) < 2:
        return row, []
    if not isinstance(blocks[1], list) or not blocks[1] or not isinstance(blocks[1][0], dict):
        row['result_status'] = 'invalid_result_block'
        return row, []
    result = blocks[1][0]
    common = result.get('common', {})
    roster = result.get('players', {})
    avatar = result.get('personal', {}).get('avatar', {})
    pid = h['playerID']
    own = [(vid, item) for vid, entries in result.get('vehicles', {}).items()
           for item in entries if item.get('accountDBID') == pid]
    if len(own) != 1 or str(pid) not in roster or avatar.get('accountDBID') != pid:
        row['result_status'] = 'invalid_self_identity'
        return row, []
    vid, personal = own[0]
    team = personal.get('team')
    if team not in (1, 2) or roster[str(pid)]['team'] != team or avatar.get('team') != team or (header_team and team != header_team):
        row['result_status'] = 'inconsistent_team'
        return row, []
    final_roster = blocks[1][1] if len(blocks[1]) > 1 and isinstance(blocks[1][1], dict) else {}
    final_vehicle = final_roster.get(vid, {}).get('vehicleType')
    if final_vehicle != header_vehicle:
        row['result_status'] = 'vehicle_mismatch'
        return row, []
    seconds = started.timestamp() - common.get('arenaCreateTime', 0)
    if not 0 <= seconds <= 300:
        row['result_status'] = 'arena_time_mismatch'
        return row, []
    winner = common.get('winnerTeam')
    if winner not in (0, 1, 2):
        row['result_status'] = 'invalid_winner'
        return row, []
    row.update(result_status='valid', arena_id=str(result['arenaUniqueID']), team=team,
               team_source='results.accountDBID', winner_team=winner,
               result='draw' if winner == 0 else 'win' if winner == team else 'loss',
               vehicle=final_vehicle, duration=common.get('duration'), finish_reason=common.get('finishReason'),
               arena_time_offset_seconds=seconds, rating_before=avatar.get('comp7Rating'),
               rating_delta=avatar.get('comp7RatingDelta'), qualification=avatar.get('comp7QualActive'),
               premature_leave=avatar.get('isPrematureLeave'), watched_to_end=avatar.get('watchedBattleToTheEnd'),
               rank_raw=avatar.get('comp7Rank'), prebattle_id=roster[str(pid)].get('prebattleID'))
    row.update(client.vehicle(final_vehicle))
    row.update({key: personal.get(key) for key in METRICS})
    row['spawn_points'] = client.spawns(row['map_id']).get(str(team), [])
    if row['rating_before'] is not None and row['rating_delta'] is not None:
        row['rating_after'] = max(0, row['rating_before'] + row['rating_delta'])
    divisions = h['serverSettings']['comp7_ranks_config']['divisions']
    players = []
    for vehicle_id, entries in result['vehicles'].items():
        for item in entries:
            aid = item.get('accountDBID')
            av = result.get('avatars', {}).get(str(aid), {})
            rank = av.get('comp7Rank')
            division = next((d for d in divisions if rank and len(rank) == 3
                             and d['rank'] == rank[0] and d['index'] == rank[1]), None)
            vehicle = final_roster.get(vehicle_id, {}).get('vehicleType')
            player = dict(file=row['file'], arena_id=row['arena_id'], in_window=row['in_window'],
                          is_self=aid == pid, is_ally=item.get('team') == team,
                          team=item.get('team'), vehicle=vehicle,
                          rank_raw=rank, qualification=av.get('comp7QualActive'),
                          rank_label=(division['tags'][0] + ' ' + division['name']).strip() if division else None,
                          rank_rating_range=division['range'] if division and not av.get('comp7QualActive') else None,
                          prebattle_id=roster.get(str(aid), {}).get('prebattleID'))
            player.update(client.vehicle(vehicle))
            player.update({key: item.get(key) for key in METRICS})
            players.append(player)
    own_rank = next((p for p in players if p['is_self']), {})
    rating_range = own_rank.get('rank_rating_range')
    row['rank_matches_rating_before'] = (rating_range[0] <= row['rating_before'] <= rating_range[1]
                                         if rating_range and row['rating_before'] is not None else None)
    row['rank_matches_rating_after'] = (rating_range[0] <= row['rating_after'] <= rating_range[1]
                                        if rating_range and row.get('rating_after') is not None else None)
    row['self_rank_matches_avatar'] = row['rank_raw'] == own_rank.get('rank_raw')
    row['ally_ranks'] = [p['rank_label'] if not p['qualification'] else 'qualification'
                        for p in players if p['is_ally'] and not p['is_self']]
    row['enemy_ranks'] = [p['rank_label'] if not p['qualification'] else 'qualification'
                         for p in players if not p['is_ally']]
    return row, players


def summarize(rows, fields=('map_id', 'map_name'), test_maps=False):
    from scipy.stats import fisher_exact
    groups = collections.defaultdict(list)
    recent = [r for r in rows if r['in_window'] and not r.get('duplicate')]
    all_known = [r for r in recent if r['result'] != 'unknown']
    total_wins = sum(r['result'] == 'win' for r in all_known)
    for row in recent:
        groups[tuple(row.get(k) for k in fields)].append(row)
    summary = []
    for key, group in groups.items():
        counts = collections.Counter(r['result'] for r in group)
        wins, losses, draws, unknown = (counts[k] for k in ('win', 'loss', 'draw', 'unknown'))
        known = wins+losses+draws
        low, high = win_interval(wins, known)
        entry = dict(zip(fields, key))
        entry.update(total=len(group), known=known, wins=wins, losses=losses, draws=draws,
                     unknown=unknown, win_rate=wins/known if known else None,
                     wilson_low=low, wilson_high=high,
                     all_replays_win_rate_lower=wins/len(group),
                     all_replays_win_rate_upper=(wins+unknown)/len(group))
        if test_maps:
            rest_n, rest_w = len(all_known)-known, total_wins-wins
            entry['rest_known_win_rate'] = rest_w/rest_n if rest_n else None
            entry['fisher_p_low'] = float(fisher_exact([[wins, known-wins], [rest_w, rest_n-rest_w]], alternative='less').pvalue) if known and rest_n else 1.
        summary.append(entry)
    if test_maps:
        for row, q in zip(summary, bh_adjust([r['fisher_p_low'] for r in summary])):
            row['bh_q_low'] = q
    return sorted(summary, key=lambda r: (r['win_rate'] is None, r['win_rate'] or 0, str(r)))


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replays', type=Path, default=Path('replays'))
    parser.add_argument('--game', type=Path, default=Path('C:/Games/World_of_Tanks_CN'))
    parser.add_argument('--cutoff', required=True, help='ISO datetime with UTC offset; exclusive')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff)
    if cutoff.tzinfo is None:
        parser.error('--cutoff must include a UTC offset')
    client = ClientDefinitions(args.game)
    cache = cache_rows(args.replays)
    rows, players, failures = [], [], []
    seen_hashes, seen_arenas = set(), set()
    for path in sorted(args.replays.rglob('*.wotreplay')):
        try:
            row, participants = extract(path, args.replays, cutoff, client, cache)
        except (ValueError, KeyError, TypeError, IndexError, OSError, struct.error) as error:
            failures.append({'file':path.relative_to(args.replays).as_posix(), 'error':str(error)})
            continue
        row['duplicate'] = row['sha256'] in seen_hashes or (row.get('arena_id') is not None and row['arena_id'] in seen_arenas)
        seen_hashes.add(row['sha256'])
        if row.get('arena_id'):
            seen_arenas.add(row['arena_id'])
        rows.append(row)
        if not row['duplicate']:
            players.extend(participants)
    client.package.close()
    recent = [r for r in rows if r['in_window'] and not r['duplicate']]
    valid = [r for r in rows if r['result_status'] == 'valid' and not r['duplicate']]
    evidence = dict(cutoff=cutoff.isoformat(), window_start=(cutoff-timedelta(days=7)).isoformat(),
                    clock='header.dateTime interpreted as UTC+08; arenaCreateTime cross-check',
                    files=len(rows), failures=failures, duplicates=sum(r['duplicate'] for r in rows),
                    all_status=dict(collections.Counter(r['result_status'] for r in rows)),
                    recent_status=dict(collections.Counter(r['result_status'] for r in recent)),
                    recent_results=dict(collections.Counter(r['result'] for r in recent)),
                    recent_count=len(recent), excluded_old_or_future=len(rows)-len(recent),
                    cache_size_matches=sum(r['cache_size_matches'] for r in rows),
                    cache_known_outcome_agrees=sum(r['cache_outcome'] == int(r['result']=='win') for r in valid),
                    unknown_cache_outcomes=dict(collections.Counter(str(r['cache_outcome']) for r in rows if r['result']=='unknown')),
                    valid_player_rows=len(players),
                    recent_player_rows=sum(p['in_window'] for p in players),
                    rank_rows=sum(p['rank_raw'] is not None for p in players),
                    qualification_rows=sum(bool(p['qualification']) for p in players),
                    rank_matches_rating_before=sum(r.get('rank_matches_rating_before') is True for r in valid),
                    rank_matches_rating_after=sum(r.get('rank_matches_rating_after') is True for r in valid),
                    self_rank_matches_avatar=sum(r.get('self_rank_matches_avatar') is True for r in valid),
                    resolved_vehicle_classes=sum(p.get('vehicle_class') is not None for p in players),
                    spawn_mapped_rows=sum(bool(r['spawn_points']) for r in rows),
                    client_entry_sha256=client.sources, spawn_definitions=client.maps,
                    caveats=['Known-result statistics only; missing outcomes may be nonrandom.',
                             'Fisher/BH is exploratory: assumes independent battles; no confounder adjustment.',
                             'Spawn coordinates are map configuration, not measured vehicle positions.',
                             'Other players have rank categories, not exact rating points.',
                             'Bounds assign all unknown results to losses or wins; they are not confidence intervals.'])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'audit.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_csv(args.output/'battles.csv', rows)
    write_csv(args.output/'players.csv', players)
    write_csv(args.output/'maps.csv', summarize(rows, test_maps=True))
    write_csv(args.output/'map_teams.csv', summarize(rows, ('map_id', 'map_name', 'team')))
    write_csv(args.output/'map_header_vehicles.csv', summarize(rows, ('map_id', 'map_name', 'header_vehicle')))
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('client_entry_sha256','spawn_definitions','caveats')}, ensure_ascii=True, indent=2))
    if failures:
        raise SystemExit('Some files failed: review audit.json before using summary tables.')


if __name__ == '__main__':
    main()
