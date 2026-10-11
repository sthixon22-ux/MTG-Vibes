import io
import json
import unittest
from unittest.mock import Mock, patch
from grounding import mentioned_names, review_claims, obvious_contradictions
from libby import ask
from test_commander import card

REAPER = card('Reaper from the Abyss', 'B', 'Creature — Demon', 'Flying\nMorbid — At the beginning of each end step, if a creature died this turn, destroy target non-Demon creature.', mana_cost='{3}{B}{B}{B}', power='6', toughness='6', scryfall_uri='https://scryfall.com/card/isd/114/reaper-from-the-abyss')
REAPER['colors'] = ['B']
QUESTION = 'would the card called "Reaper from the abyss" be good in this garruk deck?'


def response(draft):
    return io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]}).encode())


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf'), REAPER['name']: REAPER}
        self.deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}]}
        self.lookup = lambda name: next(c for n, c in self.cards.items() if n.casefold() == name.casefold())
        self.good = {'answer': '[[Reaper from the Abyss]] has black identity, costs {3}{B}{B}{B}, and is a 6/6 flyer. Its morbid trigger checks each end step if a creature died and destroys a target non-Demon creature. Six mana and triple black are real costs; reliable creature deaths make it stronger.', 'recommendations': [], 'cuts': [], 'card_references': [REAPER['name']]}

    def ask(self, outputs, reviewer, question=QUESTION, history=None):
        with patch('libby.urllib.request.urlopen', side_effect=[response(d) for d in outputs]) as upstream:
            reply = ask('test', 'model', question, {'deck': self.deck}, history or [], self.lookup, lambda *args: [], reviewer=reviewer)
        return reply, upstream

    def test_named_card_fetched_before_first_model_reply(self):
        audit = Mock(return_value={'supported': True, 'issues': []})
        reply, upstream = self.ask([self.good], audit)
        context = json.loads(json.loads(upstream.call_args.args[0].data)['input'][0]['content'].split(': ', 1)[1])
        self.assertEqual(context['mentioned_card_evidence'][0]['oracle_text'], REAPER['oracle_text'])
        self.assertEqual(context['mentioned_card_evidence'][0]['color_identity'], ['B'])
        self.assertEqual(reply['card_evidence'][0]['mana_cost'], '{3}{B}{B}{B}')
        self.assertTrue(any(s['url'] == REAPER['scryfall_uri'] for s in reply['sources']))
        self.assertEqual(audit.call_count, 1)

    def test_original_and_partially_corrected_hallucinations_retried(self):
        bad = {**self.good, 'answer': 'Reaper is black/green and forces opponents to sacrifice their biggest creatures on your upkeep.'}
        partial = {**self.good, 'answer': 'It destroys a non-Demon at end step, giving built-in removal on your upkeep.'}
        audit = Mock(return_value={'supported': True, 'issues': []})
        reply, upstream = self.ask([bad, partial, self.good], audit)
        self.assertEqual(upstream.call_count, 3)
        self.assertNotIn('upkeep', reply['answer'])
        self.assertNotIn('sacrifice', reply['answer'])
        self.assertIn('end step', reply['answer'])

    def test_persistent_bad_claims_fall_back_to_actual_oracle(self):
        bad = {**self.good, 'answer': 'It forces sacrifices on upkeep.'}
        reply, _ = self.ask([bad] * 3, lambda *args: {'supported': False, 'issues': ['Wrong trigger and effect.']})
        self.assertEqual(reply['mode'], 'source_only')
        self.assertIn(REAPER['oracle_text'], reply['answer'])
        self.assertNotIn('upkeep', reply['answer'])

    def test_review_outage_fails_closed(self):
        reply, _ = self.ask([self.good], Mock(side_effect=OSError('review unavailable')))
        self.assertEqual(reply['mode'], 'source_only')
        self.assertIn('withholding', reply['answer'])
        self.assertEqual(reply['recommendations'], [])

    def test_failed_card_lookup_never_invokes_model(self):
        with patch('libby.urllib.request.urlopen') as upstream:
            reply = ask('test', 'model', 'Would "Unknown Demon" be good?', {'deck': self.deck}, [], self.lookup, Mock())
        upstream.assert_not_called()
        self.assertIn('will not guess', reply['answer'])

    def test_card_first_named_in_draft_requires_fetch_and_regeneration(self):
        question = 'What flying threat could fit?'
        audit = Mock(return_value={'supported': True, 'issues': []})
        reply, upstream = self.ask([self.good, self.good], audit, question)
        self.assertEqual(upstream.call_count, 2)
        inputs = json.loads(upstream.call_args.args[0].data)['input']
        self.assertTrue(any(json.dumps(REAPER['oracle_text'])[1:-1] in item.get('content', '') for item in inputs))
        self.assertEqual(audit.call_count, 1)

    def test_correction_followup_refetches_original_named_card(self):
        reply, upstream = self.ask([self.good], lambda *args: {'supported': True, 'issues': []}, 'No, you got the card wrong', [{'role': 'user', 'content': QUESTION}, {'role': 'assistant', 'content': 'It forces sacrifices on upkeep.'}])
        self.assertEqual(reply['card_evidence'][0]['name'], REAPER['name'])

    def test_quotes_apostrophes_plain_names_and_no_general_false_positive(self):
        for question in [QUESTION, "Is 'Reaper from the Abyss' good in this deck?", 'Is Reaper from the Abyss good in my deck?']:
            self.assertTrue(any(n.casefold() == REAPER['name'].casefold() for n in mentioned_names(question, [])))
        self.assertEqual(mentioned_names('How does commander tax work?', []), [])

    def test_deterministic_checks_reject_original_color_and_effect_errors(self):
        wrong = {**self.good, 'answer': 'Reaper from the Abyss is a black/green creature forcing opponents to sacrifice creatures on your upkeep.'}
        errors = obvious_contradictions(wrong, [REAPER])
        self.assertTrue(any('colors' in e for e in errors))
        self.assertTrue(any('sacrifices' in e for e in errors))
        self.assertEqual(obvious_contradictions(self.good, [REAPER]), [])

    def test_real_reviewer_request_uses_oracle_and_structured_verdict(self):
        result = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'supported': False, 'issues': ['Upkeep is not end step.']})}]}]}
        with patch('grounding.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(result).encode())) as upstream:
            verdict = review_claims('test', 'model', {'answer': 'It triggers on upkeep.'}, [REAPER], [], '', QUESTION)
        payload = json.loads(upstream.call_args.args[0].data)
        self.assertIn(REAPER['oracle_text'], json.loads(payload['input'])['card_evidence'][0]['oracle_text'])
        self.assertIn('partially corrected', payload['instructions'])
        self.assertFalse(verdict['supported'])

    def test_production_review_path_rejects_and_repairs_bad_stats(self):
        bad = {**self.good, 'answer': 'Reaper from the Abyss is a 6/7 flyer.'}
        def review_response(supported):
            return io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'supported': supported, 'issues': [] if supported else ['Scryfall toughness is 6, not 7.']})}]}]}).encode())
        with patch('libby.urllib.request.urlopen', side_effect=[response(bad), review_response(False), response(self.good), review_response(True)]) as upstream:
            reply = ask('test', 'model', QUESTION, {'deck': self.deck}, [], self.lookup, lambda *args: [])
        self.assertEqual(upstream.call_count, 4)
        self.assertIn('6/6', reply['answer'])
        self.assertNotIn('6/7', reply['answer'])
        formats = [json.loads(call.args[0].data)['text']['format']['name'] for call in upstream.call_args_list]
        self.assertEqual(formats, ['libby_reply', 'card_claim_review', 'libby_reply', 'card_claim_review'])
