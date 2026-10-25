# Audit automatique des positions

Catalogue : **46 760 notices**. Contrôle local avec les contours officiels 2025, simplifiés à 100 m.

**198 alertes à examiner : 90 de priorité haute et 108 modérées.**

- [Liste des alertes](coordinate-audit.csv) : références POP, coordonnées, motif, communes de référence, distances et avertissements.
- [Cas secondaires](coordinate-audit-review.csv) : 218 positions déjà écartées, 190 appariements incomplets et 548 points proches des limites.
- [Résultats et empreintes des sources](coordinate-audit.json).

## Interprétation

- Une priorité haute signale un point à plus de 2 km du département déclaré, à plus de 10 km de toutes les communes appariées, ou une contradiction entre code INSEE et département.
- Une priorité modérée signale un point à plus de 1 km de toutes les communes appariées.
- Les distances sont mesurées aux **contours**, et non aux centres des communes. Les frontières sont des segments de grand cercle sur une sphère terrestre moyenne.
- Les codes INSEE multiples, arrondissements municipaux et communes associées/déléguées sont pris en compte. Un code manquant est signalé comme un défaut de couverture ; seul un contrôle indépendant suffisamment complet peut produire une alerte.
- L’ancien rattachement de Saint-Martin et Saint-Barthélemy au code 971 est accepté, comme dans le catalogue.
- 18 alertes portent un avertissement d’implantation maritime possible (phare, feu, amer ou balise). Leur position en mer peut être légitime.
- Ces alertes ne sont pas des erreurs confirmées : ponts, ouvrages côtiers, références administratives anciennes et contours simplifiés peuvent expliquer certains écarts.
- 43330 positions ne déclenchent aucun signal et 2276 notices n’ont pas de coordonnées. Cela ne certifie pas l’emplacement exact du bâtiment : une erreur à l’intérieur de la bonne commune reste possible.
- Aucune notice, coordonnée ou base de l’application n’est modifiée.

## Premières alertes, par priorité puis écart décroissant

| Référence | Monument | Commune déclarée | Motif | Écart commune (km) | Écart département (km) |
|---|---|---|---|---:|---:|
| [PA00104112](https://pop.culture.gouv.fr/notice/merimee/PA00104112) | Église Sainte-Colombe | Sainte-Colombe-de-la-Commanderie | code_insee_et_departement_incoherents | 733.538 | 0.0 |
| [PA00114985](https://pop.culture.gouv.fr/notice/merimee/PA00114985) | Ancienne brosserie Autin | Saint-Félix | hors_departement_declare | 715.849 | 679.243 |
| [PA00081624](https://pop.culture.gouv.fr/notice/merimee/PA00081624) | Thermes antiques (restes) | Fréjus | hors_departement_declare | 634.204 | 550.618 |
| [PA00125225](https://pop.culture.gouv.fr/notice/merimee/PA00125225) | Pont numéro 4 | Scherwiller | hors_departement_declare | 297.515 | 213.353 |
| [PA00125224](https://pop.culture.gouv.fr/notice/merimee/PA00125224) | Pont numéro 3 | Scherwiller | hors_departement_declare | 297.414 | 213.231 |
| [PA00125223](https://pop.culture.gouv.fr/notice/merimee/PA00125223) | Pont numéro 2 | Scherwiller | hors_departement_declare | 297.314 | 213.121 |
| [PA00125222](https://pop.culture.gouv.fr/notice/merimee/PA00125222) | Pont numéro 1 | Scherwiller | hors_departement_declare | 296.914 | 212.668 |
| [PA00116009](https://pop.culture.gouv.fr/notice/merimee/PA00116009) | Usine Sidoux | Saint-Quentin | hors_departement_declare | 296.301 | 187.73 |
| [PA62000009](https://pop.culture.gouv.fr/notice/merimee/PA62000009) | Villa Sans Gêne | Neufchâtel-Hardelot | hors_departement_declare | 295.659 | 246.414 |
| [PA62000010](https://pop.culture.gouv.fr/notice/merimee/PA62000010) | Maison de gardien de la Villa Sans Gêne | Neufchâtel-Hardelot | hors_departement_declare | 295.659 | 246.414 |
| [PA70000119](https://pop.culture.gouv.fr/notice/merimee/PA70000119) | église des Saints-Jumeaux | Colombier | hors_departement_declare | 187.983 | 104.503 |
| [PA00113448](https://pop.culture.gouv.fr/notice/merimee/PA00113448) | Église | Saint-Martin-de-Lixy | plus_de_10km_de_la_commune | 83.127 | 0.0 |
| [PA00132968](https://pop.culture.gouv.fr/notice/merimee/PA00132968) | Chapelle de la Colombière | Chalon-sur-Saône | plus_de_10km_de_la_commune | 77.585 | 0.0 |
| [PA00113401](https://pop.culture.gouv.fr/notice/merimee/PA00113401) | Ferme, à Saint-Romain | Romenay | plus_de_10km_de_la_commune | 75.287 | 0.0 |
| [PA00113219](https://pop.culture.gouv.fr/notice/merimee/PA00113219) | Église | Clessé | plus_de_10km_de_la_commune | 69.683 | 0.0 |
| [PA33000212](https://pop.culture.gouv.fr/notice/merimee/PA33000212) | Château de Lagrave, parc, ferme et orangerie | Bonzac | plus_de_10km_de_la_commune | 64.942 | 0.0 |
| [PA25000051](https://pop.culture.gouv.fr/notice/merimee/PA25000051) | Château de Moncley | Emagny | hors_departement_declare | 63.696 | 52.945 |
| [PA21000003](https://pop.culture.gouv.fr/notice/merimee/PA21000003) | Manoir de la Perrière | Fixin | plus_de_10km_de_la_commune | 63.08 | 0.0 |
| [PA00112451](https://pop.culture.gouv.fr/notice/merimee/PA00112451) | Église | Fixin | plus_de_10km_de_la_commune | 63.058 | 0.0 |
| [PA00113098](https://pop.culture.gouv.fr/notice/merimee/PA00113098) | Remparts romains | Autun | plus_de_10km_de_la_commune | 62.74 | 0.0 |

## Reproduire

```powershell
python tools/audit_coordinates.py
# Réutiliser les trois fichiers téléchargés, sans aucun appel réseau :
python tools/audit_coordinates.py --offline
python -m unittest discover -s tools -p "test_*.py"
```

Trois téléchargements nationaux au premier lancement, aucun appel par monument. Le cache est dans `data/geo_audit_cache/` (ignoré par Git). Python 3.11+ suffit, sans dépendance externe.

Source : [Contours administratifs officiels](https://www.data.gouv.fr/datasets/contours-administratifs/), distribués sous Licence Ouverte. Les URL et SHA-256 des trois fichiers utilisés figurent dans le JSON.
