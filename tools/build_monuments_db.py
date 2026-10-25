#!/usr/bin/env python3
"""Build the local catalogue from the inspected Ministry CSV; Python stdlib only."""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, math, os, re, sqlite3, time, unicodedata
from pathlib import Path
from national_scoring import score, VERSION, THRESHOLDS
from monument_descriptions import pop_summary, enrich_description

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    'reference': 'Reference', 'name': 'Titre_editorial_de_la_notice',
    'alternativeName': 'Autre_appellation_de_l_edifice',
    'address': 'Adresse_forme_editoriale', 'commune': 'Commune_forme_editoriale',
    'insee': 'COG_Insee_lors_de_la_protection', 'department': 'Departement_format_numerique',
    'departmentName': 'Departement_en_lettres', 'region': 'Region',
    'protection': 'Typologie_de_la_protection', 'protectionDates': 'Date_et_typologie_de_la_protection',
    'protectionDetails': 'Precision_de_la_protection', 'category': 'Denomination_de_l_edifice',
    'description': 'Description_de_l_edifice', 'history': 'Historique',
    'period': 'Siecle_de_la_campagne_principale_de_construction', 'copyright': 'Copyright',
}
TEXT_EXTRA = ['shortDescription', 'descriptionSource', 'historySource', 'popUrl', 'wikipediaUrl',
              'imageUrl', 'imagePageUrl', 'imageAuthor', 'imageLicense', 'imageLicenseUrl',
              'scoreSource', 'scoreEvidence', 'coordinateStatus', 'searchName', 'searchText']
INTS = ['importance', 'notoriety', 'globalScore', 'visualLevel']
REQUIRED = {'Reference', 'Titre_editorial_de_la_notice', 'coordonnees_au_format_WGS84',
            'Departement_format_numerique', 'Commune_forme_editoriale'}

def normalize(text):
    text = text.casefold().replace('œ','oe').replace('æ','ae')
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()

def fts_query(text):
    return ' '.join(w+'*' for w in normalize(text).split()[:12])

def distance(a, b, c, d):
    p, q = math.radians(a), math.radians(c)
    v = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(d-b)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1,max(0,v))))

# Broad territorial envelopes: an anomaly is quarantined, never silently swapped.
TERRITORIES = {
    '971': (15.7,18.2,-63.3,-60.9), '972': (14.3,15,-61.3,-60.7),
    '973': (2,6,-55,-51), '974': (-21.5,-20.7,55,56), '976': (-13.1,-12.5,44.9,45.4),
    '975': (46.7,47.2,-56.6,-55.8), '977': (17.8,18,-63,-62.7),
    '978': (17.9,18.2,-63.3,-62.9), '986': (-14.5,-13,-179,-175),
    '987': (-28,-7,-155,-134), '988': (-23,-18,163,169),
}
def coordinates(value, department=''):
    if not value.strip(): return None, None, 'missing'
    try:
        lat, lon = map(float, value.split(','))
        if not math.isfinite(lat+lon) or not (-90<=lat<=90 and -180<=lon<=180) or (lat,lon)==(0,0):
            return None, None, 'invalid'
    except (ValueError, TypeError): return None, None, 'invalid'
    box = TERRITORIES.get(department)
    if box is None and (re.fullmatch(r'\d{2}|2[AB]', department) or department in ('2A','2B')):
        box = (41,51.6,-5.5,10)
    if box and not (box[0]<=lat<=box[1] and box[2]<=lon<=box[3]):
        return None, None, 'suspect_territory'
    # Some source rows truncate both axes to whole degrees (including floating
    # point artefacts such as 3.0000000000000004). They cannot locate a building.
    if all(abs(v-round(v))<1e-9 for v in (lat,lon)):
        return None, None, 'suspect_precision'
    return lat, lon, 'valid'

def schema(db):
    columns=['id INTEGER NOT NULL PRIMARY KEY','latitude REAL','longitude REAL']
    columns += [f'{k} TEXT NOT NULL' for k in list(FIELDS)+TEXT_EXTRA]
    columns += [f'{k} INTEGER NOT NULL' for k in INTS]
    db.execute('CREATE TABLE monuments ('+','.join(columns)+')')
    for name, cols, unique in [('reference','reference',True),('name','searchName',False),
                              ('commune','commune',False),('department','department',False),
                              ('coordinates','latitude,longitude,id,globalScore,visualLevel',False)]:
        db.execute(f'CREATE {"UNIQUE " if unique else ""}INDEX index_monuments_{name} ON monuments({cols})')
    db.execute('CREATE VIRTUAL TABLE monument_fts USING fts4(searchName,searchText,tokenize=unicode61)')
    db.execute('CREATE TABLE monument_list (id INTEGER PRIMARY KEY, name TEXT NOT NULL, commune TEXT NOT NULL, department TEXT NOT NULL, visualLevel INTEGER NOT NULL,globalScore INTEGER NOT NULL,searchName TEXT NOT NULL)')
    db.execute('CREATE INDEX index_monument_list_name ON monument_list(searchName,id)')
    db.execute('CREATE TABLE map_cells (level INTEGER NOT NULL,x INTEGER NOT NULL,y INTEGER NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,count INTEGER NOT NULL,majorId INTEGER NOT NULL,importance INTEGER NOT NULL,PRIMARY KEY(level,x,y)) WITHOUT ROWID')
    db.execute('CREATE TABLE source_rows (line INTEGER PRIMARY KEY, reference TEXT, raw TEXT NOT NULL, issue TEXT NOT NULL)')
    db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute('PRAGMA user_version=1')

def tile(lat,lon,z):
    n=2**z; r=math.radians(max(-85.05112878,min(85.05112878,lat)))
    return min(n-1,int((lon+180)/360*n)), min(n-1,int((1-math.asinh(math.tan(r))/math.pi)/2*n))

def _build(source, output, enrichment, db, wikipedia=None, scoring=None):
    start=time.perf_counter(); output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp'); schema(db)
    old=json.loads(enrichment.read_text(encoding='utf-8')) if enrichment and enrichment.exists() else {}
    wiki_enrichment=json.loads(wikipedia.read_text(encoding='utf-8')) if wikipedia and wikipedia.exists() else {}
    snapshot=json.loads(scoring.read_text(encoding='utf-8')) if scoring else {}
    if snapshot and snapshot.get('version') != 1: raise ValueError('Unsupported scoring snapshot')
    signals=snapshot.get('records',{})
    def rate(row, ref):
        return score(row,signals.get(ref),retrieved=snapshot.get('retrieved',''),ambiguous=ref in snapshot.get('ambiguous',{}))
    summaries={}
    with source.open('rb') as source_handle: source_hash=hashlib.file_digest(source_handle,'sha256').hexdigest()
    report={'source':str(source.resolve()),'source_sha256':source_hash,
            'rows':0,'duplicates_merged':0,'malformed_rows':0,'coordinate_status':collections.Counter(),
            'missing_fields':collections.Counter(),'conflicts':[]}
    with source.open(encoding='utf-8-sig',newline='') as handle:
        sample=handle.read(32768); handle.seek(0)
        dialect=csv.Sniffer().sniff(sample,delimiters='|;,\t')
        reader=csv.DictReader(handle,dialect=dialect,strict=True)
        if not REQUIRED.issubset(reader.fieldnames or []): raise ValueError('Required columns missing: '+str(REQUIRED-set(reader.fieldnames or [])))
        if len(set(reader.fieldnames)) != len(reader.fieldnames): raise ValueError('Duplicate column names require an explicit mapping')
        report['columns']=reader.fieldnames; report['delimiter']=dialect.delimiter
        for row in reader:
            report['rows']+=1; line=reader.line_num; ref=(row.get('Reference') or '').strip().upper()
            malformed=None in row or any(v is None for v in row.values()) or not re.fullmatch(r'PA[0-9AB]{8}',ref)
            if malformed:
                report['malformed_rows']+=1
                db.execute('INSERT INTO source_rows VALUES (?,?,?,?)',(line,ref,json.dumps(row,ensure_ascii=False),'malformed'))
                continue
            for k,v in row.items():
                if not v.strip(): report['missing_fields'][k]+=1
            m={k:row.get(v,'').strip() for k,v in FIELDS.items()}
            m.update({k:'' for k in TEXT_EXTRA}); m['reference']=ref
            m['name']=m['name'] or ref
            m['address']=m['address'] or row.get('Adresse_forme_index','')
            lat,lon,status=coordinates(row['coordonnees_au_format_WGS84'],m['department'])
            report['coordinate_status'][status]+=1
            m.update(id=int(hashlib.sha256(ref.encode()).hexdigest()[:12],16),latitude=lat,longitude=lon,coordinateStatus=status)
            m['popUrl']='https://pop.culture.gouv.fr/notice/merimee/'+ref
            wiki=re.search(r'https://(?:[a-z]+\.)?wikipedia\.org/wiki/[^\s<>";]+',row.get('Liens_externes',''))
            if wiki: m['wikipediaUrl']=wiki.group(0)
            m['descriptionSource']='POP / Mérimée' if m['description'] else ''
            m['historySource']='POP / Mérimée' if m['history'] else ''
            legacy=old.get(ref,{})
            for key in ('description','descriptionSource','wikipediaUrl','imageUrl','imagePageUrl','imageAuthor','imageLicense','imageLicenseUrl'):
                if legacy.get(key) and (key!='description' or not m['description']): m[key]=legacy[key]
            # An existing local POP description always keeps its own attribution.
            if row.get('Description_de_l_edifice','').strip(): m['descriptionSource']='POP / Mérimée'
            if not m['history'] and legacy.get('popHistoricalDescription'):
                m['history']=legacy['popHistoricalDescription']; m['historySource']='POP / Mérimée — Flâneur'
            if not (m['imageLicense'] and m['imagePageUrl']): m['imageUrl']=''
            m['shortDescription']=(m['description'] or m['history'])[:240]
            m.update(rate(row,ref))
            m['searchName']=normalize(m['name'])
            m['searchText']=normalize(' '.join(m[k] for k in ('name','alternativeName','commune','department','departmentName','region','reference')))
            prev=db.execute('SELECT * FROM monuments WHERE reference=?',(ref,)).fetchone()
            issue='' if status=='valid' else status
            if prev:
                report['duplicates_merged']+=1
                columns=[d[0] for d in db.execute('SELECT * FROM monuments LIMIT 0').description]
                previous=dict(zip(columns,prev))
                for key in FIELDS:
                    if m[key] and previous[key] and m[key]!=previous[key]:
                        report['conflicts'].append({'reference':ref,'field':key,'line':line})
                    if key in ('protection','protectionDates','protectionDetails'):
                        previous[key]=' ; '.join(dict.fromkeys(filter(None,[previous[key],m[key]])))
                    elif not previous[key]:
                        previous[key]=m[key]
                        if key in ('description','history'):
                            previous[key+'Source']=m[key+'Source']
                if previous['latitude'] is None and lat is not None:
                    previous.update(latitude=lat,longitude=lon,coordinateStatus=status)
                elif lat is not None and previous['latitude'] is not None and distance(lat,lon,previous['latitude'],previous['longitude'])>.15:
                    previous.update(latitude=None,longitude=None,coordinateStatus='conflicting_duplicate')
                    issue='conflicting_duplicate'
                # Never restore a quarantined conflicting pair on a third row.
                if prev[columns.index('coordinateStatus')]=='conflicting_duplicate':
                    previous.update(latitude=None,longitude=None,coordinateStatus='conflicting_duplicate')
                m=previous
                merged_row=dict(row)
                for key,column in FIELDS.items(): merged_row[column]=m[key]
                m.update(rate(merged_row,ref))
                m['searchName']=normalize(m['name'])
                m['searchText']=normalize(' '.join(m[k] for k in ('name','alternativeName','commune','department','departmentName','region','reference')))
            summaries[ref]=pop_summary(m,row)
            db.execute('INSERT OR REPLACE INTO monuments ('+','.join(m)+') VALUES ('+','.join('?' for _ in m)+')',list(m.values()))
            if issue or prev:
                db.execute('INSERT INTO source_rows VALUES (?,?,?,?)',(line,ref,json.dumps(row,ensure_ascii=False),issue or 'duplicate'))
        db.commit()
    columns=[d[0] for d in db.execute('SELECT * FROM monuments LIMIT 0').description]
    for values in db.execute('SELECT * FROM monuments').fetchall():
        m=dict(zip(columns,values))
        enrich_description(m,wiki_enrichment.get(m['reference'],{}),summaries[m['reference']])
        db.execute('UPDATE monuments SET description=?,descriptionSource=?,shortDescription=?,wikipediaUrl=? WHERE id=?',
                   (m['description'],m['descriptionSource'],m['shortDescription'],m['wikipediaUrl'],m['id']))
    # Absolute, versioned thresholds: adding monuments cannot change existing stars.
    scores=[r[0] for r in db.execute('SELECT globalScore FROM monuments ORDER BY globalScore')]
    if not scores: raise ValueError('No valid monuments imported')
    thresholds=list(THRESHOLDS)
    db.execute('INSERT INTO monument_list SELECT id,name,commune,department,visualLevel,globalScore,searchName FROM monuments')
    db.execute('INSERT INTO monument_fts(docid,searchName,searchText) SELECT id,searchName,searchText FROM monuments')
    db.execute("INSERT INTO monument_fts(monument_fts) VALUES('optimize')")
    # At most ~16x16 cells per screen at its matching pyramid level, independent of density.
    for level in range(3,19):
        cells={}
        for ident,lat,lon,importance in db.execute('SELECT id,latitude,longitude,globalScore FROM monuments WHERE latitude IS NOT NULL'):
            key=tile(lat,lon,level)
            cell=cells.setdefault(key,[0.,0.,0,ident,importance])
            cell[0]+=lat; cell[1]+=lon; cell[2]+=1
            if importance>cell[4]: cell[3:]=[ident,importance]
        db.executemany('INSERT INTO map_cells VALUES (?,?,?,?,?,?,?,?)',
                       ((level,x,y,v[0]/v[2],v[1]/v[2],v[2],v[3],v[4]) for (x,y),v in cells.items()))
    report.update(unique_monuments=len(scores),visual_thresholds=thresholds,
        scoring_version=VERSION,
        scoring_snapshot_sha256=hashlib.sha256(scoring.read_bytes()).hexdigest() if scoring else None,
        scoring_retrieved=snapshot.get('retrieved'),
        rating_distribution=dict(db.execute('SELECT visualLevel,count(*) FROM monuments GROUP BY visualLevel')),
        measured_visibility=db.execute('SELECT count(*) FROM monuments WHERE notoriety>=0').fetchone()[0],
        provisional_ratings=db.execute('SELECT count(*) FROM monuments WHERE notoriety<0').fetchone()[0],
        unresolved_scoring_matches=db.execute('SELECT count(*) FROM monuments WHERE scoreEvidence LIKE ?',('%"matching": "ambiguous"%',)).fetchone()[0],
        reviewed_scoring_scopes=db.execute('SELECT count(*) FROM monuments WHERE scoreEvidence LIKE ?',('%"matching": "reviewed-monument-scope"%',)).fetchone()[0],
        with_coordinates=db.execute('SELECT count(*) FROM monuments WHERE latitude IS NOT NULL').fetchone()[0],
        with_description=db.execute("SELECT count(*) FROM monuments WHERE description<>'' OR history<>''").fetchone()[0],
        description_sources=dict(db.execute("SELECT CASE WHEN descriptionSource LIKE 'Wikipédia%' THEN 'Wikipédia' ELSE descriptionSource END AS source,count(*) FROM monuments GROUP BY source")),
        with_wikipedia=db.execute("SELECT count(*) FROM monuments WHERE wikipediaUrl<>''").fetchone()[0],
        with_image=db.execute("SELECT count(*) FROM monuments WHERE imageUrl<>''").fetchone()[0],
        with_importance=db.execute('SELECT count(*) FROM monuments WHERE importance IS NOT NULL').fetchone()[0],
        reused_enrichments=len(set(old)&{r[0] for r in db.execute('SELECT reference FROM monuments')}),
        by_department=dict(db.execute('SELECT department,count(*) FROM monuments GROUP BY department')),
        by_region=dict(db.execute('SELECT region,count(*) FROM monuments GROUP BY region')),
        multiple_protections=db.execute("SELECT count(*) FROM monuments WHERE protection LIKE '%classé%' AND protection LIKE '%inscrit%'").fetchone()[0],
        colocated_groups=db.execute('SELECT count(*) FROM (SELECT 1 FROM monuments WHERE latitude IS NOT NULL GROUP BY latitude,longitude HAVING count(*)>1)').fetchone()[0])
    report['without_coordinates']=len(scores)-report['with_coordinates']
    report['elapsed_seconds']=round(time.perf_counter()-start,3)
    db.execute('INSERT INTO metadata VALUES (?,?)',('dataset',json.dumps(report,ensure_ascii=False)))
    db.commit(); db.execute('ANALYZE'); db.execute('VACUUM')
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    db.close(); os.replace(temp,output)
    report['database_bytes']=output.stat().st_size
    output.with_name('dataset_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('columns','missing_fields','by_region','by_department','conflicts')},ensure_ascii=False,indent=2))
    return report

def build(source,output,enrichment=None,wikipedia=None,scoring=None):
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp'); temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp)
    try: return _build(source,output,enrichment,db,wikipedia,scoring)
    finally:
        db.close()
        temp.unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'app/src/main/assets/monuments.db')
    p.add_argument('--enrichment',type=Path,default=ROOT/'data/legacy_enrichment.json')
    p.add_argument('--wikipedia',type=Path,default=ROOT/'data/wikipedia_enrichment.json')
    p.add_argument('--scoring',type=Path,default=ROOT/'data/scoring_enrichment.json')
    args=p.parse_args(); build(args.input,args.output,args.enrichment,args.wikipedia,args.scoring)

