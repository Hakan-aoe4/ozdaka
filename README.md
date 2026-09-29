# OzdAka – Test minimal (1 serveur, 1 carrefour, 1 ambulance)

## Installation
```bash
python3 -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement (3 terminaux, TOUJOURS depuis la racine du projet)
```bash
python -m server.serveur --port 5000
python -m client_carrefour.carrefour --id C1 --host 127.0.0.1
python -m client_vehicule.vehicule --id AMB1 --carrefour C1 --host 127.0.0.1
```
En multi-machines : remplacer `127.0.0.1` par l'IP du PC qui lance le serveur.

## Ce que ça montre
- L'ambulance traverse le carrefour d'Ouest en Est.
- **Priorité V2I cochée** : 200 px avant le feu, elle envoie `DEMANDE_PRIORITE` → le carrefour passe l'axe EO au vert et le maintient → `FIN_PRIORITE` une fois passée → retour au cycle normal.
- **Décochée** : elle respecte le cycle normal et s'arrête au rouge.
- Le temps de chaque trajet s'affiche en bas → comparaison avant/après.

## Protocole
JSON, un message par ligne (`\n`). Détail dans `common/protocole.py`.
