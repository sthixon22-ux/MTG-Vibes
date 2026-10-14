import io
import json
import unittest
from unittest.mock import Mock, patch
from conversation import resolve_state
from libby import ask, cut_request
from test_commander import card
from test_grounding import response

QUESTION = 'If you were to change 5 cards in the current deck to 5 different cards, what would those cards be and why?'
FOLLOWUP = 'cutting lands is bad. Do not cut lands from the deck. try again'


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf'), 'Forest': card('Forest', 'G', 'Basic Land — Forest')}
        self.cards.update({f'Old {i}': card(f'Old {i}', 'G', text='Add {G}.') for i in range(5)})
        self.cards.update({f'New {i}': card(f'New {i}', 'G', text='Add {G}. Draw a card.') for i in range(5)})
        self.deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}, {'name': 'Forest', 'quantity': 94}] + [{'name': f'Old {i}', 'quantity': 1} for i in range(5)]}
        self.draft = {'answer': 'I’ll keep all lands. Here are five revised nonland swaps.', 'recommendations': [{'name': f'New {i}', 'cut': f'Old {i}', 'reason': 'Retains the mana effect and adds draw.'} for i in range(5)], 'cuts': [], 'card_references': [f'New {i}' for i in range(5)] + [f'Old {i}' for i in range(5)]}

    def run_chat(self, outputs, reviewer, context=None, history=None):
        with patch('libby.urllib.request.urlopen', side_effect=[response(d) for d in outputs]) as upstream:
            reply = ask('test', 'model', FOLLOWUP, context or {'deck': self.deck}, history if history is not None else [{'role': 'user', 'content': QUESTION}], self.cards.__getitem__, lambda *args: list(self.cards.values()), reviewer=reviewer)
        return reply, upstream

    def test_screenshot_followup_keeps_five_swaps_and_locks_lands(self):
        reply, upstream = self.run_chat([self.draft], lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(len(reply['recommendations']), 5)
        self.assertTrue(reply['conversation_state']['preferences']['preserve_lands'])
        self.assertEqual(reply['conversation_state']['task'], {'type': 'swaps', 'count': 5})
        payload = json.loads(upstream.call_args.args[0].data)
        self.assertIn('Keep every land', payload['instructions'])

    def test_land_cut_is_repaired_before_factual_review(self):
        bad = json.loads(json.dumps(self.draft))
        bad['recommendations'][0]['cut'] = 'Forest'
        reviewer = Mock(return_value={'supported': True, 'issues': []})
        reply, upstream = self.run_chat([bad, self.draft], reviewer)
        self.assertEqual(upstream.call_count, 2)
        self.assertEqual(reviewer.call_count, 1)
        self.assertNotIn('Forest', [r['cut'] for r in reply['recommendations']])

    def test_reviewer_corrects_facts_without_blocking_whole_plan(self):
        bad = {**self.draft, 'answer': 'The draw spells give you three cards.'}
        reply, upstream = self.run_chat([bad], lambda *args: {'supported': False, 'issues': ['Draw amount is wrong.'], 'corrected_reply': self.draft})
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(len(reply['recommendations']), 5)
        self.assertNotIn('three cards', reply['answer'])
        self.assertNotIn('withholding', reply['answer'])

    def test_persistent_state_survives_truncated_history(self):
        context = {'deck': self.deck, 'conversation_state': {'task': {'type': 'swaps', 'count': 5}, 'preferences': {'preserve_lands': True}}}
        reply, _ = self.run_chat([self.draft], lambda *args: {'supported': True, 'issues': []}, context=context, history=[])
        self.assertEqual(len(reply['recommendations']), 5)

    def test_preference_can_be_overridden_by_user(self):
        state = {'conversation_state': {'preferences': {'preserve_lands': True}, 'task': {'type': 'swaps', 'count': 5}}}
        _, _, result = resolve_state('You can cut lands now, try again', [], state, 100, cut_request)
        self.assertFalse(result['preferences']['preserve_lands'])

    def test_new_card_question_does_not_inherit_stale_swap_task(self):
        old = {'conversation_state': {'task': {'type': 'swaps', 'count': 5}, 'preferences': {'preserve_lands': True}}}
        swaps, cuts, state = resolve_state('Is Reaper from the Abyss good here?', [], old, 100, cut_request)
        self.assertIsNone(swaps)
        self.assertIsNone(cuts)
        self.assertIsNone(state['task'])
        history = [{'role': 'user', 'content': QUESTION}, {'role': 'user', 'content': 'Is Reaper from the Abyss good here?'}]
        swaps, cuts, _ = resolve_state('That answer is wrong, try again', history, old, 100, cut_request)
        self.assertIsNone(swaps)

    def test_failed_plan_does_not_dump_oracle_into_conversation(self):
        reply, _ = self.run_chat([self.draft] * 3, lambda *args: {'supported': False, 'issues': ['Unresolved fact.']})
        self.assertEqual(reply['mode'], 'incomplete_plan')
        self.assertIn('keep every land', reply['answer'])
        self.assertNotIn('Oracle text', reply['answer'])
        self.assertTrue(reply['card_evidence'])

    def test_production_reviewer_can_return_corrected_plan(self):
        bad = {**self.draft, 'answer': 'Each draws three cards.'}
        verdict = {'supported': False, 'issues': ['Draw amount wrong.'], 'corrected_reply': self.draft}
        audit = io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(verdict)}]}]}).encode())
        with patch('libby.urllib.request.urlopen', side_effect=[response(bad), audit]) as upstream:
            reply = ask('test', 'gpt-5.4', FOLLOWUP, {'deck': self.deck}, [{'role': 'user', 'content': QUESTION}], self.cards.__getitem__, lambda *args: list(self.cards.values()))
        self.assertEqual(len(reply['recommendations']), 5)
        payload = json.loads(upstream.call_args_list[0].args[0].data)
        self.assertEqual(payload['reasoning']['effort'], 'low')
        review_payload = json.loads(upstream.call_args_list[1].args[0].data)
        self.assertEqual(review_payload['model'], 'gpt-4.1')
        self.assertIn('corrected_reply', review_payload['text']['format']['schema']['required'])

    def test_plan_is_not_printed_twice_when_already_explained(self):
        complete = {**self.draft, 'answer': 'I’ll keep all lands.\n' + '\n'.join(f"{r['cut']} → {r['name']}: {r['reason']}" for r in self.draft['recommendations'])}
        reply, _ = self.run_chat([complete], lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(reply['answer'].count('Old 0 → New 0'), 1)
        self.assertNotIn('Suggested swaps:', reply['answer'])

    def test_requested_ten_swaps_are_supported(self):
        self.cards.update({f'Old {i}': card(f'Old {i}', 'G', text='Add {G}.') for i in range(5,10)})
        self.cards.update({f'New {i}': card(f'New {i}', 'G', text='Add {G}. Draw a card.') for i in range(5,10)})
        self.deck['cards'][1]['quantity'] = 89
        self.deck['cards'] += [{'name': f'Old {i}', 'quantity': 1} for i in range(5,10)]
        draft = {**self.draft, 'recommendations': [{'name': f'New {i}', 'cut': f'Old {i}', 'reason': 'Retains mana and adds draw.'} for i in range(10)]}
        with patch('libby.urllib.request.urlopen', side_effect=[response(draft), response(draft)]):
            reply = ask('test', 'model', 'Change 10 cards in my deck', {'deck': self.deck}, [], self.cards.__getitem__, lambda *args: list(self.cards.values()), reviewer=lambda *args: {'supported': True, 'issues': []})
        self.assertEqual(len(reply['recommendations']), 10)
