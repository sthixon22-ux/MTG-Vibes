import json
import unittest
from unittest.mock import Mock, patch
from grounding import mentioned_names
from libby import ask
from strategy import swap_request
from test_commander import card
from test_grounding import response

QUESTION = 'If you were to change 5 cards in the current deck to 5 different cards, what would those cards be and why?'


class SwapTests(unittest.TestCase):
    def test_generic_questions_are_not_card_names(self):
        for text in [QUESTION, QUESTION.rstrip('?'), 'What does ramp mean?', 'Is there a better plan?', 'Would those cards work?', 'How does this deck win?']:
            self.assertEqual(mentioned_names(text, []), [], text)
        self.assertEqual(mentioned_names('Is Counterspell good in my deck?', []), ['Counterspell'])

    def test_five_swaps_use_active_list_and_keep_count(self):
        cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf')}
        cards.update({f'Old {i}': card(f'Old {i}', 'G', text='Add {G}.') for i in range(5)})
        cards.update({f'New {i}': card(f'New {i}', 'G', text='Draw a card. Add {G}.') for i in range(5)})
        deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}] + [{'name': f'Old {i}', 'quantity': 1} for i in range(5)]}
        draft = {'answer': 'Here are five proposed swaps.', 'recommendations': [{'name': f'New {i}', 'cut': f'Old {i}', 'reason': 'Adds a draw effect while retaining the mana ability.'} for i in range(5)], 'cuts': [], 'card_references': list(cards)}
        lookup = Mock(side_effect=cards.__getitem__)
        with patch('libby.urllib.request.urlopen', return_value=response(draft)) as upstream:
            reply = ask('test', 'model', QUESTION, {'deck': deck}, [], lookup, lambda *args: list(cards.values()), reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(len(reply['recommendations']), 5)
        self.assertEqual(len({r['cut'] for r in reply['recommendations']}), 5)
        self.assertFalse(any('those cards' in call.args[0] for call in lookup.call_args_list))
        payload = json.loads(upstream.call_args.args[0].data)
        self.assertIn('ONE-FOR-ONE SWAPS', payload['instructions'])
        self.assertEqual(swap_request(QUESTION), {'type': 'swaps', 'count': 5})

    def test_incomplete_swaps_do_not_fall_back_to_three_additions(self):
        cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf'), 'Old': card('Old', 'G', text='Add {G}.'), 'New': card('New', 'G', text='Add {G}.')}
        deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}, {'name': 'Old', 'quantity': 1}]}
        draft = {'answer': 'Try this.', 'recommendations': [{'name': 'New', 'cut': '', 'reason': 'Mana.'}], 'cuts': [], 'card_references': ['New']}
        with patch('libby.urllib.request.urlopen', side_effect=[response(draft) for _ in range(3)]):
            reply = ask('test', 'model', QUESTION, {'deck': deck}, [], cards.__getitem__, lambda *args: list(cards.values()), reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(reply['code'], 'unverified_swaps')

    def test_double_faced_commander_cannot_be_a_swap_cut(self):
        leader = card('Leader // Back', 'BG', 'Legendary Creature — Elf', card_faces=[{'name': 'Leader', 'type_line': 'Legendary Creature — Elf'}, {'name': 'Back', 'type_line': 'Legendary Planeswalker'}])
        new = card('New', 'G', text='Add {G}.')
        cards = {'Leader': leader, leader['name']: leader, 'New': new}
        deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}]}
        draft = {'answer': 'One swap.', 'recommendations': [{'name': 'New', 'cut': leader['name'], 'reason': 'Mana.'}], 'cuts': [], 'card_references': ['New', leader['name']]}
        with patch('libby.urllib.request.urlopen', side_effect=[response(draft) for _ in range(3)]):
            reply = ask('test', 'model', 'Swap 1 card in my deck', {'deck': deck}, [], cards.__getitem__, lambda *args: [new], reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(reply['code'], 'unverified_swaps')
