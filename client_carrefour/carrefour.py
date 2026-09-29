"""Client carrefour : cycle de feux normal + passage au vert pour un véhicule prioritaire.

Lancement :  python -m client_carrefour.carrefour --id C1 --host 127.0.0.1
"""
import argparse
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
                             QGraphicsView, QPlainTextEdit, QMessageBox)

from common import carte
from common.client_reseau import ClientReseau
from common.protocole import PORT_DEFAUT

# (état des feux, durée en secondes)
PHASES = [
    ({"NS": "vert", "EO": "rouge"}, 5),
    ({"NS": "orange", "EO": "rouge"}, 1),
    ({"NS": "rouge", "EO": "vert"}, 5),
    ({"NS": "rouge", "EO": "orange"}, 1),
]
PHASE_VERT = {"NS": 0, "EO": 2}   # index de la phase où la direction est au vert


class FenetreCarrefour(QMainWindow):
    def __init__(self, reseau: ClientReseau, ident: str):
        super().__init__()
        self.reseau = reseau
        self.ident = ident
        self.setWindowTitle(f"OzdAka – Carrefour {ident}")

        self.scene, self.feux = carte.creer_scene_carrefour()
        self.marqueurs = {}          # id véhicule -> point sur la carte
        self.idx = 0
        self.restant = PHASES[0][1]
        self.priorite = None         # direction prioritaire ("EO"/"NS") ou None
        self.vehicule_prio = None

        vue = QGraphicsView(self.scene)
        vue.setMinimumSize(carte.TAILLE + 10, carte.TAILLE + 10)
        self.lbl_mode = QLabel()
        self.journal = QPlainTextEdit(readOnly=True)
        self.journal.setMaximumHeight(120)
        box = QVBoxLayout()
        box.addWidget(self.lbl_mode)
        box.addWidget(vue)
        box.addWidget(self.journal)
        w = QWidget()
        w.setLayout(box)
        self.setCentralWidget(w)

        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.connexion_perdue.connect(self.perte_connexion)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.changer_phase(0)

    # ---------- logique des feux ----------
    def tick(self):
        if self.priorite:
            self.appliquer_priorite()
        else:
            self.restant -= 1
            if self.restant <= 0:
                self.changer_phase((self.idx + 1) % len(PHASES))
        self.publier()

    def appliquer_priorite(self):
        cible = PHASE_VERT[self.priorite]
        if self.idx == cible:
            return                                     # déjà vert : on maintient
        if self.idx == (cible + 2) % 4:
            self.changer_phase((cible + 3) % 4)        # l'autre axe est vert -> orange
        elif self.idx == (cible + 3) % 4:
            self.restant -= 1                          # l'autre axe est orange -> on attend
            if self.restant <= 0:
                self.changer_phase(cible)
        else:
            self.changer_phase(cible)                  # notre axe est orange -> retour au vert

    def changer_phase(self, idx):
        self.idx = idx
        self.restant = PHASES[idx][1]
        carte.maj_feux(self.feux, PHASES[idx][0])
        mode = f"PRIORITÉ ({self.vehicule_prio} – axe {self.priorite})" if self.priorite else "NORMAL"
        self.lbl_mode.setText(f"Mode : {mode}")

    def publier(self):
        self.reseau.envoyer({
            "type": "ETAT_FEU",
            "id_carrefour": self.ident,
            "feux": PHASES[self.idx][0],
            "mode": "priorite" if self.priorite else "normal",
        })

    # ---------- réseau (slot appelé dans le thread IHM) ----------
    def traiter_message(self, msg: dict):
        t = msg.get("type")
        if t == "DEMANDE_PRIORITE" and msg.get("id_carrefour") == self.ident:
            self.priorite = msg["direction"]
            self.vehicule_prio = msg["id_vehicule"]
            self.journal.appendPlainText(f"🚨 Demande de priorité de {self.vehicule_prio} (axe {self.priorite})")
            self.appliquer_priorite()
            self.changer_phase(self.idx)   # rafraîchit le label
            self.publier()
        elif t == "FIN_PRIORITE" and msg.get("id_carrefour") == self.ident:
            self.journal.appendPlainText(f"✅ {msg['id_vehicule']} a passé le carrefour")
            self.priorite = None
            self.vehicule_prio = None
            self.changer_phase(self.idx)   # reprise du cycle normal
        elif t == "POSITION":
            m = self.marqueurs.get(msg["id"])
            if m is None:
                m = self.scene.addEllipse(-6, -6, 12, 12, QPen(QColor("white"), 2),
                                          QBrush(QColor("#c0392b")))
                m.setZValue(10)
                self.marqueurs[msg["id"]] = m
            m.setPos(msg["x"], msg["y"])

    def perte_connexion(self):
        self.timer.stop()
        QMessageBox.warning(self, "Réseau", "Connexion au serveur perdue.")


def main():
    parser = argparse.ArgumentParser(description="Client carrefour OzdAka")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT_DEFAUT)
    parser.add_argument("--id", default="C1")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    try:
        reseau = ClientReseau(args.host, args.port, "carrefour", args.id)
    except OSError as e:
        QMessageBox.critical(None, "Réseau", f"Serveur injoignable ({args.host}:{args.port})\n{e}")
        return 1
    fen = FenetreCarrefour(reseau, args.id)
    reseau.start()
    fen.show()
    code = app.exec()
    reseau.arreter()
    return code


if __name__ == "__main__":
    sys.exit(main())
