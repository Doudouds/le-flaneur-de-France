#!/usr/bin/env python3
"""Fetch a uniform national visibility indicator, joined by exact P380.

Count Wikipedia language editions (not Commons categories or other projects).
Ambiguous references are excluded unless their scope has a sourced review.
The checked-in snapshot makes catalogue rebuilds reproducible and offline.
"""
from __future__ import annotations
import argparse
import collections
from contextlib import closing
import hashlib
import json
import re
import sqlite3
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from urllib.parse import urlencode
from enrich_wikipedia import request_json, save_json

ROOT = Path(__file__).resolve().parents[1]
SPARQL = '''SELECT ?item ?ref (COUNT(DISTINCT ?article) AS ?languages) WHERE {
  ?item wdt:P380 ?ref.
  OPTIONAL {
    ?article schema:about ?item; schema:isPartOf ?site.
    ?site wikibase:wikiGroup "wikipedia".
  }
} GROUP BY ?item ?ref'''


def language_count(entity):
    if 'sitelinks' not in entity: raise ValueError('Missing sitelinks field is not a zero count')
    return sum(key.endswith('wiki') and key not in {'commonswiki', 'specieswiki', 'wikidatawiki', 'mediawikiwiki', 'metawiki', 'incubatorwiki', 'foundationwiki'}
               for key in entity['sitelinks'])


def apply_scope_reviews(records, ambiguous, reviews, entities):
    for ref, review in reviews.items():
        entity, retrieved = entities[review['item']]
        if review.get('source') != 'https://pop.culture.gouv.fr/notice/merimee/' + ref or not review.get('reason'):
            raise ValueError('A scope review requires the exact POP notice and a rationale')
        records[ref] = dict(item=review['item'], wikipedia_languages=language_count(entity),
                            source='https://www.wikidata.org/wiki/' + review['item'],
                            retrieved=retrieved, method='reviewed-monument-scope', scope_review=review)
        ambiguous.pop(ref, None)


def exact_signals(bindings):
    candidates = collections.defaultdict(dict)
    for binding in bindings:
        ref = binding['ref']['value'].strip().upper()
        item = binding['item']['value'].rsplit('/', 1)[-1]
        count = int(binding['languages']['value'])
        if re.fullmatch(r'PA[0-9AB]{8}', ref) and re.fullmatch(r'Q[1-9][0-9]*', item) and count >= 0:
            candidates[ref][item] = count
    records = {}
    ambiguous = {}
    for ref, items in sorted(candidates.items()):
        if len(items) != 1:
            ambiguous[ref] = sorted(items)
            continue
        item, count = next(iter(items.items()))
        records[ref] = dict(item=item, wikipedia_languages=count,
                            source='https://www.wikidata.org/wiki/' + item)
    return records, ambiguous


def cached_signals(cache_path, index_path, extra_cache=None):
    """Reuse raw API entities, never legacy scores or inferred language counts.

    Include all candidates in the national P380 index when checking ambiguity,
    even if a candidate's entity was not downloaded into the API cache.
    """
    bindings, dates = [], {}
    entities = {}
    for path in [cache_path] + ([extra_cache] if extra_cache else []):
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
            for raw, retrieved in db.execute("SELECT value_json,updated_at FROM cache WHERE namespace='wikidata_entity'"):
                entity = json.loads(raw)
                if not entity.get('id') or 'missing' in entity or 'sitelinks' not in entity: continue
                entities[entity['id']] = (entity, retrieved)
    for entity, retrieved in entities.values():
        claims = [c for c in entity.get('claims', {}).get('P380', []) if c.get('rank') != 'deprecated']
        preferred = [c for c in claims if c.get('rank') == 'preferred']
        claims = preferred or claims
        count = language_count(entity)
        for claim in claims:
            ref = claim.get('mainsnak', {}).get('datavalue', {}).get('value')
            if not isinstance(ref, str): continue
            bindings.append(dict(ref={'value': ref}, item={'value': entity['id']}, languages={'value': str(count)}))
            dates[(ref.strip().upper(), entity['id'])] = retrieved
    records, ambiguous = exact_signals(bindings)
    candidates = collections.defaultdict(set)
    for binding in bindings:
        candidates[binding['ref']['value'].strip().upper()].add(binding['item']['value'])
    for binding in json.loads(index_path.read_text(encoding='utf-8'))['results']['bindings']:
        candidates[binding['ref']['value'].strip().upper()].add(binding['item']['value'].rsplit('/', 1)[-1])
    for ref, items in candidates.items():
        if len(items) > 1:
            records.pop(ref, None)
            ambiguous[ref] = sorted(items)
    for ref, record in records.items(): record['retrieved'] = dates[(ref, record['item'])]
    return records, ambiguous


def complete_index(source_cache, index_path, extra_cache, extra_items=()):
    """Fill missing exact-index entities, one API request at a time; resumable."""
    with closing(sqlite3.connect(source_cache.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        known = {qid for qid, raw in db.execute("SELECT cache_key,value_json FROM cache WHERE namespace='wikidata_entity'")
                 if (entity := json.loads(raw)).get('id') and 'sitelinks' in entity and 'missing' not in entity}
    with closing(sqlite3.connect(extra_cache)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS cache (namespace TEXT,cache_key TEXT PRIMARY KEY,value_json TEXT,updated_at TEXT)')
        known.update(r[0] for r in db.execute('SELECT cache_key FROM cache'))
        wanted = {b['item']['value'].rsplit('/', 1)[-1] for b in json.loads(index_path.read_text(encoding='utf-8'))['results']['bindings']}
        pending = sorted(set(extra_items) - known) + sorted(wanted - known - set(extra_items))
        print(f'{len(pending)} entities to complete', flush=True)
        for offset in range(0, len(pending), 50):
            batch = pending[offset:offset+50]
            url = 'https://www.wikidata.org/w/api.php?' + urlencode(dict(action='wbgetentities', ids='|'.join(batch),
                       props='sitelinks|claims|labels', languages='fr', format='json', maxlag=60))
            # Keep successful batches and respect Retry-After. Never treat a
            # failed request as a zero count.
            for attempt in range(4):
                try:
                    with urlopen(Request(url, headers={'User-Agent': 'LesPierresDeFrance/0.3.1 (heritage catalogue audit)'}), timeout=60) as response:
                        data = json.load(response)
                    break
                except HTTPError as exc:
                    if exc.code not in (429, 502, 503, 504) or attempt == 3: raise
                    pause = max(60, int(exc.headers.get('Retry-After', '60')))
                    print(f'HTTP {exc.code}: waiting {pause}s before retry', flush=True)
                    time.sleep(pause)
            if 'error' in data: raise RuntimeError(data['error'])
            retrieved = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            for qid, entity in data['entities'].items():
                if 'missing' in entity: continue
                entity['claims'] = {k: v for k, v in entity.get('claims', {}).items() if k in ('P380', 'P361', 'P527')}
                db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?)', ('wikidata_entity', qid, json.dumps(entity), retrieved))
            db.commit()
            if offset % 500 == 0 or offset + 50 >= len(pending): print(f'Entities completed: {min(offset+50,len(pending))}/{len(pending)}', flush=True)
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/scoring_enrichment.json')
    parser.add_argument('--entity-cache', type=Path, help='Reuse raw Wikidata API entity responses instead of requesting SPARQL')
    parser.add_argument('--index', type=Path, default=ROOT/'data/wikidata_merimee.json')
    parser.add_argument('--complete-index', action='store_true', help='Fetch missing exact-index entities into a local resumable cache')
    parser.add_argument('--extra-cache', type=Path, default=ROOT/'data/scoring_api_cache.sqlite')
    parser.add_argument('--extra-items', nargs='*', default=[])
    parser.add_argument('--reviews', type=Path, default=ROOT/'data/scoring_scope_reviews.json')
    args = parser.parse_args()
    reviews = json.loads(args.reviews.read_text(encoding='utf-8'))
    provenance = {}
    if args.entity_cache:
        if args.complete_index: complete_index(args.entity_cache, args.index, args.extra_cache, set(args.extra_items) | {v['item'] for v in reviews.values()})
        records, ambiguous = cached_signals(args.entity_cache, args.index, args.extra_cache if args.extra_cache.exists() else None)
        provenance = dict(entity_cache_sha256=hashlib.sha256(args.entity_cache.read_bytes()).hexdigest(),
                          index_sha256=hashlib.sha256(args.index.read_bytes()).hexdigest())
        if args.extra_cache.exists(): provenance['extra_cache_sha256'] = hashlib.sha256(args.extra_cache.read_bytes()).hexdigest()
        response_hash = None
    else:
        result = request_json('https://query.wikidata.org/sparql?' + urlencode(dict(query=SPARQL, format='json')))
        records, ambiguous = exact_signals(result['results']['bindings'])
        response_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    review_entities = {}
    if args.entity_cache:
        for path in [args.entity_cache] + ([args.extra_cache] if args.extra_cache.exists() else []):
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
                for item in {v['item'] for v in reviews.values()}:
                    row = db.execute("SELECT value_json,updated_at FROM cache WHERE namespace='wikidata_entity' AND cache_key=?", (item,)).fetchone()
                    if row: review_entities[item] = (json.loads(row[0]), row[1])
    else:
        items = sorted({v['item'] for v in reviews.values()})
        for offset in range(0, len(items), 50):
            result = request_json('https://www.wikidata.org/w/api.php?' + urlencode(dict(action='wbgetentities',
                                  ids='|'.join(items[offset:offset+50]), props='sitelinks', format='json')))
            review_entities.update({q: (e, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())) for q, e in result['entities'].items()})
    apply_scope_reviews(records, ambiguous, reviews, review_entities)
    provenance['scope_reviews_sha256'] = hashlib.sha256(args.reviews.read_bytes()).hexdigest()
    # Reject an incomplete national response instead of overwriting the snapshot.
    if len(records) < 25000:
        raise ValueError(f'Unexpectedly incomplete national index: {len(records)} references')
    snapshot = dict(version=1, retrieved=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    method='wikidata:P380-exact + sourced scope reviews; Wikipedia language editions only',
                    license='CC0', query=SPARQL if not args.entity_cache else None,
                    mode='cached-wikidata-api-entities' if args.entity_cache else 'live-sparql',
                    provenance=provenance, response_sha256=response_hash,
                    records=records, ambiguous=ambiguous)
    save_json(args.output, snapshot)
    print(json.dumps(dict(records=len(records), ambiguous=len(ambiguous),
                          eiffel=records.get('PA00088801')), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
