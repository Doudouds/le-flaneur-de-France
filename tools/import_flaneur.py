"""Snapshot verified reference-based enrichments, without modifying the Paris project."""
import argparse, collections, csv, hashlib, json, re
from pathlib import Path
from urllib.parse import quote

def main():
    p=argparse.ArgumentParser(); p.add_argument('--project',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/legacy_enrichment.json')); args=p.parse_args()
    output={}; groups=collections.defaultdict(list)
    score_file=args.project/'outputs/heritage_enrichment/monuments_enrichis_debug.csv'
    with score_file.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            refs=re.findall(r'PA[0-9AB]{8}',row['identifiant_merimee'])
            # A score for a composite OSM entity must not be assigned to each component.
            if len(refs)!=1 or not row.get('importance_patrimoniale'): continue
            item={'importance':int(row['importance_patrimoniale']),'notoriety':int(row['notoriete']),
                  'globalScore':int(row['note_globale']),'basis':row['base_notoriete'],
                  'matching':row['source_matching'],'period':row['periode_vues_wikipedia']}
            item['components']={key:int(row[key] or 0) for key in (
                'score_protection','score_anciennete','score_exceptionnel','score_unesco',
                'score_autres_protections','score_interet_documente')}
            if row['source_matching']=='wikidata:ref-merimee' and row.get('titre_wikipedia_fr') and float(row.get('confiance_matching') or 0)>=.99:
                item['wikipediaUrl']='https://fr.wikipedia.org/wiki/'+quote(row['titre_wikipedia_fr'].replace(' ','_'))
            if row.get('raisons_verification'): continue
            groups[refs[0]].append(item)
    skipped=0
    for ref,items in groups.items():
        if any(i!=items[0] for i in items): skipped+=1; continue
        output[ref]={'scores':items[0]}
        if items[0].get('wikipediaUrl'): output[ref]['wikipediaUrl']=items[0]['wikipediaUrl']
    asset=args.project/'app/src/main/assets/paris_monuments.json'
    assets=collections.defaultdict(list)
    for m in json.loads(asset.read_text(encoding='utf-8')):
        refs=re.findall(r'PA[0-9AB]{8}',m.get('merimeeReference') or '')
        if len(refs)==1: assets[refs[0]].append(m)
    for ref,items in assets.items():
        if len(items)>1: continue
        m=items[0]; dest=output.setdefault(ref,{})
        for k in ('description','descriptionSource','popHistoricalDescription','wikipediaUrl','imageUrl',
                  'imagePageUrl','imageAuthor','imageLicense','imageLicenseUrl'):
            if m.get(k) and '\ufffd' not in m[k]: dest[k]=m[k]
        if dest.get('description') and not dest.get('descriptionSource'): dest.pop('description',None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'references':len(output),'ambiguous_scores_skipped':skipped,
                      'sources':{str(f):hashlib.file_digest(f.open('rb'),'sha256').hexdigest() for f in (score_file,asset)}},indent=2))

if __name__=='__main__': main()

