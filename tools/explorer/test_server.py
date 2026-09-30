import json
import unittest
from collections import Counter
from server import build_data,rank_label,prestige_band,rating_band,lobby_type


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

    def test_lobby_boundaries_and_full_room_count(self):
        def room(ranks):
            return [dict(rank_raw=[rank,1,0],is_self=i==13,is_ally=i>=7)
                    for i,rank in enumerate(ranks)]
        # Golden threshold is a count across both teams, not a low-rank proxy.
        examples = [([3]*5+[6]*9,'低压局'),([3]*6+[6]*8,'黄金局'),
                    ([3]*6+[4]*8,'黄金局'),([3]*14,'黄金局'),
                    ([6]*14,'低压局'),([4]*7+[5]*7,'低压局')]
        for high in (1,2):
            examples.extend([([3]*13+[high],'高压局'),
                             ([4]+[3]*12+[high],'高压局'),
                             ([5]+[3]*12+[high],'高压局'),
                             ([4,5]+[3]*11+[high],'低压局'),
                             ([4]*13+[high],'低压局')])
        for ranks,expected in examples:
            with self.subTest(ranks=ranks):
                self.assertEqual(lobby_type(room(ranks)),expected)
        players = room([3]*14)
        for malformed in ([],players[:13],players+players[:1]):
            self.assertEqual(lobby_type(malformed),'未知')
        for rank in (None,[0,1,0]):
            players = room([3]*14)
            players[-1].update(rank_raw=rank)
            self.assertEqual(lobby_type(players),'未知')

    def test_lobby_skips_qualification_in_every_count(self):
        def classify(ranks,skipped):
            return lobby_type([dict(rank_raw=[rank,1,0] if rank else None,
                                    qualification=i in skipped) for i,rank in enumerate(ranks)])
        # Skipping the high rank allows gold; skipping bronze allows high pressure.
        self.assertEqual(classify([1]+[3]*6+[6]*7,{0}),'黄金局')
        self.assertEqual(classify([2,4,5]+[3]*11,{1}),'高压局')
        # Skipping the sixth gold falls below the room-wide threshold.
        self.assertEqual(classify([3]*6+[6]*8,{0}),'低压局')
        self.assertEqual(classify([None]+[3]*6+[6]*7,{0}),'黄金局')
        self.assertEqual(classify([None]*14,set(range(14))),'低压局')

    def test_lobby_replaces_five_dimensions_and_keeps_missing(self):
        dimensions = {d['key'] for d in self.data['dimensions']}
        self.assertIn('lobby_type',dimensions)
        self.assertTrue(dimensions.isdisjoint({'self_rank','ally_ranks','enemy_ranks','allies_high','enemies_high'}))
        for row in self.data['records']:
            self.assertEqual(row['tags']['lobby_type'],lobby_type(row['players']))
            self.assertIn(row['tags']['lobby_type'],{'高压局','黄金局','低压局','未知'})
            if not row['players']:
                self.assertEqual(row['tags']['lobby_type'],'未知')
        # All 42 formerly unknown rooms with qualification players are now classified.
        qualified=[r for r in self.recent if any(p.get('qualification') for p in r['players'])]
        self.assertEqual(len(qualified),42)
        self.assertTrue(all(r['tags']['lobby_type']!='未知' for r in qualified))

    def test_full_scoreboard_is_numeric_and_matches_self(self):
        fields=[f['key'] for f in self.data['performance_fields']]
        self.assertEqual(len(fields),19)
        for row in self.data['records']:
            if row['result_status']!='valid':
                self.assertIsNone(row['comp7PrestigePoints'])
                self.assertIsNone(row['rating_delta'])
                self.assertEqual(row['tags']['prestige_band'],'未知')
                continue
            own=next(p for p in row['players'] if p['is_self'])
            for key in fields:
                self.assertEqual(row[key],own[key])
                for player in row['players']:
                    self.assertIsInstance(player[key],(int,float))
            # Other players' exact rating is not supplied by these replays.
            self.assertTrue(all('rating_delta' not in p for p in row['players']))

    def test_prestige_is_not_capped_at_200(self):
        values=[r['comp7PrestigePoints'] for r in self.data['records'] if r['result_status']=='valid']
        self.assertEqual(max(values),242)
        self.assertEqual(sum(v>200 for v in values),9)

    def test_metric_bands_preserve_zero_missing_and_boundaries(self):
        for value,expected in [(None,'未知'),(0,'<80'),(79,'<80'),(80,'80–109'),
                               (110,'110–139'),(140,'140–199'),(200,'≥200'),(242,'≥200')]:
            self.assertEqual(prestige_band(value),expected)
        self.assertEqual(rating_band(None),'未知')
        self.assertEqual(rating_band(0),'0')
        self.assertEqual(rating_band(-46),'<−30')
        self.assertEqual(rating_band(46),'>+30')


if __name__=='__main__':
    unittest.main()
