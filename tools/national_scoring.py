"""Versioned discovery rating, independent of category and catalogue quantiles.

Protection is a limited heritage signal; Wikipedia language coverage is an
imperfect but uniformly measured visibility signal, not a visitor rating.
Missing visibility is explicitly unknown (-1), never a fabricated low measure.
"""
from __future__ import annotations
import json
import math
import re
import unicodedata

VERSION = 'national-v2'
THRESHOLDS = (55, 75)


def normalized(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return ''.join(c for c in text if not unicodedata.combining(c))


def round_half_up(value):
    return int(math.floor(value + .5))


def visual_level(value):
    return 3 if value >= THRESHOLDS[1] else 2 if value >= THRESHOLDS[0] else 1


def score(row, signal=None, *, retrieved='', ambiguous=False):
    if signal and ambiguous: raise ValueError('An unresolved ambiguous signal cannot be scored')
    protection = normalized(row.get('Typologie_de_la_protection', ''))
    # Never infer extent of protection from words such as "clocher" or "façade".
    # Mixed protection keeps the strongest documented status.
    if re.search(r'\bclass(?:e|ee|es|ees|ement)\b', protection):
        importance, status = 70, 'classé MH'
    elif re.search(r'\binscrit(?:e|s|es)?\b|\binscription\b', protection):
        importance, status = 50, 'inscrit MH'
    else:
        importance, status = 30, 'protection à préciser'
    languages = signal.get('wikipedia_languages') if signal else None
    if languages is not None and (type(languages) is not int or languages < 0):
        raise ValueError('Wikipedia language count must be a non-negative integer')
    notoriety = -1 if languages is None else min(100, round_half_up(100 * math.log(max(1, languages)) / math.log(100)))
    value = min(100, round_half_up(.5 * importance + .65 * max(0, notoriety)))
    visibility = 'non mesuré (rapprochement ambigu)' if ambiguous else 'non mesuré (donnée absente)'
    if languages is not None:
        visibility = f'{languages} édition(s) linguistique(s) Wikipédia'
    evidence = dict(version=VERSION, protection=status, wikipedia_languages=languages,
                    matching='ambiguous' if ambiguous else signal.get('method', 'wikidata:P380-exact') if signal else 'missing',
                    wikidata=signal.get('source') if signal else None,
                    retrieved=signal.get('retrieved', retrieved) if signal else retrieved,
                    protection_points=.5 * importance,
                    visibility_points=round(.65 * max(0, notoriety), 2),
                    provisional=languages is None, thresholds=list(THRESHOLDS))
    if signal and signal.get('scope_review'): evidence['scope_review'] = signal['scope_review']
    return dict(importance=importance, notoriety=notoriety, globalScore=value,
                visualLevel=visual_level(value),
                scoreSource=f'Barème national v2 — {status} ; rayonnement : {visibility}. Sources : Mérimée et Wikidata.',
                scoreEvidence=json.dumps(evidence, ensure_ascii=False))
