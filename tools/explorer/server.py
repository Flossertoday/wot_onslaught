"""Local Onslaught research UI with replay sync at startup. Run from any directory."""
import argparse
import csv
import hashlib
import json
import mimetypes
import subprocess
import sys
import tempfile
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent
EVIDENCE = ROOT/'DOCS/status/evidence/2026-09-30-replay-audit'
sys.path.insert(0, str(ROOT / 'tools/replay_analysis'))
from sync_replays import DEFAULT_SOURCE, sync_replays
RANKS = {1:'传说', 2:'勇士', 3:'黄金', 4:'白银', 5:'青铜', 6:'黑铁'}
CLASSES = {'heavyTank':'重坦','mediumTank':'中坦','lightTank':'轻坦','AT-SPG':'坦歼','SPG':'火炮'}
NUMBERS = {'team','header_team','rating_before','rating_after','rating_delta','duration','health',
           'damageDealt','damageAssistedRadio','damageAssistedTrack','damageAssistedStun',
           'damageBlockedByArmor','damageReceived','kills','lifeTime','maxHealth','shots',
           'piercings','comp7PrestigePoints','roleSkillUsed','capturePoints','level',
           'damageAssistedInspire','directHits','droppedCapturePoints','poiCapturedByOwnTeam'}
JSON_FIELDS = {'rank_raw','ally_ranks','enemy_ranks','spawn_points','rank_rating_range'}
BOOLS = {'in_window','duplicate','is_self','is_ally','qualification','premature_leave','watched_to_end'}
PERFORMANCE_FIELDS = [
    ('comp7PrestigePoints','声望'), ('damageDealt','伤害'), ('kills','击杀'),
    ('damageAssistedRadio','侦查协助'), ('damageAssistedTrack','断带协助'),
    ('damageBlockedByArmor','格挡'), ('roleSkillUsed','技能使用'),
    ('damageAssistedInspire','激励协助'), ('damageAssistedStun','眩晕协助'),
    ('damageReceived','承伤'), ('health','剩余血量'), ('maxHealth','最大血量'),
    ('lifeTime','生存秒数'), ('shots','射击'), ('directHits','直接命中'),
    ('piercings','穿透'), ('capturePoints','占领点数'),
    ('droppedCapturePoints','防守点数'), ('poiCapturedByOwnTeam','本队战略点占领')]


def prestige_band(value):
    if value is None:
        return '未知'
    return '<80' if value < 80 else '80–109' if value < 110 else '110–139' if value < 140 else '140–199' if value < 200 else '≥200'


def rating_band(value):
    if value is None:
        return '未知'
    return '<−30' if value < -30 else '−30～−16' if value < -15 else '−15～−1' if value < 0 else '0' if value == 0 else '+1～+15' if value <= 15 else '+16～+30' if value <= 30 else '>+30'


def load_csv(path):
    with path.open(encoding='utf-8-sig') as f:
        output = []
        for raw in csv.DictReader(f):
            row = {}
            for key, value in raw.items():
                if value == '' or value is None:
                    row[key] = None
                elif key in JSON_FIELDS:
                    row[key] = json.loads(value)
                elif key in BOOLS:
                    row[key] = value == 'True'
                elif key in NUMBERS:
                    row[key] = float(value)
                else:
                    row[key] = value
            output.append(row)
        return output


def rank_label(player, detailed=True):
    rank = player.get('rank_raw')
    if player.get('qualification'):
        return '定级赛'
    if not rank or rank[0] not in RANKS:
        return '未知'
    suffix = {1:'A',2:'B',3:'C',4:'D',5:'E'}.get(rank[1], '') if rank[0]>=3 and detailed else ''
    return RANKS[rank[0]] + suffix


def lobby_type(players):
    # A room includes both teams and self. Qualification is not a known rank.
    if len(players) != 14 or any(
        p.get('qualification') or not p.get('rank_raw') or p['rank_raw'][0] not in RANKS
        for p in players
    ):
        return '未知'
    ranks = [p['rank_raw'][0] for p in players]
    low = sum(rank in (4, 5) for rank in ranks)
    high = any(rank in (1, 2) for rank in ranks)
    if low >= 6:
        return '白银局'
    if high and low <= 2:
        return '高压局'
    if not high and low <= 4:
        return '黄金局'
    return '未分类'


def build_data(evidence=EVIDENCE, investigation_evidence=None):
    audit = json.loads((evidence/'audit.json').read_text(encoding='utf-8'))
    battles = load_csv(evidence/'battles.csv')
    players = load_csv(evidence/'players.csv')
    grouped = defaultdict(list)
    classes = {}
    for p in players:
        p['rank_display'] = rank_label(p)
        grouped[p['file']].append(p)
        if p.get('vehicle_class'):
            classes[p['vehicle']] = p['vehicle_class']
    forensic_path = (investigation_evidence or evidence)/'missing-results.json'
    forensic = json.loads(forensic_path.read_text(encoding='utf-8')) if forensic_path.exists() else {}
    events = {r['file']:r for r in forensic.get('records',[])}
    if investigation_evidence is not None:
        # Historical investigations only apply to byte-identical replays.
        hashes = {r['file']:r['sha256'] for r in load_csv(investigation_evidence/'battles.csv')}
        unchanged = {r['file'] for r in battles if hashes.get(r['file']) == r['sha256']}
        events = {name:event for name,event in events.items() if name in unchanged}
    records=[]
    for b in battles:
        if b.get('duplicate'):
            continue
        party = grouped[b['file']]
        vehicle = b.get('vehicle') or b['header_vehicle']
        cls = b.get('vehicle_class') or classes.get(vehicle)
        event = events.get(b['file'])
        death_state = ('阵亡后结束 / 无结算' if event and event['death_clock'] is not None and not event['has_afterbattle']
                       else '已记录结算' if b['result']!='unknown' else '未确定')
        damage=b.get('damageDealt')
        b.update(id=b['sha256'], players=party, investigation=event,
                 replay_path=str(ROOT/'replays'/b['file']),
                 tags=dict(map=b['map_name'],side=f"队伍 {int(b['team'])}" if b.get('team') else '未知',
                           vehicle=vehicle.split(':')[-1],vehicle_class=CLASSES.get(cls,'未知'),
                           day=b['started_at'][:10],lobby_type=lobby_type(party),
                           result={'win':'胜','loss':'负','draw':'平','unknown':'未知'}[b['result']],
                           completeness='有战报' if b['result_status']=='valid' else '无战报' if b['result_status']=='no_result_block' else '战报异常',
                           recording_end=death_state,
                           observed_death='已观测阵亡' if event and event['death_clock'] is not None else '未观测阵亡' if event else '未调查',
                           damage_band='未知' if damage is None else '<2000' if damage<2000 else '2000–3999' if damage<4000 else '≥4000',
                           survival='未知' if b.get('health') is None else '存活' if b['health']>0 else '阵亡',
                           prestige_band=prestige_band(b.get('comp7PrestigePoints')),
                           rating_band=rating_band(b.get('rating_delta'))))
        records.append(b)
    dimensions=[('map','地图','赛前'),('side','出生队伍','赛前'),('vehicle','具体坦克','赛前'),('vehicle_class','车辆类别','赛前'),
                ('day','日期','时间'),('lobby_type','局型','赛前'),
                ('damage_band','伤害区间','战后'),('prestige_band','本人声望区间','战后'),
                ('rating_band','本人积分变化区间','战后'),('survival','最终存活状态','战后'),('result','战斗结果','战后'),
                ('completeness','战报完整性','数据质量'),('recording_end','录制结束状态','数据质量'),('observed_death','本人阵亡（录像观测）','战后')]
    return dict(metadata={k:audit[k] for k in ('cutoff','window_start','recent_count','recent_results')},
                dimensions=[dict(key=k,label=l,kind=t) for k,l,t in dimensions], records=records,
                performance_fields=[dict(key=k,label=l) for k,l in PERFORMANCE_FIELDS],
                investigation_summary=forensic.get('summary'),control_validation=forensic.get('control_validation'))


def load_startup_data(source=DEFAULT_SOURCE, game=DEFAULT_SOURCE.parent):
    messages = []
    if source is not None:
        report = sync_replays(source, ROOT/'replays')
        messages.append(f"录像同步：新增 {report['copied']}，已有 {report['existing']}，"
                        f"普通模式 {report['ignored']}，待完成 {report['pending']}，"
                        f"冲突 {len(report['conflicts'])}，错误 {len(report['errors'])}。")
        print(json.dumps(report, ensure_ascii=True), flush=True)
        if report['conflicts'] or report['errors']:
            messages.append('部分录像未同步，请查看启动窗口的具体原因。')
    else:
        messages.append('已跳过源目录同步。')
    cache = ROOT/'.drafts/explorer'
    try:
        cache.mkdir(parents=True, exist_ok=True)
        # Each launch builds privately; historical evidence is never overwritten.
        with tempfile.TemporaryDirectory(dir=cache, prefix='snapshot-') as folder:
            evidence = Path(folder)
            cutoff = datetime.now(timezone(timedelta(hours=8))).isoformat()
            print('Refreshing replay analysis...', flush=True)
            result = subprocess.run([
                sys.executable, str(ROOT/'tools/replay_analysis/audit.py'),
                '--replays', str(ROOT/'replays'), '--game', str(game),
                '--cutoff', cutoff, '--output', str(evidence),
            ], capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            data = build_data(evidence, investigation_evidence=EVIDENCE)
        messages.append(f"分析已更新，共 {len(data['records'])} 场录像；默认显示最近七天。")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Analysis refresh failed: {error}', flush=True)
        data = build_data(EVIDENCE)
        messages.append('分析刷新失败，当前显示历史快照，新录像尚未纳入。请查看启动窗口。')
    data['metadata']['startup_message'] = ' '.join(messages)
    return data


def make_handler(data):
    payload=json.dumps(data,ensure_ascii=False).encode('utf-8')
    replays={row['id']:row for row in data['records']}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=unquote(self.path.split('?',1)[0])
            if path=='/api/data':
                return self.send_bytes(payload,'application/json; charset=utf-8')
            if path.startswith('/replay/'):
                row=replays.get(path.rsplit('/',1)[-1])
                if not row:
                    return self.send_error(404)
                raw=Path(row['replay_path']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=row['sha256']:
                    return self.send_error(409,'Replay differs from analysis snapshot')
                return self.send_bytes(raw,'application/octet-stream',Path(row['file']).name)
            asset={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(path)
            if not asset:
                return self.send_error(404)
            return self.send_bytes((ASSETS/asset).read_bytes(),mimetypes.guess_type(asset)[0]+'; charset=utf-8')

        def send_bytes(self,body,kind,filename=None):
            self.send_response(200)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'")
            if filename:
                self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open-browser',action='store_true')
    parser.add_argument('--replay-source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--game',type=Path,default=DEFAULT_SOURCE.parent)
    parser.add_argument('--no-sync',action='store_true',help='Analyze local replays without copying from the game')
    args=parser.parse_args()
    data = load_startup_data(None if args.no_sync else args.replay_source, args.game)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(data))
    print(f'Onslaught explorer: http://127.0.0.1:{server.server_port}',flush=True)
    if args.open_browser:
        webbrowser.open(f'http://127.0.0.1:{server.server_port}')
    server.serve_forever()


if __name__=='__main__':
    main()
