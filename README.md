# Le flâneur de France

Application Android de découverte des Monuments historiques français, créée comme
projet distinct du **Flâneur de Paris**. Kotlin, Compose Material 3, MapLibre, Room,
coroutines et Coil. Android 8.0 minimum ; aucune clé de carte nécessaire pour la V1.

Deux onglets : **Carte** et **Liste**. Carte nationale avec regroupements, recherche
locale dans tout le pays, position ponctuelle facultative, liste par distance et
fiche avec textes sourcés, scores, photographie à la demande et itinéraire externe.

La version 0.3.2 écarte des calculs géographiques les 216 positions tronquées au
degré, tout en conservant leurs notices consultables. Toucher un point partagé
par plusieurs monuments ouvre un choix avec leurs adresses et références.
La fermeture d’une fiche annule également sa recherche d’image en cours ;
les imports conservent la source de chaque texte lors de la fusion de doublons.

## Démarrer

Pour installer directement la V1 sur un téléphone ARM 64 bits :
[télécharger l’APK de test](dist/Les-Pierres-de-France-0.3.2-arm64.apk), puis l’ouvrir
sur Android. Autoriser l’installation depuis l’application qui ouvre le fichier si
Android le demande. La première préparation du catalogue prend quelques secondes.

Ouvrir ce dossier dans Android Studio, laisser Gradle synchroniser, puis lancer `app`.
Le SDK 36 et un JDK 17 ou 21 sont requis. Le wrapper Gradle est fourni.
La base est déjà générée dans `app/src/main/assets/monuments.db` : aucune préparation
de données n’est nécessaire pour compiler.
Après un clonage, exécuter `git lfs pull` pour récupérer la base complète. La
compilation refuse un pointeur Git LFS à la place du fichier SQLite.

```powershell
.\gradlew.bat :app:assembleDebug
```

APK de test pour les téléphones Android récents :
`app/build/outputs/apk/debug/app-arm64-v8a-debug.apk`.
Des variantes `armeabi-v7a` (anciens appareils 32 bits) et `x86_64` (émulateur)
sont également produites. L’APK est signé avec la clé de développement, pour les essais.
Identifiant Android : `fr.pierresdefrance`, distinct de `fr.parisfogofwar`.
Au premier démarrage, la base embarquée est copiée une seule fois en arrière-plan.
Une empreinte du fichier embarqué identifie chaque version du catalogue ; une mise
à jour APK contenant un nouveau catalogue ouvre automatiquement la nouvelle base.
Après validation de cette nouvelle base, les anciens catalogues sont supprimés.
Les autres bases de l’application sont conservées.

## Dataset et reconstruction

Inventaire de référence : export Mérimée du ministère de la Culture trouvé dans
`C:\Users\edoua\Downloads\merimee.csv`. Ce fichier de 100 Mo est laissé intact.
Il contient 46 760 notices, 77 colonnes UTF-8 séparées par `|`, avec une paire
`latitude,longitude` dans `coordonnees_au_format_WGS84`.

```powershell
python tools/build_monuments_db.py --input "C:\Users\edoua\Downloads\merimee.csv"
```

Si Python n’est pas dans le PATH sur cette machine :

```powershell
.\tools\rebuild.ps1 -SourceCsv "C:\Users\edoua\Downloads\merimee.csv"
```

Python 3.11+ suffit, sans pandas ni autre dépendance externe. Le pipeline lit le CSV
progressivement, valide ses colonnes, conserve les références corses et ultramarines,
normalise la recherche, sépare les coordonnées absentes/suspectes, conserve les
protections multiples et fusionne uniquement les lignes de même référence. Des noms
ou points identiques ne suffisent pas à fusionner deux références différentes.

Il produit une base SQLite atomiquement remplacée après contrôle d’intégrité et un
rapport `app/src/main/assets/dataset_report.json`. Une entrée mal formée est mise
en quarantaine ; une structure de CSV incompatible arrête l’import sans remplacer
la base précédente. Les lignes problématiques restent dans la table `source_rows`.
Une rupture de quoting empêchant d’identifier la fin d’une ligne nécessite de corriger
l’export source ; l’import ne tente pas de deviner les limites des notices.

Pour actualiser les enrichissements issus du Flâneur :

```powershell
python tools/import_flaneur.py --project "C:\Users\edoua\Documents\paris-fog-of-war"
python tools/build_monuments_db.py --input "C:\chemin\nouveau-merimee.csv"
```

Le snapshot `data/legacy_enrichment.json` permet de reconstruire sans avoir le projet
parisien sur l’autre ordinateur. Les enrichissements et liens sont associés par référence,
les cas ambigus écartés. Les anciens scores du Flâneur ne sont plus repris : le
[barème national v2](docs/NOTATIONS.md) combine une contribution limitée de la
protection avec le rayonnement encyclopédique, collecté par référence Mérimée exacte.
Les seuils sont fixes (55 et 75) ; aucun bonus ne dépend du type de monument, de la
date de protection ou de la longueur de sa notice. Les données absentes sont
signalées, et les notes correspondantes sont provisoires. Le snapshot
`data/scoring_enrichment.json` assure une reconstruction hors ligne ;
`python tools/enrich_scoring.py` permet de l'actualiser. Les correspondances Wikipédia sont complétées par le script
national décrit ci-dessous, à partir d’identifiants Mérimée exacts. Les descriptions
POP sont conservées ; les textes manquants sont complétés par Wikipédia ou une synthèse
factuelle des champs POP. Les synthèses sont explicitement identifiées.

## Descriptions et associations Wikipédia (0.3.0)

Les 46 760 notices ont un texte sourcé. La base contient 29 533 liens Wikipédia
(8 063 supplémentaires), et 1 784 descriptions Wikipédia déjà embarquées, dont
Passy-les-Tours et le Désert de Retz. Pour les autres fiches liées sans description
POP, l’introduction Wikipédia se charge à l’ouverture, en parallèle de la photo.
Le texte local reste visible pendant le chargement ou sans réseau. L’introduction
téléchargée est mise en cache sept jours et reste utilisable hors connexion après
expiration si son actualisation échoue. Les erreurs sont réessayées après cinq minutes.

Sans texte Wikipédia disponible, l’historique POP sert de présentation ; à défaut,
un condensé est composé automatiquement avec les faits renseignés : commune,
dénomination, période, auteurs, matériaux, état et protection. Les incertitudes des
champs source sont conservées. Aucun appel à un modèle n’est nécessaire.

Le script Python utilise la propriété [Mérimée P380 de Wikidata](https://www.wikidata.org/wiki/Property:P380)
pour trouver les articles français malgré les différences de titre. Il écarte les
nouveaux rapprochements ambigus et conserve leur liste dans `data/wikipedia_report.json`.
Les liens hérités sans nouvelle correspondance restent conservés. Il n’applique pas
de correspondance approximative fondée uniquement sur un nom. Les introductions
sont récupérées via [TextExtracts](https://www.mediawiki.org/wiki/Extension:TextExtracts),
avec redirections, contrôle des homonymies, cache SQLite, reprise et temporisation HTTP.
Les contributions Wikipédia sont attribuées sous CC BY-SA 4.0, avec liens vers
l’article, son historique et la licence ; Wikidata est sous CC0.

```powershell
# Actualiser tous les liens en réutilisant les textes déjà téléchargés (rapide).
python tools/enrich_wikipedia.py --refresh-index --links-only
# Télécharger les textes de références choisies ; exporter aussi tous les liens.
python tools/enrich_wikipedia.py --only-references PA00113040 PA00087398
# Optionnel : télécharger toutes les introductions, par lots. Peut être long selon
# les limites de Wikipédia ; une interruption conserve les lots déjà reçus.
python tools/enrich_wikipedia.py
# Reconstruire le catalogue avec le snapshot d’enrichissement obtenu.
python tools/build_monuments_db.py --input "C:\Users\edoua\Downloads\merimee.csv"
```

Les fichiers `data/wikipedia_enrichment.json` et `data/legacy_enrichment.json`
permettent une reconstruction sans réseau. Le cache et l’index national sont des
fichiers de travail du script et ne sont pas inclus dans l’APK.

Pour une nouvelle édition Mérimée : remplacer le chemin CSV, reconstruire, examiner
le rapport et les différences de compteurs, lancer les tests, puis compiler.
Le test Android qui fixe le total à 46 760 doit être adapté au nouveau snapshot
après vérification du rapport. La table `source_rows` aide à examiner les anomalies.

## Architecture et performances

| Élément | Rôle |
|---|---|
| `tools/build_monuments_db.py` | Import, normalisation, index, pyramide spatiale, rapport |
| `tools/national_scoring.py` | Barème national v2, seuils fixes et preuves par notice |
| `tools/enrich_scoring.py` | Collecte nationale du rayonnement par référence Mérimée exacte |
| `tools/audit_scoring.py` | Recalcul intégral, comparaison des notes et cohérence carte/liste |
| `data/MonumentDatabase.kt` | Room, fiche détaillée chargée par identifiant |
| `data/MonumentRepository.kt` | Projections carte/liste, FTS, bounding boxes, proximité |
| `domain/Geo.kt` | Distance, découpage spatial, recherche normalisée |
| `ui/DiscoveryViewModel.kt` | StateFlow, annulation, debounce et état des écrans |
| `ui/MapScreen.kt` | Couches GPU, clustering, lifecycle et sources séparées |
| `location/LocationProvider.kt` | Position ponctuelle, précision selon l’action, annulation |
| `data/ImageResolver.kt` | Commons par référence exacte, droits et cache de métadonnées |

La base comporte `monuments` (fiches complètes), `monument_list` (projection légère),
`monument_fts` (FTS4), `map_cells` (agrégats), `metadata` et `source_rows` (audit).
Room valide le schéma de `monuments` à la première ouverture ; les tables dérivées
sont produites par Python et testées sur SQLite Android. Elles ne sont pas éditées
sur le téléphone. Les futures données personnelles devront être dans une base
séparée, reliées à `reference`, pour survivre aux remplacements du catalogue.

Index : référence unique, nom normalisé, commune, département, coordonnées avec
projection couvrante, clé `(level,x,y)` des cellules et FTS4. La recherche élimine les
accents, développe les ligatures et accepte les préfixes de mots, avec pages de 50.
Elle ne fait pas de scan `LIKE '%texte%'` national.

À faible zoom, la carte reçoit uniquement les agrégats visibles. À partir du zoom 11,
elle reçoit au plus 6 000 points ; si une zone dépasse cette limite, elle reçoit
les agrégats correspondants, sans perdre les monuments excédentaires. MapLibre
regroupe les points ordinaires et donne priorité aux monuments majeurs. Les clics
sur les regroupements zooment ; les fiches ne sont chargées qu’à la sélection.
Marge de 20 %, requête après caméra idle + 220 ms, cache de la dernière zone.

La proximité choisit le premier rayon 1/2/5/10/20/50 km contenant au moins dix
monuments, puis trie par distance exacte. Le compteur couvre tout le rayon et la
liste montre jusqu’aux 200 plus proches. Cache de deux minutes et 250 m pour limiter
les variations. Sans position, la liste nationale reste consultable par nom.

## Images, cartes et hors connexion

### Rechercher une adresse sur la carte (0.3.0)

Le bandeau ne contient que le champ **Adresse ou ville**. Saisir au moins trois
caractères : après une pause de 350 ms, les propositions s’affichent automatiquement.
La loupe et la touche de recherche du clavier restent disponibles. Choisir un résultat : la carte se centre
sur ce lieu (repère brun) et la liste affiche les monuments autour, par distance.
Dans la liste, le libellé **Autour de…** rappelle l’origine des distances. Le point GPS bleu reste
distinct. Déplacer la carte ou revenir dans l’application ne remplace pas le lieu choisi.

Le bouton de géolocalisation rétablit la proximité autour de la position actuelle et
efface la recherche active, après obtention d’une position fiable. En cas de refus ou
d’échec GPS, le lieu choisi reste consultable. La recherche nationale de monuments
dans l’onglet Liste reste disponible ; effacer ses termes retrouve le centre choisi.

Le [géocodeur public IGN / Géoplateforme](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/geocodage/)
résout les adresses depuis la Base Adresse Nationale. Il nécessite Internet : seuls
les termes saisis à partir de trois caractères lui sont transmis, après temporisation,
sans position GPS ni historique.
Les requêtes obsolètes sont annulées et cinq résultats maximum sont proposés.
Une recherche échouée ne change pas le centre en cours. Après sélection, les calculs
de proximité et les notices restent locaux, y compris sans réseau. Le choix est conservé
en mémoire pendant la session, sans historique persistant.

Les images sont recherchées seulement à l’ouverture d’une fiche : référence Mérimée
exacte dans le fichier Commons, miniature 900 px, licence explicite et crédit.
Les rapprochements par nom ou seule proximité sont exclus. Les métadonnées positives
et négatives sont conservées sept jours, les erreurs réseau une heure. Coil assure
le cache des miniatures ; aucun lot de photographies n’est téléchargé à l’avance.
Un emplacement illustré remplace les images absentes ou inaccessibles.
Les requêtes de métadonnées et de miniatures identifient explicitement l’application
dans leur User-Agent, conformément à la [politique Wikimedia](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy).

Le fond OSM est demandé à la volée et géré par le cache MapLibre. Les compteurs sont
dessinés avec la police Android dans de petites icônes du moteur cartographique,
réutilisées par effectif et libérées lorsqu’elles ne servent plus. Ils fonctionnent
sans serveur de polices. L’attribution OpenStreetMap reste accessible sur la carte.
Aucun pack national de tuiles n’est téléchargé. Le fournisseur standard n’offre
pas de garantie de service ; configurer un fournisseur adapté avant une large diffusion.

Les notices, scores, recherche, liste et distances fonctionnent sans réseau. Une
zone cartographique jamais consultée peut apparaître avec le seul fond clair et
les monuments. Les liens externes dépendent du navigateur et du réseau ; l’application
ne prétend pas vérifier qu’une page distante existe. Aucun accès internet n’est
nécessaire pour ouvrir une fiche locale.

La position n’est ni enregistrée ni envoyée à un serveur applicatif. Aucun suivi
en arrière-plan, aucune télémétrie. Les fournisseurs de tuiles voient les zones
demandées, Commons voit la référence recherchée, Wikipédia voit le titre de l’article
consulté et l’IGN voit les termes saisis ; leurs requêtes passent directement
du téléphone à leurs services. La sauvegarde Android de l’application est désactivée.
L’ouverture demande une position équilibrée seulement si la permission est déjà accordée.
Le bouton de recentrage demande une position précise pendant au plus 15 secondes,
puis s’arrête ; quitter l’application annule également la demande.

## Vérification

```powershell
python -m unittest discover -s tools -p "test_*.py" -v
python tools/benchmark_dataset.py
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug
$env:ANDROID_SERIAL="emulator-5554"
.\gradlew.bat :app:connectedDebugAndroidTest
```

Les tests couvrent parsing, références corses, données manquantes, coordonnées
invalides et inversées, doublons, conservation de la base en cas d’échec, recherche
partielle, Haversine, antéméridien, rayon adaptatif, cache et règles de scoring.
Sur Android : ouverture Room de la base complète, recherches, zones France/Paris/
Bordeaux/Lyon, proximité urbaine/rurale, parcours recherche/fiche/carte, rendu des
regroupements et vues à différents zooms.

Pour l’émulateur Windows, utiliser le GPU matériel (`-gpu host`) et au moins 4 Go
de RAM sur l’image Pixel 10 / Android 17 employée ici. Son rendu logiciel SwiftShader
masque les symboles MapLibre dans les essais réalisés ; le test visuel le détecte.

Consulter [les corrections et tests sur téléphone 0.3.2](docs/VERIFICATION-0.3.2.md),
[la validation des notes 0.3.1](docs/VERIFICATION-0.3.1.md),
[le barème national](docs/NOTATIONS.md), [la validation 0.3.0](docs/VERIFICATION-0.3.0.md),
[l’analyse détaillée](docs/ANALYSE.md), [les mesures de la V1](docs/VERIFICATION.md)
et [le benchmark SQL complet](docs/benchmark-desktop.json).
