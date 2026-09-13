#!/usr/bin/env python3
"""Refresh exact Mérimée ↔ French Wikipedia links and cache introductory extracts.

Standard library only; public read-only APIs, resumable SQLite cache, bounded requests.
No model calls. Ambiguous references and disambiguation pages are never auto-selected.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, re, sqlite3, time
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = 'LesPierresDeFrance/0.3 (local French heritage catalogue; Wikipedia enrichment)'
SPARQL = '''SELECT DISTINCT ?item ?ref ?article WHERE {
  ?item wdt:P380 ?ref.
  ?article schema:about ?item; schema:isPartOf <https://fr.wikipedia.org/>.
}'''

def request_json(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'}), timeout=90) as response:
                data = json.load(response)
            if 'error' in data: raise RuntimeError(str(data['error']))
            return data
        except HTTPError as exc:
            if attempt == 3: raise
            pause = max(5 * 2 ** attempt, int(exc.headers.get('Retry-After', '0') or '0'))
            print(f'HTTP {exc.code}; retry after {pause}s', flush=True)
            time.sleep(pause)
        except Exception:
            if attempt == 3: raise
            time.sleep(2 ** (attempt + 1))

def wiki_title(url):
    parts = urlsplit(url)
    if parts.hostname != 'fr.wikipedia.org' or not parts.path.startswith('/wiki/'): return ''
    return unquote(parts.path[6:]).replace('_', ' ')

def exact_links(bindings):
    candidates = collections.defaultdict(dict)
    for binding in bindings:
        ref = binding['ref']['value'].strip().upper()
        url = binding['article']['value']
        if re.fullmatch(r'PA[0-9AB]{8}', ref) and wiki_title(url):
            candidates[ref][url] = binding['item']['value']
    accepted = {ref: {'url': next(iter(urls)), 'item': next(iter(urls.values())),
                       'method': 'wikidata:P380-exact'} for ref, urls in candidates.items() if len(urls) == 1}
    ambiguous = {ref: sorted(urls) for ref, urls in candidates.items() if len(urls) > 1}
    return accepted, ambiguous

def fetch_pages(titles):
    params = dict(action='query', format='json', formatversion=2, redirects=1,
                  prop='extracts|pageprops|info', inprop='url',
                  exintro=1, explaintext=1, exlimit=20, titles='|'.join(titles), maxlag=5)
    result = request_json('https://fr.wikipedia.org/w/api.php?' + urlencode(params))
    query = result.get('query', {})
    aliases = {item['from']: item['to'] for field in ('normalized', 'redirects') for item in query.get(field, [])}
    pages = {page['title']: page for page in query.get('pages', [])}
    output = {}
    for title in titles:
        canonical = title
        seen = set()
        while canonical in aliases and canonical not in seen:
            seen.add(canonical); canonical = aliases[canonical]
        page = pages.get(canonical, {})
        valid = bool(page) and 'missing' not in page and 'disambiguation' not in page.get('pageprops', {}) and page.get('ns') == 0
        output[title] = dict(title=canonical, valid=valid,
            extract=page.get('extract', '').strip() if valid else '',
            url=page.get('fullurl', ''), revision=page.get('lastrevid'),
            retrieved=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    return output

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'app/src/main/assets/monuments.db')
    parser.add_argument('--output', type=Path, default=ROOT/'data/wikipedia_enrichment.json')
    parser.add_argument('--cache', type=Path, default=ROOT/'data/wikipedia_cache.sqlite')
    parser.add_argument('--refresh-index', action='store_true')
    parser.add_argument('--index-only', action='store_true')
    parser.add_argument('--only-references', nargs='*', help='Fetch extracts only for these references; still export all links')
    parser.add_argument('--links-only', action='store_true', help='Export the complete link index with already cached extracts')
    args = parser.parse_args()
    index_path = args.cache.with_name('wikidata_merimee.json')
    if args.refresh_index or not index_path.exists():
        print('Fetching national Wikidata P380 index...', flush=True)
        save_json(index_path, request_json('https://query.wikidata.org/sparql?' + urlencode({'query': SPARQL, 'format': 'json'})))
    links, ambiguous = exact_links(json.loads(index_path.read_text(encoding='utf-8'))['results']['bindings'])
    print(f'Unique exact links: {len(links)}; ambiguous references: {len(ambiguous)}', flush=True)
    if args.index_only: return
    with sqlite3.connect(f'file:{args.database.as_posix()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        monuments = [dict(row) for row in db.execute('SELECT reference,description,descriptionSource,wikipediaUrl FROM monuments')]
    selected = {}
    conflicts = []
    for m in monuments:
        ref = m['reference']; current = m['wikipediaUrl']
        if ref in ambiguous:
            conflicts.append({'reference': ref, 'candidates': ambiguous[ref]})
            # Existing manually sourced link is retained; new ambiguous matches are excluded.
        match = links.get(ref)
        if match:
            if current and wiki_title(current) != wiki_title(match['url']):
                conflicts.append({'reference': ref, 'previous': current, 'selected': match['url'], 'method': match['method']})
            selected[ref] = dict(match)
        elif wiki_title(current): selected[ref] = {'url': current, 'method': 'existing-catalogue-link'}
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    cache = sqlite3.connect(args.cache)
    cache.execute('CREATE TABLE IF NOT EXISTS pages (title TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    cached = {title: json.loads(payload) for title, payload in cache.execute('SELECT title,payload FROM pages')}
    titles = sorted({wiki_title(item['url']) for item in selected.values()})
    wanted = {wiki_title(item['url']) for ref,item in selected.items() if args.only_references is None or ref in args.only_references}
    pending = [title for title in titles if title not in cached and title in wanted and not args.links_only]
    batches = [pending[i:i+20] for i in range(0, len(pending), 20)]
    print(f'{len(selected)} linked notices; {len(titles)} pages; {len(pending)} uncached pages', flush=True)
    failures = []
    # One in-flight request. The batch delay bounds request rate and cache
    # writes happen only in the main thread. Interrupted runs reuse completed batches.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        def fetch(batch):
            time.sleep(1.2)
            return fetch_pages(batch)
        for i, batch in enumerate(batches):
            # A small window prevents thousands of submitted requests on interruption.
            if i % 2: continue
            futures = [(part, executor.submit(fetch, part)) for part in batches[i:i+2]]
            for part, future in futures:
                try:
                    records = future.result(); cached.update(records)
                    cache.executemany('INSERT OR REPLACE INTO pages VALUES (?,?)', [(title, json.dumps(value, ensure_ascii=False)) for title, value in records.items()])
                    cache.commit()
                except Exception as exc:
                    failures.append({'titles': part, 'error': str(exc)})
                    print(f'Batch failed: {exc}', flush=True)
            if i % 20 == 0 or i + 2 >= len(batches): print(f'Pages cached: {len(cached)}/{len(titles)}', flush=True)
    cache.close()
    for ref, item in selected.items():
        page = cached.get(wiki_title(item['url']), {})
        item['page'] = page
    save_json(args.output, selected)
    report = dict(notices=len(monuments), linked=len(selected), new_links=sum(not m['wikipediaUrl'] and m['reference'] in selected for m in monuments),
        linked_notices_with_extract=sum(bool(item['page'].get('extract')) for item in selected.values()),
        uncached_pages=sum(title not in cached for title in titles),
        pages_with_extract=sum(bool(value.get('extract')) for value in cached.values()),
        ambiguous=ambiguous, conflicts=conflicts, failures=failures,
        index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(),
        license='Wikipedia text: CC BY-SA 4.0; Wikidata structured data: CC0')
    save_json(args.output.with_name('wikipedia_report.json'), report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('ambiguous', 'conflicts', 'failures')}, ensure_ascii=False), flush=True)
    if failures: raise SystemExit('Some batches failed; rerun to retry (successful pages are cached).')

if __name__ == '__main__': main()
