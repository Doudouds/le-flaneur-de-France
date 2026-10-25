#!/usr/bin/env python3
"""Audit every catalogue position against official polygons; never change a notice.

Python stdlib only. Three national downloads, cached for subsequent offline runs.
Distances are to administrative boundaries, not to town centres. A warning is a
review candidate, not proof of an incorrect monument position.
"""
import argparse
import collections
from contextlib import closing
import csv
import datetime
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.request import Request, urlopen
from build_monuments_db import distance, normalize

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://object.data.gouv.fr/contours-administratifs/2025/geojson/'
KINDS = ('communes', 'communes-associees-deleguees', 'departements')
RADIUS = 6371.0088


def ring_status(point, ring):
    """Return inside=1, boundary=0, outside=-1, unwrapping date-line rings."""
    lat, lon = point
    vertices = []
    for x, y, *_ in ring:
        x = (x-lon+180) % 360-180
        if vertices:
            x += 360*round((vertices[-1][0]-x)/360)
        vertices.append((x, y-lat))
    inside = False
    for i, (x, y) in enumerate(vertices):
        a, b = vertices[i-1]
        if abs(a*y-x*b) < 1e-12 and min(a, x) <= 0 <= max(a, x) and min(b, y) <= 0 <= max(b, y):
            return 0
        if (y > 0) != (b > 0) and 0 < (a-x)*(-y)/(b-y)+x:
            inside = not inside
    return 1 if inside else -1


def polygons(geometry):
    if geometry['type'] == 'Polygon':
        return [geometry['coordinates']]
    if geometry['type'] == 'MultiPolygon':
        return geometry['coordinates']
    raise ValueError('Expected Polygon/MultiPolygon')


def contains(point, geometry):
    for polygon in polygons(geometry):
        outer = ring_status(point, polygon[0])
        if outer == 0:
            return True
        if outer > 0:
            holes = [ring_status(point, ring) for ring in polygon[1:]]
            if 0 in holes or not any(status > 0 for status in holes):
                return True
    return False


def bearing(a, b):
    p, q = map(math.radians, (a[0], b[0]))
    d = math.radians(b[1]-a[1])
    return math.atan2(math.sin(d)*math.cos(q), math.cos(p)*math.sin(q)-math.sin(p)*math.cos(q)*math.cos(d))


def segment_distance(point, a, b):
    """Great-circle distance to the minor arc a-b, in kilometres."""
    length = distance(*a, *b)/RADIUS
    start = distance(*a, *point)/RADIUS
    if length < 1e-12:
        return start*RADIUS
    angle = bearing(a, point)-bearing(a, b)
    along = math.atan2(math.sin(start)*math.cos(angle), math.cos(start))
    if along < 0 or along > length:
        return min(start*RADIUS, distance(*point, *b))
    return abs(math.asin(max(-1, min(1, math.sin(start)*math.sin(angle)))))*RADIUS


def geometry_distance(point, geometry):
    if contains(point, geometry):
        return 0.0
    return min(segment_distance(point, (ring[i-1][1], ring[i-1][0]), (p[1], p[0]))
               for polygon in polygons(geometry) for ring in polygon for i, p in enumerate(ring))


def read_reference(cache, kind, offline=False):
    path = cache/(kind+'-100m.geojson.gz')
    url = BASE+path.name
    if not path.exists():
        if offline:
            raise FileNotFoundError('Reference missing in offline mode: '+str(path))
        with urlopen(Request(url, headers={'User-Agent': 'LeFlaneurDeFrance/coordinate-audit'}), timeout=60) as response:
            raw = response.read()
        data = json.loads(gzip.decompress(raw))
        if data.get('type') != 'FeatureCollection' or not data.get('features'):
            raise ValueError('Invalid reference: '+url)
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    raw = path.read_bytes()
    data = json.loads(gzip.decompress(raw))
    return data['features'], dict(url=url, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), features=len(data['features']))


def commune_name(value):
    value = re.sub(r'^(.*?)\s*\((Le|La|Les|L\')\)$', r'\2 \1', value, flags=re.I)
    return normalize(value)


def department_codes(value):
    codes = set(re.split(r'[;,/|\s]+', value))
    # Old Mérimée notices retain Guadeloupe's code for Saint-Barthélemy and
    # Saint-Martin, which became separate collectivities in 2007.
    if '971' in codes:
        codes.update(('977', '978'))
    return codes


def match_communes(monument, by_code, by_name):
    codes = re.findall(r'(?<![A-Z0-9])(?:\d{5}|2[AB]\d{3})(?![A-Z0-9])', monument['insee'].upper())
    found = {code: by_code[code] for code in codes if code in by_code}
    unresolved = sorted(set(codes)-set(found))
    if found:
        return list(found.values()), 'code_insee', unresolved
    # Never match a homonymous town in a different department.
    departments = department_codes(monument['department'])
    found = {feature['properties']['code']: feature for name in monument['commune'].split(';')
             for dep in departments for feature in by_name.get((dep, commune_name(name)), [])}
    return list(found.values()), 'nom_et_departement' if found else 'non_apparie', unresolved


def inspect(monument, communes, departments, method, unresolved):
    row = dict(reference=monument['reference'], nom=monument['name'], commune=monument['commune'],
               insee=monument['insee'], departement=monument['department'], latitude=monument['latitude'],
               longitude=monument['longitude'], statut_catalogue=monument['coordinateStatus'],
               appariement_commune=method, codes_controles=';'.join(f['properties']['code'] for f in communes),
               communes_reference=';'.join(f['properties']['nom']+' ('+f['properties'].get('departement', '?')+')' for f in communes),
               codes_non_apparies=';'.join(unresolved), ecart_commune_km=None, ecart_departement_km=None,
               priorite='', motif='', suggestion_a_verifier='', fiche_pop=monument['popUrl'])
    row['avertissement'] = 'implantation_maritime_possible' if re.search(r'\b(phare|amer|balise|feu)\b', normalize(monument['name'])) else ''
    point = (row['latitude'], row['longitude'])
    if None in point:
        row.update(priorite='deja_ecarte' if monument['coordinateStatus'] != 'missing' else 'sans_position',
                   motif=monument['coordinateStatus'])
        return row
    if not all(math.isfinite(v) for v in point) or not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
        row.update(priorite='haute', motif='coordonnees_invalides_actives')
        return row
    dc = min((geometry_distance(point, f['geometry']) for f in communes), default=None)
    declared = department_codes(monument['department'])
    expected = [departments[code] for code in declared if code in departments]
    departments_complete = bool(expected) and declared.issubset(departments)
    commune_departments = {f['properties'].get('departement') for f in communes}
    inside_matching_commune = dc == 0 and any(f['properties'].get('departement') in declared and contains(point, f['geometry']) for f in communes)
    dd = 0.0 if inside_matching_commune else min((geometry_distance(point, f['geometry']) for f in expected), default=None)
    row.update(ecart_commune_km=round(dc, 3) if dc is not None else None,
               ecart_departement_km=round(dd, 3) if dd is not None else None)
    # Tolerate 1 km around commune boundaries / 2 km around department boundaries:
    # these are simplified 100 m contours and some monuments straddle borders.
    if communes and commune_departments.isdisjoint(declared) and method == 'code_insee':
        row.update(priorite='haute', motif='code_insee_et_departement_incoherents')
    elif dd is not None and dd > 2 and departments_complete:
        row.update(priorite='haute', motif='hors_departement_declare')
    elif not communes or unresolved:
        row.update(priorite='couverture_a_verifier', motif='referentiel_incomplet')
    elif dc is not None and dc > 10:
        row.update(priorite='haute', motif='plus_de_10km_de_la_commune')
    elif dc is not None and dc > 1:
        row.update(priorite='moderee', motif='hors_commune_plus_de_1km')
    elif not departments_complete:
        row.update(priorite='couverture_a_verifier', motif='referentiel_incomplet')
    elif dc > 0:
        row.update(priorite='limite', motif='moins_de_1km_de_la_limite')
    else:
        row.update(priorite='aucun_signal', motif='dans_la_commune')
    if row['priorite'] in ('haute', 'moderee') and communes:
        for label, candidate in [('axes_inverses', point[::-1]), ('signe_longitude', (point[0], -point[1])),
                                 ('signe_latitude', (-point[0], point[1])), ('deux_signes', (-point[0], -point[1]))]:
            if -90 <= candidate[0] <= 90 and any(contains(candidate, f['geometry']) for f in communes):
                row['suggestion_a_verifier'] = label
                break
    return row


def write_markdown(output, summary, rows):
    counts = summary['priorities']
    candidates = [r for r in rows if r['priorite'] in ('haute', 'moderee')]
    maritime = sum(bool(r['avertissement']) for r in candidates)
    total_label = f"{summary['total']:,}".replace(',', ' ')
    lines = ['# Audit automatique des positions', '',
             f"Catalogue : **{total_label} notices**. Contrôle local avec les contours officiels 2025, simplifiés à 100 m.", '',
             f"**{len(candidates)} alertes à examiner : {counts.get('haute', 0)} de priorité haute et {counts.get('moderee', 0)} modérées.**", '',
             f"- [Liste des alertes]({output.name}.csv) : références POP, coordonnées, motif, communes de référence, distances et avertissements.",
             f"- [Cas secondaires]({output.name}-review.csv) : {counts.get('deja_ecarte', 0)} positions déjà écartées, {counts.get('couverture_a_verifier', 0)} appariements incomplets et {counts.get('limite', 0)} points proches des limites.",
             f"- [Résultats et empreintes des sources]({output.name}.json).", '',
             '## Interprétation', '',
             '- Une priorité haute signale un point à plus de 2 km du département déclaré, à plus de 10 km de toutes les communes appariées, ou une contradiction entre code INSEE et département.',
             '- Une priorité modérée signale un point à plus de 1 km de toutes les communes appariées.',
             '- Les distances sont mesurées aux **contours**, et non aux centres des communes. Les frontières sont des segments de grand cercle sur une sphère terrestre moyenne.',
             '- Les codes INSEE multiples, arrondissements municipaux et communes associées/déléguées sont pris en compte. Un code manquant est signalé comme un défaut de couverture ; seul un contrôle indépendant suffisamment complet peut produire une alerte.',
             '- L’ancien rattachement de Saint-Martin et Saint-Barthélemy au code 971 est accepté, comme dans le catalogue.',
             f"- {maritime} alertes portent un avertissement d’implantation maritime possible (phare, feu, amer ou balise). Leur position en mer peut être légitime.",
             '- Ces alertes ne sont pas des erreurs confirmées : ponts, ouvrages côtiers, références administratives anciennes et contours simplifiés peuvent expliquer certains écarts.',
             f"- {counts.get('aucun_signal', 0)} positions ne déclenchent aucun signal et {counts.get('sans_position', 0)} notices n’ont pas de coordonnées. Cela ne certifie pas l’emplacement exact du bâtiment : une erreur à l’intérieur de la bonne commune reste possible.",
             '- Aucune notice, coordonnée ou base de l’application n’est modifiée.', '',
             '## Premières alertes, par priorité puis écart décroissant', '',
             '| Référence | Monument | Commune déclarée | Motif | Écart commune (km) | Écart département (km) |',
             '|---|---|---|---|---:|---:|']
    for row in candidates[:20]:
        def cell(value):
            return html.escape(str(value) if value is not None else 'non déterminé').replace('|', '\\|').replace('\n', ' ')
        lines.append('| '+f"[{row['reference']}]({row['fiche_pop']})"+' | '+' | '.join(cell(row[k]) for k in ('nom', 'commune', 'motif', 'ecart_commune_km', 'ecart_departement_km'))+' |')
    lines += ['', '## Reproduire', '', '```powershell', 'python tools/audit_coordinates.py',
              '# Réutiliser les trois fichiers téléchargés, sans aucun appel réseau :',
              'python tools/audit_coordinates.py --offline',
              'python -m unittest discover -s tools -p "test_*.py"', '```', '',
              'Trois téléchargements nationaux au premier lancement, aucun appel par monument. Le cache est dans `data/geo_audit_cache/` (ignoré par Git). Python 3.11+ suffit, sans dépendance externe.', '',
              'Source : [Contours administratifs officiels](https://www.data.gouv.fr/datasets/contours-administratifs/), distribués sous Licence Ouverte. Les URL et SHA-256 des trois fichiers utilisés figurent dans le JSON.', '']
    output.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')


def audit(database, cache, output, offline=False):
    by_code, by_name, departments, provenance = {}, collections.defaultdict(list), {}, {}
    for kind in KINDS:
        features, provenance[kind] = read_reference(cache, kind, offline)
        for f in features:
            props = f['properties']
            if not f.get('geometry'):
                continue
            if kind == 'departements':
                departments[props['code']] = f
            else:
                by_code.setdefault(props['code'], f)
                by_name[(props.get('departement', ''), commune_name(props['nom']))].append(f)
    rows = []
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
        db.row_factory = sqlite3.Row
        for m in db.execute('SELECT reference,name,commune,insee,department,latitude,longitude,coordinateStatus,popUrl FROM monuments ORDER BY reference'):
            communes, method, unresolved = match_communes(m, by_code, by_name)
            rows.append(inspect(m, communes, departments, method, unresolved))
        # Preserve evidence even for positions already excluded from the app.
        raw_by_ref = {s['reference']: json.loads(s['raw']).get('coordonnees_au_format_WGS84', '')
                      for s in db.execute("SELECT reference,raw FROM source_rows WHERE issue IN ('suspect_precision','suspect_territory','invalid')")}
    for row in rows:
        row['coordonnees_source_ecartees'] = raw_by_ref.get(row['reference'], '') if row['priorite'] == 'deja_ecarte' else ''
    rank = {'haute': 0, 'moderee': 1, 'deja_ecarte': 2, 'couverture_a_verifier': 3, 'limite': 4, 'aucun_signal': 5, 'sans_position': 6}
    rows.sort(key=lambda r: (rank[r['priorite']], -max(r['ecart_commune_km'] or 0, r['ecart_departement_km'] or 0), r['reference']))
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix, subset in [('.csv', [r for r in rows if r['priorite'] in ('haute', 'moderee')]),
                           ('-review.csv', [r for r in rows if r['priorite'] in ('deja_ecarte', 'couverture_a_verifier', 'limite')])]:
        with output.with_name(output.name+suffix).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=';')
            writer.writeheader(); writer.writerows(subset)
    with database.open('rb') as handle:
        database_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
    summary = dict(total=len(rows), priorities=dict(collections.Counter(r['priorite'] for r in rows)),
                   reasons=dict(collections.Counter(r['motif'] for r in rows)),
                   coverage=dict(matched_communes=sum(bool(r['codes_controles']) for r in rows),
                                 complete_active_positions=sum(r['latitude'] is not None and r['appariement_commune'] != 'non_apparie' and not r['codes_non_apparies'] for r in rows)),
                   database_sha256=database_hash,
                   references=provenance, checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   tolerance_km=dict(commune=1, department=2, severe_commune=10),
                   known_case=next((r for r in rows if r['reference'] == 'PA00114985'), None), top_20=rows[:20])
    output.with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    write_markdown(output, summary, rows)
    print(json.dumps({k: summary[k] for k in ('total', 'priorities', 'coverage', 'known_case')}, ensure_ascii=True, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'app/src/main/assets/monuments.db')
    parser.add_argument('--cache', type=Path, default=ROOT/'data/geo_audit_cache')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/coordinate-audit')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    audit(args.database, args.cache, args.output, args.offline)
