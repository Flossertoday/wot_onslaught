import pickle
import struct
import unittest

from cache_audit import primitive_load
from missing_results import investigate


def frame(kind,time,payload):
    return struct.pack('<IIf',len(payload),kind,time)+payload


class MissingTests(unittest.TestCase):
    def test_recorder_death_not_other_vehicle_death(self):
        def health(entity,time,value):
            return frame(8,time,struct.pack('<IIIhhIBb',entity,4,10,value,300,8,0,-1))
        data=frame(0x16,50,struct.pack('<I',3))+health(9,70,0)+health(7,80,100)
        result=investigate(data,7)
        self.assertIsNone(result['death_clock'])
        data+=health(7,90,0)+frame(0x1b,94,struct.pack('<I',10)+b'postmortem')+frame(0xffffffff,0,b'1234567890123456')
        result=investigate(data,7)
        self.assertEqual(result['death_battle_seconds'],40)
        self.assertEqual(result['seconds_from_death_to_end'],4)
        self.assertTrue(result['terminal_marker_is_last'])
        self.assertFalse(result['has_afterbattle'])

    def test_reject_health_signature_drift(self):
        data=frame(8,1,struct.pack('<III',7,4,9)+b'123456789')
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            investigate(data,7)

    def test_cache_unpickler_rejects_globals(self):
        with self.assertRaisesRegex(ValueError,'forbidden'):
            primitive_load(b'cos\nsystem\n(S"echo forbidden"\ntR.')
        self.assertEqual(primitive_load(pickle.dumps({1,2},protocol=2)),{1,2})


if __name__=='__main__':
    unittest.main()
