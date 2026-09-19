# Barème national des monuments — version 2

Les étoiles servent à repérer des monuments pour une promenade. Elles ne sont ni
une note de visiteurs, ni une expertise complète de leur valeur architecturale,
ni une garantie d'ouverture. La notation précédente sous-évaluait notamment la
tour Eiffel et favorisait indirectement les édifices religieux.

## Diagnostic

Sur les 46 760 notices de la version 0.3.0, la tour Eiffel (PA00088801) avait
une étoile et un indice de 25. Son rayonnement était inconnu, mais remplacé par
une note de 2/100. L'ancien calcul privilégiait le statut patrimonial, la date
de protection et la quantité de documentation ; les étoiles étaient ensuite
attribuées par quantiles nationaux. La date de protection n'est pourtant pas
une mesure de l'intérêt de visite, et une donnée absente n'est pas une mauvaise note.

Les édifices religieux représentaient 14 150 notices : 43,75 % avaient deux ou
trois étoiles, contre 19,16 % des 32 610 autres notices. Ce regroupement est un
outil d'audit fondé sur la dénomination Mérimée, pas un critère de notation.
Il inclut églises, cathédrales, chapelles, abbayes, couvents, prieurés, basiliques,
temples, synagogues et mosquées ; il n'est pas une classification exhaustive.

## Deux indices homogènes et des seuils fixes

1. **Protection patrimoniale** : classé MH = 70/100, inscrit MH = 50/100,
   statut non reconnu = 30/100. Le statut le plus fort prévaut si plusieurs
   protections coexistent. Sa contribution à l'indice final est de **35, 25
   ou 15 points**. On ne déduit pas une protection partielle de mots comme
   « façade » ou « clocher ».
2. **Rayonnement encyclopédique** : nombre d'éditions linguistiques de Wikipédia
   possédant un article lié au monument. Le score est
   `R = min(100, arrondi(100 × ln(max(1, langues)) / ln(100)))`.
   La progression est logarithmique pour distinguer les lieux connus sans laisser
   les très grands monuments écraser les autres. Une édition donne 0, dix donnent
   50 et cent ou davantage donnent 100. Cette composante contribue jusqu'à
   **65 points**.

L'indice final est `min(100, arrondi(0,5 × protection + 0,65 × R))`.
L'arrondi est arithmétique, une demi-unité étant arrondie vers le haut.

| Indice | Étoiles | Lecture |
|---|---|---|
| Moins de 55 | ★☆☆ | Monument à découvrir |
| 55 à 74 | ★★☆ | Intérêt notable, rayonnement établi |
| 75 à 100 | ★★★ | Monument remarquable, fort rayonnement |

Ces poids et seuils sont des choix éditoriaux explicites, pas des paramètres
statistiquement validés sur des avis de voyageurs. Ils limitent l'effet du statut
administratif et permettent à un monument inscrit mais très connu d'obtenir
trois étoiles. Le seuil des trois étoiles a été calibré sur des sites de périodes
et catégories diverses, dont la tour Eiffel, les grands domaines, le pont du Gard,
la villa Savoye et l'abbaye du Mont-Saint-Michel (distincte de la commune dans
Wikipédia). Aucune exception nominative n'est prévue pour la tour Eiffel.

Ni la religion, ni la catégorie, ni la période de construction, ni la date de
protection, ni la longueur du texte, ni la présence d'un architecte nommé
n'ajoutent de points. Aucun quota par catégorie ou département n'est imposé.
Les seuils sont absolus : ajouter une notice ne change pas la note des autres.

## Données, incertitudes et traçabilité

Le statut est lu dans le CSV Mérimée. Le rayonnement est collecté nationalement
par `tools/enrich_scoring.py`, avec la propriété
[Mérimée P380](https://www.wikidata.org/wiki/Property:P380). Les associations se
font automatiquement par référence exacte. Plusieurs entités revendiquant la même
référence entraînent une mise à l'écart, sans sélectionner la plus populaire.
Les grands ensembles et certaines ambiguïtés font ensuite l'objet d'une revue
de périmètre dans `data/scoring_scope_reviews.json` : l'édifice principal doit être
explicitement compris dans la notice POP, et la décision cite cette notice avec
son motif. Cela rattache, par exemple, le domaine de Chambord à son château,
mais empêche le menhir Pierre Saint-Julien d'hériter de la notoriété de la
cathédrale voisine. Ces revues sélectionnent l'objet mesuré ; elles n'imposent
jamais un nombre d'étoiles ou un bonus de points.
Seuls les sites du groupe Wikipédia sont comptés : Commons et les autres projets
Wikimedia sont exclus. Les
[liens de sites Wikidata](https://www.wikidata.org/wiki/Help:Sitelinks) sont des
liens éditoriaux, pas une mesure de fréquentation réelle.

Un signal absent ou ambigu est stocké comme inconnu (`notoriety = -1`), affiché
par un tiret, et la note est explicitement provisoire dans la fiche. Seule la
contribution de protection est alors disponible. Un zéro effectivement mesuré
reste distinct d'une absence. Une étoile ne démontre donc pas un faible intérêt.
La couverture de Wikipédia reste inégale : elle peut sous-estimer des sites
locaux, récents ou ultramarins. Ce modèle réduit les biais identifiés, sans
prétendre supprimer tous les biais de documentation.

Le snapshot `data/scoring_enrichment.json` conserve le mode de collecte, les dates,
les entités, les comptes, les ambiguïtés et la licence CC0. La collecte SPARQL
en direct conserve sa requête et l'empreinte de sa réponse. Chaque
notice conserve le modèle, les contributions, la référence de source et la date
dans `scoreEvidence`. Les anciens scores importés du Flâneur ne sont plus utilisés.
Les textes, images et liens hérités restent des enrichissements indépendants.

Le snapshot livré utilise les réponses brutes de l'API Wikidata déjà présentes
dans le cache du projet parisien (collectées entre août et septembre 2026).
Chaque référence garde la date de sa réponse, et les empreintes du cache et de
l'index national sont conservées. Les éditions Wikipédia sont recomptées dans
les liens de sites bruts ; aucun ancien score n'est converti ou réutilisé.
Les candidats supplémentaires de l'index national sont pris en compte pour
détecter les ambiguïtés, même si leur réponse individuelle manque du cache.
La collecte SPARQL en direct a reçu HTTP 429 et a été arrêtée pendant son délai de
temporisation. Les entités absentes du cache sont complétées par lots via l'API,
à partir de l'index national exact, avec sauvegarde de chaque lot et respect des
délais HTTP. La date propre à chaque entité distingue les données réutilisées
des compléments téléchargés pour cette révision.

## Reproduction et contrôle

```powershell
python tools/enrich_scoring.py
python tools/audit_scoring.py --capture
python tools/build_monuments_db.py --input "C:\Users\edoua\Downloads\merimee.csv"
python tools/audit_scoring.py
python -m unittest discover -s tools -p "test_*.py" -v
```

Pour réutiliser le cache brut existant et compléter l'index national :

```powershell
python tools/enrich_scoring.py --entity-cache "C:\Users\edoua\Documents\paris-fog-of-war\outputs\heritage_enrichment\heritage_cache.sqlite3" --complete-index
```

Le cache complémentaire `data/scoring_api_cache.sqlite` permet de reprendre une
collecte interrompue ; il est un fichier de travail ignoré par Git. Le snapshot
JSON final contient les indicateurs nécessaires à la reconstruction sur une autre
machine. Le cache du projet parisien est seulement lu.

La collecte est facultative pour reconstruire : le snapshot versionné suffit,
sans réseau. Une erreur de collecte conserve le snapshot précédent ; un snapshot
absent fait échouer la commande de reconstruction plutôt que d'effacer silencieusement
tous les signaux. Pour une comparaison ultérieure, fournir un nouveau chemin
`--before` à la capture et à l'audit, afin de conserver la référence choisie.

Le rapport `docs/scoring-audit.json` contient distributions, transitions, groupes
de catégories, départements et trois étoiles. Le CSV associé donne les anciennes
et nouvelles notes **pour chaque référence**. L'audit recalcule chaque note,
vérifie les projections carte/liste et l'intégrité SQLite, et compare une empreinte
de tous les champs hors notation pour contrôler la conservation des notices.
