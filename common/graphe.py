"""Réseau routier (carrefours + routes), chargement JSON et Dijkstra (heapq)."""
import heapq
import json
import math
import os


class Reseau:
    def __init__(self, noeuds, routes, image=None, largeur=600, hauteur=600):
        self.noeuds = noeuds      # {"C1": (x, y)}
        self.routes = routes      # [("C1", "C2")]
        self.image = image
        self.largeur = largeur
        self.hauteur = hauteur

    @classmethod
    def par_defaut(cls):
        noeuds = {
            "C1": (100, 100), "C2": (300, 100), "C3": (500, 100),
            "C4": (100, 300), "C5": (300, 300), "C6": (500, 300),
            "C7": (100, 500), "C8": (300, 500), "C9": (500, 500),
        }
        routes = [
            ("C1", "C2"), ("C2", "C3"), ("C4", "C5"), ("C5", "C6"), ("C7", "C8"),
            ("C8", "C9"), ("C1", "C4"), ("C4", "C7"), ("C2", "C5"), ("C5", "C8"),
            ("C3", "C6"), ("C6", "C9"),
        ]
        return cls(noeuds, routes)

    @classmethod
    def charger(cls, chemin_json):
        with open(chemin_json, encoding="utf-8") as f:
            d = json.load(f)
        dossier = os.path.dirname(os.path.abspath(chemin_json))
        image = d.get("image")
        if image:
            image = os.path.join(dossier, image)
        return cls({n: tuple(p) for n, p in d["noeuds"].items()},
                   [tuple(r) for r in d["routes"]],
                   image, d.get("largeur", 600), d.get("hauteur", 600))

    def sauvegarder(self, chemin_json):
        d = {
            "image": self.image,
            "largeur": self.largeur,
            "hauteur": self.hauteur,
            "noeuds": {n: [round(x), round(y)] for n, (x, y) in self.noeuds.items()},
            "routes": [list(r) for r in self.routes],
        }
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)

    def longueur(self, a, b):
        (x1, y1), (x2, y2) = self.noeuds[a], self.noeuds[b]
        return math.hypot(x2 - x1, y2 - y1)

    def construire_graphe(self, trafic=None):
        """trafic = {frozenset({"C1","C2"}): 3.0} -> route 3x plus lente."""
        trafic = trafic or {}
        graphe = {n: [] for n in self.noeuds}
        for a, b in self.routes:
            cout = self.longueur(a, b) * trafic.get(frozenset((a, b)), 1.0)
            graphe[a].append((b, cout))
            graphe[b].append((a, cout))
        return graphe


def dijkstra(graphe, depart, arrivee):
    """Retourne (chemin, cout) ou ([], inf) si pas de chemin."""
    dist = {n: math.inf for n in graphe}
    prec = {}
    dist[depart] = 0
    file = [(0, depart)]
    while file:
        d, u = heapq.heappop(file)
        if u == arrivee:
            break
        if d > dist[u]:
            continue
        for v, cout in graphe[u]:
            nd = d + cout
            if nd < dist[v]:
                dist[v] = nd
                prec[v] = u
                heapq.heappush(file, (nd, v))
    if dist[arrivee] == math.inf:
        return [], math.inf
    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(prec[chemin[-1]])
    return chemin[::-1], dist[arrivee]