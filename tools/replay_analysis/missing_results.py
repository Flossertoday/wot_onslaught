"""Investigate recorder death and stream termination; never infer final winners.

Method 0x04 is accepted only with the current 10-byte onHealthChanged layout,
validated against Vehicle.def and the complete-results control group.
"""
import argparse
import collections
import csv
import hashlib
import json
import statistics
import struct
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from audit import read_blocks
from packed_xml import unpack
from stream_audit import stream


def investigate(data, own_id):
    offset, end_time = 0, 0.
    health, views, phases, tail = [], [], [], []
    result_packets, close_markers = 0, 0
    while offset < len(data):
        if offset+12 > len(data):
            raise ValueError('truncated frame header')
        length, kind, clock = struct.unpack_from('<IIf', data, offset)
        payload = data[offset+12:offset+12+length]
        if len(payload) != length:
            raise ValueError('truncated frame payload')
        offset += 12+length
        end_time = max(end_time, clock)
        tail.append(hex(kind))
        tail = tail[-6:]
        if kind == 8 and length >= 12:
            entity, method, size = struct.unpack_from('<III', payload)
            if entity == own_id and method == 4:
                if size != 10 or length != 22:
                    raise ValueError('unreviewed onHealthChanged layout')
                new, old, attacker, reason, part = struct.unpack_from('<hhIBb', payload, 12)
                health.append(dict(clock=clock, new=new, old=old, reason=reason))
        elif kind == 0x1b and length >= 4:
            size, = struct.unpack_from('<I', payload)
            if size != length-4:
                raise ValueError('unreviewed view-mode layout')
            views.append(dict(clock=clock, mode=payload[4:].decode('ascii')))
        elif kind == 0x16 and length == 4:
            phases.append(dict(clock=clock, value=struct.unpack('<I',payload)[0]))
        elif kind == 0x11:
            result_packets += 1
        elif kind == 0xffffffff:
            close_markers += 1
    death = next((v['clock'] for v in health if v['new'] <= 0), None)
    battle = next((v['clock'] for v in phases if v['value'] == 3), None)
    return dict(end_clock=end_time, death_clock=death, battle_start_clock=battle,
                seconds_from_death_to_end=end_time-death if death is not None else None,
                death_battle_seconds=death-battle if death is not None and battle is not None else None,
                last_observed_health=health[-1]['new'] if health else None,
                health_events=health, view_modes=views, phases=phases,
                has_postmortem=any(v['mode']=='postmortem' for v in views),
                has_look_at_killer=any(v['mode']=='lookAtKiller' for v in views),
                has_afterbattle=any(v['value']==4 for v in phases),
                result_packets=result_packets, close_markers=close_markers,
                terminal_marker_is_last=tail[-1]=='0xffffffff', last_packet_types=tail)


def distribution(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return dict(n=len(values), min=min(values), median=statistics.median(values), max=max(values))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--battles', required=True, type=Path)
    p.add_argument('--replays', type=Path, default=Path('replays'))
    p.add_argument('--game', type=Path, default=Path('C:/Games/World_of_Tanks_CN'))
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    with zipfile.ZipFile(args.game/'res/packages/scripts.pkg') as z:
        definition = z.read('scripts/entity_defs/Vehicle.def')
        types = [a.text for a in unpack(definition).findall('ClientMethods/onHealthChanged/Arg')]
        if types != ['INT16','INT16','OBJECT_ID','UINT8','INT8']:
            raise ValueError('current client health signature changed')
    with args.battles.open(encoding='utf-8-sig') as f:
        rows = sorted((r for r in csv.DictReader(f) if r['in_window']=='True' and r['duplicate']=='False'), key=lambda r:r['started_at'])
    records, errors = [], []
    for i, row in enumerate(rows):
        try:
            path = args.replays/row['file']
            header = read_blocks(path)[0]
            own_ids = [int(k) for k,v in header['vehicles'].items() if v.get('name')==header['playerName']]
            if len(own_ids) != 1:
                raise ValueError('ambiguous recorder identity')
            record = investigate(stream(path), own_ids[0])
            record.update(file=row['file'], json_result=row['result'], started_at=row['started_at'])
            if row['result_status']=='valid':
                record['json_dead'] = float(row['health']) <= 0
                record['death_agrees_json'] = record['json_dead'] == (record['death_clock'] is not None)
                record['final_health_agrees_json'] = (max(0,record['last_observed_health'])==max(0,float(row['health'])) if record['last_observed_health'] is not None else None)
                if record['json_dead'] and record['death_battle_seconds'] is not None:
                    record['death_time_minus_json_lifetime'] = record['death_battle_seconds']-float(row['lifeTime'])
            if i+1 < len(rows):
                next_row = rows[i+1]
                gap=(datetime.fromisoformat(next_row['started_at'])-datetime.fromisoformat(row['started_at'])).total_seconds()-record['end_clock']
                record.update(next_file=next_row['file'], seconds_end_to_next_start=gap)
            records.append(record)
        except (ValueError, KeyError, struct.error) as e:
            errors.append(dict(file=row['file'],error=str(e)))
        if (i+1)%50==0:
            print('Investigated',i+1,'/',len(rows),flush=True)
    summary = {}
    for state in ('unknown','win','loss'):
        group=[r for r in records if r['json_result']==state]
        summary[state] = dict(files=len(group), self_death_observed=sum(r['death_clock'] is not None for r in group),
                              postmortem=sum(r['has_postmortem'] for r in group), look_at_killer=sum(r['has_look_at_killer'] for r in group),
                              terminal_marker_last=sum(r['terminal_marker_is_last'] for r in group),
                              has_afterbattle=sum(r['has_afterbattle'] for r in group),
                              death_to_end_seconds=distribution(r['seconds_from_death_to_end'] for r in group),
                              end_to_next_start_seconds=distribution(r.get('seconds_end_to_next_start') for r in group),
                              next_battle_within_120s=sum(0<=r.get('seconds_end_to_next_start',-1)<=120 for r in group))
    known=[r for r in records if r['json_result']!='unknown']
    controls=dict(files=len(known),death_agrees_json=sum(r['death_agrees_json'] for r in known),
                  final_health_agrees_json=sum(r.get('final_health_agrees_json') is True for r in known),
                  final_health_unobserved=sum(r.get('final_health_agrees_json') is None for r in known),
                  death_time_error=distribution(r.get('death_time_minus_json_lifetime') for r in known))
    output=dict(summary=summary,control_validation=controls,errors=errors,records=records,
                client_health_definition=dict(entry='scripts/entity_defs/Vehicle.def',sha256=hashlib.sha256(definition).hexdigest(),args=types),
                source_reference='https://intelliagent.gitlab.io/wotto-wiki/packets/packet08/subtype04/',
                limitations=['An observed death or early stop is not a final defeat.',
                             'Next-battle gaps are approximate: header wall clock plus stream clock.',
                             'No specific exit-button click or disconnect reason is decoded.'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ('summary','control_validation','errors')},indent=2))
    if errors or controls['death_agrees_json']!=len(known):
        raise SystemExit('Control mismatch or errors: investigate before using unknown-case classifications')


if __name__=='__main__':
    main()
