"""Carte intelligente : feux, priorité V2I, accidents, bouchons, recalcul auto, journal."""
import math
import os
import random
import sys
from datetime import datetime

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
                             QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout,
                             QLabel, QMainWindow, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget)

from common.graphe import Reseau, dijkstra

BLOQUE = 1e6          # facteur d'une route bloquée (accident / travaux)
CYCLE = 14.0          # durée d'un cycle de feu complet (s)
COULEURS_FEU = {"vert": "#2ecc71", "orange": "#f39c12", "rouge": "#e74c3c"}
# type de véhicule : (sensibilité au trafic, couleur). 1.0 = subit tout, 0.5 = passe mieux
VEHICULES = {
    "Ambulance": (0.5, "#ffffff"),
    "Police": (0.6, "#3498db"),
    "Pompiers": (0.5, "#e67e22"),
}

STYLE = """
QMainWindow, QWidget#racine { background:#0d1117; }
QWidget { color:#e6edf3; font-family:'Segoe UI'; font-size:13px; }
QFrame#carte { background:#161b22; border:1px solid #262f3b; border-radius:12px; }
QLabel#titreCarte { color:#8b949e; font-size:11px; font-weight:700; }
QFrame#tuile { background:#1c232d; border-radius:8px; }
QLabel#petit { color:#8b949e; font-size:11px; }
QLabel#valeur { font-size:15px; font-weight:700; }
QLabel#bandeau { background:#161b22; border:1px solid #262f3b; border-left:4px solid #e74c3c;
                 border-radius:8px; padding:10px 14px; font-size:14px; font-weight:600; }
QLabel#legende { background:#c9d1d9; color:#161b22; border-radius:8px; padding:6px 12px;
                 font-weight:600; }
QLabel#aide { color:#8b949e; font-size:12px; }
QPushButton { background:#232b36; border:1px solid #2f3a48; border-radius:8px;
              padding:9px 14px; font-weight:600; }
QPushButton:hover { background:#2b3543; }
QPushButton:pressed { background:#1c232d; }
QPushButton#primaire { background:#e74c3c; border:none; font-size:14px; padding:12px 14px; }
QPushButton#primaire:hover { background:#ff5b48; }
QComboBox { background:#232b36; border:1px solid #2f3a48; border-radius:8px;
            padding:8px 12px; font-weight:600; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox QAbstractItemView { background:#232b36; border:1px solid #2f3a48;
                              selection-background-color:#e74c3c; }
QTextEdit#journal { background:#0d1117; border:1px solid #262f3b; border-radius:8px;
                    font-family:Consolas; font-size:12px; padding:6px; }
QScrollBar:vertical { background:transparent; width:10px; }
QScrollBar::handle:vertical { background:#2f3a48; border-radius:5px; min-height:20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""


def cle(a, b):
    return frozenset((a, b))


def couleur_trafic(f):
    if f >= 1e5:
        c = QColor("#000000")
    elif f < 1.5:
        c = QColor("#2ecc71")
    elif f < 3:
        c = QColor("#f39c12")
    else:
        c = QColor("#e74c3c")
    c.setAlpha(215)
    return c


def etat_cycle(c):
    """État du feu pour un sens, c = position dans le cycle (0 à CYCLE)."""
    if c < 6:
        return "vert"
    if c < 7:
        return "orange"
    return "rouge"


def dist_segment(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def fmt(t):
    return "bloqué" if t == math.inf else f"{t:.1f} s"


class SceneVille(QGraphicsScene):
    def __init__(self, fenetre, reseau):
        super().__init__(0, 0, reseau.largeur, reseau.hauteur)
        self.fenetre = fenetre
        self.reseau = reseau
        self.actif = True
        self.k = max(reseau.largeur, reseau.hauteur) / 600     # échelle
        self.rayon = 16 * self.k
        self.vitesse = 120.0 * self.k
        if reseau.image and os.path.exists(reseau.image):
            self.addPixmap(QPixmap(reseau.image)).setZValue(-10)
        else:
            self.setBackgroundBrush(QColor("#6ab04c"))

        self.trafic = {cle(a, b): 1.0 for a, b in reseau.routes}
        self.coef = 0.5
        self.a = self.b = None
        self.chemin = []
        self.progress = 0.0
        self.temps = 0.0
        self.attente = 0.0
        self.en_attente = False
        self.arrive = False
        self.recalculs = 0
        self.derniere_prio = None
        self.temps_opt = self.temps_naif = 0.0
        self.vehicule = None
        self.items_trajet = []
        self.lignes = {}
        self.items_noeuds = {}

        # feux : un feu par carrefour ayant au moins 3 routes
        degres = {n: 0 for n in reseau.noeuds}
        for a, b in reseau.routes:
            degres[a] += 1
            degres[b] += 1
        self.decalage = {n: random.uniform(0, CYCLE) for n, d in degres.items() if d >= 3}
        self.points_feu = {}
        self.feux_actifs = True
        self.v2i = True
        self.priorite = None        # (carrefour, phase) forcé au vert par le véhicule
        self.horloge = 0.0
        self.accidents = {}         # route -> marqueur graphique

        self._dessiner()

        self.timer_v = QTimer()
        self.timer_v.timeout.connect(self.tick)
        self.timer_t = QTimer()
        self.timer_t.timeout.connect(self.bouchons_aleatoires)
        self.timer_a = QTimer()
        self.timer_a.timeout.connect(self.accident_auto)
        self.timer_f = QTimer()
        self.timer_f.timeout.connect(self.tick_feux)
        self.timer_f.start(100)

    def arreter(self):
        self.actif = False
        for t in (self.timer_v, self.timer_t, self.timer_a, self.timer_f):
            t.stop()

    # ---------- dessin ----------
    def _dessiner(self):
        noeuds = self.reseau.noeuds
        for a, b in self.reseau.routes:
            (x1, y1), (x2, y2) = noeuds[a], noeuds[b]
            self.lignes[cle(a, b)] = self.addLine(x1, y1, x2, y2)
        self.maj_couleurs()
        police = QFont("Arial")
        police.setPixelSize(max(8, int(12 * self.k)))
        police.setBold(True)
        for nom, (x, y) in noeuds.items():
            item = self.addEllipse(x - self.rayon, y - self.rayon, 2 * self.rayon,
                                   2 * self.rayon, QPen(QColor("black"), 2 * self.k),
                                   QBrush(QColor("#bdc3c7")))
            item.setZValue(5)
            self.items_noeuds[nom] = item
            txt = self.addText(nom, police)
            r = txt.boundingRect()
            txt.setPos(x - r.width() / 2, y - r.height() / 2)
            txt.setZValue(6)
        # petits feux : à gauche = sens Est-Ouest, en haut = sens Nord-Sud
        r = self.rayon * 0.4
        pen = QPen(QColor("black"), self.k)
        for nom in self.decalage:
            x, y = noeuds[nom]
            eo = self.addEllipse(x - self.rayon * 1.7 - r, y - r, 2 * r, 2 * r, pen)
            ns = self.addEllipse(x - r, y - self.rayon * 1.7 - r, 2 * r, 2 * r, pen)
            eo.setZValue(7)
            ns.setZValue(7)
            self.points_feu[nom] = {"EO": eo, "NS": ns}
        self.maj_feux()

    def maj_couleurs(self):
        for k, ligne in self.lignes.items():
            ligne.setPen(QPen(couleur_trafic(self.trafic[k]), 14 * self.k,
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

    def dessiner_trajet(self, chemin):
        for item in self.items_trajet:
            self.removeItem(item)
        self.items_trajet = []
        pen = QPen(QColor("#2c3e50"), 4 * self.k, Qt.PenStyle.DashLine,
                   Qt.PenCapStyle.RoundCap)
        for u, v in zip(chemin, chemin[1:]):
            (x1, y1), (x2, y2) = self.reseau.noeuds[u], self.reseau.noeuds[v]
            ligne = self.addLine(x1, y1, x2, y2, pen)
            ligne.setZValue(3)
            self.items_trajet.append(ligne)

    def _couleur_noeud(self, nom, couleur):
        self.items_noeuds[nom].setBrush(QBrush(QColor(couleur)))

    # ---------- feux ----------
    def phase(self, u, v):
        (x1, y1), (x2, y2) = self.reseau.noeuds[u], self.reseau.noeuds[v]
        return "EO" if abs(x2 - x1) >= abs(y2 - y1) else "NS"

    def etat_feu(self, nom, phase):
        if not self.feux_actifs or nom not in self.decalage:
            return "vert"
        if self.priorite and self.priorite[0] == nom:
            return "vert" if self.priorite[1] == phase else "rouge"
        c = (self.horloge + self.decalage[nom]) % CYCLE
        if phase == "NS":
            c = (c + CYCLE / 2) % CYCLE
        return etat_cycle(c)

    def maj_feux(self):
        for nom, pts in self.points_feu.items():
            for phase, item in pts.items():
                item.setBrush(QBrush(QColor(COULEURS_FEU[self.etat_feu(nom, phase)])))
                item.setVisible(self.feux_actifs)

    def tick_feux(self):
        self.horloge += 0.1
        self.maj_feux()

    def set_feux(self, actif):
        self.feux_actifs = actif
        self.maj_feux()

    # ---------- calcul d'itinéraire ----------
    def eff(self, f):
        """Facteur réellement subi par ce type de véhicule."""
        return BLOQUE if f >= 1e5 else 1 + (f - 1) * self.coef

    def itineraire(self, dep, arr):
        facteurs = {k: self.eff(f) for k, f in self.trafic.items()}
        chemin, cout = dijkstra(self.reseau.construire_graphe(facteurs), dep, arr)
        if cout >= 1e5:
            return [], math.inf
        return chemin, cout

    def temps_direct(self, dep, arr):
        """Temps du trajet le plus court en distance (qui ignore le trafic)."""
        chemin, _ = dijkstra(self.reseau.construire_graphe(), dep, arr)
        total = 0.0
        for u, v in zip(chemin, chemin[1:]):
            f = self.eff(self.trafic[cle(u, v)])
            if f >= 1e5:
                return math.inf
            total += self.reseau.longueur(u, v) * f
        return total / self.vitesse

    # ---------- interaction ----------
    def noeud_proche(self, pos):
        for nom, (x, y) in self.reseau.noeuds.items():
            if (pos.x() - x) ** 2 + (pos.y() - y) ** 2 <= (self.rayon + 6 * self.k) ** 2:
                return nom
        return None

    def reinitialiser(self):
        self.timer_v.stop()
        self.chemin = []
        self.priorite = None
        self.arrive = False
        self.en_attente = False
        if self.vehicule:
            self.removeItem(self.vehicule)
            self.vehicule = None
        self.dessiner_trajet([])
        for nom in self.reseau.noeuds:
            self._couleur_noeud(nom, "#bdc3c7")
        self.a = self.b = None
        self.fenetre.message("Clique sur le point de départ (A).")

    def mousePressEvent(self, event):
        pos = event.scenePos()
        if event.button() == Qt.MouseButton.RightButton:
            self.basculer_blocage(pos)
            return
        nom = self.noeud_proche(pos)
        if not nom:
            return
        if self.a is None or self.b is not None:
            self.reinitialiser()
            self.a = nom
            self._couleur_noeud(nom, "#2ecc71")
            self.fenetre.message(f"Départ : {nom}. Clique sur l'arrivée.")
        elif nom != self.a:
            self.b = nom
            self._couleur_noeud(nom, "#e74c3c")
            chemin, cout = self.itineraire(self.a, self.b)
            if chemin:
                self.dessiner_trajet(chemin)
                self.fenetre.message(f"Trajet estimé : {fmt(cout / self.vitesse)}. "
                                     "Choisis le véhicule et lance la mission.")
            else:
                self.fenetre.message("Aucun trajet possible.")

    def route_courante(self):
        if self.chemin:
            return cle(self.chemin[0], self.chemin[1])
        return None

    def basculer_blocage(self, pos):
        meilleur, dmin = None, 12 * self.k
        for a, b in self.reseau.routes:
            d = dist_segment((pos.x(), pos.y()), self.reseau.noeuds[a],
                             self.reseau.noeuds[b])
            if d < dmin:
                meilleur, dmin = cle(a, b), d
        if meilleur is None:
            return
        if meilleur in self.accidents:
            self.lever_accident(meilleur)
            self.fenetre.message("Route rouverte.")
        elif meilleur == self.route_courante():
            self.fenetre.message("Impossible : le véhicule est sur cette route.")
        else:
            self.poser_accident(meilleur)
            self.fenetre.message("Accident : route bloquée.")

    # ---------- accidents ----------
    def poser_accident(self, k, duree=None):
        if k in self.accidents:
            return
        a, b = tuple(k)
        (x1, y1), (x2, y2) = self.reseau.noeuds[a], self.reseau.noeuds[b]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        r = self.rayon * 0.8
        marqueur = self.addEllipse(mx - r, my - r, 2 * r, 2 * r,
                                   QPen(QColor("white"), 2 * self.k),
                                   QBrush(QColor("#c0392b")))
        marqueur.setZValue(8)
        police = QFont("Arial")
        police.setPixelSize(max(10, int(r * 1.4)))
        police.setBold(True)
        txt = self.addText("!", police)
        txt.setDefaultTextColor(QColor("white"))
        txt.setParentItem(marqueur)
        rect = txt.boundingRect()
        txt.setPos(mx - rect.width() / 2, my - rect.height() / 2)
        self.accidents[k] = marqueur
        self.trafic[k] = BLOQUE
        self.maj_couleurs()
        self.fenetre.log(f"Accident sur la route {a}-{b} : route bloquée", "#e74c3c")
        self.replanifier()
        if duree:
            QTimer.singleShot(int(duree * 1000), lambda: self.lever_accident(k))

    def lever_accident(self, k):
        if not self.actif or k not in self.accidents:
            return
        a, b = tuple(k)
        self.removeItem(self.accidents.pop(k))
        self.trafic[k] = 1.0
        self.maj_couleurs()
        self.fenetre.log(f"Route {a}-{b} rouverte", "#2ecc71")
        self.replanifier()

    def set_accidents(self, actif):
        if actif:
            self.timer_a.start(5000)
        else:
            self.timer_a.stop()

    def accident_auto(self):
        if random.random() < 0.6:
            courante = self.route_courante()
            libres = [k for k, f in self.trafic.items() if f < 1e5 and k != courante]
            if libres:
                self.poser_accident(random.choice(libres), duree=12)
                self.fenetre.message("Accident signalé, itinéraire recalculé.")

    # ---------- simulation ----------
    def set_bouchons(self, actif):
        if actif:
            self.bouchons_aleatoires()
            self.timer_t.start(4000)
        else:
            self.timer_t.stop()

    def bouchons_aleatoires(self):
        for k, f in self.trafic.items():
            if f >= 1e5:          # une route bloquée le reste
                continue
            r = random.random()
            self.trafic[k] = 1.0 if r < 0.55 else 2.0 if r < 0.85 else 4.0
        self.maj_couleurs()
        bouchons = sum(1 for f in self.trafic.values() if 3 <= f < 1e5)
        denses = sum(1 for f in self.trafic.values() if 1.5 <= f < 3)
        self.fenetre.log(f"Trafic mis à jour : {bouchons} bouchons, {denses} routes denses",
                         "#f39c12")
        self.replanifier()

    def replanifier(self):
        """Un événement change le trafic : on recalcule la suite du trajet."""
        if not self.chemin:
            return
        prochain = self.chemin[1]
        if prochain == self.b:
            return
        suite, _ = self.itineraire(prochain, self.b)
        if suite:
            if suite != self.chemin[1:]:
                self.recalculs += 1
                self.fenetre.log("Itinéraire recalculé : " + " → ".join(suite), "#3498db")
            self.chemin = [self.chemin[0]] + suite
            self.dessiner_trajet(self.chemin)

    def lancer(self, nom_vehicule):
        if self.a is None or self.b is None:
            self.fenetre.message("Choisis d'abord le départ et l'arrivée sur la carte.")
            return
        self.timer_v.stop()
        self.coef, couleur = VEHICULES[nom_vehicule]
        chemin, cout = self.itineraire(self.a, self.b)
        if not chemin:
            self.fenetre.message("Aucun trajet possible.")
            return
        self.temps_opt = cout / self.vitesse
        self.temps_naif = self.temps_direct(self.a, self.b)
        self.chemin = chemin
        self.progress = 0.0
        self.temps = 0.0
        self.attente = 0.0
        self.recalculs = 0
        self.priorite = None
        self.en_attente = False
        self.arrive = False
        self.derniere_prio = None
        self.dessiner_trajet(chemin)
        if self.vehicule:
            self.removeItem(self.vehicule)
        k = self.k
        self.vehicule = self.addRect(-14 * k, -8 * k, 28 * k, 16 * k,
                                     QPen(QColor("#c0392b"), 3 * k), QBrush(QColor(couleur)))
        self.vehicule.setZValue(10)
        self.vehicule.setPos(*self.reseau.noeuds[self.a])
        self.timer_v.start(30)
        self.fenetre.message(f"{nom_vehicule} en route...")
        self.fenetre.log(f"{nom_vehicule} part de {self.a} vers {self.b} "
                         f"(estimé : {fmt(self.temps_opt)})", "#ffffff")

    def recalculer(self, depuis):
        chemin, _ = self.itineraire(depuis, self.b)
        self.progress = 0.0
        if not chemin:
            self.timer_v.stop()
            self.chemin = []
            self.priorite = None
            self.fenetre.message("Bloqué : plus aucun trajet possible.")
            self.fenetre.log("Bloqué : plus aucun trajet possible", "#e74c3c")
            return
        self.chemin = chemin
        self.dessiner_trajet(chemin)
        self.vehicule.setPos(*self.reseau.noeuds[depuis])

    def tick(self):
        dt = 0.03
        if not self.chemin:
            return
        u, v = self.chemin[0], self.chemin[1]
        f = self.eff(self.trafic[cle(u, v)])
        if f >= 1e5:
            f = 1.0
        L = self.reseau.longueur(u, v)
        self.temps += dt

        a_un_feu = self.feux_actifs and v in self.decalage and v != self.b
        phase = self.phase(u, v)

        # V2I : à l'approche du carrefour, le véhicule demande le vert
        self.priorite = None
        if self.v2i and a_un_feu and L - self.progress < self.rayon * 8:
            self.priorite = (v, phase)
            if self.priorite != self.derniere_prio:
                self.derniere_prio = self.priorite
                self.fenetre.log(f"V2I : le carrefour {v} passe au vert pour le véhicule",
                                 "#2ecc71")

        nouveau = self.progress + self.vitesse / f * dt
        seuil = L - min(self.rayon * 1.6, L * 0.4)          # ligne d'arrêt
        if (a_un_feu and self.progress <= seuil < nouveau
                and self.etat_feu(v, phase) != "vert"):
            self.progress = seuil                              # arrêt au feu
            self.attente += dt
            if not self.en_attente:
                self.en_attente = True
                self.fenetre.log(f"Arrêt au feu rouge, carrefour {v}", "#e74c3c")
        else:
            if self.en_attente:
                self.en_attente = False
                self.fenetre.log(f"Feu vert au carrefour {v}, le véhicule repart", "#2ecc71")
            self.progress = nouveau

        if self.progress >= L:
            self.vehicule.setPos(*self.reseau.noeuds[v])
            if v == self.b:
                self.timer_v.stop()
                self.chemin = []
                self.priorite = None
                self.arrive = True
                texte = (f"Arrivé en {self.temps:.1f} s (dont {self.attente:.1f} s aux feux) "
                         f"| estimé au départ : {fmt(self.temps_opt)} "
                         f"| trajet direct : {fmt(self.temps_naif)}")
                self.fenetre.message(texte)
                self.fenetre.log("Arrivée : " + texte, "#ffffff")
                return
            self.fenetre.log(f"Passage au carrefour {v}", "#95a5a6")
            self.recalculer(v)       # à chaque carrefour on recalcule
            return
        (x1, y1), (x2, y2) = self.reseau.noeuds[u], self.reseau.noeuds[v]
        t = self.progress / L
        self.vehicule.setPos(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)


class Interrupteur(QCheckBox):
    """Interrupteur ON/OFF dessiné à la main."""

    def __init__(self, texte, defaut=False):
        super().__init__(texte)
        self.setChecked(defaut)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(30)

    def sizeHint(self):
        return QSize(220, 30)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = 42, 22
        y = (self.height() - h) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2ecc71" if self.isChecked() else "#3b4552"))
        p.drawRoundedRect(QRectF(0, y, w, h), h / 2, h / 2)
        p.setBrush(QColor("white"))
        x = w - h + 3 if self.isChecked() else 3
        p.drawEllipse(QRectF(x, y + 3, h - 6, h - 6))
        p.setPen(QColor("#e6edf3"))
        p.setFont(self.font())
        p.drawText(QRectF(w + 12, 0, self.width() - w - 12, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


def creer_carte(titre):
    cadre = QFrame()
    cadre.setObjectName("carte")
    layout = QVBoxLayout(cadre)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(8)
    lbl = QLabel(titre.upper())
    lbl.setObjectName("titreCarte")
    layout.addWidget(lbl)
    return cadre, layout


def creer_tuile(nom):
    cadre = QFrame()
    cadre.setObjectName("tuile")
    layout = QVBoxLayout(cadre)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(0)
    petit = QLabel(nom)
    petit.setObjectName("petit")
    valeur = QLabel("—")
    valeur.setObjectName("valeur")
    layout.addWidget(petit)
    layout.addWidget(valeur)
    return cadre, valeur


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OzdAka - Gestion du trafic d'urgence")
        self.setStyleSheet(STYLE)
        self.scene = None

        # journal (créé en premier : log() l'utilise)
        self.journal = QTextEdit()
        self.journal.setObjectName("journal")
        self.journal.setReadOnly(True)

        # ----- zone carte -----
        self.vue = QGraphicsView()
        self.vue.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vue.setFrameShape(QFrame.Shape.NoFrame)
        self.vue.setStyleSheet("background:#0d1117; border:1px solid #262f3b; "
                               "border-radius:12px;")
        self.bandeau = QLabel()
        self.bandeau.setObjectName("bandeau")
        legende = QLabel(
            "<span style='color:#27ae60'>■</span> Fluide &nbsp;&nbsp;"
            "<span style='color:#e67e22'>■</span> Dense &nbsp;&nbsp;"
            "<span style='color:#e74c3c'>■</span> Bouchon &nbsp;&nbsp;"
            "<span style='color:#000000'>■</span> Bloquée")
        legende.setObjectName("legende")
        aide = QLabel("Clic gauche : départ puis arrivée   |   "
                      "Clic droit sur une route : accident / travaux (bloque ou rouvre)")
        aide.setObjectName("aide")
        bas = QHBoxLayout()
        bas.addWidget(legende)
        bas.addWidget(aide, 1)

        gauche = QVBoxLayout()
        gauche.setSpacing(10)
        gauche.addWidget(self.bandeau)
        gauche.addWidget(self.vue, 1)
        gauche.addLayout(bas)

        # ----- carte Mission -----
        c_mission, l_mission = creer_carte("Mission")
        self.combo = QComboBox()
        self.combo.addItems(list(VEHICULES))
        btn_lancer = QPushButton("Lancer la mission")
        btn_lancer.setObjectName("primaire")
        btn_lancer.clicked.connect(lambda: self.scene.lancer(self.combo.currentText()))
        btn_reset = QPushButton("Réinitialiser")
        btn_reset.clicked.connect(lambda: self.scene.reinitialiser())
        btn_charger = QPushButton("Charger une carte")
        btn_charger.clicked.connect(self.choisir_carte)
        ligne = QHBoxLayout()
        ligne.addWidget(btn_reset)
        ligne.addWidget(btn_charger)
        l_mission.addWidget(QLabel("Véhicule d'urgence"))
        l_mission.addWidget(self.combo)
        l_mission.addWidget(btn_lancer)
        l_mission.addLayout(ligne)

        # ----- carte Simulation -----
        c_sim, l_sim = creer_carte("Simulation")
        self.btn_feux = self.bascule("Feux tricolores", True, lambda a: self.scene.set_feux(a))
        self.btn_v2i = self.bascule("Priorité V2I", True,
                                    lambda a: setattr(self.scene, "v2i", a))
        self.btn_bouchons = self.bascule("Bouchons aléatoires", False,
                                         lambda a: self.scene.set_bouchons(a))
        self.btn_accidents = self.bascule("Accidents aléatoires", False,
                                          lambda a: self.scene.set_accidents(a))
        for b in (self.btn_feux, self.btn_v2i, self.btn_bouchons, self.btn_accidents):
            l_sim.addWidget(b)

        # ----- carte Statistiques -----
        c_stats, l_stats = creer_carte("Statistiques en direct")
        grille = QGridLayout()
        grille.setSpacing(8)
        noms = ["Statut", "Trajet", "Temps écoulé", "Attente aux feux",
                "Estimé", "Trajet direct", "Recalculs", "Accidents actifs"]
        self.valeurs = {}
        for i, nom in enumerate(noms):
            tuile, valeur = creer_tuile(nom)
            grille.addWidget(tuile, i // 2, i % 2)
            self.valeurs[nom] = valeur
        l_stats.addLayout(grille)

        # ----- carte Journal -----
        c_journal, l_journal = creer_carte("Journal des événements")
        btn_effacer = QPushButton("Effacer le journal")
        btn_effacer.clicked.connect(self.journal.clear)
        self.journal.setMinimumHeight(120)
        l_journal.addWidget(self.journal, 1)
        l_journal.addWidget(btn_effacer)

        droite = QVBoxLayout()
        droite.setSpacing(12)
        droite.addWidget(c_mission)
        droite.addWidget(c_sim)
        droite.addWidget(c_stats)
        droite.addWidget(c_journal, 1)
        panneau = QWidget()
        panneau.setFixedWidth(390)
        panneau.setLayout(droite)
        droite.setContentsMargins(0, 0, 0, 0)

        # ----- en-tête -----
        titre = QLabel(
            "<span style='font-size:22px; font-weight:800;'>Ozd"
            "<span style='color:#e74c3c;'>Aka</span></span>"
            "<span style='color:#8b949e; font-size:13px;'> &nbsp;·&nbsp; "
            "Gestion du trafic pour véhicules d'urgence (V2X / V2I)</span>")

        racine = QWidget()
        racine.setObjectName("racine")
        principal = QVBoxLayout(racine)
        principal.setContentsMargins(16, 12, 16, 16)
        principal.setSpacing(12)
        principal.addWidget(titre)
        corps = QHBoxLayout()
        corps.setSpacing(16)
        corps.addLayout(gauche, 1)
        corps.addWidget(panneau)
        principal.addLayout(corps, 1)
        self.setCentralWidget(racine)
        self.resize(1400, 900)

        self.charger(Reseau.par_defaut())

        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self.maj_stats)
        self.timer_stats.start(150)

    def bascule(self, nom, defaut, action):
        b = Interrupteur(nom, defaut)
        b.nom = nom

        def change(actif):
            self.log(f"{nom} {'activé' if actif else 'désactivé'}", "#f1c40f")
            action(actif)

        b.toggled.connect(change)
        return b

    def charger(self, reseau):
        if self.scene is not None:
            self.scene.arreter()
        for b in (self.btn_bouchons, self.btn_accidents):
            b.blockSignals(True)
            b.setChecked(False)
            b.blockSignals(False)
            b.update()
        self.scene = SceneVille(self, reseau)
        self.scene.feux_actifs = self.btn_feux.isChecked()
        self.scene.v2i = self.btn_v2i.isChecked()
        self.scene.maj_feux()
        self.vue.setScene(self.scene)
        self.ajuster_vue()
        self.log(f"Carte chargée : {len(reseau.noeuds)} carrefours, "
                 f"{len(reseau.routes)} routes", "#3498db")
        self.message("Clique sur le point de départ (A).")

    def choisir_carte(self):
        chemin, _ = QFileDialog.getOpenFileName(self, "Choisir une carte", "cartes",
                                                "Cartes (*.json)")
        if not chemin:
            return
        try:
            self.charger(Reseau.charger(chemin))
        except Exception as e:
            self.message(f"Carte illisible : {e}")

    def ajuster_vue(self):
        if self.scene:
            self.vue.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ajuster_vue()

    def showEvent(self, event):
        super().showEvent(event)
        self.ajuster_vue()

    def message(self, texte):
        self.bandeau.setText(texte)

    def log(self, texte, couleur="#ecf0f1"):
        heure = datetime.now().strftime("%H:%M:%S")
        self.journal.append(f'<span style="color:#7f8c8d">[{heure}]</span> '
                            f'<span style="color:{couleur}">{texte}</span>')

    def maj_stats(self):
        s = self.scene
        if s is None:
            return
        if s.chemin:
            statut, couleur = (("Arrêt au feu", "#e74c3c") if s.en_attente
                               else ("En route", "#2ecc71"))
        elif s.arrive:
            statut, couleur = "Arrivé", "#3498db"
        else:
            statut, couleur = "En attente", "#8b949e"
        v = self.valeurs
        v["Statut"].setText(statut)
        v["Statut"].setStyleSheet(f"color:{couleur};")
        v["Trajet"].setText(f"{s.a} → {s.b}" if s.a and s.b else "—")
        actif = bool(s.chemin) or s.arrive
        v["Temps écoulé"].setText(f"{s.temps:.1f} s" if actif else "—")
        v["Attente aux feux"].setText(f"{s.attente:.1f} s" if actif else "—")
        v["Estimé"].setText(fmt(s.temps_opt) if actif else "—")
        v["Trajet direct"].setText(fmt(s.temps_naif) if actif else "—")
        v["Recalculs"].setText(str(s.recalculs) if actif else "—")
        v["Accidents actifs"].setText(str(len(s.accidents)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    f = Fenetre()
    f.showMaximized()
    sys.exit(app.exec())