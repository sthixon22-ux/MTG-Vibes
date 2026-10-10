"""Commander construction checks based on official rules and Scryfall Oracle data."""
import re
from collections import Counter
from pathlib import Path

RULES_SOURCE = 'https://magic.wizards.com/en/rules'
RULES_DATE = '2026-09-25'
RULEBOOK = (Path(__file__).parent / 'rules/comprehensive-20260925.txt').read_text()
RULES = dict(re.findall(r'^([1-9]\d\d\.\d+[a-z]?)[. ]+(.+?)(?=\n[1-9]\d\d\.\d|\Z)', RULEBOOK, re.M | re.S))
CORE_RULES = '\n\n'.join(f'{n}. {text.strip()}' for n, text in RULES.items() if n.startswith(('903.', '702.124')) and not n.startswith(('903.12', '903.13')))
COLORS = set('WUBRG')
LAND_COLORS = {'Plains': 'W', 'Island': 'U', 'Swamp': 'B', 'Mountain': 'R', 'Forest': 'G'}


def commander_names(deck):
    return [n.strip() for n in (deck.get('commander', ''), deck.get('partner', '')) if isinstance(n, str) and n.strip()]


def oracle(card):
    return card.get('oracle_text') or '\n'.join(f.get('oracle_text', '') for f in card.get('card_faces', []))


def front_type(card):
    return (card.get('card_faces') or [card])[0].get('type_line', '')


def identity(card):
    value = card.get('color_identity')
    return set(value) if isinstance(value, list) and set(value) <= COLORS else None


def eligible(card):
    types = front_type(card)
    return ('Legendary' in types and ('Creature' in types or 'Vehicle' in types or ('Spacecraft' in types and bool(card.get('power') or any(f.get('power') for f in card.get('card_faces', [])))))) or 'can be your commander' in oracle(card).lower()


def compatible_pair(a, b):
    ta, tb = oracle(a), oracle(b)
    # Background and Doctor pairs have their own eligibility exceptions.
    for lead, other in ((a, b), (b, a)):
        types = front_type(other)
        if 'Choose a Background' in oracle(lead) and eligible(lead) and all(t in types for t in ('Legendary', 'Enchantment', 'Background')):
            return True
        subtypes = types.split(' — ', 1)[-1].split()
        if 'Doctor’s companion' in oracle(lead) and eligible(lead) and 'Legendary' in types and 'Creature' in types and subtypes == ['Time', 'Lord', 'Doctor']:
            return True
    if not eligible(a) or not eligible(b):
        return False
    if re.search(r'^Partner(?:\s*\(|\s*$)', ta, re.M) and re.search(r'^Partner(?:\s*\(|\s*$)', tb, re.M):
        return True
    if f'Partner with {b.get("name")}' in ta and f'Partner with {a.get("name")}' in tb:
        return True
    tags = lambda text: set(re.findall(r'^Partner\s*[—–-]\s*([^\n(]+)', text, re.M))
    if tags(ta) & tags(tb):
        return True
    return 'Friends forever' in ta and 'Friends forever' in tb


def copy_limit(card):
    if 'Basic' in front_type(card).split(' — ')[0].split():
        return None
    text = oracle(card)
    if re.search(r'A deck can have any number of cards named ', text, re.I):
        return None
    match = re.search(r'A deck can have up to (\w+) cards named ', text, re.I)
    numbers = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
    if match:
        return int(match[1]) if match[1].isdigit() else numbers.get(match[1].lower(), 1)
    return 1


def addition_errors(card, check):
    errors = []
    if card.get('legalities', {}).get('commander') != 'legal':
        errors.append('not legal in Commander')
    colors = identity(card)
    allowed = set(check['color_identity']) if check.get('identity_verified') else None
    if colors is None or allowed is None:
        errors.append('color identity could not be verified')
    elif not colors <= allowed:
        errors.append('outside the commander’s color identity (' + ', '.join(sorted(colors - allowed)) + ')')
    # Basic land types have inherent mana abilities even if Oracle text is blank.
    types = front_type(card).split(' — ', 1)
    if allowed is not None and len(types) == 2 and 'Land' in types[0] and any(t in types[1].split() and c not in allowed for t, c in LAND_COLORS.items()):
        errors.append('basic land type produces a color outside the commander’s identity')
    return errors


def check_deck(deck, lookup):
    from analytics import validate_deck
    validate_deck(deck)
    names = commander_names(deck)
    issues, unknown, resolved = [], [], {}
    total = sum(c['quantity'] for c in deck['cards'])
    if total != 100:
        issues.append(f'Exactly 100 cards are required, including commanders; this list has {total}. (903.5a)')
    if not names:
        issues.append('Choose a commander before checking color identity.')
    if len({n.casefold() for n in names}) != len(names):
        issues.append('Two commanders must be different cards.')
    for name in dict.fromkeys([c['name'] for c in deck['cards']] + names):
        try:
            resolved[name.casefold()] = lookup(name)
        except Exception:
            unknown.append(name)
    commanders = [resolved.get(n.casefold()) for n in names]
    verified = bool(names) and all(c is not None and identity(c) is not None for c in commanders)
    colors = set().union(*(identity(c) for c in commanders)) if verified else set()
    if any(c and c.get('legalities', {}).get('commander') != 'legal' for c in commanders):
        verified = False
        issues.append('A selected commander is not verified as Commander-legal; additions are unavailable.')
    # These cards need a deck-building color choice. Never guess it.
    if any(c and re.search(r'(choose a color|choose two colors) before the game begins', oracle(c), re.I) for c in commanders):
        verified = False
        issues.append('This commander requires a pregame color choice; color checks and additions are unavailable until that choice is supported. (903.4b)')
    if len(commanders) == 1 and commanders[0] and not eligible(commanders[0]):
        issues.append(f'{names[0]} cannot normally be your commander. (903.3)')
        verified = False
    if len(commanders) == 2 and all(commanders) and (not compatible_pair(*commanders) or (commanders[0].get('oracle_id') or commanders[0].get('name')) == (commanders[1].get('oracle_id') or commanders[1].get('name'))):
        issues.append('The selected commanders do not form a legal partner, named partner, Background, or Doctor pair. (702.124)')
        verified = False
    counts = Counter()
    cards_by_name = {}
    for entry in deck['cards']:
        card = resolved.get(entry['name'].casefold())
        if not card:
            continue
        # Oracle id groups alternate/universes-beyond interchangeable names.
        key = card.get('oracle_id') or card.get('name', entry['name']).casefold()
        counts[key] += entry['quantity']
        cards_by_name[key] = card
    present = {c.get('oracle_id') or c.get('name', n).casefold() for n, c in resolved.items() if n in {e['name'].casefold() for e in deck['cards']}}
    for name, card in zip(names, commanders):
        key = (card.get('oracle_id') or card.get('name', name).casefold()) if card else None
        if key not in present:
            issues.append(f'Include {name} in the imported 100-card list.')
    check = {'color_identity': [c for c in 'WUBRG' if c in colors], 'identity_verified': verified}
    for key, card in cards_by_name.items():
        limit = copy_limit(card)
        if limit is not None and counts[key] > limit:
            issues.append(f'{card.get("name", key)}: {counts[key]} copies; allowed maximum is {limit}. (903.5b / Oracle text)')
        for error in addition_errors(card, check):
            if 'could not be verified' not in error or verified:
                issues.append(f'{card.get("name", key)}: {error}. (903.5 / Commander legality)')
    if unknown:
        issues.append('Card data unavailable: ' + ', '.join(unknown))
    if not verified:
        issues.append('Commander color identity is not fully verified; additions will not be recommended.')
    check.update({'status': 'issues' if issues else 'passed', 'issues': issues, 'unknown_cards': unknown, 'commanders': names, 'total': total, 'rules_date': RULES_DATE, 'rules_source': RULES_SOURCE, 'scope': 'Construction checks only; companion conditions, unusual deck-building effects, and Rule 0 agreements need individual review.'})
    return check, list(cards_by_name.values())


def card_facts(card):
    facts = {key: card.get(key) for key in ('name', 'mana_cost', 'cmc', 'type_line', 'color_identity', 'oracle_text', 'legalities', 'power', 'toughness', 'keywords', 'scryfall_uri')}
    facts['card_faces'] = [{key: face.get(key) for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors', 'color_indicator', 'power', 'toughness')} for face in card.get('card_faces', [])]
    return facts


def find_rules(query):
    numbers = set(re.findall(r'\b[1-9]\d\d\.\d+[a-z]?\b', query))
    tokens = set(re.findall(r'[a-z]{4,}', query.lower())) - {'what', 'when', 'does', 'that', 'with', 'have', 'this', 'rules', 'about', 'commander'}
    ranked = sorted(RULES.items(), key=lambda pair: (pair[0] in numbers, sum(len(t) for t in tokens if t in pair[1].lower())), reverse=True)
    return {'source': RULES_SOURCE, 'effective': RULES_DATE, 'excerpts': [{'rule': n, 'text': t.strip()[:5000]} for n, t in ranked[:8] if n in numbers or any(w in t.lower() for w in tokens)]}
