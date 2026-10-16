"""Exercise the HTTP JSON boundary used by Meego's native model reader."""
import copy
import io
import json
import unittest

from apk_revival.meego.engine import server


class BuildingExpiryWireTests(unittest.TestCase):
    def wire(self, value):
        handler = object.__new__(server.Handler)
        handler.wfile = io.BytesIO()
        headers = {}
        handler.send_response = lambda code: self.assertEqual(code, 200)
        handler.send_header = lambda key, value: headers.update({key: value})
        handler.end_headers = lambda: None
        handler.reply(200, value)
        body = handler.wfile.getvalue()
        self.assertEqual(int(headers['Content-Length']), len(body))
        return json.loads(body)

    def test_no_timer_buildings_use_missing_field_in_login_and_action_responses(self):
        building = dict(building_id=18, building_type=5, state=1,
                        progress=0, expire_date=0, last_update=123)
        state = dict(buildings={'18': building}, all_villagers={})
        for value, path in ((state, ('buildings', '18')),
                            ({'game_state': state}, ('game_state', 'buildings', '18')),
                            (building, ())):
            before = copy.deepcopy(value)
            actual = self.wire(value)
            for key in path:
                actual = actual[key]
            self.assertNotIn('expire_date', actual)
            self.assertEqual(actual, {k: v for k, v in building.items() if k != 'expire_date'})
            self.assertEqual(value, before, 'Wire projection must preserve saved data')

    def test_real_construction_deadline_and_completed_upgrade_state_are_preserved(self):
        records = [dict(building_id=18, building_type=5, state=10, expire_date=200),
                   dict(building_id=19, building_type=5, state=11, expire_date=0)]
        actual = self.wire(records)
        self.assertEqual(actual[0], records[0])
        self.assertEqual(actual[1]['state'], 11)
        self.assertNotIn('expire_date', actual[1])

    def test_job_resource_and_unrelated_zero_expirations_are_not_reinterpreted(self):
        value = {'job': {'job_id': 1, 'expire_date': 0},
                 'resources': {'3': {'count': 0, 'expire_date': 0}},
                 'item': {'expire_date': 0}, 'empty': [], 'scalar': 0}
        self.assertEqual(self.wire(value), value)


class FinalHarvestWireTests(BuildingExpiryWireTests):
    def test_rocks_trees_and_bushes_expose_a_smaller_final_pickup_without_changing_saves(self):
        for kind in (2,3,4):
            for stock in (1,2):
                with self.subTest(kind=kind,stock=stock):
                    person={'villager_id':7,'job':{'source_id':9,'gather_rate':2.35,'trip_time':12}}
                    state={'buildings':{'9':{'building_id':9,'building_type':kind,'state':1,'count':stock}},'all_villagers':{'7':person}}
                    before=copy.deepcopy(state)
                    for packet in (state,{'game_state':state}):
                        result=self.wire(packet)
                        if 'game_state' in result:result=result['game_state']
                        self.assertEqual(result['all_villagers']['7']['job']['gather_rate'],stock)
                    self.assertEqual(state,before)

    def test_partial_villager_response_uses_current_source_context(self):
        person={'villager_id':7,'job':{'source_id':9,'gather_rate':1.02}}
        state={'buildings':{'9':{'building_id':9,'building_type':4,'state':1,'count':1}},'all_villagers':{'7':person}}
        self.assertEqual(server.native_payload(person,state)['job']['gather_rate'],1)
        self.assertEqual(person['job']['gather_rate'],1.02)

    def test_unlimited_sources_and_full_sized_trips_keep_their_rate(self):
        for kind,stock in ((2,75),(3,30),(4,75),(22,1)):
            state={'buildings':{'9':{'building_type':kind,'state':1,'count':stock}},
                   'all_villagers':{'7':{'villager_id':7,'job':{'source_id':9,'gather_rate':1.02}}}}
            self.assertEqual(self.wire(state)['all_villagers']['7']['job']['gather_rate'],1.02)


if __name__ == '__main__':
    unittest.main()
