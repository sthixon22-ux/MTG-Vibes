import unittest
from analytics import summarize


class AnalyticsTests(unittest.TestCase):
    def lookup(self, name):
        return {
            'Commander': {'type_line': 'Legendary Creature', 'cmc': 4},
            'Land': {'type_line': 'Basic Land', 'cmc': 0},
            'Cheap': {'type_line': 'Artifact', 'cmc': 2},
            'Other': {'type_line': 'Creature', 'cmc': 6},
        }[name]

    def deck(self, lands, cheap, other):
        return {'commander': 'Commander', 'cards': [{'name': 'Commander', 'quantity': 1}, {'name': 'Land', 'quantity': lands}, {'name': 'Cheap', 'quantity': cheap}, {'name': 'Other', 'quantity': other}]}

    def test_eight_card_library_excluding_one_card(self):
        # There are eight equally likely seven-card hands. Exactly five keep
        # all three lands and at least one of the two cheap spells.
        result = summarize(self.deck(3, 2, 3), self.lookup)
        self.assertEqual(result['library_size'], 8)
        self.assertEqual(result['opening_hand_odds']['exactly_three_lands_and_cheap_spell'], 62.5)
        self.assertEqual(result['opening_hand_odds']['at_least_three_lands_and_cheap_spell'], 62.5)

    def test_exact_and_at_least_are_distinct(self):
        result = summarize(self.deck(4, 2, 2), self.lookup)
        self.assertEqual(result['opening_hand_odds']['exactly_three_lands_and_cheap_spell'], 50)
        self.assertEqual(result['opening_hand_odds']['at_least_three_lands_and_cheap_spell'], 100)

    def test_missing_data_does_not_invent_odds(self):
        result = summarize(self.deck(3, 2, 3), lambda name: self.lookup(name) if name != 'Cheap' else (_ for _ in ()).throw(KeyError(name)))
        self.assertIsNone(result['opening_hand_odds'])
        self.assertEqual(result['unknown_cards'], ['Cheap'])

    def test_oversized_decks_rejected(self):
        with self.assertRaises(ValueError):
            summarize(self.deck(100, 100, 100), self.lookup)
