import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from enrich_scoring import exact_signals, cached_signals, apply_scope_reviews
from national_scoring import score, visual_level


class ScoringTests(unittest.TestCase):
    def signal(self, n):
        return dict(wikipedia_languages=n, source='https://www.wikidata.org/wiki/Q1')

    def test_no_category_date_or_documentation_bonus(self):
        base = {'Typologie_de_la_protection': 'classé MH'}
        expected = score(base, self.signal(3))
        for category in ('église', 'château', 'usine', 'pont', 'maison', 'mosquée'):
            for date in ('1840', '1920', '2020', ''):
                row = base | {'Denomination_de_l_edifice': category,
                              'Date_et_typologie_de_la_protection': date,
                              'Historique': 'Un chef-d’œuvre exceptionnel. ' * 200,
                              'Auteur_de_l_edifice': 'Auteur très connu',
                              'Precision_de_la_protection': 'clocher et façades'}
                self.assertEqual(score(row, self.signal(3)), expected)

    def test_missing_is_distinct_from_measured_zero(self):
        missing, zero = score({}), score({}, self.signal(0))
        self.assertEqual(missing['notoriety'], -1)
        self.assertEqual(zero['notoriety'], 0)
        self.assertTrue(json.loads(missing['scoreEvidence'])['provisional'])
        self.assertFalse(json.loads(zero['scoreEvidence'])['provisional'])
        self.assertIn('ambigu', score({}, ambiguous=True)['scoreSource'])

    def test_ambiguous_evidence_cannot_be_used_as_an_exact_signal(self):
        with self.assertRaises(ValueError): score({}, self.signal(100), ambiguous=True)

    def test_landmark_can_be_three_stars_even_when_only_inscribed(self):
        m = score({'Typologie_de_la_protection': 'inscrit MH'}, self.signal(100))
        self.assertEqual(m['visualLevel'], 3)
        self.assertEqual(m['globalScore'], 90)
        self.assertEqual(score({'Typologie_de_la_protection': 'classé MH'}, self.signal(1))['visualLevel'], 1)

    def test_monotonic_bounded_and_fixed_thresholds(self):
        for protection in ('', 'inscrit MH', 'classé MH', 'classé MH ; inscrit MH'):
            scores = [score({'Typologie_de_la_protection': protection}, self.signal(n))['globalScore'] for n in range(301)]
            self.assertEqual(scores, sorted(scores))
            self.assertTrue(all(0 <= n <= 100 for n in scores))
        self.assertEqual([visual_level(n) for n in (54, 55, 74, 75)], [1, 2, 2, 3])
        for protection in ('classé MH', 'classée MH', 'classés MH', 'classement', 'inscrit MH ; classé MH'):
            self.assertEqual(score({'Typologie_de_la_protection': protection})['importance'], 70)
        for n in (-1, 1.5, True, '20'):
            with self.assertRaises(ValueError): score({}, self.signal(n))

    def test_exact_join_excludes_ambiguity_even_if_one_item_is_more_popular(self):
        def binding(ref, item, count):
            return dict(ref={'value': ref}, item={'value': 'http://www.wikidata.org/entity/' + item}, languages={'value': str(count)})
        records, ambiguous = exact_signals([
            binding('PA00000001', 'Q1', 2), binding('PA00000001', 'Q2', 200),
            binding('PA00000002', 'Q3', 0), binding('PA00000002', 'Q3', 0),
            binding('invalid', 'Q4', 90), binding('PA2A000001', 'Q5', 4)])
        self.assertEqual(set(records), {'PA00000002', 'PA2A000001'})
        self.assertEqual(ambiguous, {'PA00000001': ['Q1', 'Q2']})

    def test_raw_cache_counts_only_wikipedia_and_checks_uncached_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache, index = Path(tmp)/'cache.sqlite', Path(tmp)/'index.json'
            entity = dict(id='Q1', sitelinks={key: {} for key in ('frwiki', 'enwiki', 'simplewiki', 'commonswiki', 'specieswiki', 'frwikisource', 'frwikivoyage')},
                          claims={'P380': [dict(rank='normal', mainsnak={'datavalue': {'value': 'PA00000001'}}),
                                           dict(rank='deprecated', mainsnak={'datavalue': {'value': 'PA00000002'}})]})
            with sqlite3.connect(cache) as db:
                db.execute('CREATE TABLE cache (namespace TEXT,value_json TEXT,updated_at TEXT)')
                db.execute('INSERT INTO cache VALUES (?,?,?)', ('wikidata_entity', json.dumps(entity), '2026-08-22'))
            db.close()
            index.write_text(json.dumps({'results': {'bindings': []}}))
            records, ambiguous = cached_signals(cache, index)
            self.assertEqual(list(records), ['PA00000001'])
            self.assertEqual(records['PA00000001']['wikipedia_languages'], 3)
            self.assertEqual(records['PA00000001']['retrieved'], '2026-08-22')
            index.write_text(json.dumps({'results': {'bindings': [dict(ref={'value': 'PA00000001'}, item={'value': 'http://www.wikidata.org/entity/Q2'})]}}))
            records, ambiguous = cached_signals(cache, index)
            self.assertFalse(records)
            self.assertEqual(ambiguous, {'PA00000001': ['Q1', 'Q2']})

    def test_scope_review_selects_the_object_not_the_most_popular_neighbour(self):
        records, ambiguous = {}, {'PA00000001': ['Q1', 'Q2']}
        review = dict(item='Q1', source='https://pop.culture.gouv.fr/notice/merimee/PA00000001', reason='Menhir, not the adjacent cathedral')
        entities = {'Q1': ({'sitelinks': {'frwiki': {}}}, '2026-09-18'),
                    'Q2': ({'sitelinks': {str(i)+'wiki': {} for i in range(100)}}, '2026-09-18')}
        apply_scope_reviews(records, ambiguous, {'PA00000001': review}, entities)
        self.assertFalse(ambiguous)
        self.assertEqual(records['PA00000001']['wikipedia_languages'], 1)
        m = score({}, records['PA00000001'])
        self.assertEqual(m['visualLevel'], 1)
        self.assertEqual(json.loads(m['scoreEvidence'])['matching'], 'reviewed-monument-scope')


if __name__ == '__main__': unittest.main()
