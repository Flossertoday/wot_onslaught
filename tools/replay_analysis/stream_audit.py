"""Audit packet framing and phase/result-packet presence, without executing pickle.

Format references (independently implemented):
https://github.com/Monstrofil/replays_unpack/blob/master/replay_unpack/replay_reader.py
https://intelliagent.gitlab.io/wotto-wiki/format/packet-stream/
Semantic labels must also be checked against the installed client.
"""
import argparse
import collections
import csv
import json
import math
import struct
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, modes
try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
except ImportError:
    from cryptography.hazmat.primitives.ciphers.algorithms import Blowfish


def stream(path):
    raw = path.read_bytes()
    if len(raw) < 8 or struct.unpack_from('<I', raw)[0] != 0x11343212:
        raise ValueError('invalid header')
    count, = struct.unpack_from('<I', raw, 4)
    if not 1 <= count <= 8:
        raise ValueError('invalid block count')
    offset = 8
    for _ in range(count):
        if offset+4 > len(raw):
            raise ValueError('truncated block')
        offset += 4 + struct.unpack_from('<I', raw, offset)[0]
    encrypted = raw[offset+8:]
    if not encrypted or len(encrypted) % 8:
        raise ValueError('invalid encrypted stream length')
    decryptor = Cipher(Blowfish(bytes.fromhex('de72bea0de04beb1defebeefdeadbeef')), modes.ECB()).decryptor()
    blocks = decryptor.update(encrypted) + decryptor.finalize()
    previous = 0
    compressed = bytearray()
    for word, in struct.iter_unpack('<Q', blocks):
        previous ^= word
        compressed.extend(struct.pack('<Q', previous))
    inflater = zlib.decompressobj()
    decoded = inflater.decompress(compressed, 128*1024*1024)
    if not inflater.eof or inflater.unconsumed_tail:
        raise ValueError('incomplete or oversized compressed stream')
    return decoded


def frame_metadata(data):
    counts = collections.Counter()
    offset, maximum = 0, 0.
    phases, result_times = [], []
    while offset < len(data):
        if offset+12 > len(data):
            raise ValueError('truncated packet header')
        length, kind, clock = struct.unpack_from('<IIf', data, offset)
        end = offset+12+length
        if end > len(data) or not math.isfinite(clock):
            raise ValueError('invalid packet frame')
        counts[hex(kind)] += 1
        maximum = max(maximum, clock)
        if kind == 0x16 and length == 4:
            phases.append({'clock':clock, 'value':struct.unpack_from('<I',data,offset+12)[0]})
        if kind == 0x11:
            result_times.append(clock)
        offset = end
    battle = next((p['clock'] for p in phases if p['value']==3), None)
    after = next((p['clock'] for p in phases if p['value']==4), None)
    return dict(decoded_bytes=len(data), packet_count=sum(counts.values()),
                max_clock=maximum, phases=phases, has_afterbattle_phase=after is not None,
                result_packet_count=len(result_times), result_packet_times=result_times,
                phase_battle_duration=after-battle if after is not None and battle is not None else None,
                packet_types=dict(counts))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--battles', required=True, type=Path)
    p.add_argument('--replays', default=Path('replays'), type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    with args.battles.open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['in_window']=='True' and r['duplicate']=='False']
    records, failures = [], []
    for i, row in enumerate(rows):
        try:
            entry = frame_metadata(stream(args.replays / row['file']))
            entry.update(file=row['file'], json_result=row['result'], json_duration=row['duration'])
            records.append(entry)
        except (ValueError, struct.error, zlib.error) as error:
            failures.append({'file':row['file'], 'error':str(error)})
        if (i+1) % 50 == 0:
            print('Framed', i+1, 'of', len(rows), flush=True)
    summary = {}
    for state in ('unknown', 'win', 'loss', 'draw'):
        group = [r for r in records if r['json_result']==state]
        if group:
            summary[state] = dict(files=len(group), with_result_packet=sum(r['result_packet_count']>0 for r in group),
                                  with_afterbattle_phase=sum(r['has_afterbattle_phase'] for r in group))
    output = dict(scope='All nonduplicate replays in the frozen seven-day window',
                  summary=summary, failures=failures, records=records,
                  limitations=['Packet 0x11 presence is a framing observation, not decoded result content.',
                               'Absence of result packet alone does not prove no other event could reveal outcome.',
                               'No winner is inferred from partial streams or rating differences.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'summary':summary, 'failures':failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
