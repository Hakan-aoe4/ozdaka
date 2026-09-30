# OzdAka : gestion du trafic pour véhicules d'urgence (V2X / V2I)

SAÉ 3.02, BUT Réseaux et Télécommunications.
Équipe : Hakan AKAKCA, Furkan OZDEMIR. Encadrant : M. Drouhin.

## Présentation

Application Python qui fluidifie le trajet d'un véhicule d'urgence (ambulance, police, pompiers) d'un point A à un point B. La carte simule une ville : le trafic évolue (bouchons, accidents, travaux), les feux tricolores changent, et l'itinéraire est **recalculé automatiquement** à chaque événement, comme un GPS, mais pensé pour les secours. Grâce à la communication V2I, un carrefour passe au vert à l'approche du véhicule d'urgence.

## Fonctionnalités

- Carte de la ville avec carrefours et routes (grille par défaut, ou image réelle + fichier JSON)
- Éditeur de cartes : on pose les carrefours et les routes sur une capture de carte
- Choix du départ (A) et de l'arrivée (B) au clic
- Calcul du trajet le plus rapide (Dijkstra, implémentation maison avec `heapq`)
- Véhicule animé, avec recalcul de l'itinéraire à chaque carrefour
- Niveaux de trafic (fluide, dense, bouchon) colorés sur la carte
- Accidents et travaux : clic droit sur une route (blocage et contournement), ou accidents aléatoires
- Feux tricolores, et priorité V2I (le carrefour passe au vert pour le véhicule)
- Choix du type de véhicule (ambulance, police, pompiers)
- Statistiques en direct (temps écoulé, attente aux feux, estimé, trajet direct, recalculs) et journal des événements

## Lancement rapide (Windows)

1. Installer Python 3.12 (https://www.python.org/downloads/), en cochant « Add python.exe to PATH ».
2. Cloner le dépôt :
```
   git clone https://github.com/Hakan-aoe4/ozdaka.git
```
3. Double-cliquer sur `run.bat` dans le dossier du projet.

Au premier lancement, `run.bat` crée l'environnement virtuel et installe les dépendances. Un menu propose ensuite :
1. Lancer la carte (simulation)
2. Éditeur de cartes

> Conseil : placer le projet sur le disque local (C:), pas sur un lecteur réseau.

## Lancement manuel

```
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m client.carte_ville
python -m client.editeur
```

## Utilisation

**Simulation** (`client.carte_ville`)
- Clic gauche sur un carrefour : départ, puis arrivée
- Choisir le véhicule puis « Lancer la mission »
- Clic droit sur une route : bloquer (accident ou travaux) ou rouvrir
- Interrupteurs : feux, priorité V2I, bouchons et accidents aléatoires
- « Charger une carte » : ouvre un fichier `.json` du dossier `cartes`

**Éditeur** (`client.editeur`)
1. « Ouvrir une image » (capture de carte dans `cartes/`)
2. Clic sur le vide : nouveau carrefour. Clic sur deux carrefours : route. Clic droit : supprimer
3. « Sauvegarder » crée le `.json` à côté de l'image

## Structure du projet

```
ozdaka/
├── run.bat              # lanceur (menu carte / éditeur)
├── requirements.txt     # versions exactes des librairies
├── client/              # IHM PyQt6 : carte_ville.py, editeur.py
├── common/              # graphe.py (réseau + Dijkstra), protocole et réseau
├── server/              # serveur central (partie réseau)
├── client_carrefour/    # client carrefour (partie réseau)
├── client_vehicule/     # client véhicule (partie réseau)
├── cartes/              # images de cartes + fichiers JSON
└── db/                  # base sqlite3 (statistiques)
```

## Technologies

Python 3.x, PyQt6 (QGraphicsScene / QGraphicsView), `socket` / `select` / `json` pour le réseau, `sqlite3`, `matplotlib`, `heapq`, `random`, `math`, `time`, `datetime`. Uniquement les librairies autorisées par le sujet.

## Répartition

- **Hakan AKAKCA** : IHM, simulation, calcul d'itinéraire, statistiques
- **Furkan OZDEMIR** : couche réseau (sockets TCP/UDP, protocole V2X/V2I, serveur central)

## Avancement

- [x] Carte, clic A/B, calcul de trajet, affichage
- [x] Simulation du trafic, accidents, feux, priorité V2I
- [x] Éditeur de cartes, statistiques en direct, journal
- [ ] Communication client/serveur (sockets) branchée à l'IHM
- [ ] Multi-threading (QThread et signaux Qt)
- [ ] Statistiques en base sqlite3 et graphiques

## Crédits

Cartes : © OpenStreetMap contributors (https://www.openstreetmap.org/copyright)
