import concurrent.futures
import csv
import http.client
import io
import json
import math
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from review_coordinates import ReviewServer, ReviewStore


class CoordinateReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.audit=self.root/'audit.csv'; self.reviews=self.root/'reviews.json'
        rows=[dict(reference=ref,nom='Test monument',commune='Example',latitude=48.5,longitude=2.5,
                   codes_controles='',priorite='haute') for ref in ('PA00000001','PA00000002')]
        with self.audit.open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]),delimiter=';');writer.writeheader();writer.writerows(rows)
        self.store=ReviewStore(self.audit,self.reviews)
        self.server=ReviewServer(0,self.store,self.root)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.worker.join()
        self.temporary.cleanup()

    def request(self, method, path, payload=None, headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request(method,path,body=json.dumps(payload) if payload is not None else None,headers=headers or {})
            response=connection.getresponse();return response.status,response.read()
        finally:connection.close()

    def local_headers(self):
        return {'Origin':f'http://127.0.0.1:{self.server.server_port}',
                'X-Review-Token':self.server.token,'Content-Type':'application/json'}

    def test_save_survives_restart_and_can_be_reversed(self):
        status,body=self.request('PUT','/api/reviews/PA00000001',{'decision':'mauvais','note':'Position dans la mer'},self.local_headers())
        self.assertEqual(status,200)
        restored=ReviewStore(self.audit,self.reviews)
        self.assertEqual(restored.read()['reviews']['PA00000001']['decision'],'mauvais')
        self.assertEqual(json.loads(body)['latitude'],48.5)
        restored.save('PA00000001','bon','Adresse confirmée')
        status,body=self.request('GET','/api/data')
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['reviews']['PA00000001']['note'],'Adresse confirmée')
        restored.save('PA00000001','a_verifier','')
        self.assertEqual(self.store.read()['reviews']['PA00000001']['decision'],'a_verifier')

    def test_parallel_decisions_do_not_overwrite_each_other(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda ref:self.store.save(ref,'bon','checked'),self.store.by_ref))
        self.assertEqual(len(self.store.read()['reviews']),2)

    def test_external_requests_and_invalid_decisions_cannot_write(self):
        for headers in ({},{'Origin':'https://example.org','X-Review-Token':self.server.token}):
            self.assertEqual(self.request('PUT','/api/reviews/PA00000001',{'decision':'bon'},headers)[0],403)
        for ref,decision in [('PA00000001','invalid'),('unknown','bon')]:
            self.assertEqual(self.request('PUT','/api/reviews/'+ref,{'decision':decision},self.local_headers())[0],400)
        self.assertEqual(self.request('GET','/api/data',headers={'Host':'evil.example'})[0],403)
        self.assertFalse(self.reviews.exists())
        self.assertEqual(self.request('GET','/../review_coordinates.py')[0],404)

    def test_exports_include_notes_and_protect_excel_formulas(self):
        self.store.save('PA00000001','mauvais','=1+1')
        status,body=self.request('GET','/api/export.csv')
        self.assertEqual(status,200)
        rows=list(csv.DictReader(io.StringIO(body.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[0]['commentaire'],"'=1+1")
        self.assertEqual(rows[0]['decision'],'mauvais')
        self.assertEqual(rows[1]['decision'],'a_verifier')
        status,body=self.request('GET','/api/export.json')
        self.assertEqual(json.loads(body)['reviews']['PA00000001']['note'],'=1+1')

    def test_damaged_personal_file_is_preserved(self):
        self.reviews.write_text('damaged',encoding='utf-8')
        self.assertEqual(self.request('GET','/api/data')[0],500)
        self.assertEqual(self.reviews.read_text(encoding='utf-8'),'damaged')

    def test_changed_position_is_explicit_in_export(self):
        self.store.save('PA00000001','bon','old position')
        data=self.store.read();data['reviews']['PA00000001']['latitude']=49
        self.reviews.write_text(json.dumps(data),encoding='utf-8')
        rows=list(csv.DictReader(io.StringIO(self.store.export_csv().decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[0]['position_modifiee_depuis_decision'],'True')

    def test_existing_reviews_are_unchanged_until_edit_and_backed_up_exactly(self):
        legacy={'version':1,'extra_metadata':'preserve', 'reviews':{
            'PA00000001':{'decision':'bon','note':'Existing personal note','latitude':48.5,'longitude':2.5,'updated_at':'2026-10-25T10:00:00Z','future_field':42},
            'PA00000002':{'decision':'a_verifier','note':'Second note','latitude':48.5,'longitude':2.5,'updated_at':'2026-10-25T11:00:00Z'}}}
        self.reviews.write_text(json.dumps(legacy),encoding='utf-8');before=self.reviews.read_bytes()
        restored=ReviewStore(self.audit,self.reviews)
        self.assertEqual(self.reviews.read_bytes(),before)
        result=restored.save('PA00000001',correction={'latitude':48.6,'longitude':2.6})
        self.assertEqual(result['decision'],'bon');self.assertEqual(result['note'],'Existing personal note')
        self.assertEqual(result['future_field'],42)
        self.assertEqual(result['latitude'],48.5)
        data=restored.read()
        self.assertEqual(data['extra_metadata'],'preserve')
        self.assertEqual(data['reviews']['PA00000002'],legacy['reviews']['PA00000002'])
        backups=list((self.root/'coordinate_review_backups').glob('*.json'))
        self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),before)
        self.assertEqual(len(result['history']),2)
        self.assertEqual(result['history'][0]['note'],'Existing personal note')
        self.assertEqual(result['history'][0]['action'],'etat_initial_conserve')

    def test_corrections_survive_old_client_saves_restart_and_reset(self):
        self.store.save('PA00000001','mauvais','Original note')
        payload={'correction':{'latitude':49.343,'longitude':2.282}}
        status,body=self.request('PUT','/api/corrections/PA00000001',payload,self.local_headers())
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['decision'],'mauvais')
        self.assertEqual(json.loads(body)['note'],'Original note')
        self.store.save('PA00000001','bon','Edited note from an older browser tab')
        restored=ReviewStore(self.audit,self.reviews)
        self.assertEqual(restored.read()['reviews']['PA00000001']['correction']['latitude'],49.343)
        restored.save('PA00000001',correction={'latitude':49.344,'longitude':2.283})
        reset=restored.save('PA00000001',correction=None)
        self.assertIsNone(reset['correction']);self.assertEqual(reset['decision'],'bon')
        previous_points=[h['correction']['latitude'] for h in reset['history'] if h.get('correction')]
        self.assertIn(49.343,previous_points);self.assertIn(49.344,previous_points)
        self.assertEqual(reset['history'][-1]['action'],'position_retablie')

    def test_export_contains_original_corrected_coordinates_and_full_history(self):
        self.store.save('PA00000001','mauvais','Keep this judgment')
        self.store.save('PA00000001',correction={'latitude':49.34,'longitude':2.28})
        status,body=self.request('GET','/api/export.csv')
        self.assertEqual(status,200)
        row=next(csv.DictReader(io.StringIO(body.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(row['latitude'],'48.5');self.assertEqual(row['latitude_corrigee'],'49.34')
        self.assertEqual(row['decision'],'mauvais');self.assertEqual(row['position_modifiee_depuis_decision'],'False')
        status,body=self.request('GET','/api/export.json')
        self.assertEqual(len(json.loads(body)['reviews']['PA00000001']['history']),2)

    def test_invalid_corrections_are_rejected_without_touching_existing_work(self):
        self.store.save('PA00000001','bon','Do not lose this')
        before=self.reviews.read_bytes()
        for value in ({'latitude':91,'longitude':2},{'latitude':49,'longitude':181},
                      {'latitude':math.nan,'longitude':2},{'latitude':math.inf,'longitude':2},
                      {'latitude':True,'longitude':2},{'latitude':'49','longitude':2},{'latitude':49}):
            status,_=self.request('PUT','/api/corrections/PA00000001',{'correction':value},self.local_headers())
            self.assertEqual(status,400)
            self.assertEqual(self.reviews.read_bytes(),before)

    def test_noop_saves_do_not_fill_history_with_duplicate_entries(self):
        result=self.store.save('PA00000001','bon','Same note')
        result=self.store.save('PA00000001',correction={'latitude':49,'longitude':2})
        before=self.reviews.read_bytes()
        self.store.save('PA00000001','bon','Same note')
        self.store.save('PA00000001',correction={'latitude':49,'longitude':2})
        self.assertEqual(self.reviews.read_bytes(),before)
        self.assertEqual(len(result['history']),2)

    def test_failed_atomic_replacement_preserves_work_and_recovery_copy(self):
        self.store.save('PA00000001','bon','Existing note')
        before=self.reviews.read_bytes()
        with patch.object(Path,'replace',side_effect=OSError('disk unavailable')):
            status,_=self.request('PUT','/api/corrections/PA00000001',{'correction':{'latitude':49,'longitude':2}},self.local_headers())
        self.assertEqual(status,500);self.assertEqual(self.reviews.read_bytes(),before)
        self.assertTrue(any(p.read_bytes()==before for p in (self.root/'coordinate_review_backups').glob('*.json')))
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_parallel_correction_and_comment_preserve_both_updates(self):
        self.store.save('PA00000001','bon','old')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            tasks=[pool.submit(self.store.save,'PA00000001','bon','new note'),
                   pool.submit(self.store.save,'PA00000001',correction={'latitude':49,'longitude':2})]
            for task in tasks:task.result()
        result=self.store.read()['reviews']['PA00000001']
        self.assertEqual(result['note'],'new note');self.assertEqual(result['correction']['latitude'],49)
        self.assertEqual(len(result['history']),3)


if __name__=='__main__':unittest.main()
