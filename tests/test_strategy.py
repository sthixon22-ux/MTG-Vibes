import io
import json
import unittest
from unittest.mock import patch
from commander import check_deck
from libby import ask, verify_reply
from strategy import edhrec_candidates, research_magic, EDHREC_CACHE, RESEARCH_CACHE, wants_suggestions
from test_commander import card


def response(draft):
    return io.BytesIO(json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]}).encode())


class StrategyTests(unittest.TestCase):
    def setUp(self):
        EDHREC_CACHE.clear()
        RESEARCH_CACHE.clear()
        self.cards = {'Leader': card('Leader', 'BG', 'Legendary Creature — Elf'),
                      'Ramp': card('Ramp', 'G', text='Add {G}.', prices={'usd': '1.00'}),
                      'Draw': card('Draw', 'B', text='Draw two cards.', prices={'usd': '2.00'}),
                      'Removal': card('Removal', 'B', text='Destroy target creature.', prices={'usd': '3.00'}),
                      'Blue': card('Blue', 'U', text='Draw three cards.'),
                      'Expensive': card('Expensive', 'G', prices={'usd': '25.00'})}
        self.deck = {'commander': 'Leader', 'cards': [{'name': 'Leader', 'quantity': 1}]}
        self.check = check_deck(self.deck, self.cards.__getitem__)[0]

    def test_questions_only_get_concrete_verified_fallback(self):
        draft = {'answer': 'What is your budget and power level?', 'recommendations': []}
        with patch('libby.urllib.request.urlopen', side_effect=[response(draft) for _ in range(3)]) as upstream:
            reply = ask('test', 'model', 'Suggest improvements', {'deck': self.deck}, [], self.cards.__getitem__, lambda *args: list(self.cards.values()))
        self.assertEqual(upstream.call_count, 3)
        self.assertEqual({r['name'] for r in reply['recommendations']}, {'Ramp', 'Draw', 'Removal'})
        self.assertNotIn('?', reply['answer'])
        self.assertEqual(reply['mode'], 'verified_candidates')

    def test_mixed_suggestions_preserve_good_cards_and_remove_bad_reason(self):
        draft = {'answer': 'Try these.', 'recommendations': [
            {'name': 'Ramp', 'reason': 'Combine with [[Blue]].', 'cut': 'Made up'},
            {'name': 'Blue', 'reason': 'Draw.', 'cut': ''}]}
        result = verify_reply(draft, self.check, {}, '', self.cards.__getitem__)
        self.assertEqual([r['name'] for r in result['recommendations']], ['Ramp'])
        self.assertNotIn('Blue', result['answer'])
        self.assertEqual(result['recommendations'][0]['cut'], '')

    def test_followup_discussion_is_not_blocked(self):
        reply = verify_reply({'answer': '[[Ramp]] adds green mana.', 'recommendations': []}, self.check, {}, 'How does it work?', self.cards.__getitem__)
        self.assertEqual(reply['mode'], 'verified')

    def test_copy_count_is_grounded(self):
        self.deck['cards'].append({'name': 'Ramp', 'quantity': 1})
        check, cards = check_deck(self.deck, self.cards.__getitem__)
        self.assertEqual(cards[-1]['deck_quantity'], 1)
        reply = verify_reply({'answer': 'Add another.', 'recommendations': [{'name': 'Ramp', 'reason': 'Mana.', 'cut': ''}]}, check, {c['name'].casefold(): c for c in cards}, '', self.cards.__getitem__)
        self.assertEqual(reply['recommendations'], [])

    def test_edhrec_candidates_verify_legality_existing_cards_and_price(self):
        entries = [{'name': name, 'num_decks': 100, 'potential_decks': 200} for name in self.cards]
        data = {'container': {'json_dict': {'cardlists': [{'header': 'Top Cards', 'cardviews': entries}]}}}
        with patch('strategy.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            result = edhrec_candidates(self.check, {'leader': self.cards['Leader']}, self.cards.__getitem__, 'cheap upgrades')
        self.assertEqual({r['card']['name'] for r in result['candidates']}, {'Ramp', 'Draw', 'Removal'})
        self.assertEqual(result['sources'][0]['url'], 'https://edhrec.com/commanders/leader')
        self.assertEqual(result['candidates'][0]['publisher_context']['num_decks'], 100)

    def test_web_research_requires_real_citations_and_uses_search(self):
        data = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Strategy summary.', 'annotations': [
            {'type': 'url_citation', 'title': 'EDHREC', 'url': 'https://edhrec.com/articles/example'},
            {'type': 'url_citation', 'title': 'Bad', 'url': 'javascript:alert(1)'}]}]}]}
        with patch('strategy.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as upstream:
            result = research_magic('test', 'Golgari aristocrats')
        payload = json.loads(upstream.call_args.args[0].data)
        self.assertEqual(payload['tools'][0]['type'], 'web_search')
        self.assertEqual(result['sources'], [{'title': 'EDHREC', 'url': 'https://edhrec.com/articles/example'}])
        with patch('strategy.urllib.request.urlopen', return_value=io.BytesIO(json.dumps({'output': []}).encode())):
            self.assertIn('error', research_magic('test', 'Uncited query'))

    def test_research_failure_does_not_block_reply(self):
        tool = {'output': [{'type': 'function_call', 'name': 'research_magic', 'arguments': json.dumps({'query': 'Commander strategy'}), 'call_id': 'one'}]}
        draft = {'answer': 'Your commander has black and green identity.', 'recommendations': []}
        with patch('libby.urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(tool).encode()), response(draft)]):
            reply = ask('test', 'model', 'Explain my commander', {'deck': self.deck}, [], self.cards.__getitem__, lambda *args: [], research=lambda query: (_ for _ in ()).throw(OSError('unavailable')))
        self.assertIn('black and green', reply['answer'])
        self.assertEqual(reply['sources'], [])

    def test_suggestion_intent_and_opt_out(self):
        self.assertTrue(wants_suggestions('Give me upgrades'))
        self.assertFalse(wants_suggestions("Don't recommend cards; explain ward"))
