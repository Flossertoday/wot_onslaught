"""Read only the game's battle_results cache, with restricted pickle globals.

Infer common-field array positions from matching replay JSON controls, requiring
one unique index per field across ALL matches. Do not assume an old schema.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import pickle
import zlib
from collections import Counter
from pathlib import Path

from audit import read_blocks


class PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module in ('__builtin__','builtins') and name in ('set','frozenset'):
            return set if name=='set' else frozenset
        raise ValueError('forbidden pickle global: '+module+'.'+name)

    def persistent_load(self, value):
        raise ValueError('pickle persistent IDs are forbidden')


def primitive_load(raw):
    if len(raw)>32*1024*1024:
        raise ValueError('oversized cache')
    return PrimitiveUnpickler(io.BytesIO(raw),encoding='bytes').load()


def inflate(raw):
    d=zlib.decompressobj()
    output=d.decompress(raw,32*1024*1024)
    if not d.eof or d.unconsumed_tail:
        raise ValueError('incomplete or oversized cache payload')
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path(os.environ['APPDATA'])/'Wargaming.net/WorldOfTanks/battle_results')
    p.add_argument('--battles',type=Path,required=True)
    p.add_argument('--replays',type=Path,default=Path('replays'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    with args.battles.open(encoding='utf-8-sig') as f:
        known={r['arena_id']:r for r in csv.DictReader(f) if r['result_status']=='valid'}
    fields=('arenaCreateTime','bonusType','winnerTeam','duration')
    candidates={k:None for k in fields}
    records=[]
    for path in sorted(args.cache.rglob('*.dat')):
        raw=path.read_bytes()
        outer=primitive_load(raw)
        common=primitive_load(inflate(outer[1][3]))[0]
        arena=str(outer[1][0])
        if arena!=path.stem:
            raise ValueError('cache filename identity mismatch')
        match=known.get(arena)
        if match:
            json_common=read_blocks(args.replays/match['file'])[1][0]['common']
            for key in fields:
                positions={i for i,value in enumerate(common) if type(value)==type(json_common[key]) and value==json_common[key]}
                candidates[key]=positions if candidates[key] is None else candidates[key]&positions
        records.append(dict(arena_id=arena,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                            matching_replay=match['file'] if match else None,common=common))
    if not records or any(v is None or len(v)!=1 for v in candidates.values()):
        raise ValueError('could not validate an unambiguous current cache schema')
    indices={k:next(iter(v)) for k,v in candidates.items()}
    for r in records:
        common=r.pop('common')
        r.update({k:common[i] for k,i in indices.items()})
    unmatched=[r for r in records if not r['matching_replay']]
    output=dict(source='APPDATA/Wargaming.net/WorldOfTanks/battle_results',files=len(records),
                matching_valid_replays=len(records)-len(unmatched),unmatched=len(unmatched),
                unmatched_bonus_types=dict(Counter(r['bonusType'] for r in unmatched)),
                field_indices_validated_against_all_matches=indices,records=records,
                caveat='This is a local cache snapshot, not an inventory of every battle ever played.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='records'},indent=2))


if __name__=='__main__':
    main()
