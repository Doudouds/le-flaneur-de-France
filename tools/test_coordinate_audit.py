import contextlib
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from audit_coordinates import audit, contains, geometry_distance, inspect, match_communes, segment_distance


def square(west=0, south=0, east=1, north=1):
    return {'type': 'Polygon', 'coordinates': [[[west,south],[east,south],[east,north],[west,north],[west,south]]]}


def feature(code='01001', department='01', name='Example', geometry=None):
    return {'type': 'Feature', 'properties': {'code':code,'departement':department,'nom':name}, 'geometry':geometry or square()}


def monument(**changes):
    return dict(reference='PA00114985',name='Example',commune='Example',insee='01001',department='01',
                latitude=.5,longitude=.5,coordinateStatus='valid',popUrl='https://pop.culture.gouv.fr/notice/merimee/PA00114985')|changes


class CoordinateAuditTests(unittest.TestCase):
    def test_inside_edges_holes_and_multipolygons(self):
        shape=square()
        self.assertTrue(contains((.5,.5),shape))
        self.assertTrue(contains((0,.5),shape))
        self.assertFalse(contains((2,.5),shape))
        shape['coordinates'].append(square(.3,.3,.7,.7)['coordinates'][0])
        self.assertFalse(contains((.5,.5),shape))
        self.assertTrue(contains((.3,.5),shape))
        self.assertGreater(geometry_distance((.5,.5),shape),20)
        multi={'type':'MultiPolygon','coordinates':[shape['coordinates'],square(2,2,3,3)['coordinates']]}
        self.assertTrue(contains((2.5,2.5),multi))

    def test_date_line_and_great_circle_segment_endpoints(self):
        shape=square(179,-1,-179,1)
        self.assertTrue(contains((0,179.5),shape))
        self.assertTrue(contains((0,-179.5),shape))
        self.assertFalse(contains((0,0),shape))
        self.assertAlmostEqual(segment_distance((.01,.5),(0,0),(0,1)),1.11195,places=3)
        self.assertAlmostEqual(segment_distance((0,2),(0,0),(0,1)),111.195,places=2)
        self.assertAlmostEqual(segment_distance((0,-1),(0,0),(0,1)),111.195,places=2)

    def test_multiple_insee_codes_take_all_communes_and_preserve_gaps(self):
        first=feature(); second=feature('01002',geometry=square(2,2,3,3))
        found,method,gaps=match_communes(monument(insee='01001;01002;01999'),{'01001':first,'01002':second},{})
        self.assertEqual(len(found),2); self.assertEqual(gaps,['01999'])
        self.assertEqual(method,'code_insee')
        row=inspect(monument(latitude=2.5,longitude=2.5),found,{'01':feature(geometry=square(0,0,4,4))},method,gaps)
        self.assertEqual(row['ecart_commune_km'],0)
        self.assertEqual(row['priorite'],'couverture_a_verifier')

    def test_name_fallback_never_uses_another_department(self):
        found,method,gaps=match_communes(monument(insee='unknown'),{}, {('02','example'):[feature('02001','02')]})
        self.assertFalse(found)
        self.assertEqual(method,'non_apparie')

    def test_partial_reference_is_not_mistaken_for_a_position_error(self):
        deps={'01':feature(geometry=square(-1,-1,5,5))}
        row=inspect(monument(latitude=3,longitude=3),[feature()],deps,'code_insee',['01999'])
        self.assertEqual(row['priorite'],'couverture_a_verifier')
        mismatch=inspect(monument(),[feature(department='02')],deps,'code_insee',[])
        self.assertEqual(mismatch['motif'],'code_insee_et_departement_incoherents')
        lighthouse=inspect(monument(name='Phare en mer',latitude=3,longitude=3),[feature()],deps,'code_insee',[])
        self.assertEqual(lighthouse['avertissement'],'implantation_maritime_possible')

    def test_boundary_tolerance_and_severe_department_error(self):
        commune=feature(); deps={'01':feature(geometry=square(-1,-1,2,2))}
        self.assertEqual(inspect(monument(latitude=-.001),[commune],deps,'code_insee',[])['priorite'],'limite')
        self.assertEqual(inspect(monument(latitude=-.02),[commune],deps,'code_insee',[])['priorite'],'moderee')
        self.assertEqual(inspect(monument(latitude=45,longitude=4),[commune],deps,'code_insee',[])['priorite'],'haute')
        self.assertEqual(inspect(monument(latitude=None,longitude=None,coordinateStatus='suspect_precision'),[],{},'non_apparie',[])['priorite'],'deja_ecarte')

    def test_historical_guadeloupe_attachment_is_not_a_geographic_bug(self):
        commune=feature('97701','977')
        deps={'971':feature('971',geometry=square(10,10,11,11)),
              '977':feature('977'), '978':feature('978',geometry=square(2,2,3,3))}
        row=inspect(monument(insee='97701',department='971'),[commune],deps,'code_insee',[])
        self.assertEqual(row['priorite'],'aucun_signal')
        found,_,_=match_communes(monument(insee='old',department='971'),{}, {('977','example'):[commune]})
        self.assertEqual(found,[commune])

    def test_axis_and_sign_suggestions_require_inside_expected_commune(self):
        expected=[feature(geometry=square(2,48,3,49))]
        deps={'01':feature(geometry=square(1,47,4,50))}
        swapped=inspect(monument(latitude=2.5,longitude=48.5),expected,deps,'code_insee',[])
        self.assertEqual(swapped['suggestion_a_verifier'],'axes_inverses')
        signed=inspect(monument(latitude=48.5,longitude=-2.5),expected,deps,'code_insee',[])
        self.assertEqual(signed['suggestion_a_verifier'],'signe_longitude')

    def test_complete_offline_audit_is_read_only_and_exports_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); database=root/'catalogue.db'
            with contextlib.closing(sqlite3.connect(database)) as db:
                db.execute('CREATE TABLE monuments (reference,name,commune,insee,department,latitude,longitude,coordinateStatus,popUrl)')
                for m in [monument(),monument(reference='PA00000002',latitude=40),
                          monument(reference='PA00000003',latitude=None,longitude=None,coordinateStatus='suspect_precision')]:
                    db.execute('INSERT INTO monuments VALUES (?,?,?,?,?,?,?,?,?)',tuple(m.values()))
                db.execute('CREATE TABLE source_rows (reference,raw,issue)')
                db.execute('INSERT INTO source_rows VALUES (?,?,?)',('PA00000003',json.dumps({'coordonnees_au_format_WGS84':'44,0'}),'suspect_precision'))
                db.commit()
            before=hashlib.sha256(database.read_bytes()).hexdigest()
            for kind,features in [('communes',[feature()]),('communes-associees-deleguees',[]),
                                  ('departements',[feature('01',geometry=square(-1,-1,2,2))])]:
                (root/(kind+'-100m.geojson.gz')).write_bytes(gzip.compress(json.dumps({'type':'FeatureCollection','features':features}).encode()))
            with contextlib.redirect_stdout(io.StringIO()): report=audit(database,root,root/'result',offline=True)
            self.assertEqual(report['total'],3)
            self.assertEqual(report['priorities'],{'haute':1,'deja_ecarte':1,'aucun_signal':1})
            self.assertEqual(before,hashlib.sha256(database.read_bytes()).hexdigest())
            self.assertIn('1 alertes', (root/'result.md').read_text(encoding='utf-8'))
            with (root/'result.csv').open(encoding='utf-8-sig',newline='') as f:
                self.assertEqual([r['reference'] for r in csv.DictReader(f,delimiter=';')],['PA00000002'])
            with (root/'result-review.csv').open(encoding='utf-8-sig',newline='') as f:
                self.assertEqual(next(csv.DictReader(f,delimiter=';'))['coordonnees_source_ecartees'],'44,0')


if __name__ == '__main__':
    unittest.main()
