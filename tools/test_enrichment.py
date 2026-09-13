import unittest
from enrich_wikipedia import exact_links, wiki_title
from monument_descriptions import enrich_description, pop_summary, SYNTHESIS_SOURCE

class EnrichmentTests(unittest.TestCase):
    def test_exact_identifiers_reject_ambiguity_and_non_french_articles(self):
        def binding(ref, title, host='fr'):
            return {'ref': {'value': ref}, 'item': {'value': 'http://www.wikidata.org/entity/Q1'},
                    'article': {'value': f'https://{host}.wikipedia.org/wiki/{title}'}}
        links, ambiguous = exact_links([binding('PA00087398', 'D%C3%A9sert_de_Retz'),
            binding('PA00000001', 'A'), binding('PA00000001', 'B'),
            binding('PA00000002', 'C', 'en'), binding('invalid', 'D')])
        self.assertEqual(set(links), {'PA00087398'})
        self.assertEqual(set(ambiguous), {'PA00000001'})
        self.assertEqual(wiki_title(links['PA00087398']['url']), 'Désert de Retz')
        self.assertEqual(wiki_title('https://fr.wikipedia.org.evil.test/wiki/Faux'), '')

    def test_pop_then_wikipedia_then_history_then_factual_summary(self):
        base = dict(reference='PA00000001', name='Ancien château', commune='Commune',
            departmentName='Département', description='', descriptionSource='',
            history='', historySource='POP / Mérimée', wikipediaUrl='', period='15e siècle (?)',
            category='château', protection='inscrit MH', protectionDetails='')
        page = dict(valid=True, url='https://fr.wikipedia.org/wiki/Château',
            title='Château', extract='Introduction encyclopédique.', revision=1234)
        fallback = pop_summary(base, {'Auteur_de_l_edifice': 'architecte inconnu'})
        self.assertIn('15e siècle (?)', fallback)
        self.assertIn('architecte inconnu', fallback)
        self.assertNotIn('ouvert au public', fallback)
        m = enrich_description(base.copy(), {'page': page}, fallback)
        self.assertEqual(m['description'], page['extract'])
        self.assertIn('CC BY-SA 4.0', m['descriptionSource'])
        self.assertIn('1234', m['descriptionSource'])
        m = enrich_description(base | {'description': 'Description POP.', 'descriptionSource': 'POP / Mérimée'}, {'page': page}, fallback)
        self.assertEqual(m['description'], 'Description POP.')
        m = enrich_description(base | {'history': 'Historique POP.'}, {}, fallback)
        self.assertEqual(m['description'], 'Historique POP.')
        m = enrich_description(base.copy(), {'page': page | {'valid': False}}, fallback)
        self.assertEqual(m['description'], fallback)
        self.assertEqual(m['descriptionSource'], SYNTHESIS_SOURCE)
        self.assertEqual(m['wikipediaUrl'], '')
        m = enrich_description(base.copy(), {'method': 'wikidata:P380-exact', 'url': page['url']}, fallback)
        self.assertEqual(m['wikipediaUrl'], page['url'])
        self.assertEqual(m['description'], fallback)
        m = enrich_description(base | {'description': 'La notice POP identifie ce monument sous le nom…', 'descriptionSource': 'POP'}, {'page': page}, fallback)
        self.assertEqual(m['description'], page['extract'])

if __name__ == '__main__': unittest.main()
