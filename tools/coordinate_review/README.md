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
- Les exports CSV et JSON permettent de récupérer les décisions. Un export CSV
  contient aussi les lieux restant à vérifier. Le JSON conserve les notes exactes.
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

Vérification : 30 tests Python réussis, dont sauvegarde après redémarrage,
écritures concurrentes, exports et conservation d’un fichier endommagé.
Le clic sur carte, le choix entre points superposés, les filtres, les photos IGN
et la persistance après rechargement ont également été vérifiés dans le navigateur
avec un fichier de décisions isolé.

Autre port ou fichier de décisions, pour un test isolé :

```powershell
python tools/review_coordinates.py --port 8766 --reviews chemin/decisions-test.json
```
