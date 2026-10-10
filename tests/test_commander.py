import io
import json
import unittest
from unittest.mock import patch
from commander import check_deck, addition_errors, compatible_pair, eligible, find_rules
from analytics import summarize
from libby import verify_reply, ask


def card(name, colors=(), types='Artifact', text='', legal='legal', **extras):
    return dict(name=name, color_identity=list(colors), type_line=types, oracle_text=text, legalities={'commander': legal}, cmc=2, **extras)


class CommanderTests(unittest.TestCase):
    def setUp(self):
        self.cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf'), 'Forest': card('Forest', 'G', 'Basic Land — Forest'), 'Rock': card('Rock')}
        self.deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}, {'name': 'Forest', 'quantity': 98}, {'name': 'Rock', 'quantity': 1}]}

    def check(self):
        return check_deck(self.deck, self.cards.__getitem__)[0]

    def test_valid_deck_and_colorless_addition(self):
        result = self.check()
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['color_identity'], ['B', 'G'])
        self.assertEqual(addition_errors(card('Colorless'), result), [])

    def test_activated_hybrid_devoid_and_back_faces_use_scryfall_identity(self):
        result = self.check()
        for c in [card('Blue Rock', 'U', text='{U}: Draw a card.'), card('Hybrid', 'GW'), card('Devoid', 'R', text='Devoid'), card('Two faces', 'GU', card_faces=[{'color_indicator': ['U']}])]:
            self.assertTrue(any('outside' in x for x in addition_errors(c, result)), c['name'])
        self.assertFalse(addition_errors(card('Extort', 'B', text='Extort (Reminder {W/B})'), result))
        self.assertFalse(addition_errors(card('Any color', text='Add one mana of any color.'), result))

    def test_basic_land_type_and_banned_cards(self):
        result = self.check()
        self.assertTrue(addition_errors(card('Typed land', types='Land — Island'), result))
        self.assertTrue(addition_errors(card('Banned', legal='banned'), result))
        self.cards['Rock']['legalities']['commander'] = 'banned'
        self.assertIn('not legal', ' '.join(self.check()['issues']))

    def test_singleton_and_oracle_copy_exceptions(self):
        self.deck['cards'][-1]['quantity'] = 2
        self.assertIn('allowed maximum is 1', ' '.join(self.check()['issues']))
        self.cards['Rock']['oracle_text'] = 'A deck can have any number of cards named Rock.'
        self.assertNotIn('allowed maximum', ' '.join(self.check()['issues']))
        self.cards['Rock']['oracle_text'] = 'A deck can have up to nine cards named Rock.'
        self.deck['cards'][-1]['quantity'] = 10
        self.assertIn('allowed maximum is 9', ' '.join(self.check()['issues']))

    def test_interchangeable_names_share_oracle_id(self):
        self.cards['Rock']['oracle_id'] = 'same'
        self.cards['Alternate'] = card('Alternate', oracle_id='same')
        self.deck['cards'].append({'name': 'Alternate', 'quantity': 1})
        self.assertIn('allowed maximum is 1', ' '.join(self.check()['issues']))

    def test_unknown_and_invalid_commander_fail_closed(self):
        self.cards['Leader']['color_identity'] = None
        self.assertFalse(self.check()['identity_verified'])
        self.assertTrue(addition_errors(card('Rock'), self.check()))
        self.cards['Leader'] = card('Leader', 'BG', 'Legendary Planeswalker')
        self.assertFalse(self.check()['identity_verified'])
        self.cards['Leader']['oracle_text'] = 'Leader can be your commander.'
        self.assertTrue(self.check()['identity_verified'])
        self.cards['Leader']['legalities']['commander'] = 'banned'
        self.assertFalse(self.check()['identity_verified'])
        del self.cards['Leader']
        self.assertIn('Leader', self.check()['unknown_cards'])

    def test_current_legendary_vehicle_and_spacecraft_eligibility(self):
        self.assertTrue(eligible(card('Vehicle', types='Legendary Artifact — Vehicle')))
        self.assertTrue(eligible(card('Spacecraft', types='Legendary Artifact — Spacecraft', power='4', toughness='4')))
        self.assertFalse(eligible(card('Artifact', types='Legendary Artifact')))

    def test_partners_combine_colors_and_exclude_both_from_library(self):
        self.cards['Leader']['oracle_text'] = 'Partner (You can have two commanders.)'
        self.cards['Partner'] = card('Partner', 'U', 'Legendary Creature — Bird', 'Partner')
        self.deck['partner'] = 'Partner'
        self.deck['cards'][1]['quantity'] = 97
        self.deck['cards'].append({'name': 'Partner', 'quantity': 1})
        result = self.check()
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['color_identity'], ['U', 'B', 'G'])
        self.assertEqual(summarize(self.deck, self.cards.__getitem__)['library_size'], 98)
        self.cards['Partner']['oracle_text'] = 'Friends forever'
        self.assertFalse(self.check()['identity_verified'])

    def test_named_partner_background_and_doctor(self):
        a = card('A', types='Legendary Creature', text='Partner with B')
        b = card('B', types='Legendary Creature', text='Partner with A')
        self.assertTrue(compatible_pair(a, b))
        b['oracle_text'] = 'Partner with C'
        self.assertFalse(compatible_pair(a, b))
        a['oracle_text'] = 'Choose a Background'
        b = card('Background', types='Legendary Enchantment — Background')
        self.assertTrue(compatible_pair(a, b))
        a['oracle_text'] = 'Doctor’s companion'
        b = card('Doctor', types='Legendary Creature — Time Lord Doctor')
        self.assertTrue(compatible_pair(a, b))
        b['type_line'] += ' Human'
        self.assertFalse(compatible_pair(a, b))

    def test_rules_lookup_returns_real_numbered_rules(self):
        found = find_rules('903.4c reminder text color identity')
        self.assertEqual(found['effective'], '2026-09-25')
        self.assertTrue(any(e['rule'] == '903.4c' and 'Reminder text is ignored' in e['text'] for e in found['excerpts']))

    def test_off_color_and_hallucinated_cuts_withhold_draft(self):
        self.cards['Blue Spell'] = card('Blue Spell', 'U')
        reply = verify_reply({'answer': 'This is great!', 'recommendations': [{'name': 'Blue Spell', 'reason': 'Ramp', 'cut': 'Rock'}]}, self.check(), {'rock': self.cards['Rock']}, '', self.cards.__getitem__)
        self.assertEqual(reply['mode'], 'guarded')
        self.assertNotIn('This is great', reply['answer'])
        self.assertEqual(reply['recommendations'], [])
        self.cards['Legal Spell'] = card('Legal Spell', 'G')
        reply = verify_reply({'answer': 'Upgrade.', 'recommendations': [{'name': 'Legal Spell', 'reason': 'Ramp', 'cut': 'Invented Card'}]}, self.check(), {'rock': self.cards['Rock']}, '', self.cards.__getitem__)
        self.assertEqual(reply['mode'], 'guarded')

    def test_verified_additions_and_user_illegal_card_discussion(self):
        self.cards['New Card'] = card('New Card', 'G')
        self.cards['Blue Card'] = card('Blue Card', 'U')
        reply = verify_reply({'answer': '[[Blue Card]] has blue identity; it is illegal here.', 'recommendations': [{'name': 'New Card', 'reason': 'An optional improvement.', 'cut': 'Rock'}]}, self.check(), {'rock': self.cards['Rock']}, 'Why is Blue Card illegal?', self.cards.__getitem__)
        self.assertEqual(reply['recommendations'][0]['name'], 'New Card')
        self.assertIn('Checked additions', reply['answer'])

    def test_tool_loop_supplies_verified_data_and_rules(self):
        outputs = [
            {'output': [{'type': 'function_call', 'name': 'lookup_rules', 'arguments': '{"query":"903.8 commander tax"}', 'call_id': 'rule-call', 'id': 'rule-id'}]},
            {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'answer': 'Commander tax adds {2} per prior command-zone cast (903.8).', 'recommendations': []})}]}]}
        ]
        with patch('libby.urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(o).encode()) for o in outputs]) as upstream:
            answer = ask('test-only', 'gpt-4.1-mini', 'How does commander tax work?', {'deck': self.deck, 'analysis': 'Blue cards are legal'}, [], self.cards.__getitem__, lambda *args: [])
            payload = json.loads(upstream.call_args.args[0].data)
        self.assertIn('903.8', answer['answer'])
        self.assertIn('color_identity', payload['input'][0]['content'])
        self.assertNotIn('Blue cards are legal', payload['input'][0]['content'])
        self.assertTrue(any(t.get('type') == 'function_call_output' and '903.8' in t['output'] for t in payload['input']))

    def test_bad_draft_repaired_before_delivery(self):
        self.cards['Blue'] = card('Blue', 'U')
        self.cards['Green'] = card('Green', 'G')
        outputs = []
        for name in ('Blue', 'Green'):
            draft = {'answer': 'One optional improvement.', 'recommendations': [{'name': name, 'reason': 'Fits this plan.', 'cut': 'Rock'}]}
            outputs.append({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]})
        with patch('libby.urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(o).encode()) for o in outputs]) as upstream:
            reply = ask('test-only', 'gpt-4.1-mini', 'Suggest a card', {'deck': self.deck}, [], self.cards.__getitem__, lambda *args: [])
        self.assertEqual(upstream.call_count, 2)
        self.assertEqual(reply['recommendations'][0]['name'], 'Green')
        self.assertNotIn('Blue', reply['answer'])
