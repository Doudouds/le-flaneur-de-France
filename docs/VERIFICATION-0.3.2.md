# Vérification 0.3.2 — 25 octobre 2026

Version Android : `0.3.2`, code `5`. Tests effectués sur un Pixel 10a physique,
Android 17 / API 37, avec l’APK ARM64 disponible dans `dist/`.

## Corrections vérifiées

- Les 216 couples de coordonnées tronqués au degré sont classés
  `suspect_precision`, conservés dans l’audit et exclus de la carte et des
  distances. Les 46 760 notices restent consultables ; 44 266 sont positionnées.
  Le stade Chaban-Delmas (`PA33000253`) ne produit plus de faux itinéraire vers
  `(44,0)`. Aucun emplacement de remplacement n’est inventé.
- Un clic réel sur le point de Pérouges partagé par 13 notices ouvre un choix
  avec adresses et références. Le test ouvre deux notices différentes puis
  vérifie qu’un monument isolé s’ouvre directement. La sélection utilise l’ID
  stable du monument : les coordonnées GeoJSON peuvent être arrondies par le
  moteur cartographique.
- Les anciens catalogues sont supprimés dans le callback d’ouverture Room,
  après validation de leur remplacement. Le test vérifie l’absence de
  suppression avant ouverture et la conservation du contenu de deux bases
  sans rapport avec les anciens catalogues. Une seule base de 236 670 976
  octets est présente sur le téléphone après les tests.
- L’annulation d’une recherche d’image annule aussi l’appel HTTP. Les tests
  couvrent une réponse tardive, l’absence de faux cache négatif après annulation
  et la réutilisation des résultats positifs et négatifs.
- La fusion de doublons conserve ensemble chaque texte et sa source, même si
  description et historique apparaissent seulement dans la deuxième ligne.
- La compilation refuse une base absente ou un pointeur Git LFS non extrait.

## Résultats

| Vérification | Résultat |
|---|---|
| Tests Python du pipeline, des enrichissements et des scores | 15 réussis |
| Tests unitaires Kotlin | 4 réussis |
| Tests Android sur le Pixel 10a | 15 réussis, aucun ignoré |
| Lint Android | 0 erreur, 26 avertissements |
| Assemblage APK et APK de tests | Réussi |
| Intégrité SQLite et sommes de toutes les pyramides spatiales | Réussies |

Le résultat complet de la dernière exécution sur téléphone est conservé dans
[`validation/android-tests-0.3.2.txt`](validation/android-tests-0.3.2.txt).
Les recherches, fiches hors ligne, suggestions d’adresses, recentrage GPS,
listes par distance et rendus nationaux/urbains/ruraux font partie de cette suite.

Le scénario de zoom à Paris relève 178 trames de fenêtre, avec un 95e percentile
de 3,87 ms. Le [benchmark SQL sur PC](benchmark-desktop.json) relève des médianes
de 1,53 ms pour la projection de Paris et de 10,13 ms pour la recherche « église ».
Ces mesures décrivent les scénarios exécutés sur ces appareils.

## Reproduire

```powershell
git lfs pull
python -m unittest discover -s tools -p "test_*.py" -v
python tools/benchmark_dataset.py
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest
adb install -r -t app/build/outputs/apk/debug/app-arm64-v8a-debug.apk
adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w -r fr.pierresdefrance.test/androidx.test.runner.AndroidJUnitRunner
```

Le lancement direct du runner conserve l’application installée après les tests.
La suite rétablit les réglages réseau et la simulation GPS après ses scénarios.

APK livré : `dist/Les-Pierres-de-France-0.3.2-arm64.apk`.
SHA-256 : `e0afcce09452b81c93f26ee1ca466b9370c28973089d4159794d9892b7081eff`.
