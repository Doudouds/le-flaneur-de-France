# Validation de la recherche d’adresse — 0.2.0

Contrôles du 12 septembre 2026 sur émulateur Pixel 10, Android 17, x86_64,
4 Go de RAM, GPU matériel. Le catalogue embarqué reste celui de la V1.

## Résultats

- Compilation des APK : réussite ; version Android 0.2.0, code 2.
- Quatre tests Kotlin : réussite, aucun échec.
- Sept tests Android : réussite, aucun échec ni test ignoré.
- Lint : zéro erreur, 21 avertissements de versions/API.

Les nouveaux tests Android contrôlent le parsing GeoJSON IGN, l’ordre longitude /
latitude, les résultats invalides et les doublons. Le parcours d’interface avec
géocodeur injecté couvre le choix d’une ville puis d’une rue, les distances et
l’origine de la liste, ainsi que la conservation du lieu lors d’une recherche vide
ou d’une erreur réseau. Le test de localisation utilise une position GPS simulée
pour vérifier que le bouton rétablit les monuments proches de l’utilisateur et
efface la recherche active. Une demande GPS automatique ne remplace pas le lieu choisi.

Les tests existants du catalogue complet, des recherches, des fiches hors connexion
et du rendu cartographique ont également été exécutés. Les scripts Python et les
données n’ont pas changé ; leur précédente validation et les mesures de performance
de la V1 restent décrites dans [VERIFICATION.md](VERIFICATION.md).

Rapports conservés : [Android](validation/android-tests-0.2.0.xml),
[Kotlin](validation/kotlin-tests-0.2.0.xml), [lint](validation/lint-0.2.0.txt).

## Vérification réelle du service d’adresses

Une recherche de **Bordeaux** depuis l’application installée a reçu les résultats
du service IGN public. Le choix de la commune de Gironde a centré la carte sur les
coordonnées renvoyées et affiché **14 monuments à moins de 1 km**. La liste indiquait
**Autour de Bordeaux**, avec les premières distances 222 m, 521 m, 524 m et 561 m.
Le repère brun et les regroupements de monuments étaient visibles sur la carte.

- [Résultats d’adresses](screenshots/recherche-adresse.png)
- [Carte centrée sur Bordeaux](screenshots/carte-bordeaux-adresse.png)
- [Liste autour du lieu choisi](screenshots/liste-bordeaux-adresse.png)

La recherche d’adresse nécessite Internet. Les calculs de proximité et les notices
restent locaux après sélection. Le choix est conservé pendant la session.

## APK livré

[Les-Pierres-de-France-0.2.0-arm64.apk](../dist/Les-Pierres-de-France-0.2.0-arm64.apk)
est l’APK de développement ARM 64 bits. Son empreinte SHA-256 figure dans
[SHA256SUMS.txt](../dist/SHA256SUMS.txt). La version 0.1.0 est conservée séparément.
