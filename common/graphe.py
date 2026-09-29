"""Graphe de la ville + Dijkstra (heapq)."""
import heapq
import math

NOEUDS = {
    "C1": (100, 100), "C2": (300, 100), "C3": (500, 100),
    "C4": (100, 300), "C5": (300, 300), "C6": (500, 300),
    "C7": (100, 500), "C8": (300, 500), "C9": (500, 500),
}

ROUTES = [
    ("C1", "C2"), ("C2", "C3"), ("C4", "C5"), ("C5", "C6"), ("C7", "C8"), ("C8", "C9"),
    ("C1", "C4"), ("C4", "C7"), ("C2", "C5"), ("C5", "C8"), ("C3", "C6"), ("C6", "C9"),
]


def longueur(a, b):
    (x1, y1), (x2, y2) = NOEUDS[a], NOEUDS[b]
    return math.hypot(x2 - x1, y2 - y1)


def construire_graphe(trafic=None):
    """trafic = {frozenset({"C1","C2"}): 3.0} -> route 3x plus lente (bouchon)."""
    trafic = trafic or {}
    graphe = {n: [] for n in NOEUDS}
    for a, b in ROUTES:
        cout = longueur(a, b) * trafic.get(frozenset((a, b)), 1.0)
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