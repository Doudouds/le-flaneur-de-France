#!/usr/bin/env python3
"""Capture old ratings or audit every rebuilt rating and its derived projections."""
import argparse
import collections
from contextlib import closing
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from national_scoring import score

ROOT = Path(__file__).resolve().parents[1]
RATING_FIELDS = {'importance', 'notoriety', 'globalScore', 'visualLevel', 'scoreSource', 'scoreEvidence'}
RELIGIOUS = ('église', 'cathédrale', 'chapelle', 'abbaye', 'couvent', 'prieuré', 'basilique', 'temple', 'synagogue', 'mosquée')


def catalogue(path):
    ratings, digest = {}, hashlib.sha256()
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute('SELECT * FROM monuments ORDER BY reference'):
            m = dict(row)
            digest.update(json.dumps({k: v for k, v in m.items() if k not in RATING_FIELDS}, sort_keys=True, ensure_ascii=False).encode())
            ratings[m['reference']] = {k: m[k] for k in ('globalScore', 'visualLevel')}
    return dict(ratings=ratings, unaffected_sha256=digest.hexdigest())


def audit(database, before, snapshot, output):
    baseline = json.loads(before.read_text(encoding='utf-8'))
    current = catalogue(database)
    if set(baseline['ratings']) != set(current['ratings']): raise ValueError('Monuments were added or lost')
    if baseline['unaffected_sha256'] != current['unaffected_sha256']: raise ValueError('Non-rating catalogue content changed')
    signals = json.loads(snapshot.read_text(encoding='utf-8'))
    transitions, before_stars, after_stars = collections.Counter(), collections.Counter(), collections.Counter()
    groups = collections.defaultdict(lambda: dict(total=0, before=collections.Counter(), after=collections.Counter(), unknown=0))
    departments = collections.defaultdict(collections.Counter)
    rows = []
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Corrupt SQLite database')
        for m in db.execute('SELECT * FROM monuments ORDER BY reference'):
            ref = m['reference']
            expected = score({'Typologie_de_la_protection': m['protection']}, signals['records'].get(ref),
                             retrieved=signals['retrieved'], ambiguous=ref in signals['ambiguous'])
            if any(m[k] != v for k, v in expected.items()): raise ValueError('Rating mismatch: ' + ref)
            prev = baseline['ratings'][ref]
            a, b = prev['visualLevel'], m['visualLevel']
            transitions[f'{a}->{b}'] += 1; before_stars[a] += 1; after_stars[b] += 1
            group = 'religieux' if any(word in m['category'].casefold() for word in RELIGIOUS) else 'autres'
            g = groups[group]; g['total'] += 1; g['before'][a] += 1; g['after'][b] += 1; g['unknown'] += m['notoriety'] < 0
            departments[m['department']][b] += 1
            evidence = json.loads(m['scoreEvidence'])
            rows.append(dict(reference=ref, name=m['name'], commune=m['commune'], category=m['category'],
                             before_stars=a, after_stars=b, before_score=prev['globalScore'], after_score=m['globalScore'],
                             wikipedia_languages=evidence['wikipedia_languages'], matching=evidence['matching'], source=evidence['wikidata']))
        if db.execute('SELECT count(*) FROM monuments').fetchone()[0] != db.execute('SELECT count(*) FROM monument_list').fetchone()[0]: raise ValueError('Incomplete list projection')
        if db.execute('SELECT count(*) FROM monuments m JOIN monument_list l USING(id) WHERE m.globalScore!=l.globalScore OR m.visualLevel!=l.visualLevel').fetchone()[0]: raise ValueError('List projection out of sync')
        if db.execute('SELECT count(*) FROM map_cells c JOIN monuments m ON m.id=c.majorId WHERE c.importance!=m.globalScore').fetchone()[0]: raise ValueError('Map projection out of sync')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    report = dict(total=len(rows), before=before_stars, after=after_stars, transitions=transitions,
                  by_category_group=groups, by_department=departments,
                  unaffected_sha256=current['unaffected_sha256'],
                  snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                  unknown=sum(r['wikipedia_languages'] is None for r in rows),
                  zero_languages=sum(r['wikipedia_languages'] == 0 for r in rows),
                  reviewed_scopes=sum(r['matching'] == 'reviewed-monument-scope' for r in rows),
                  three_stars=[r for r in rows if r['after_stars'] == 3])
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('three_stars', 'by_department')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'app/src/main/assets/monuments.db')
    parser.add_argument('--before', type=Path, default=ROOT/'data/scoring_before.tmp')
    parser.add_argument('--snapshot', type=Path, default=ROOT/'data/scoring_enrichment.json')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/scoring-audit.json')
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    if args.capture:
        if args.before.exists(): raise SystemExit('Baseline already exists; choose a new --before path')
        args.before.write_text(json.dumps(catalogue(args.database), ensure_ascii=False), encoding='utf-8')
    else: audit(args.database, args.before, args.snapshot, args.output)
