#!/usr/bin/env python3
"""Compare suspect positions with exact-reference Monumentum search results.

Downloads are sequential, throttled and cached. By default only a comparison is
prepared. With --apply, the local review server saves verified corrections using
its backups and history. The catalogue and Android assets are never modified.
"""
import argparse
import csv
import datetime
from html import unescape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://monumentum.fr'
REFERENCE = re.compile(r'PA[0-9A-Z]{8}', re.I)
NUMBER = r'[-+]?\d+(?:\.\d+)?'
MARKER = re.compile(r'L\.marker\(\[\s*('+NUMBER+r')\s*,\s*('+NUMBER+r')\s*\]\s*,\s*\{\s*title\s*:\s*"((?:[^"\\]|\\.)*)"')


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.meta, self.ids = [], {}, []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
        if tag == 'meta':
            self.meta[a.get('property', a.get('name', ''))] = a.get('content', '')
        if 'data-object-id' in a:
            self.ids.append(a['data-object-id'].upper())


def exact_url(url, ref):
    parts = urlsplit(url)
    return (parts.scheme == 'https' and parts.netloc == 'monumentum.fr'
            and bool(re.fullmatch(r'/monument-historique/'+re.escape(ref.lower())+r'/[^/]+', parts.path.lower()))
            and not parts.query and not parts.fragment)


def markers(html):
    result = []
    for lat, lon, title in MARKER.findall(html):
        lat, lon = float(lat), float(lon)
        if not (math.isfinite(lat+lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Coordonnées invalides sur la page source')
        result.append((lat, lon, unescape(json.loads('"'+title+'"'))))
    return result


def parse_search(html, ref):
    if not REFERENCE.fullmatch(ref):
        raise ValueError('Référence invalide')
    links = sorted({url for url in Page(html).links if exact_url(url, ref)})
    points = {(lat, lon) for lat, lon, title in markers(html)
              if re.search(r' - '+re.escape(ref)+r'$', title, re.I)}
    if len(links) != 1 or len(points) != 1:
        raise ValueError(f'Recherche non univoque pour {ref}: {len(links)} fiches, {len(points)} positions')
    return links[0], next(iter(points))


def parse_detail(html, ref, url, search_point):
    page = Page(html)
    # Matching a name alone is insufficient, especially for neighbouring bridges.
    if ((page.ids and ref not in page.ids) or not exact_url(page.meta.get('og:url', ''), ref)
            or not any(re.fullmatch(r'https://(?:www\.)?pop\.culture\.gouv\.fr/notice/merimee/'+re.escape(ref), link, re.I)
                       for link in page.links)):
        raise ValueError('Identité de la fiche non confirmée')
    points = {(lat, lon) for lat, lon, _ in markers(html)}
    if len(points) != 1:
        raise ValueError('Plusieurs positions sur la fiche')
    point = next(iter(points))
    if any(abs(a-b) > 1e-7 for a, b in zip(point, search_point)):
        raise ValueError('Recherche et fiche détaillée donnent des positions différentes')
    return dict(reference=ref, latitude=point[0], longitude=point[1], url=url,
                title=page.meta.get('og:title', ''), address=page.meta.get('description', ''))


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8*2*math.asin(math.sqrt(min(1, max(0, h))))


class Source:
    def __init__(self, cache, delay=0.7, offline=False):
        self.cache, self.delay, self.last, self.offline = cache, delay, 0, offline
        cache.mkdir(parents=True, exist_ok=True)

    def get(self, url, name):
        path = self.cache/name
        if path.exists():
            return path.read_text(encoding='utf-8')
        if self.offline:
            raise FileNotFoundError('Page absente du cache : '+name)
        time.sleep(max(0, self.last+self.delay-time.monotonic()))
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; FranceDiscoveryCoordinateReview/1.0)'})
        try:
            with urlopen(request, timeout=30) as response:
                if urlsplit(response.url).netloc != 'monumentum.fr':
                    raise ValueError('Redirection externe inattendue')
                html = response.read().decode('utf-8')
        finally:
            self.last = time.monotonic()
        path.write_text(html, encoding='utf-8')
        return html

    def lookup(self, ref):
        search_url = BASE+'/recherche/'+ref.lower()
        search = self.get(search_url, 'search-'+ref+'.html')
        url, point = parse_search(search, ref)
        detail = self.get(url, ref+'.html')
        item = parse_detail(detail, ref, url, point)
        item['search_url'] = search_url
        item['retrieved_at'] = datetime.datetime.fromtimestamp((self.cache/(ref+'.html')).stat().st_mtime,
                                                              datetime.timezone.utc).isoformat()
        return item


def reconcile(rows, reviews, source, output):
    candidates = [row for row in rows if reviews.get(row['reference'], {}).get('decision', 'a_verifier') != 'bon'
                  or reviews.get(row['reference'], {}).get('correction')]
    records = []
    for index, row in enumerate(candidates, 1):
        ref = row['reference']
        review = reviews.get(ref, {})
        original = (float(row['latitude']), float(row['longitude']))
        correction = review.get('correction')
        current = (correction['latitude'], correction['longitude']) if correction else original
        record = dict(reference=ref, nom=row['nom'], commune=row['commune'], departement=row['departement'],
                      decision=review.get('decision', 'a_verifier'), original=original, current=current,
                      had_correction=bool(correction))
        try:
            found = source.lookup(ref)
            record.update(source=found, distance_original_m=round(distance_m(original, (found['latitude'], found['longitude'])), 2),
                          distance_current_m=round(distance_m(current, (found['latitude'], found['longitude'])), 2), status='matched')
        except Exception as error:
            record.update(status='unresolved', error=str(error))
        records.append(record)
        output.write_text(json.dumps({'version': 1, 'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
        if index % 10 == 0 or index == len(candidates) or record['status'] != 'matched':
            print(f'{index}/{len(candidates)}: {ref} {record["status"]}', flush=True)
    return records


def proposed_change(record, tolerance=50):
    """Keep small manual differences and flag ambiguous multi-part monuments."""
    result = dict(record)
    result['final'] = list(record['current'])
    result['needs_review'] = False
    if record['status'] != 'matched':
        result.update(action='source_non_resolue', needs_review=True, reason=record['error'])
        return result
    found = record['source']
    target = [found['latitude'], found['longitude']]
    if record['distance_current_m'] <= tolerance:
        result.update(action='correction_manuelle_conservee' if record['had_correction'] else 'position_initiale_conservee',
                      reason=f'Écart inférieur ou égal à {tolerance} m : déplacement non nécessaire.')
    elif record['had_correction'] and re.search(r'aqueduc|tronçon|troncon|voies? romaines?|canal|remparts?', record['nom'], re.I):
        result.update(action='correction_manuelle_a_confirmer', needs_review=True,
                      reason='Ouvrage étendu ou à plusieurs tronçons : un autre point représentatif ne prouve pas une erreur. Correction conservée.')
    else:
        result.update(final=target, action='correction_manuelle_ajustee' if record['had_correction'] else 'nouvelle_correction',
                      reason='Alignement sur le point de la fiche Monumentum, référence et recherche concordantes.')
    result['movement_m'] = round(distance_m(record['current'], result['final']), 2)
    return result


def report_matrix(records):
    headers = ['reference', 'monument', 'commune', 'departement', 'action',
               'latitude_origine', 'longitude_origine', 'latitude_avant', 'longitude_avant',
               'latitude_corrigee', 'longitude_corrigee', 'latitude_monumentum', 'longitude_monumentum',
               'ecart_avant_monumentum_m', 'deplacement_applique_m', 'a_confirmer', 'motif', 'source', 'date_source']
    rows = []
    for item in records:
        source = item.get('source', {})
        rows.append([item['reference'], item['nom'], item['commune'], item['departement'], item['action'],
                     *item['original'], *item['current'], *item['final'],
                     source.get('latitude'), source.get('longitude'), item.get('distance_current_m'),
                     item.get('movement_m', 0), item['needs_review'], item['reason'], source.get('url', ''), source.get('retrieved_at', '')])
    return [headers]+rows


def write_reports(records, folder):
    corrected = [item for item in records if distance_m(item['original'], item['final']) > 0.01]
    for name, selected in [('positions-corrigees-monumentum', corrected), ('verification-monumentum', records)]:
        with (folder/(name+'.csv')).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle, delimiter=';', quoting=csv.QUOTE_ALL)
            for row in report_matrix(selected):
                # Text is literal; signed numeric coordinates remain numeric.
                writer.writerow([("'"+value if value.startswith(('=', '+', '-', '@')) else value) if isinstance(value, str)
                                 else ('oui' if value else 'non') if isinstance(value, bool)
                                 else value for value in row])


def apply_plan(records, expected_reviews, base='http://127.0.0.1:8765'):
    """Use the running review server so its lock, backups and history apply.

    Refuse a stale plan instead of overwriting changes made during the lookup.
    Decisions and personal notes are deliberately omitted from PUT requests.
    """
    parts = urlsplit(base)
    if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or parts.path or parts.query or parts.fragment:
        raise ValueError('Le serveur de correction doit être local sur 127.0.0.1')

    def request(route, payload=None, token=None):
        headers = {}
        if payload is not None:
            headers = {'Content-Type':'application/json', 'Origin':base, 'X-Review-Token':token}
        req = Request(base+route, data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                      method='PUT' if payload is not None else 'GET', headers=headers)
        with urlopen(req, timeout=15) as response:
            return json.load(response)

    live = request('/api/data')
    if live['reviews'] != expected_reviews:
        raise ValueError('Les décisions ont changé depuis le début du contrôle. Refaire le comparatif avant application.')
    known = {row['reference']: row for row in live['monuments']}
    seen = set()
    # Validate the entire batch before the first mutation.
    for item in records:
        ref = item['reference']
        if ref in seen or ref not in known:
            raise ValueError('Référence inconnue ou répétée dans le plan')
        seen.add(ref)
        if list(item['original']) != [known[ref]['latitude'], known[ref]['longitude']]:
            raise ValueError('Le catalogue a changé depuis le contrôle')
        if item['action'] in ('nouvelle_correction', 'correction_manuelle_ajustee'):
            source = item['source']
            if (item['status'] != 'matched' or item['needs_review'] or not exact_url(source['url'], ref)
                    or item['final'] != [source['latitude'], source['longitude']]
                    or not all(type(n) in (float, int) and math.isfinite(n) and -limit <= n <= limit
                               for n, limit in zip(item['final'], (90, 180)))):
                raise ValueError('Correction non vérifiée dans le plan')
    applied = []
    for item in records:
        if item['action'] not in ('nouvelle_correction', 'correction_manuelle_ajustee'):
            continue
        ref = item['reference']
        before = expected_reviews.get(ref, {})
        result = request('/api/corrections/'+ref, {'correction':dict(zip(('latitude','longitude'),item['final']))}, live['token'])
        if result['decision'] != before.get('decision', 'a_verifier') or result['note'] != before.get('note', ''):
            raise ValueError('Décision ou commentaire modifié de façon inattendue')
        history = before.get('history', [])
        if result['history'][:len(history)] != history:
            raise ValueError('Historique modifié de façon inattendue')
        applied.append(ref)
    return applied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviews', type=Path, default=ROOT/'data/coordinate_reviews.json')
    parser.add_argument('--audit', type=Path, default=ROOT/'docs/coordinate-audit.csv')
    parser.add_argument('--cache', type=Path, default=ROOT/'data/monumentum_cache')
    parser.add_argument('--output', type=Path, default=ROOT/'data/monumentum_reconciliation/comparison.json')
    parser.add_argument('--offline', action='store_true', help='Utiliser uniquement les pages déjà mises en cache')
    parser.add_argument('--apply', action='store_true', help='Appliquer les corrections vérifiées à la carte PC démarrée')
    args = parser.parse_args()
    with args.audit.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    reviews = json.loads(args.reviews.read_text(encoding='utf-8-sig'))['reviews']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = reconcile(rows, reviews, Source(args.cache, offline=args.offline), args.output)
    proposed = [proposed_change(record) for record in records]
    args.output.with_name('plan.json').write_text(json.dumps({'version': 1, 'tolerance_m': 50, 'records': proposed},
                                                           ensure_ascii=False, indent=2), encoding='utf-8')
    changed = [record for record in proposed if distance_m(record['original'], record['final']) > 0.01]
    args.output.with_name('report-matrices.json').write_text(json.dumps({
        'positions-corrigees-monumentum': report_matrix(changed),
        'verification-monumentum': report_matrix(proposed)}, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.apply:
        applied = apply_plan(proposed, reviews)
        args.output.with_name('applied.json').write_text(json.dumps({'references':applied}, indent=2), encoding='utf-8')
        print(f'{len(applied)} corrections appliquées à la carte PC.', flush=True)
    write_reports(proposed, args.output.parent)


if __name__ == '__main__':
    main()
