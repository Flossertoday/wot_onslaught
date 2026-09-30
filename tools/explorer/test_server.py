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
        def room(low, high=None):
            # Self is the last player; both sides contain low-rank players.
            ranks = [4 if i % 2 else 5 for i in range(low)] + [3] * (14-low)
            if high is not None:
                ranks[-1] = high
            return [dict(rank_raw=[rank,1,0],is_self=i==13,is_ally=i>=7)
                    for i,rank in enumerate(ranks)]
        for high in (None,1,2):
            for low in range(14):
                expected = ('白银局' if low>=6 else '高压局' if high and low<=2
                            else '黄金局' if not high and low<=4 else '未分类')
                with self.subTest(high=high,low=low):
                    self.assertEqual(lobby_type(room(low,high)),expected)
        self.assertEqual(lobby_type(room(14)), '白银局')
        players = room(2,1)
        players[0]['rank_raw'] = [6,1,0]  # Black iron does not count as silver/bronze.
        self.assertEqual(lobby_type(players),'高压局')
        for malformed in ([],players[:13],players+players[:1]):
            self.assertEqual(lobby_type(malformed),'未知')
        for rank,qualification in ((None,False),([0,1,0],False),([3,1,0],True)):
            players = room(6)
            players[-1].update(rank_raw=rank,qualification=qualification)
            self.assertEqual(lobby_type(players),'未知')

    def test_lobby_replaces_five_dimensions_and_keeps_missing(self):
        dimensions = {d['key'] for d in self.data['dimensions']}
        self.assertIn('lobby_type',dimensions)
        self.assertTrue(dimensions.isdisjoint({'self_rank','ally_ranks','enemy_ranks','allies_high','enemies_high'}))
        for row in self.data['records']:
            self.assertEqual(row['tags']['lobby_type'],lobby_type(row['players']))
            if not row['players']:
                self.assertEqual(row['tags']['lobby_type'],'未知')

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
