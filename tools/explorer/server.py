"""Local, read-only Onslaught research UI. Run from any directory."""
import argparse
import csv
import hashlib
import json
import mimetypes
import webbrowser
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent
EVIDENCE = ROOT/'DOCS/status/evidence/2026-09-30-replay-audit'
RANKS = {1:'传奇', 2:'冠军', 3:'黄金', 4:'白银', 5:'青铜', 6:'黑铁'}
CLASSES = {'heavyTank':'重坦','mediumTank':'中坦','lightTank':'轻坦','AT-SPG':'坦歼','SPG':'火炮'}
NUMBERS = {'team','header_team','rating_before','rating_after','rating_delta','duration','health',
           'damageDealt','damageAssistedRadio','damageAssistedTrack','damageAssistedStun',
           'damageBlockedByArmor','damageReceived','kills','lifeTime','maxHealth','shots',
           'piercings','comp7PrestigePoints','roleSkillUsed','capturePoints','level'}
JSON_FIELDS = {'rank_raw','ally_ranks','enemy_ranks','spawn_points','rank_rating_range'}
BOOLS = {'in_window','duplicate','is_self','is_ally','qualification','premature_leave','watched_to_end'}


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


def composition(players):
    if not players:
        return '未知'
    counts = Counter(rank_label(p,False) for p in players)
    order = list(RANKS.values())+['定级赛','未知']
    return ' · '.join(f'{rank}×{counts[rank]}' for rank in order if counts[rank])


def build_data(evidence=EVIDENCE):
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
    forensic_path = evidence/'missing-results.json'
    forensic = json.loads(forensic_path.read_text(encoding='utf-8')) if forensic_path.exists() else {}
    events = {r['file']:r for r in forensic.get('records',[])}
    records=[]
    for b in battles:
        if b.get('duplicate'):
            continue
        party = grouped[b['file']]
        own = next((p for p in party if p['is_self']),{})
        allies = [p for p in party if p['is_ally'] and not p['is_self']]
        enemies = [p for p in party if not p['is_ally']]
        vehicle = b.get('vehicle') or b['header_vehicle']
        cls = b.get('vehicle_class') or classes.get(vehicle)
        event = events.get(b['file'])
        death_state = ('阵亡后结束 / 无结算' if event and event['death_clock'] is not None and not event['has_afterbattle']
                       else '已记录结算' if b['result']!='unknown' else '未确定')
        def count_high(team):
            if not team or any(not p.get('rank_raw') or p.get('qualification') for p in team):
                return '未知 / 含定级'
            return str(sum(1<=p['rank_raw'][0]<=3 for p in team))+'人'
        damage=b.get('damageDealt')
        b.update(id=b['sha256'], players=party, investigation=event,
                 replay_path=str(ROOT/'replays'/b['file']),
                 tags=dict(map=b['map_name'],side=f"队伍 {int(b['team'])}" if b.get('team') else '未知',
                           vehicle=vehicle.split(':')[-1],vehicle_class=CLASSES.get(cls,'未知'),
                           day=b['started_at'][:10],self_rank=rank_label(own),
                           ally_ranks=composition(allies),enemy_ranks=composition(enemies),
                           allies_high=count_high(allies),enemies_high=count_high(enemies),
                           result={'win':'胜','loss':'负','draw':'平','unknown':'未知'}[b['result']],
                           completeness='有战报' if b['result_status']=='valid' else '无战报' if b['result_status']=='no_result_block' else '战报异常',
                           recording_end=death_state,
                           observed_death='已观测阵亡' if event and event['death_clock'] is not None else '未观测阵亡' if event else '未调查',
                           damage_band='未知' if damage is None else '<2000' if damage<2000 else '2000–3999' if damage<4000 else '≥4000',
                           survival='未知' if b.get('health') is None else '存活' if b['health']>0 else '阵亡'))
        records.append(b)
    dimensions=[('map','地图','赛前'),('side','出生队伍','赛前'),('vehicle','具体坦克','赛前'),('vehicle_class','车辆类别','赛前'),
                ('day','日期','时间'),('self_rank','本人分段','赛前'),('ally_ranks','六名队友分段构成','赛前'),
                ('enemy_ranks','七名对手分段构成','赛前'),('allies_high','队友黄金及以上人数','赛前'),('enemies_high','对手黄金及以上人数','赛前'),
                ('damage_band','伤害区间','战后'),('survival','最终存活状态','战后'),('result','战斗结果','战后'),
                ('completeness','战报完整性','数据质量'),('recording_end','录制结束状态','数据质量'),('observed_death','本人阵亡（录像观测）','战后')]
    return dict(metadata={k:audit[k] for k in ('cutoff','window_start','recent_count','recent_results')},
                dimensions=[dict(key=k,label=l,kind=t) for k,l,t in dimensions], records=records,
                investigation_summary=forensic.get('summary'),control_validation=forensic.get('control_validation'))


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
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(build_data()))
    print(f'Onslaught explorer: http://127.0.0.1:{server.server_port}',flush=True)
    if args.open_browser:
        webbrowser.open(f'http://127.0.0.1:{server.server_port}')
    server.serve_forever()


if __name__=='__main__':
    main()
