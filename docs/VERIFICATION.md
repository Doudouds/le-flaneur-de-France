# Validation de la V1 — septembre 2026

Les contrôles portent sur le catalogue complet fourni, pas sur un échantillon.
L’application est un projet Android distinct du Flâneur de Paris, qui reste intact.

## Catalogue livré

| Donnée | Résultat |
|---|---:|
| Notices uniques Mérimée | 46 760 |
| Positions affichables | 44 482 |
| Coordonnées absentes | 2 276 |
| Coordonnées suspectes, écartées de la carte | 2 |
| Notices avec description ou historique | 26 118 |
| Notices bénéficiant de l’enrichissement historique de scoring | 42 715 |
| Liens Wikipédia | 21 470 |
| Taille SQLite embarquée | 207 282 176 octets, soit 198 Mio |
| Vérification SQLite | `integrity_check = ok` |

Les deux notices sans position fiable restent recherchables et consultables ; leur
bouton d’itinéraire est désactivé. Aucune coordonnée n’a été inventée. Le rapport
complet est dans `app/src/main/assets/dataset_report.json`.

## Tests automatisés

La suite comprend quatre tests Python, quatre tests Kotlin et cinq tests Android.
Tous ont réussi sur la version finale du 12 septembre : 13 tests, aucun échec ni
test ignoré. Lint : zéro erreur, 21 avertissements de versions/API. Les rapports
Android, Kotlin et lint sont conservés dans `docs/validation/`.
Le parcours de localisation a été ajouté après correction de la précision demandée
lors d’un recentrage explicite. Le test Python de scoring empêche une ancienne valeur
sans protection de remplacer les faits Mérimée et vérifie la conservation des
enrichissements complémentaires, de la notoriété et des poids 60/40.

- Import : colonnes et quoting, coordonnées, références corses, doublons, protections,
  FTS, scoring historique et conservation de la base précédente si l’import échoue.
- Kotlin : Haversine, préfixes sans accents, antéméridien, rayon adaptatif et cache.
- Android : ouverture Room du catalogue, recherche nationale, bounding boxes, proximité
  urbaine/rurale, parcours recherche → fiche → carte.
- Hors connexion : Wi-Fi et données désactivés pendant le test ; recherche de
  `PA95000004`, ouverture de la notice et vérification de l’itinéraire désactivé.
- Carte : France entière, Paris, Bordeaux, Cévennes et zoom de quartier ; les nombres
  sont vérifiés par des pixels clairs à l’intérieur des clusters, en plus des données
  rendues par MapLibre.

## Mesures

Environnement Android : émulateur Pixel 10, Android 17, x86_64, 4 Go de RAM, GPU
matériel AMD Radeon 780M via l’émulateur Windows. APK de développement, sans profil
de compilation de production. Les mesures ne constituent pas une garantie sur téléphone.

| Mesure Android finale du 12 septembre | Résultat |
|---|---:|
| Quatre recherches nationales, total | 44 ms |
| Quatre requêtes de viewport, total | 48 ms |
| Deux calculs de proximité, total | 30 ms |
| Entités rendues à Paris / Bordeaux / Cévennes | 74 / 42 / 3 |
| Zoom animé de Paris, frames de fenêtre observées | 176 |
| Durée p95 des frames pendant ce zoom | 37,01 ms |
| Première fenêtre, installation neuve (`am start -W`) | 4,61 s |
| Monuments nationaux visibles après installation neuve | au plus 10,33 s |
| Redémarrage du processus, catalogue déjà copié | 2,26 s |
| Mémoire relevée en usage carte/liste/fiche | environ 101–128 Mio PSS |

L’installation neuve inclut la préparation de la base locale ; un écran de progression
reste visible pendant cette étape. Le temps de carte est une borne supérieure mesurée
par captures successives et détection des marqueurs, avec le coût de capture inclus.
La mémoire RSS, qui inclut des pages partagées, était d’environ 214–241 Mio. Ce sont
des relevés ponctuels, pas une mesure du pic ni un test prolongé de fuite mémoire.

Cette mesure de frames porte sur la fenêtre Android ; ce n’est pas un profil complet
du GPU MapLibre. Elle ne permet pas d’affirmer un maintien à 60 images/s. La validation
sur téléphone physique, en particulier un appareil moins puissant, reste à effectuer.

Benchmark SQLite sur le PC, 30 répétitions, base complète :

| Requête | Résultats | Médiane | p95 |
|---|---:|---:|---:|
| Zone Paris | 2 005 | 2,10 ms | 3,53 ms |
| Zone Bordeaux | 385 | 0,43 ms | 0,54 ms |
| Recherche Chambord | 4 | 0,08 ms | 0,26 ms |
| Recherche « église », première page | 50 | 12,61 ms | 15,34 ms |
| Agrégats nationaux | 27 | 0,07 ms | 0,15 ms |

Voir `benchmark-desktop.json` pour les autres villes, les premières exécutions et
les plans de requête. Les chiffres PC ne sont pas des temps d’affichage Android.

## Points vérifiés et limites

Le rendu logiciel SwiftShader de l’émulateur masquait les symboles MapLibre, dans les
versions 13.0.2 et 13.6.0 essayées. Les essais avec le GPU matériel affichent les nombres.
Une première exécution sur un émulateur de 2 Go a aussi été arrêtée par Android pour
manque de mémoire ; les tests ont été repris sur la configuration de 4 Go indiquée.

La recherche Commons de la référence exacte de Chambord (`PA00098405`) a été vérifiée
en ligne : des fichiers avec cette référence unique et une licence CC BY-SA 4.0 sont
retournés. La résolution et les miniatures restent tributaires du réseau. Une photographie
absente ou inaccessible conserve le placeholder ; aucun rapprochement par nom n’est tenté.
Le refus HTTP 403 des miniatures avec l’agent générique OkHttp a été reproduit ; les
requêtes identifiées `LesPierresDeFrance/0.1` ont reçu HTTP 200. Le chargeur d’images
utilise donc le même User-Agent explicite que le résolveur de métadonnées.
La miniature a ensuite été chargée et contrôlée visuellement dans l’application.
Le recentrage GPS simulé à Paris affiche un point bleu et 537 notices dans un rayon
de 1 km ; la liste commence à 30 m et ses distances augmentent. Le bouton d’itinéraire
ouvre Google Maps sur l’émulateur ; le guidage routier lui-même n’a pas été testé.

Le fond de carte non déjà mis en cache nécessite Internet. Le catalogue, les descriptions
embarquées et la recherche fonctionnent sans réseau. Les liens POP/Wikipédia s’ouvrent
dans une application externe ; l’application ne vérifie pas l’existence de toutes les
pages distantes. Le choix d’un fournisseur de tuiles dimensionné au trafic et une signature
de production restent à prévoir pour une diffusion publique.

## Livraison et captures

`dist/Les-Pierres-de-France-0.1.0-arm64.apk` : 71 238 118 octets (environ 71 Mo),
Android 8.0+, ARM 64 bits, signé avec la clé de développement. La signature APK v2
a été vérifiée avec `apksigner`. L’empreinte est dans `dist/SHA256SUMS.txt`.
Les variantes ARM 32 bits et x86_64 restent dans `app/build/outputs/apk/debug/`.

- [Carte nationale](screenshots/carte-france.png)
- [Paris](screenshots/carte-paris.png) et [quartier](screenshots/carte-paris-quartier.png)
- [Bordeaux](screenshots/carte-bordeaux.png) et [Cévennes](screenshots/carte-rural.png)
- [Position simulée](screenshots/localisation.png) et [liste par distance](screenshots/liste-proximite.png)
- [Fiche de Chambord avec photo](screenshots/fiche-chambord.png) — photo de Pierre André Leclercq,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  [source Commons](https://commons.wikimedia.org/wiki/File:Chambord_Et%C3%A92016_exposition_de_Cal%C3%A8ches_au_ch%C3%A2teau_(4).jpg).

## Reproduire

```powershell
python -m unittest discover -s tools -p "test_*.py" -v
python tools/benchmark_dataset.py
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug
$env:ANDROID_SERIAL="emulator-5554"
.\gradlew.bat :app:connectedDebugAndroidTest
.\gradlew.bat :app:assembleDebug
```

Le test de localisation utilise une position simulée via Google Play Services et
rétablit le mode de simulation après exécution. Il nécessite une image d’émulateur
avec Google Play Services. Aucun historique réel de déplacement n’est collecté.
