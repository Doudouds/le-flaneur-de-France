# Validation 0.3.0 — 12 septembre 2026

## Changements livrés

Le bandeau de la carte contient uniquement le champ d’adresse. Les suggestions
apparaissent après trois caractères et 350 ms de pause, sans appui sur la loupe.
Les requêtes remplacées sont annulées. Pour un nom court, des suggestions de villes
complètent les propositions de rues. Le choix d’un lieu et le retour GPS conservent
le comportement de la version 0.2.0.

Chaque notice possède une description et une source non vides. Les descriptions POP
sont conservées ; les textes manquants sont complétés par une introduction Wikipédia,
un historique POP ou une synthèse factuelle explicitement identifiée. Les synthèses
préservent les incertitudes et n’ajoutent ni horaires, ni accès public, ni faits inventés.

## Catalogue et script

| Contrôle | Résultat |
|---|---:|
| Notices | 46 760 |
| Descriptions et sources non vides | 46 760 |
| Liens Wikipédia | 29 533 |
| Nouveaux liens par rapport à 0.2.0 | 8 063 |
| Descriptions Wikipédia embarquées, anciennes et nouvelles | 1 784 |
| Textes POP / Mérimée, description ou historique | 24 182 |
| Synthèses factuelles POP | 20 678 |
| Textes hérités Wikidata / OpenStreetMap | 98 / 18 |
| Intégrité SQLite | ok |
| Taille de la base embarquée | 241 233 920 octets |

Le script `tools/enrich_wikipedia.py` utilise les références P380 exactes et les
sitelinks français de Wikidata. Il n’exige pas que le titre POP ressemble au titre
Wikipédia. L’index national signale 275 références ambiguës ; aucun nouveau lien
n’est choisi automatiquement dans ces cas. Le rapport conserve également les
différences avec les anciennes associations. Les associations héritées sans nouvelle
correspondance exacte sont conservées et ne sont pas toutes revérifiées.

Le téléchargement massif a rencontré des réponses HTTP 429. Le script respecte les
temporisations du serveur et permet de reprendre les lots. Le snapshot livré réutilise
1 322 pages mises en cache par le script ; 27 705 pages liées ne sont pas téléchargées
dans ce cache. Elles sont résolues à la demande dans Android lorsqu’un texte POP
descriptif manque, avec une présentation locale toujours disponible.

Les identifiants **PA00113040** (Château de Passy-les-Tours) et **PA00087398** (Désert
de Retz) ont une introduction Wikipédia embarquée et attribuée sous CC BY-SA 4.0.
L’interface donne accès à l’article, à ses contributeurs et à sa licence.

Rapports de données : [enrichissement Wikipédia](../data/wikipedia_report.json),
[catalogue](../app/src/main/assets/dataset_report.json).

## Vérifications

Environnement : émulateur Pixel 10, Android 17, x86_64, 4 Go de RAM, GPU matériel.

- Six tests Python réussis : pipeline, scoring, correspondances exactes et ambiguës,
  priorité des sources et synthèses factuelles.
- Quatre tests Kotlin réussis.
- Neuf tests Android réussis : catalogue complet, description sur chaque notice,
  parsing Wikipédia et homonymies, suggestions à trois lettres, choix ville/rue,
  erreur réseau, retour GPS, recherche et fiche hors connexion, rendu cartographique.
- Lint : zéro erreur, 21 avertissements de versions/API.
- Contrôle réel sur Bazeilles (**PA00078340**) : la synthèse embarquée est remplacée
  par l’introduction Wikipédia à l’ouverture, puis le texte est encore présent après
  redémarrage sans Wi-Fi ni données mobiles. Le réseau de l’émulateur est rétabli.

Les anciennes mesures de performances restent dans [VERIFICATION.md](VERIFICATION.md) ;
elles ne sont pas présentées comme des mesures de cette version.

Rapports : [Android](validation/android-tests-0.3.0.xml),
[Kotlin](validation/kotlin-tests-0.3.0.xml), [Python](validation/python-tests-0.3.0.txt),
[lint](validation/lint-0.3.0.txt).

Captures : [bandeau compact](screenshots/carte-compacte-030.png),
[suggestions automatiques « Bor » → Bordeaux](screenshots/suggestions-030.png),
[Wikipédia à la demande](screenshots/wikipedia-bazeilles-030.png),
[texte en cache hors ligne](screenshots/wikipedia-hors-ligne-030.png).

## Livraison

[APK ARM 64 bits 0.3.0](../dist/Les-Pierres-de-France-0.3.0-arm64.apk), signé avec
la clé de développement. Empreinte dans [SHA256SUMS.txt](../dist/SHA256SUMS.txt).
Les APK précédents sont conservés séparément.
