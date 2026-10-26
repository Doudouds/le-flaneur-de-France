# Vérification 0.3.3 — 26 octobre 2026

Version Android `0.3.3`, code `6`, installée sur le Pixel 10a physique.

## Dernier état intégré

Le snapshot final [`data/coordinate_overrides.json`](../data/coordinate_overrides.json)
conserve 87 choix de positions : 79 points Monumentum, 2 retouches manuelles finales
et 6 retours explicites à la position d’origine. Les 81 positions différentes du
catalogue précédent sont appliquées ; les 6 restaurations sont conservées dans la
trace. Les 198 vérifications sont archivées localement avec leurs décisions,
commentaires, historique complet et export CSV. Les jugements « À vérifier »
restants dans l’outil PC ne modifient pas les dernières positions choisies.

Le JSON personnel exact, son CSV complet, l’ancienne base SQLite et son rapport
sont dans `data/coordinate_review_backups/final-application-20261026T213033264644Z/`,
ignoré par Git. Un manifeste y relie les empreintes des données et des APK avant
et après mise à jour. Les commentaires et décisions personnels ne sont pas
embarqués dans l’application ni publiés dans Git.

L’APK précédent `dist/Les-Pierres-de-France-0.3.2-arm64.apk` est conservé.
Le CSV ministère reste intact. À chaque reconstruction, le pipeline vérifie les
références et positions d’origine, applique le snapshot final, puis régénère les
16 niveaux de regroupement spatial. Une incohérence arrête la reconstruction
avant remplacement du catalogue.

## Contrôles

- 46 760 monuments, dont 44 266 positionnés ; 216 positions tronquées restent
  écartées des calculs géographiques.
- Comparaison intégrale avec la base archivée : exactement 81 paires de
  coordonnées changées, aucun autre champ de monument modifié.
- Les 87 choix finaux correspondent exactement aux fiches du catalogue.
- Intégrité SQLite, index de recherche et totaux des 16 pyramides spatiales valides.
- Sur téléphone, un test vérifie les coordonnées des 87 références dans leurs
  fiches et la présence de chacune sur la carte au point retenu.
- Après installation, le catalogue ouvert est `monuments-6f66e365e7400172.db`.

| Vérification | Résultat |
|---|---|
| Tests Python | 60 réussis |
| Tests unitaires Kotlin | 4 réussis |
| Tests Android sur Pixel 10a | 16 réussis, aucun échec |
| Lint | 0 erreur, 26 avertissements |
| APK et APK de tests | Compilation réussie |
| Mise à jour du téléphone | Installation avec conservation des données, version confirmée 0.3.3 |

Rapports : [comparaison des catalogues](validation/coordinate-review-0.3.3.json),
[Python](validation/python-tests-0.3.3.txt), [Kotlin](validation/kotlin-tests-0.3.3.xml),
[Android](validation/android-tests-0.3.3.txt), [lint](validation/lint-0.3.3.txt),
[compilation](validation/build-0.3.3.txt).

APK : [`Les-Pierres-de-France-0.3.3-arm64.apk`](../dist/Les-Pierres-de-France-0.3.3-arm64.apk).
SHA-256 : `607e56ad8c8fb2d7cd476aa4510ce01f7b3b1d3125eaa5e1868a14d85783451d`.

## Reproduire

```powershell
python -B tools/build_monuments_db.py --input "C:\Users\edoua\Downloads\merimee.csv"
python -B -m unittest discover -s tools -p "test_*.py" -v
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest
adb install -r -t app/build/outputs/apk/debug/app-arm64-v8a-debug.apk
adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w -r fr.pierresdefrance.test/androidx.test.runner.AndroidJUnitRunner
```
