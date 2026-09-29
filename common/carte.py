"""Dessin du carrefour (partagé entre le client véhicule et le client carrefour)."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QFont
from PyQt6.QtWidgets import QGraphicsScene

TAILLE = 600
CENTRE = 300
DEMI_ROUTE = 40                                  # route de 80 px de large
LIGNE_STOP_EO = CENTRE - DEMI_ROUTE - 5          # x de la ligne d'arrêt (sens Ouest -> Est)
Y_VOIE_EST = CENTRE + DEMI_ROUTE // 2            # milieu de la voie qui va vers l'Est

COULEURS = {
    "vert": QColor("#2ecc71"),
    "orange": QColor("#f39c12"),
    "rouge": QColor("#e74c3c"),
}


def creer_scene_carrefour():
    """Retourne (scene, feux) ; feux = {"NS": item, "EO": item}."""
    scene = QGraphicsScene(0, 0, TAILLE, TAILLE)
    scene.setBackgroundBrush(QColor("#6ab04c"))
    sans_bord = QPen(Qt.PenStyle.NoPen)
    bitume = QBrush(QColor("#555555"))

    # Routes
    scene.addRect(0, CENTRE - DEMI_ROUTE, TAILLE, 2 * DEMI_ROUTE, sans_bord, bitume)
    scene.addRect(CENTRE - DEMI_ROUTE, 0, 2 * DEMI_ROUTE, TAILLE, sans_bord, bitume)

    # Marquage central en pointillés
    tirets = QPen(QColor("white"), 2, Qt.PenStyle.DashLine)
    scene.addLine(0, CENTRE, CENTRE - DEMI_ROUTE, CENTRE, tirets)
    scene.addLine(CENTRE + DEMI_ROUTE, CENTRE, TAILLE, CENTRE, tirets)
    scene.addLine(CENTRE, 0, CENTRE, CENTRE - DEMI_ROUTE, tirets)
    scene.addLine(CENTRE, CENTRE + DEMI_ROUTE, CENTRE, TAILLE, tirets)

    # Ligne d'arrêt pour le sens Ouest -> Est
    scene.addLine(LIGNE_STOP_EO, CENTRE, LIGNE_STOP_EO, CENTRE + DEMI_ROUTE,
                  QPen(QColor("white"), 4))

    # Feux
    noir = QPen(QColor("black"), 2)
    feux = {
        "EO": scene.addEllipse(CENTRE - DEMI_ROUTE - 30, CENTRE + DEMI_ROUTE + 8, 22, 22,
                               noir, QBrush(COULEURS["rouge"])),
        "NS": scene.addEllipse(CENTRE + DEMI_ROUTE + 8, CENTRE - DEMI_ROUTE - 30, 22, 22,
                               noir, QBrush(COULEURS["rouge"])),
    }
    police = QFont("Arial", 10, QFont.Weight.Bold)
    for nom, item in feux.items():
        txt = scene.addText(nom, police)
        txt.setDefaultTextColor(QColor("white"))
        r = item.rect()
        txt.setPos(r.x() - 4, r.y() + 22)
    return scene, feux


def maj_feux(feux: dict, etat: dict):
    for direction, item in feux.items():
        item.setBrush(QBrush(COULEURS.get(etat.get(direction), QColor("gray"))))


def creer_vehicule(scene, ident: str, longueur=40, largeur=20):
    """Rectangle blanc bordé de rouge + étiquette."""
    item = scene.addRect(0, 0, longueur, largeur, QPen(QColor("#c0392b"), 3),
                         QBrush(QColor("white")))
    txt = scene.addText(ident, QFont("Arial", 7, QFont.Weight.Bold))
    txt.setDefaultTextColor(QColor("#c0392b"))
    txt.setParentItem(item)
    txt.setPos(0, 1)
    item.setZValue(10)
    return item
