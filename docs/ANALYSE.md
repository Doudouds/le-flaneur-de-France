# Analyse préalable et décisions — 6 septembre 2026

## Projet de référence examiné

`C:\Users\edoua\Documents\paris-fog-of-war` (« Le Flâneur de Paris »).
Le projet original n’a pas été modifié.

Fichiers examinés : `Entities.kt`, `Daos.kt`, `RepositoriesImpl.kt`, `AppViewModel.kt`
(structure générale), `ParisApp.kt`, `MonumentDetailsBottomSheet.kt`, `MapScreen.kt`,
`MapConfig.kt`, `FusedLocationRepository.kt`, `Theme.kt`, configuration Gradle,
`DATA_ENRICHMENT.md`, les scripts d’enrichissement et l’asset `paris_monuments.json`.

| Sujet | Existant | Décision nationale |
|---|---|---|
| Stack | Kotlin 2.2.20, Compose, Room 2.8.4, MapLibre OpenGL 13.0.2, Coil 3.3 | Versions conservées ; pas de Hilt nécessaire pour trois écrans |
| Catalogue | Asset JSON de 1 969 monuments, décodage de toute la liste, flux `observeAll()` | Réécrit : base SQLite préconstruite, projections bornées, fiches à la demande |
| Description | Historique POP, descriptions locales/Wikipédia, source affichée | Réutilisation par référence exacte ; priorité au texte officiel fourni ; pas de texte généré |
| Images | Résolution Commons par référence, puis recherche géographique/nom ; contrôle des droits ; Coil | Référence exacte uniquement, licence explicite, miniature 900 px, cache des résultats et échecs ; aucune recherche par nom |
| Fiche | Bottom sheet, photo, étoiles, textes lisibles, liens POP/Wikipédia | Adaptée avec commune, trois scores, itinéraire, retour carte, crédit/licence cliquables |
| Scores | Script national déjà enrichi, calcul 60 % patrimoine / 40 % notoriété ; étoiles selon Paris | Fonctions de scoring conservées ; protection/dates Mérimée, enrichissements non ambigus par référence ; quantiles nationaux |
| Carte | MapLibre, sources GeoJSON, couches GPU, fond raster OSM, brouillard parisien | Même moteur ; suppression du brouillard et des zones ; pyramide nationale + clustering local |
| GPS | Haute précision toutes les secondes, découverte, service de suivi | Réécrit : demande ponctuelle au premier plan, annulation à la sortie, aucune permission de fond |
| Navigation | Compose Navigation, plusieurs onglets découverte/collection/statistiques/réglages | Deux destinations conservées en état Compose et une fiche modale ; pas de bibliothèque de navigation additionnelle |
| Thème | Material 3, bleu et jaune, clair/sombre | Pierre, bleu ardoise, anthracite, titres serif ; thèmes clair et sombre |

## CSV réellement analysé

Source : `C:\Users\edoua\Downloads\merimee.csv`, 100 062 530 octets.
Le second export Mérimée/OSM trouvé dans Downloads n’est pas l’inventaire de référence.
SHA-256 : `45bb2eaedf8e4fb77a73bd4122fbffe3519e18835d6c947c0fa3f8be8afce53f`.

Le CSV UTF-8 contient **77 colonnes**, séparées par `|`, des cellules citées et des retours
à la ligne internes. Les coordonnées sont `latitude,longitude` dans
`coordonnees_au_format_WGS84` ; ce n’est pas du GeoJSON. Les références sont des chaînes,
y compris `PA2A…` et `PA2B…` : les traiter comme des nombres ou comme uniquement des chiffres
perdrait des notices corses.

Résultat final : 46 760 lignes et références uniques ; 44 484 paires numériques,
2 276 coordonnées absentes ; deux paires suspectes mises en quarantaine, soit
44 482 positions affichables. Les deux anomalies sont :

- `PA95000004` : `1.9968162410986903,49.1631330999842` ; paire apparemment inversée.
- `PA97200009` : `14,-61` ; point hors de l’enveloppe de la Martinique et manifestement peu précis.

Ces notices restent consultables. Aucune correction géographique n’est inventée.
Les anciens codes 971 incluant Saint-Martin/Saint-Barthélemy sont pris en compte.
Les enveloppes sont un contrôle grossier, pas une validation cadastrale ou communale.
128 groupes ont des coordonnées identiques : ils ne sont pas fusionnés automatiquement.
2 562 notices contiennent à la fois une protection classée et inscrite ; les protections
et leurs précisions restent dans la même notice. Les liens vers ensembles et parties sont
présents dans la source ; ils ne justifient pas une fusion entre références distinctes.

La description architecturale est rare (925 notices), l’historique plus fréquent
(24 819 notices). Après reprise du Flâneur, 26 118 notices ont une description ou un
historique. Aucun fichier image n’est embarqué. Le rapport généré recense les colonnes,
les cellules manquantes et les distributions territoriales.

## Scores et sources

`tools/heritage_scoring.py` reprend textuellement les fonctions pures de
`tools/enrich_monuments.py` du Flâneur : protection, ancienneté de protection,
caractère exceptionnel, UNESCO prouvé, autres protections et intérêt documentaire.
`Resolver` traduit les colonnes du nouveau CSV vers les entrées de ces fonctions.
Les indicateurs non présents dans le CSV ne sont pas devinés.

L’export historique contient 46 381 lignes. Les entités réunissant plusieurs références,
les dossiers signalés à vérifier et 312 groupes de scores/liens contradictoires sont exclus
de la reprise automatique. **42 715 enrichissements de scoring** sont réutilisés sur le
catalogue final. La protection et l’ancienneté sont recalculées avec les colonnes Mérimée
pour toutes les notices. Les composantes complémentaires prennent le maximum entre
les éléments locaux et l’enrichissement historique exact, sans additionner deux fois
le même critère. La notoriété historique est conservée ; sans mesure, le plancher
explicite reste 2. Chaque résultat conserve ses composantes et les valeurs historiques
en JSON. Les fonctions et les poids n’ont pas changé.

Cette adaptation corrige un défaut constaté le 12 septembre : l’ancien export OSM
attribuait 3 points de patrimoine à Chambord, faute de données de protection. Les
mêmes règles alimentées par Mérimée donnent 60 ; sa notoriété reste signalée comme
non mesurée. Une valeur historiquement calculée sur des données absentes ne doit pas
écraser une protection connue dans le CSV de référence.

Les quantiles nationaux donnent 37 points pour le niveau 2 et 49 pour le niveau 3.
Les ex æquo sont conservés ensemble. Les poids 60/40 ne changent pas.
La notoriété ancienne peut être datée : l’import conserve sa période quand elle existe.
Les futures métriques peuvent être introduites en amont dans l’enrichissement par référence.

## Choix spatial et cartographique

MapLibre était déjà installé et maîtrisé dans le projet original : changer de moteur
aurait ajouté du travail sans avantage identifié. Il dessine des couches GPU sans vue
Android par monument. Les conditions des fonds restent indépendantes du moteur.

- Vue nationale : cellules Web Mercator préagrégées aux niveaux 3–18, clé primaire
  `(level,x,y)`, effectif exact de la cellule et représentant le plus important.
- Niveau de cellule = `floor(zoom)+3`. À zoom < 11, seules les cellules intersectant
  la zone et sa marge sont transmises, sans parcourir les 44 482 points.
- À zoom ≥ 11, index couvrant `(latitude,longitude,id,globalScore,visualLevel)`, 6 001 candidats au
  maximum. Si ce plafond est dépassé, retour aux cellules : pas de troncature cachée.
- Points ordinaires : clustering MapLibre, rayon 42 px, décomposition jusqu’au zoom 16.
  Les monuments à score ≥ 65 utilisent une couche distincte, dessinée au-dessus.
- Position et sélection ont chacune leur source ; leur mise à jour ne reconstruit pas
  les monuments. Les conversions GeoJSON tournent sur `Dispatchers.Default`.
- Événement caméra idle + délai de 220 ms, annulation des résultats périmés, marge 20 %
  et réutilisation de la zone précédente au même niveau de cellule.

Un cluster préagrégé représente une cellule entière, y compris sa portion en marge du
viewport. Son compteur n’est donc pas un décompte strict des seuls pixels visibles.
Les points exactement superposés restent tous accessibles par la liste/recherche.

## Recherche et proximité

FTS4 est utilisé pour la compatibilité avec SQLite Android à partir d’API 26. Les champs
sont normalisés en amont : minuscules, accents retirés, ligatures développées, ponctuation
transformée en espaces. Les termes sont assainis avant d’ajouter `*`. L’AND implicite
(espace) fonctionne aussi sur les builds Android sans grammaire FTS enrichie.
Une table légère `monument_list` évite les lectures des descriptions pendant la recherche.
Tri : nom exact, préfixe de nom, autres correspondances ; puis score, nom et identifiant.
Pages de 50 lignes, identifiants stables dans LazyColumn.

La proximité utilise les rayons 1/2/5/10/20/50 km, le premier contenant au moins dix
monuments. En zone très dense, un rayon de 1 km peut dépasser trente résultats.
Seuls les identifiants/coordonnées de la bounding box sont lus, puis filtrés au rayon
exact par Haversine. Les 200 plus proches sont affichés ; le compteur couvre tout le rayon.
Le résultat est réutilisé pendant deux minutes si le déplacement est inférieur à 250 m.
Sans localisation, la liste nationale est disponible par ordre alphabétique.

## Références techniques vérifiées

- [MapLibre Android, clustering de couches](https://maplibre.org/maplibre-native/android/examples/styling/circle-layer/)
- [Options des sources GeoJSON](https://maplibre.org/maplibre-native/android/api/-map-libre%20-native%20-android/org.maplibre.android.style.sources/-geo-json-options/index.html)
- [Politique des tuiles OSM](https://operations.osmfoundation.org/policies/tiles/)

Le style local fonctionne sans charger une configuration distante. Les tuiles OSM sont
demandées à la volée. Les nombres des clusters sont des icônes créées avec la police
Android, sans requête de glyphes distante. Le fond n’est pas garanti
hors connexion en dehors du cache ; les notices, la recherche et la liste sont locales.
Un fournisseur de tuiles adapté au trafic attendu devra être choisi avant
une diffusion publique importante. Il n’y a aucun préchargement massif de tuiles.

Lors de la reprise du 11 septembre, MapLibre est passé de 13.0.2 à 13.6.0, puis validé
sur le catalogue complet. Les versions et changements du moteur sont publiés dans
[ses notes officielles](https://github.com/maplibre/maplibre-native/releases/tag/android-v13.6.0).
Le rendu logiciel SwiftShader de l’émulateur utilisé n’affiche pas les symboles, même
quand ils sont présents dans les données du moteur. La validation utilise donc le GPU
matériel et vérifie aussi des pixels des nombres à l’intérieur des clusters.
