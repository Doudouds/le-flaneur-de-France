"""Repeatable full-dataset SQL measurements. Not an Android frame-rate benchmark."""
import argparse,json,sqlite3,time,statistics
from pathlib import Path
from build_monuments_db import fts_query,tile,distance

def main():
    p=argparse.ArgumentParser(); p.add_argument('--database',type=Path,default=Path('app/src/main/assets/monuments.db'))
    p.add_argument('--output',type=Path,default=Path('docs/benchmark-desktop.json')); args=p.parse_args()
    db=sqlite3.connect(args.database); results={}
    scenarios={
        'Paris':(48.81,2.22,48.92,2.43),'Bordeaux':(44.80,-.64,44.89,-.52),
        'Lyon':(45.7,4.75,45.81,4.91),'Strasbourg':(48.54,7.68,48.63,7.82),
        'Rouen':(49.4,1.04,49.47,1.15),'Avignon':(43.91,4.76,43.97,4.85),
        'Rural_Cevennes':(44.0,3.2,44.3,3.7)}
    def measure(name,sql,params):
        durations=[]; count=0
        for _ in range(30):
            t=time.perf_counter(); count=len(db.execute(sql,params).fetchall()); durations.append((time.perf_counter()-t)*1000)
        results[name]={'rows':count,'median_ms':round(statistics.median(durations),3),
                       'p95_ms':round(sorted(durations)[28],3),'first_ms':round(durations[0],3),
                       'plan':[r[3] for r in db.execute('EXPLAIN QUERY PLAN '+sql,params)]}
    for name,b in scenarios.items():
        measure('viewport_'+name,'SELECT id,latitude,longitude,globalScore,visualLevel FROM monuments WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? LIMIT 6001',(b[0],b[2],b[1],b[3]))
    for q in ('chambord','mont saint mich','chartres','eglise','zzzzzz','PA2A000001'):
        measure('search_'+q,"SELECT m.id,m.name FROM monument_fts f JOIN monument_list m ON m.id=f.docid WHERE monument_fts MATCH ? ORDER BY CASE WHEN m.searchName=? THEN 0 WHEN m.searchName GLOB ? THEN 1 ELSE 2 END,m.globalScore DESC,m.searchName,m.id LIMIT 50",(fts_query(q),q,q+'*'))
    level=7; x0,y1=tile(41,-5.5,level); x1,y0=tile(51.6,10,level)
    measure('national_clusters','SELECT majorId,latitude,longitude,importance,count FROM map_cells WHERE level=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?',(level,x0,x1,y0,y1))
    # The pyramid must never lose or duplicate a positioned notice.
    count=db.execute('SELECT count(*) FROM monuments WHERE latitude IS NOT NULL').fetchone()[0]
    for level,total in db.execute('SELECT level,sum(count) FROM map_cells GROUP BY level'): assert count==total,(level,total,count)
    results['dataset']={'monuments':db.execute('SELECT count(*) FROM monuments').fetchone()[0],
                        'positioned':count,'bytes':args.database.stat().st_size,'sqlite':sqlite3.sqlite_version,
                        'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{a:b for a,b in v.items() if a!='plan'} for k,v in results.items()},ensure_ascii=False,indent=2))
    db.close()

if __name__=='__main__':main()
