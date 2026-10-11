import io
import json
import unittest
from unittest.mock import Mock, patch
from commander import check_deck
from libby import ask, cut_request, verify_cuts
from test_commander import card

QUESTION = 'Libby I need help removing 13 cards from this Bolas deck so that I can have 100 cards only in the deck. Any suggestions from the list?'


def response(draft):
    return io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]}).encode())


class CutTests(unittest.TestCase):
    def setUp(self):
        self.cards = {'Nicol Bolas, the Ravager': card('Nicol Bolas, the Ravager', 'UBR', 'Legendary Creature — Elder Dragon'), 'Island': card('Island', 'U', 'Basic Land — Island')}
        self.cards.update({f'Spell {i}': card(f'Spell {i}', 'B', 'Sorcery', 'Draw a card.', cmc_override=7) for i in range(13)})
        self.deck = {'name': 'Bolas', 'commander': 'Nicol Bolas, the Ravager', 'cards': [{'name': 'Nicol Bolas, the Ravager', 'quantity': 1}, {'name': 'Island', 'quantity': 99}] + [{'name': f'Spell {i}', 'quantity': 1} for i in range(13)]}
        self.check, self.facts = check_deck(self.deck, self.cards.__getitem__)
        self.task = cut_request(QUESTION, 113)
        self.draft = {'answer': 'Cut redundant expensive spells.', 'recommendations': [], 'cuts': [{'name': f'Spell {i}', 'quantity': 1, 'reason': 'This draw spell overlaps other draw slots.'} for i in range(13)]}

    def test_exact_user_request_routes_to_thirteen_cuts(self):
        self.assertEqual(self.task['count'], 13)
        search, publisher = Mock(), Mock()
        with patch('libby.urllib.request.urlopen', return_value=response(self.draft)) as upstream:
            reply = ask('test', 'model', QUESTION, {'deck': self.deck}, [], self.cards.__getitem__, search, commander_recs=publisher, reviewer=lambda *args: {'supported': True, 'issues': []})
        search.assert_not_called()
        publisher.assert_not_called()
        self.assertEqual(reply['total_after'], 100)
        self.assertEqual(len(reply['cuts']), 13)
        self.assertEqual(reply['recommendations'], [])
        self.assertEqual(reply['mode'], 'verified_cuts')
        payload = json.loads(upstream.call_args.args[0].data)
        context = json.loads(payload['input'][0]['content'].split(': ', 1)[1])
        self.assertEqual(sum(e['quantity'] for e in context['deck']['cards']), 113)
        self.assertEqual(len(context['server_verified_deck']['cards']), 15)
        self.assertEqual(context['requested_task']['count'], 13)
        self.assertNotIn('search_cards', [t['name'] for t in payload['tools']])

    def test_additions_only_reply_is_repaired_not_returned(self):
        bad = {'answer': 'Add Counterspell.', 'recommendations': [{'name': 'Counterspell', 'reason': 'Good.', 'cut': ''}], 'cuts': []}
        with patch('libby.urllib.request.urlopen', side_effect=[response(bad), response(self.draft)]) as upstream:
            reply = ask('test', 'model', QUESTION, {'deck': self.deck}, [], self.cards.__getitem__, Mock(), reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(upstream.call_count, 2)
        self.assertNotIn('Counterspell', reply['answer'])
        self.assertEqual(reply['total_after'], 100)

    def test_outsiders_commanders_duplicate_and_excess_quantity_rejected(self):
        for item in [{'name': 'Counterspell', 'quantity': 1}, {'name': self.deck['commander'], 'quantity': 1}, {'name': 'Spell 0', 'quantity': 2}, {'name': 'Spell 0', 'quantity': -1}]:
            draft = {**self.draft, 'cuts': [{**item, 'reason': 'Cut.'}]}
            self.assertEqual(verify_cuts(draft, self.task, self.deck, self.check, self.facts)['mode'], 'guarded')
        draft = {**self.draft, 'cuts': [self.draft['cuts'][0]] * 13}
        self.assertEqual(verify_cuts(draft, self.task, self.deck, self.check, self.facts)['mode'], 'guarded')

    def test_twelve_cuts_do_not_claim_to_reach_one_hundred(self):
        draft = {**self.draft, 'cuts': self.draft['cuts'][:-1]}
        reply = verify_cuts(draft, self.task, self.deck, self.check, self.facts)
        self.assertEqual(reply['mode'], 'guarded')
        self.assertIn('exactly 13', ' '.join(reply['validation_notes']))

    def test_missing_oracle_data_is_distinct_from_missing_list(self):
        self.deck['cards'][2]['name'] = 'Unavailable card'
        check, facts = check_deck(self.deck, self.cards.__getitem__)
        draft = {**self.draft, 'cuts': self.draft['cuts'][1:] + [{'name': 'Island', 'quantity': 1, 'reason': 'Test quantity accounting.'}]}
        reply = verify_cuts(draft, self.task, self.deck, check, facts)
        self.assertEqual(reply['total_after'], 100)
        self.assertIn('I have the full list', reply['answer'])
        self.assertIn('Unavailable card', reply['answer'])

    def test_failed_repairs_never_fallback_to_additions(self):
        draft = {'answer': 'What do you want to cut?', 'recommendations': [], 'cuts': []}
        with patch('libby.urllib.request.urlopen', side_effect=[response(draft) for _ in range(3)]):
            reply = ask('test', 'model', QUESTION, {'deck': self.deck}, [], self.cards.__getitem__, Mock(), reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(reply['code'], 'unverified_cuts')
        self.assertIn('active deck list', reply['error'])

    def test_noncut_requests_and_explicit_quantities(self):
        self.assertIsNone(cut_request('Suggest creature removal', 113))
        self.assertIsNone(cut_request('Recommend upgrades', 113))
        self.assertEqual(cut_request('Cut 5 cards', 113)['count'], 5)
        self.assertEqual(cut_request('Which 13 cards would you remove?', 113)['count'], 13)
        self.assertEqual(cut_request('Trim my deck to 100 cards', 120)['count'], 20)

    def test_alias_and_multiple_copies_are_counted(self):
        self.cards['Imported alias'] = {**self.cards['Spell 0'], 'oracle_id': 'shared'}
        self.deck['cards'][2] = {'name': 'Imported alias', 'quantity': 13}
        check, facts = check_deck(self.deck, self.cards.__getitem__)
        task = cut_request('Remove 13 cards', check['total'])
        reply = verify_cuts({'recommendations': [], 'cuts': [{'name': 'Spell 0', 'quantity': 13, 'reason': 'Duplicate copies.'}]}, task, self.deck, check, facts)
        self.assertEqual(reply['mode'], 'verified_cuts')
        self.assertEqual(reply['total_before'] - reply['total_after'], 13)
