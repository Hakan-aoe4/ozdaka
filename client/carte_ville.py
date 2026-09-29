"""Carte de la ville : clic sur A puis B, affichage du trajet le plus rapide."""
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QFont, QPainter
from PyQt6.QtWidgets import (QApplication, QGraphicsScene, QGraphicsView,
                             QMainWindow)

from common.graphe import NOEUDS, ROUTES, construire_graphe, dijkstra

RAYON = 16


class SceneVille(QGraphicsScene):
    def __init__(self, fenetre):
        super().__init__(0, 0, 600, 600)
        self.fenetre = fenetre
        self.setBackgroundBrush(QColor("#6ab04c"))
        self.graphe = construire_graphe()
        self.a = None
        self.b = None
        self.items_trajet = []
        self.items_noeuds = {}
        self._dessiner()

    def _dessiner(self):
        route = QPen(QColor("#555555"), 14, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap)
        for a, b in ROUTES:
            (x1, y1), (x2, y2) = NOEUDS[a], NOEUDS[b]
            self.addLine(x1, y1, x2, y2, route)
        police = QFont("Arial", 9, QFont.Weight.Bold)
        for nom, (x, y) in NOEUDS.items():
            item = self.addEllipse(x - RAYON, y - RAYON, 2 * RAYON, 2 * RAYON,
                                   QPen(QColor("black"), 2), QBrush(QColor("#bdc3c7")))
            item.setZValue(5)
            self.items_noeuds[nom] = item
            txt = self.addText(nom, police)
            txt.setPos(x - 12, y - 12)
            txt.setZValue(6)

    def _noeud_proche(self, pos):
        for nom, (x, y) in NOEUDS.items():
            if (pos.x() - x) ** 2 + (pos.y() - y) ** 2 <= (RAYON + 6) ** 2:
                return nom
        return None

    def _couleur(self, nom, couleur):
        self.items_noeuds[nom].setBrush(QBrush(QColor(couleur)))

    def _reinitialiser(self):
        for item in self.items_trajet:
            self.removeItem(item)
        self.items_trajet = []
        for nom in NOEUDS:
            self._couleur(nom, "#bdc3c7")
        self.a = self.b = None

    def mousePressEvent(self, event):
        nom = self._noeud_proche(event.scenePos())
        if nom:
            if self.a is None or self.b is not None:
                self._reinitialiser()
                self.a = nom
                self._couleur(nom, "#2ecc71")
                self.fenetre.statusBar().showMessage(f"Départ : {nom}. Clique sur l'arrivée.")
            elif nom != self.a:
                self.b = nom
                self._couleur(nom, "#e74c3c")
                self._calculer()
        super().mousePressEvent(event)

    def _calculer(self):
        chemin, cout = dijkstra(self.graphe, self.a, self.b)
        if not chemin:
            self.fenetre.statusBar().showMessage("Aucun trajet possible.")
            return
        pen = QPen(QColor("#f39c12"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        for u, v in zip(chemin, chemin[1:]):
            (x1, y1), (x2, y2) = NOEUDS[u], NOEUDS[v]
            ligne = self.addLine(x1, y1, x2, y2, pen)
            ligne.setZValue(3)
            self.items_trajet.append(ligne)
        self.fenetre.statusBar().showMessage(
            f"Trajet : {' -> '.join(chemin)}  (coût {cout:.0f}). Clique pour recommencer.")


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OzdAka - Carte")
        self.scene = SceneVille(self)
        vue = QGraphicsView(self.scene)
        vue.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setCentralWidget(vue)
        self.resize(640, 680)
        self.statusBar().showMessage("Clique sur le point de départ (A).")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    f = Fenetre()
    f.show()
    sys.exit(app.exec())