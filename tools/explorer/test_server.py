import json
import unittest
from collections import Counter
from server import build_data,rank_label


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=build_data()
        cls.recent=[r for r in cls.data['records'] if r['in_window']]

    def test_counts_and_unknowns(self):
        self.assertEqual(len(self.recent),369)
        self.assertEqual(Counter(r['result'] for r in self.recent),{'win':158,'loss':133,'unknown':78})
        for r in self.recent:
            if r['result']=='unknown':
                self.assertIsNone(r['damageDealt'])
                self.assertEqual(r['tags']['observed_death'],'已观测阵亡')
                self.assertEqual(r['players'],[])

    def test_roster_excludes_self_from_six_allies(self):
        for r in self.recent:
            if r['result']!='unknown':
                self.assertEqual(sum(p['is_ally'] and not p['is_self'] for p in r['players']),6)
                self.assertEqual(sum(not p['is_ally'] for p in r['players']),7)

    def test_header_only_class_is_resolved(self):
        self.assertTrue(all(r['tags']['vehicle_class']!='未知' for r in self.recent))

    def test_identifiers_remain_strings(self):
        self.assertTrue(all(isinstance(r['arena_id'],str) for r in self.recent if r['arena_id']))
        json.dumps(self.data,allow_nan=False)

    def test_qualification_not_fake_rating(self):
        self.assertEqual(rank_label({'rank_raw':[3,1,19],'qualification':True}),'定级赛')


if __name__=='__main__':
    unittest.main()
