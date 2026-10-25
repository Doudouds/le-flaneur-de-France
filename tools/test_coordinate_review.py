import concurrent.futures
import csv
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
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


if __name__=='__main__':unittest.main()
