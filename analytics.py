"""Deterministic deck facts and opening-hand probabilities; no AI required."""
from math import comb


def summarize(deck, lookup):
    cards = deck.get('cards', [])
    if not isinstance(cards, list) or not 1 <= len(cards) <= 250:
        raise ValueError('Choose a saved deck first.')
    if any(not isinstance(c, dict) or not isinstance(c.get('name'), str) or not 0 < len(c['name']) <= 200 or type(c.get('quantity')) is not int or not 1 <= c['quantity'] <= 250 for c in cards):
        raise ValueError('Invalid deck list.')
    if sum(c['quantity'] for c in cards) > 250:
        raise ValueError('Deck exceeds 250 cards.')
    commander = str(deck.get('commander', '')).casefold()
    total = lands = cheap = known = flex_lands = 0
    curve = [0] * 8
    unknown = []
    verified = []
    for entry in cards:
        quantity = entry['quantity'] - (1 if entry['name'].casefold() == commander else 0)
        total += quantity
        try:
            card = lookup(entry['name'])
        except Exception:
            unknown.append(entry['name'])
            continue
        verified.append({k: card.get(k) for k in ('name', 'type_line', 'cmc', 'color_identity', 'oracle_text')})
        known += quantity
        faces = card.get('card_faces') or []
        front = faces[0].get('type_line', '') if faces else card.get('type_line', '')
        land = 'Land' in front.split(' — ')[0].split()
        if land:
            lands += quantity
        else:
            mana = max(0, float(card.get('cmc') or 0))
            cheap += quantity if mana <= 2 else 0
            curve[min(int(mana), 7)] += quantity
            if any('Land' in face.get('type_line', '').split(' — ')[0].split() for face in faces[1:]):
                flex_lands += quantity
    odds = None
    if not unknown and total >= 7:
        other = total - lands - cheap
        denominator = comb(total, 7)
        def probability(exact):
            numerator = 0
            for land_count in range(3, min(lands, 7) + 1):
                if exact and land_count != 3:
                    continue
                for spell_count in range(1, min(cheap, 7 - land_count) + 1):
                    rest = 7 - land_count - spell_count
                    if 0 <= rest <= other:
                        numerator += comb(lands, land_count) * comb(cheap, spell_count) * comb(other, rest)
            return round(100 * numerator / denominator, 2)
        odds = {'exactly_three_lands_and_cheap_spell': probability(True), 'at_least_three_lands_and_cheap_spell': probability(False)}
    return {'library_size': total, 'known_cards': known, 'lands': lands, 'cheap_nonland_spells': cheap, 'flexible_back_face_lands': flex_lands, 'curve': curve, 'unknown_cards': unknown, 'opening_hand_odds': odds, 'verified_cards': verified, 'method': 'Exact hypergeometric probability for seven cards before mulligans; commander excluded. Lands count front-face lands. Flexible land back faces are listed separately.'}


def odds_answer(stats):
    odds = stats['opening_hand_odds']
    if odds is None:
        return 'I cannot give reliable odds yet: some card data is missing or the library has fewer than seven cards. Refresh card data on Deck analysis and try again.'
    return (f"Computed from your {stats['library_size']}-card library: {stats['lands']} front-face lands and {stats['cheap_nonland_spells']} nonland spells with mana value 2 or less.\n\n"
            f"Exactly 3 lands plus at least one such spell: {odds['exactly_three_lands_and_cheap_spell']}%.\n"
            f"At least 3 lands plus at least one such spell: {odds['at_least_three_lands_and_cheap_spell']}%.\n\n"
            f"{stats['method']} These are deck calculations, independent of the AI connection.")
