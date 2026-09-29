"""Éditeur de carte : on pose les carrefours et les routes sur une image."""
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QFileDialog, QGraphicsScene, QGraphicsView,
                             QHBoxLayout, QLabel, QMainWindow, QPushButton,
                             QVBoxLayout, QWidget)

from common.graphe import Reseau


class SceneEditeur(QGraphicsScene):
    def __init__(self, fenetre, pixmap, noeuds, routes):
        super().__init__(0, 0, pixmap.width(), pixmap.height())
        self.fenetre = fenetre
        self.pixmap = pixmap
        self.noeuds = noeuds
        self.routes = routes
        self.selection = None
        self.r = max(8, max(pixmap.width(), pixmap.height()) / 70)
        self.redessiner()

    def redessiner(self):
        self.clear()
        self.addPixmap(self.pixmap)
        pen = QPen(QColor("#e74c3c"), self.r / 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        for a, b in self.routes:
            (x1, y1), (x2, y2) = self.noeuds[a], self.noeuds[b]
            self.addLine(x1, y1, x2, y2, pen).setZValue(1)
        police = QFont("Arial")
        police.setPixelSize(int(self.r * 1.1))
        police.setBold(True)
        for nom, (x, y) in self.noeuds.items():
            couleur = "#f39c12" if nom == self.selection else "#3498db"
            item = self.addEllipse(x - self.r, y - self.r, 2 * self.r, 2 * self.r,
                                   QPen(QColor("black"), 2), QBrush(QColor(couleur)))
            item.setZValue(5)
            txt = self.addText(nom, police)
            rect = txt.boundingRect()
            txt.setPos(x - rect.width() / 2, y - self.r - rect.height())
            txt.setDefaultTextColor(QColor("black"))
            txt.setZValue(6)

    def noeud_proche(self, pos):
        for nom, (x, y) in self.noeuds.items():
            if (pos.x() - x) ** 2 + (pos.y() - y) ** 2 <= (self.r * 1.3) ** 2:
                return nom
        return None

    def nouveau_nom(self):
        i = 1
        while f"C{i}" in self.noeuds:
            i += 1
        return f"C{i}"

    def mousePressEvent(self, event):
        pos = event.scenePos()
        nom = self.noeud_proche(pos)
        if event.button() == Qt.MouseButton.RightButton:
            if nom:
                del self.noeuds[nom]
                self.routes = [r for r in self.routes if nom not in r]
                self.selection = None
                self.redessiner()
            return
        if nom:
            if self.selection is None:
                self.selection = nom
            elif self.selection == nom:
                self.selection = None
            else:
                a, b = self.selection, nom
                if (a, b) not in self.routes and (b, a) not in self.routes:
                    self.routes.append((a, b))
                self.selection = None
        else:
            self.noeuds[self.nouveau_nom()] = (pos.x(), pos.y())
            self.selection = None
        self.redessiner()
        self.fenetre.message(f"{len(self.noeuds)} carrefours, {len(self.routes)} routes")


class FenetreEditeur(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OzdAka - Éditeur de carte")
        self.scene = None
        self.chemin_image = None
        self.vue = QGraphicsView()
        self.vue.setRenderHint(QPainter.RenderHint.Antialiasing)

        btn_ouvrir = QPushButton("Ouvrir une image")
        btn_ouvrir.clicked.connect(self.ouvrir)
        btn_sauver = QPushButton("Sauvegarder")
        btn_sauver.clicked.connect(self.sauvegarder)
        barre = QHBoxLayout()
        barre.addWidget(btn_ouvrir)
        barre.addWidget(btn_sauver)
        aide = QLabel("Clic sur le vide : nouveau carrefour  |  clic sur un carrefour "
                      "puis sur un autre : route  |  clic droit sur un carrefour : supprimer")

        centre = QWidget()
        layout = QVBoxLayout(centre)
        layout.addLayout(barre)
        layout.addWidget(self.vue)
        layout.addWidget(aide)
        self.setCentralWidget(centre)
        self.resize(1000, 900)
        self.message("Ouvre une image de carte.")

    def message(self, texte):
        self.statusBar().showMessage(texte)

    def ajuster_vue(self):
        if self.scene:
            self.vue.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ajuster_vue()

    def ouvrir(self):
        chemin, _ = QFileDialog.getOpenFileName(self, "Image de la carte", "cartes",
                                                "Images (*.png *.jpg *.jpeg)")
        if not chemin:
            return
        pix = QPixmap(chemin)
        if pix.isNull():
            self.message("Image illisible.")
            return
        self.chemin_image = chemin
        noeuds, routes = {}, []
        chemin_json = os.path.splitext(chemin)[0] + ".json"
        if os.path.exists(chemin_json):
            r = Reseau.charger(chemin_json)
            noeuds, routes = dict(r.noeuds), list(r.routes)
        self.scene = SceneEditeur(self, pix, noeuds, routes)
        self.vue.setScene(self.scene)
        self.ajuster_vue()
        self.message("Pose les carrefours en cliquant sur l'image.")

    def sauvegarder(self):
        if not self.scene:
            self.message("Ouvre d'abord une image.")
            return
        if len(self.scene.noeuds) < 2 or not self.scene.routes:
            self.message("Il faut au moins 2 carrefours et 1 route.")
            return
        chemin_json = os.path.splitext(self.chemin_image)[0] + ".json"
        r = Reseau(self.scene.noeuds, self.scene.routes,
                   os.path.basename(self.chemin_image),
                   int(self.scene.width()), int(self.scene.height()))
        r.sauvegarder(chemin_json)
        self.message(f"Sauvegardé : {chemin_json}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    f = FenetreEditeur()
    f.show()
    sys.exit(app.exec())