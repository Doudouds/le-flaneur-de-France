import contextlib,csv,io,json,sqlite3,tempfile,unittest
from pathlib import Path
from build_monuments_db import build,coordinates,distance,fts_query,normalize,score,tile,REQUIRED

class PipelineTests(unittest.TestCase):
    def test_coordinates(self):
        self.assertEqual(coordinates('48.2, 2.4','75'),(48.2,2.4,'valid'))
        self.assertEqual(coordinates('-20.9,55.4','974')[2],'valid')
        self.assertEqual(coordinates('17.9,-62.85','971')[2],'valid') # historical code
        self.assertEqual(coordinates('1.99,49.16','95')[2],'suspect_territory')
        self.assertEqual(coordinates('14,-61','972')[2],'suspect_territory')
        for text in ('nan,2','91,3','0,0','1,2,3','a,b','inf,2'):
            self.assertEqual(coordinates(text)[2],'invalid')
        self.assertEqual(coordinates('')[2],'missing')

    def test_distance_and_search(self):
        self.assertAlmostEqual(distance(48.8566,2.3522,45.764,4.8357),391.5,delta=1)
        self.assertAlmostEqual(distance(0,179.9,0,-179.9),22.24,delta=.1)
        self.assertEqual(distance(0,0,0,0),0)
        self.assertEqual(normalize('CHÂTEAU, cœur'),'chateau coeur')
        self.assertEqual(fts_query('Mont-Saint-Mich'),'mont* saint* mich*')
        self.assertEqual(fts_query('"* OR ;'),'or*')
        self.assertEqual(tile(0,0,3),(4,4))

    def test_scoring_preserves_rules(self):
        m=score({'Typologie_de_la_protection':'classé MH','Date_et_typologie_de_la_protection':'1840'})
        self.assertEqual(m['importance'],65); self.assertEqual(m['notoriety'],2); self.assertEqual(m['globalScore'],40)
        self.assertEqual(score({'Typologie_de_la_protection':'inscrit MH'})['importance'],32)
        self.assertEqual(score({'Typologie_de_la_protection':'classé MH','Precision_de_la_protection':'façade'})['importance'],42)
        old=dict(importance=3,notoriety=2,globalScore=3,components={'score_protection':0,'score_anciennete':3})
        corrected=score({'Typologie_de_la_protection':'classé MH','Date_et_typologie_de_la_protection':'1840'},old)
        self.assertEqual(corrected['importance'],65)
        self.assertEqual(corrected['globalScore'],40)
        old.update(notoriety=90,components={'score_unesco':15,'score_interet_documente':8})
        enriched=score({'Typologie_de_la_protection':'classé MH','Date_et_typologie_de_la_protection':'1840'},old)
        self.assertEqual(enriched['importance'],88)
        self.assertEqual(enriched['globalScore'],89)

    def test_full_import_dedup_search_box_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source.csv'; out=root/'monuments.db'
            columns=sorted(REQUIRED|{'Typologie_de_la_protection','Date_et_typologie_de_la_protection','Historique'})
            base={'Reference':'PA00000001','Titre_editorial_de_la_notice':'Château de Chambord',
                  'coordonnees_au_format_WGS84':'47.616,1.517','Departement_format_numerique':'41',
                  'Commune_forme_editoriale':'Chambord','Typologie_de_la_protection':'classé MH','Historique':'Texte sourcé.\nDeuxième ligne.'}
            rows=[base,base|{'Date_et_typologie_de_la_protection':'1840'},
                  base|{'Reference':'PA2A000001','Titre_editorial_de_la_notice':'Église','coordonnees_au_format_WGS84':''},
                  base|{'Reference':'PA00000002','coordonnees_au_format_WGS84':'2,49'},
                  base|{'Reference':'PA00000003'},base|{'Reference':'PA00000003','coordonnees_au_format_WGS84':'48,2'}]
            with source.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=columns,delimiter='|'); w.writeheader(); w.writerows(rows)
            with contextlib.redirect_stdout(io.StringIO()): result=build(source,out)
            self.assertEqual(result['unique_monuments'],4); self.assertEqual(result['duplicates_merged'],2)
            c=sqlite3.connect(out)
            self.assertEqual(c.execute("SELECT count(*) FROM monument_fts WHERE monument_fts MATCH ?",(fts_query('CHÂMBO'),)).fetchone()[0],4)
            self.assertEqual(c.execute('SELECT count(*) FROM monuments WHERE latitude BETWEEN 47 AND 48 AND longitude BETWEEN 1 AND 2').fetchone()[0],1)
            self.assertEqual(c.execute("SELECT coordinateStatus FROM monuments WHERE reference='PA00000003'").fetchone()[0],'conflicting_duplicate')
            self.assertEqual(c.execute('SELECT sum(count) FROM map_cells WHERE level=6').fetchone()[0],1)
            self.assertEqual(c.execute("SELECT history FROM monuments WHERE reference='PA00000001'").fetchone()[0],base['Historique'])
            self.assertEqual(c.execute("SELECT count(*) FROM monuments WHERE trim(description)='' OR trim(descriptionSource)=''").fetchone()[0],0)
            c.close(); before=out.read_bytes(); source.write_text('bad|headers\nx|y',encoding='utf-8')
            with self.assertRaises(ValueError): build(source,out)
            self.assertEqual(out.read_bytes(),before)

if __name__=='__main__': unittest.main()

