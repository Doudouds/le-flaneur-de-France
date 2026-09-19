# Validation 0.3.1 — 19 septembre 2026

## Révision nationale des notes

Les **46 760 notices** utilisent désormais le [barème national v2](NOTATIONS.md).
Le rayonnement encyclopédique est calculé à partir de réponses brutes Wikidata,
avec association Mérimée exacte et 54 revues de périmètre sourcées. Les anciennes
notes du Flâneur, dates de protection et longueurs de descriptions n'ajoutent
plus de points. Les seuils d'étoiles sont fixes : 55 et 75.

| Étoiles | Avant | Après |
|---|---:|---:|
| ★☆☆ | 34 321 | 44 943 |
| ★★☆ | 9 484 | 1 589 |
| ★★★ | 2 955 | 228 |

39 054 notices ont un rayonnement mesuré. Les **7 706 autres notes sont
provisoires**, dont 280 correspondances ambiguës non résolues. Une absence est
distincte d'un zéro mesuré et affichée par un tiret dans la fiche. Les 9 864
comptes effectivement nuls correspondent à des entités sans édition Wikipédia.
La couverture reste inégale et ces notes ne mesurent pas la qualité de visite.

Dans le regroupement religieux défini par l'audit, la part de deux ou trois
étoiles passe de 43,75 % à **4,52 %** ; pour les autres notices, de 19,16 % à
**3,61 %**. Aucun quota par catégorie n'a été utilisé. L'écart restant ne prouve
pas l'absence de biais dans les sources ; les signaux manquent notamment plus
souvent pour les autres catégories.

## Exemples vérifiés

| Monument | Référence | Avant | Après | Indice final |
|---|---|---|---|---:|
| Tour Eiffel | PA00088801 | ★☆☆ | ★★★ | 90 |
| Domaine de Versailles | PA00087673 | ★★☆ | ★★★ | 100 |
| Domaine de Chambord | PA00098405 | ★★☆ | ★★★ | 92 |
| Palais du Louvre et Tuileries | PA00085992 | ★☆☆ | ★★★ | 86 |
| Pont du Gard et aqueduc | PA00103291 | ★★★ | ★★★ | 92 |
| Abbaye du Mont-Saint-Michel | PA00110460 | ★★☆ | ★★★ | 77 |
| Cathédrale de Chartres | PA00096993 | ★★★ | ★★★ | 94 |
| Villa Savoye | PA00087573 | ★★☆ | ★★★ | 82 |
| Menhir Pierre Saint-Julien | PA00109848 | ★★★ | ★☆☆ | 45 |

Le menhir ne reçoit plus la notoriété de la cathédrale voisine. De même, un
alignement de Kerloquet n'hérite pas de celle de tout Carnac et les fortifications
des Cluses ne reçoivent pas le rayonnement de la commune. Les revues concernent
le sujet mesuré, sans imposer d'étoiles ni de bonus nominatifs.

## Audit de la base

- Chaque score a été recalculé et comparé à la notice livrée.
- Les projections de la liste et les scores de la carte sont cohérents avec les fiches.
- L'intégrité SQLite est valide.
- Les références, identifiants et tous les champs hors notation sont conservés,
  vérifiés par une empreinte commune avant/après.
- Les 46 760 notices conservent leur texte sourcé et les 29 533 liens Wikipédia.
- La mise à jour du catalogue est détectée par l'empreinte embarquée de l'APK.

Le [tableau CSV complet](scoring-audit.csv) contient une ligne par monument avec
ancienne note, nouvelle note, indicateur et source. Le [rapport JSON](scoring-audit.json)
contient les distributions, transitions, départements et listes des trois étoiles.

## Vérification et livraison

Les tests couvrent la neutralité par catégorie, la suppression des anciens bonus,
les seuils, l'incertitude, les ambiguïtés, les sites composés, la reconstruction
atomique et des monuments repères de périodes et catégories diverses.

Les preuves d'exécution sont enregistrées dans `docs/validation/`.
Les **14 tests Python**, **4 tests Kotlin** et **7 tests Android** ont réussi sur
la version finale. Les tests Android couvrent l'ouverture Room, les recherches,
les projections carte/liste, la fiche de la tour Eiffel, le fonctionnement hors
connexion, les descriptions et le rendu de la carte à plusieurs échelles.
Lint termine avec **0 erreur et 25 avertissements**. L'émulateur utilisé est
Pixel 10 / Android 17, avec 4 Go de RAM et GPU matériel.

L'APK ARM64 est disponible dans
[Les-Pierres-de-France-0.3.1-arm64.apk](../dist/Les-Pierres-de-France-0.3.1-arm64.apk).
Son catalogue embarqué est comparé par SHA-256 à la base auditée ; l'empreinte
de l'APK est conservée dans [SHA256SUMS.txt](../dist/SHA256SUMS.txt).
