# Carte de vérification — PC uniquement

Double-cliquer sur `tools/Ouvrir-carte-positions.cmd`, ou lancer depuis le projet :

```powershell
python tools/review_coordinates.py --open
```

La carte s’ouvre sur <http://127.0.0.1:8765/>. Python 3.11+ suffit, sans installation
de paquet. Le serveur écoute uniquement sur le PC. Un second lancement du raccourci
rouvre l’outil déjà démarré. « Arrêter l’outil » arrête son serveur local.

- Les 198 lieux de `docs/coordinate-audit.csv` sont cliquables sur la carte ou dans
  la liste. Les points superposés proposent les différentes notices.
- Choisir « Bon emplacement », « Mauvais emplacement » ou « À vérifier », avec un
  commentaire facultatif. Le choix et le commentaire sont enregistrés ensemble.
  Changer de lieu enregistre aussi un commentaire en cours.
- Les décisions sont conservées dans `data/coordinate_reviews.json`, ignoré par
  Git. Recharger ou fermer le navigateur ne les efface pas. Le fichier est écrit
  atomiquement ; un fichier endommagé n’est pas remplacé silencieusement.
- Les anciennes décisions et notes sont relues telles quelles, sans réinitialiser
  le fichier. Les coordonnées corrigées sont ajoutées à la même sauvegarde.
- Pour déplacer un lieu : le sélectionner, cliquer sur « Corriger la position
  par un clic », puis cliquer sur le nouvel emplacement. On peut d’abord déplacer
  ou zoomer la carte, ou afficher la commune et les photos IGN. Le point corrigé
  devient bleu et son enregistrement est confirmé dans la fiche. « Annuler le mode
  correction » quitte ce mode sans déplacer le point.
- La position d’origine reste conservée et apparaît en gris lorsque le lieu est
  sélectionné. Les boutons permettent de revoir l’origine ou le point corrigé.
  « Rétablir la position d’origine » annule la correction courante en la conservant
  dans l’historique. Le filtre « Positions corrigées » retrouve les ajustements.
- Le jugement Bon/Mauvais concerne la position d’origine ; déplacer le point ne
  change pas ce jugement et ne supprime pas son commentaire. Le bouton
  « Enregistrer le commentaire » peut être utilisé séparément.
- Chaque changement enregistré est conservé dans l’historique du lieu : date,
  jugement, commentaire et coordonnées. Au premier changement d’une ancienne
  décision, son état précédent est conservé. Les enregistrements sans changement
  ne créent pas de doublon.
- Avant chaque écriture, une copie datée complète est créée dans
  `data/coordinate_review_backups/`, également ignoré par Git. Aucune ancienne
  sauvegarde n’est supprimée automatiquement. Pour récupérer une copie, arrêter
  l’outil et recopier la sauvegarde choisie vers `data/coordinate_reviews.json`.
- Les exports CSV et JSON permettent de récupérer les décisions. Un export CSV
  contient aussi les lieux restant à vérifier, les coordonnées originales et
  corrigées, la date de correction et le nombre d’entrées d’historique. Le JSON
  conserve les notes exactes et l’historique complet de tous les ajustements.
- Le filtre permet de ne voir que les lieux à vérifier, bons ou mauvais. La
  recherche accepte nom, référence, commune ou département. Le bouton « Lieu
  suivant » passe au prochain lieu à vérifier dans le filtre courant.
- Un contour bleu montre la commune correspondant au code INSEE, grâce au cache
  de l’audit. Le code peut être erroné : la commune déclarée et la commune de
  référence sont affichées séparément. Si le cache manque, la carte et les
  décisions fonctionnent sans ces contours.
- Plan OpenStreetMap et photos aériennes IGN nécessitent Internet. Leaflet 1.9.4
  est fourni localement avec sa licence BSD. Aucun compte, hébergement ni clé API.
- Si un nouvel audit change les coordonnées d’une notice déjà évaluée, l’outil
  demande de la revérifier et l’export indique ce changement.

Cette interface ne modifie ni la base SQLite des monuments, ni l’application
Android. Les décisions personnelles restent sur le PC et ne sont pas poussées.

Vérification : 37 tests Python réussis, dont conservation des anciennes décisions,
sauvegardes exactes avant modification, historique de corrections successives,
compatibilité avec un ancien onglet, écritures concurrentes, exports, rejet de
coordonnées invalides et récupération après une erreur d’écriture.
Le clic sur carte, le choix entre points superposés, les filtres, les photos IGN
et la persistance après rechargement ont également été vérifiés dans le navigateur
avec un fichier de décisions isolé. Le clic de correction, le rechargement et le
rétablissement de l’origine ont aussi été vérifiés sans toucher aux décisions
personnelles.

Autre port ou fichier de décisions, pour un test isolé :

```powershell
python tools/review_coordinates.py --port 8766 --reviews chemin/decisions-test.json
```
