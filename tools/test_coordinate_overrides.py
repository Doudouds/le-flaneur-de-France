import contextlib
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_monuments_db import build, REQUIRED, tile


class FinalCoordinateTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.source=self.root/'source.csv';self.output=self.root/'monuments.db';self.snapshot=self.root/'final.json'
        self.original=(47.616,1.517);self.target=(49.34309,2.282292)
        row=dict.fromkeys(sorted(REQUIRED),'')|{'Reference':'PA00000001','Titre_editorial_de_la_notice':'Test',
            'Commune_forme_editoriale':'Example','Departement_format_numerique':'60','coordonnees_au_format_WGS84':'47.616,1.517'}
        with self.source.open('w',encoding='utf-8',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(row),delimiter='|');writer.writeheader();writer.writerow(row)
        self.item=dict(latitude=self.target[0],longitude=self.target[1],original_latitude=self.original[0],
            original_longitude=self.original[1],selection='manual_final')
        self.write_snapshot(self.item)

    def tearDown(self):
        self.temporary.cleanup()

    def write_snapshot(self,item,ref='PA00000001'):
        self.snapshot.write_text(json.dumps({'version':1,'reviewed_monuments':1,'records':{ref:item}}),encoding='utf-8')

    def rebuild(self):
        with contextlib.redirect_stdout(io.StringIO()):return build(self.source,self.output,coordinate_overrides=self.snapshot)

    def test_final_choice_survives_rebuild_and_all_spatial_levels_use_new_point(self):
        source_before=self.source.read_bytes()
        for _ in range(2):
            report=self.rebuild()
            with contextlib.closing(sqlite3.connect(self.output)) as db:
                self.assertEqual(db.execute('SELECT latitude,longitude FROM monuments').fetchone(),self.target)
                for level in range(3,19):
                    x,y=tile(*self.target,level)
                    self.assertEqual(db.execute('SELECT count FROM map_cells WHERE level=? AND x=? AND y=?',(level,x,y)).fetchone(),(1,))
                self.assertEqual(db.execute('SELECT count(*) FROM monument_fts').fetchone(),(1,))
            self.assertEqual(report['coordinate_review']['changed_positions'],1)
        self.assertEqual(self.source.read_bytes(),source_before)

    def test_explicit_original_restoration_is_kept_in_final_provenance(self):
        self.write_snapshot(self.item|dict(latitude=self.original[0],longitude=self.original[1],selection='original_restored'))
        report=self.rebuild()
        self.assertEqual(report['coordinate_review']['restored_positions'],1)
        self.assertEqual(report['coordinate_review']['changed_positions'],0)
        with contextlib.closing(sqlite3.connect(self.output)) as db:
            self.assertEqual(db.execute('SELECT latitude,longitude FROM monuments').fetchone(),self.original)

    def test_invalid_stale_or_unknown_override_never_replaces_previous_catalogue(self):
        self.rebuild();before=self.output.read_bytes()
        for item,ref in [(self.item|{'latitude':91},'PA00000001'),(self.item|{'latitude':True},'PA00000001'),
                         (self.item|{'longitude':float('nan')},'PA00000001'),(self.item|{'original_latitude':48},'PA00000001'),
                         (self.item,'PA00000002'),(self.item|{'selection':'original_restored'},'PA00000001')]:
            self.write_snapshot(item,ref)
            with self.assertRaises(ValueError):self.rebuild()
            self.assertEqual(self.output.read_bytes(),before)
            self.assertFalse(self.output.with_suffix('.tmp').exists())


if __name__=='__main__':unittest.main()
