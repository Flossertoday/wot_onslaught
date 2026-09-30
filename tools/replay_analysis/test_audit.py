"""Checks for failure modes that would silently distort win-rate analysis."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from audit import bh_adjust, read_blocks, summarize, win_interval
from stream_audit import frame_metadata


class AuditTests(unittest.TestCase):
    def test_missing_is_not_a_loss(self):
        rows = [dict(in_window=True, map_id='a', map_name='A', result=r)
                for r in ('win', 'loss', 'unknown', 'unknown')]
        row = summarize(rows, test_maps=True)[0]
        self.assertEqual((row['known'], row['unknown']), (2, 2))
        self.assertEqual(row['win_rate'], .5)
        self.assertEqual(row['all_replays_win_rate_lower'], .25)
        self.assertEqual(row['all_replays_win_rate_upper'], .75)

    def test_excludes_old_and_duplicate(self):
        rows = [dict(in_window=w, duplicate=d, map_id='a', map_name='A', result=r)
                for w,d,r in [(True, False, 'win'), (False, False, 'loss'), (True, True, 'loss')]]
        self.assertEqual(summarize(rows)[0]['known'], 1)

    def test_all_unknown(self):
        row = summarize([dict(in_window=True, map_id='a', map_name='A', result='unknown')])[0]
        self.assertIsNone(row['win_rate'])
        self.assertIsNone(row['wilson_low'])
        self.assertEqual(row['all_replays_win_rate_upper'], 1)

    def test_wilson_not_zero_width_at_extreme(self):
        low, high = win_interval(0, 3)
        self.assertAlmostEqual(low, 0)
        self.assertGreater(high, .5)
        self.assertEqual(win_interval(0, 0), (None, None))

    def test_bh_correction(self):
        adjusted = bh_adjust([.04, .001, .03, 1.])
        for value, expected in zip(adjusted, [.053333333333, .004, .053333333333, 1.]):
            self.assertAlmostEqual(value, expected)

    def test_truncated_json_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'a.wotreplay'
            p.write_bytes(struct.pack('<III', 0x11343212, 1, 20)+b'{}')
            with self.assertRaisesRegex(ValueError, 'truncated'):
                read_blocks(p)

    def test_no_second_block_does_not_read_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'a.wotreplay'
            raw = json.dumps({'mapName':'a'}).encode()
            p.write_bytes(struct.pack('<III', 0x11343212, 1, len(raw))+raw+b'opaque binary')
            self.assertEqual(read_blocks(p), [{'mapName':'a'}])

    def test_phase_and_result_packets_are_distinct(self):
        data = (struct.pack('<IIfI', 4, 0x16, 50., 3)
                + struct.pack('<IIfI', 4, 0x16, 170., 4)
                + struct.pack('<IIf', 2, 0x11, 175.) + b'xx')
        row = frame_metadata(data)
        self.assertEqual(row['phase_battle_duration'], 120.)
        self.assertEqual(row['result_packet_count'], 1)
        with self.assertRaisesRegex(ValueError, 'invalid packet frame'):
            frame_metadata(data[:-1])


if __name__ == '__main__':
    unittest.main()
