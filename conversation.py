"""Small, persistent conversation state; preferences constrain plans, not card facts."""
import re
from strategy import swap_request


def resolve_state(message, history, context, total, cut_request):
    saved = context.get('conversation_state', {})
    if not isinstance(saved, dict):
        saved = {}
    preserve_lands = (saved.get('preferences') or {}).get('preserve_lands') is True if isinstance(saved.get('preferences'), dict) else False
    user_turns = [t['content'] for t in history if t['role'] == 'user'] + [message]
    for text in user_turns:
        if re.search(r"\b(?:do not|don[’']t|never|avoid)\s+(?:cut(?:ting)?|remov(?:e|ing)|swap(?:ping)?(?: out)?)\s+(?:any |the )?lands?\b|\b(?:keep|preserve)\s+(?:all |my |the )?lands?\b", text, re.I):
            preserve_lands = True
        elif re.search(r'\b(?:you can|you may|okay to|allow)\s+(?:cut|remove)\s+lands?\b|\ballow land cuts\b', text, re.I):
            preserve_lands = False
    swaps = swap_request(message)
    cuts = None if swaps else cut_request(message, total)
    revision = bool(re.search(r'\b(try again|revise|redo|instead|keep|preserve|avoid|do not|don[’\']t)\b', message, re.I))
    prior = saved.get('task')
    if not isinstance(prior, dict) or prior.get('type') not in ('swaps', 'cuts'):
        prior = None
    if revision and not swaps and not re.search(r'\b\d+\s+cards?\b', message):
        for text in reversed(user_turns[:-1]):
            previous = swap_request(text)
            if previous:
                prior = previous
                break
            previous = cut_request(text, total)
            if previous and previous.get('count') is not None:
                prior = previous
                break
            if '?' in text and not re.search(r'\b(try again|revise|redo|keep|preserve|avoid|do not|don[’\']t)\b', text, re.I):
                prior = None
                break
        if prior:
            if prior['type'] == 'swaps' and type(prior.get('count')) is int and 1 <= prior['count'] <= 20:
                swaps, cuts = prior, None
            elif prior['type'] == 'cuts':
                count = prior.get('count')
                if type(count) is int and 0 <= count <= 250:
                    cuts = {'type': 'cuts', 'count': count, 'total_before': total, 'target': total - count}
    if not revision and not swaps and not cuts and ('?' in message or re.search(r'\b(?:tell me about|what does|how does|evaluate)\b', message, re.I)):
        prior = None
    state = {'preferences': {'preserve_lands': preserve_lands}, 'task': swaps or cuts or prior}
    return swaps, cuts, state


def constraint_errors(draft, cards, state):
    if not state['preferences']['preserve_lands']:
        return []
    from commander import front_type
    lands = {c['name'].casefold() for c in cards if 'Land' in front_type(c).split(' — ')[0].split()}
    for card in cards:
        if card['name'].casefold() in lands:
            lands.update(n.casefold() for n in card.get('imported_names', []))
    proposed = [r.get('cut', '') for r in draft.get('recommendations', []) if isinstance(r, dict)] + [r.get('name', '') for r in draft.get('cuts', []) if isinstance(r, dict)]
    return [name + ': the user said to keep all lands. Choose a nonland instead.' for name in proposed if isinstance(name, str) and name.casefold() in lands]
