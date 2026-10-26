import csv
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reconcile_monumentum_positions import (BASE, Source, apply_plan, distance_m, exact_url,
                                            parse_detail, parse_search, proposed_change, reconcile, report_matrix, write_reports)
from review_coordinates import ReviewServer, ReviewStore

REF = 'PA00114985'
URL = BASE+'/monument-historique/pa00114985/saint-felix-ancienne-brosserie-autin'
MARKER = 'L.marker([49.34309,2.282292],{ title : "Autin - PA00114985"})'
SEARCH = '<a href="'+URL+'">Autin</a>'+MARKER
DETAIL = ('<meta property="og:url" content="'+URL+'">'
          '<span data-object-id="PA00114985"></span>'
          '<a href="https://www.pop.culture.gouv.fr/notice/merimee/PA00114985">POP</a>'
          '<meta property="og:title" content="Autin &amp; moulin">'+MARKER)


class MonumentumTests(unittest.TestCase):
    def test_exact_reference_matches_both_search_and_detail(self):
        url, point = parse_search(SEARCH, REF)
        found = parse_detail(DETAIL, REF, url, point)
        self.assertEqual((found['latitude'], found['longitude']), (49.34309, 2.282292))
        self.assertEqual(found['title'], 'Autin & moulin')

    def test_pages_without_optional_voting_widget_still_need_canonical_and_pop_identity(self):
        html = DETAIL.replace('<span data-object-id="PA00114985"></span>', '')
        self.assertEqual(parse_detail(html, REF, URL, (49.34309, 2.282292))['reference'], REF)
        with self.assertRaises(ValueError):
            parse_detail(html.replace('content="'+URL+'"', 'content="'+URL+'-bad"').replace('pa00114985/', 'pa00114986/'),
                         REF, URL, (49.34309, 2.282292))

    def test_neighbouring_references_and_edit_links_are_not_selected(self):
        for url in (URL+'/edit-localisation', URL.replace('pa00114985', 'pa001149850'),
                    URL.replace('monumentum.fr', 'example.org'), URL+'?redirect=1'):
            self.assertFalse(exact_url(url, REF))
        unrelated = '<a href="'+URL.replace('pa00114985', 'pa00114986')+'">Neighbour</a>'+MARKER
        with self.assertRaises(ValueError):
            parse_search(unrelated, REF)

    def test_ambiguous_points_or_multiple_exact_pages_are_rejected(self):
        for html in (SEARCH+MARKER.replace('49.34309', '49.35'),
                     SEARCH+'<a href="'+URL+'-other">Other page</a>'):
            with self.assertRaises(ValueError):
                parse_search(html, REF)

    def test_identity_and_coordinate_disagreements_are_rejected(self):
        for html in (DETAIL.replace('data-object-id="PA00114985"', 'data-object-id="PA00114986"'),
                     DETAIL.replace('/merimee/PA00114985', '/merimee/PA00114986'),
                     DETAIL.replace('49.34309', '49.35'), DETAIL+MARKER.replace('49.34309', '49.35')):
            with self.assertRaises(ValueError):
                parse_detail(html, REF, URL, (49.34309, 2.282292))

    def test_out_of_range_coordinates_and_invalid_reference_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_search(SEARCH.replace('49.34309', '91'), REF)
        with self.assertRaises(ValueError):
            parse_search(SEARCH, REF+'0')

    def test_cached_lookup_never_needs_network(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            (cache/('search-'+REF+'.html')).write_text(SEARCH, encoding='utf-8')
            (cache/(REF+'.html')).write_text(DETAIL, encoding='utf-8')
            self.assertEqual(Source(cache).lookup(REF)['reference'], REF)

    def test_scope_includes_manual_corrections_and_unreviewed_but_preserves_inputs(self):
        rows = [dict(reference=REF, nom='Autin', commune='Saint-Félix', departement='60', latitude=43, longitude=-2),
                dict(reference='PA00000002', nom='Other', commune='X', departement='60', latitude=49, longitude=2),
                dict(reference='PA00000003', nom='Reviewed', commune='X', departement='60', latitude=49, longitude=2)]
        reviews = {REF: dict(decision='bon', note='keep', correction={'latitude':49.34309,'longitude':2.282292}),
                   'PA00000003': dict(decision='bon', note='untouched')}
        before = json.dumps(reviews)
        class FakeSource:
            def lookup(self, ref):
                if ref != REF:
                    raise ValueError('No exact result')
                return dict(latitude=49.34309, longitude=2.282292)
        with tempfile.TemporaryDirectory() as folder:
            records = reconcile(rows, reviews, FakeSource(), Path(folder)/'result.json')
        self.assertEqual([r['reference'] for r in records], [REF, 'PA00000002'])
        self.assertEqual(records[0]['distance_current_m'], 0)
        self.assertEqual(records[1]['status'], 'unresolved')
        self.assertEqual(json.dumps(reviews), before)

    def test_distance_is_in_metres(self):
        self.assertEqual(distance_m((49, 2), (49, 2)), 0)
        self.assertAlmostEqual(distance_m((0, 0), (0, 1)), 111195.08, places=1)

    def candidate(self, **kwargs):
        return dict(reference=REF, nom='Autin', commune='Saint-Félix', departement='60',
                    original=[43, -2], current=[49.34309, 2.282292], had_correction=True,
                    source={'latitude':49.34309, 'longitude':2.282292}, distance_current_m=1, status='matched', **kwargs)

    def test_small_manual_difference_is_kept_without_rounding(self):
        item = self.candidate()
        item['current'] = [49.3430912345678, 2.2822912345678]
        result = proposed_change(item)
        self.assertEqual(result['final'], item['current'])
        self.assertEqual(result['movement_m'], 0)
        self.assertEqual(result['action'], 'correction_manuelle_conservee')

    def test_large_difference_is_corrected_but_extended_monument_is_flagged(self):
        item = self.candidate()
        item.update(current=[49.35, 2.3], distance_current_m=1500)
        self.assertEqual(proposed_change(item)['action'], 'correction_manuelle_ajustee')
        item['nom'] = 'Aqueduc sur plusieurs communes'
        result = proposed_change(item)
        self.assertEqual(result['final'], item['current'])
        self.assertTrue(result['needs_review'])

    def test_unresolved_source_is_not_applied_and_export_marks_it(self):
        item = self.candidate()
        item.update(status='unresolved', error='No exact match')
        result = proposed_change(item)
        self.assertEqual(result['final'], item['current'])
        self.assertTrue(result['needs_review'])
        matrix = report_matrix([result])
        self.assertEqual(len(matrix[0]), len(matrix[1]))
        self.assertEqual(matrix[1][matrix[0].index('a_confirmer')], True)

    def test_offline_missing_cache_does_not_fetch_anything(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                Source(Path(folder), offline=True).get(BASE+'/recherche/pa00114985', 'missing.html')

    def test_csv_roundtrip_keeps_precision_negative_longitude_and_literal_text(self):
        item = self.candidate()
        item.update(nom='=unsafe; "label"',current=[49.3430912345678,-2.2822912345678])
        result = proposed_change(item)
        with tempfile.TemporaryDirectory() as folder:
            write_reports([result],Path(folder))
            with (Path(folder)/'positions-corrigees-monumentum.csv').open(encoding='utf-8-sig',newline='') as handle:
                row=next(csv.DictReader(handle,delimiter=';'))
        self.assertEqual(row['monument'],"'=unsafe; \"label\"")
        self.assertEqual(float(row['longitude_corrigee']),-2.2822912345678)
        self.assertEqual(row['a_confirmer'],'non')


class ApplyMonumentumTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        audit = self.root/'audit.csv'
        with audit.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['reference','latitude','longitude'], delimiter=';')
            writer.writeheader()
            writer.writerows([{'reference':ref,'latitude':48,'longitude':2} for ref in (REF,'PA00000002')])
        self.store = ReviewStore(audit, self.root/'reviews.json')
        self.store.save(REF, 'mauvais', 'Personal note stays exact. é')
        self.before = self.store.read()['reviews']
        self.server = ReviewServer(0, self.store, self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def plan(self):
        return [dict(reference=REF, original=[48,2], current=[48,2], final=[49.34309,2.282292],
                     had_correction=False, source=dict(url=URL,latitude=49.34309,longitude=2.282292),
                     action='nouvelle_correction',status='matched',needs_review=False)]

    def test_apply_uses_existing_backup_and_history_without_changing_judgment(self):
        applied = apply_plan(self.plan(), self.before, self.base)
        self.assertEqual(applied, [REF])
        after = self.store.read()['reviews'][REF]
        self.assertEqual(after['note'], self.before[REF]['note'])
        self.assertEqual(after['decision'], 'mauvais')
        self.assertEqual(after['history'][:-1], self.before[REF]['history'])
        self.assertEqual(after['correction']['latitude'],49.34309)
        self.assertTrue(list((self.root/'coordinate_review_backups').glob('*.json')))

    def test_stale_plan_does_not_overwrite_newer_personal_work(self):
        self.store.save(REF, 'bon', 'Newer note')
        raw = self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            apply_plan(self.plan(), self.before, self.base)
        self.assertEqual(self.store.path.read_bytes(),raw)

    def test_whole_batch_is_validated_before_any_write(self):
        plan = self.plan()
        plan.append(dict(plan[0],reference='PA00000002'))  # Source URL still names the other reference.
        raw = self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            apply_plan(plan,self.before,self.base)
        self.assertEqual(self.store.path.read_bytes(),raw)


if __name__ == '__main__':
    unittest.main()
