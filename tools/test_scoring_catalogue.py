"""Regression anchors across eras and categories, using the delivered catalogue."""
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest


class CatalogueRatingTests(unittest.TestCase):
    def test_major_landmarks_and_scope_boundaries(self):
        path = Path(__file__).resolve().parents[1]/'app/src/main/assets/monuments.db'
        with closing(sqlite3.connect(path)) as db:
            for ref in (
                'PA00088801',  # Tour Eiffel: modern, inscribed only
                'PA00087673',  # Versailles: protected estate
                'PA00098405',  # Chambord: estate vs castle
                'PA00085992',  # Louvre palace, not the museum institution
                'PA00088804',  # Arc de Triomphe
                'PA00089004',  # Opera Garnier
                'PA00103291',  # Pont du Gard and aqueduct
                'PA00110460',  # Mont-Saint-Michel abbey, distinct from the commune
                'PA00096993',  # Chartres cathedral: religious landmarks still count
                'PA00087573',  # Villa Savoye: twentieth-century architecture
                'PA00088714',  # Invalides: whole complex vs church
                'PA00114578',  # Chantilly: estate vs castle
                'PA00086476',  # Place des Vosges: square vs its central garden
            ):
                with self.subTest(reference=ref):
                    self.assertEqual(db.execute('SELECT visualLevel FROM monuments WHERE reference=?', (ref,)).fetchone(), (3,))
            # Adjacency is not identity: neither a menhir beside a cathedral nor
            # a house within Mont-Saint-Michel inherits the enclosing site's fame.
            for ref in ('PA00109848', 'PA00110485', 'PA00091126', 'PA00103994', 'PA14000027'):
                with self.subTest(reference=ref):
                    self.assertEqual(db.execute('SELECT visualLevel FROM monuments WHERE reference=?', (ref,)).fetchone(), (1,))
