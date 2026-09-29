"""Client véhicule d'urgence : traverse le carrefour d'Ouest en Est.

Si « Priorité V2I » est cochée, il demande le vert au carrefour à l'approche.
Le temps de chaque trajet est affiché pour comparer avec / sans priorité.

Lancement :  python -m client_vehicule.vehicule --id AMB1 --carrefour C1 --host 127.0.0.1
"""
import argparse
import sys
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QCheckBox, QGraphicsView, QMessageBox)

from common import carte
from common.client_reseau import ClientReseau
from common.protocole import PORT_DEFAUT

TICK_MS = 50               # 20 images/s
VITESSE = 4                # px par tick (= 80 px/s)
LONGUEUR = 40
DISTANCE_DETECTION = 200   # px avant la ligne d'arrêt où on demande la priorité


class FenetreVehicule(QMainWindow):
    def __init__(self, reseau: ClientReseau, ident: str, id_carrefour: str):
        super().__init__()
        self.reseau = reseau
        self.ident = ident
        self.id_carrefour = id_carrefour
        self.setWindowTitle(f"OzdAka – Véhicule {ident}")

        self.scene, self.feux = carte.creer_scene_carrefour()
        self.vehicule = carte.creer_vehicule(self.scene, ident, LONGUEUR)
        self.etat_feux = {"NS": "rouge", "EO": "rouge"}
        self.reinit_trajet()
        self.n_trajet = 0

        vue = QGraphicsView(self.scene)
        vue.setMinimumSize(carte.TAILLE + 10, carte.TAILLE + 10)
        self.btn = QPushButton("▶ Démarrer")
        self.btn.clicked.connect(self.basculer)
        self.chk_prio = QCheckBox("Priorité V2I")
        self.chk_prio.setChecked(True)
        self.lbl_etat = QLabel("À l'arrêt")
        self.lbl_stats = QLabel("Aucun trajet terminé")

        barre = QHBoxLayout()
        barre.addWidget(self.btn)
        barre.addWidget(self.chk_prio)
        barre.addWidget(self.lbl_etat, 1)
        box = QVBoxLayout()
        box.addLayout(barre)
        box.addWidget(vue)
        box.addWidget(self.lbl_stats)
        w = QWidget()
        w.setLayout(box)
        self.setCentralWidget(w)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.avancer)
        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.connexion_perdue.connect(self.perte_connexion)
        self.maj_position()

    def reinit_trajet(self):
        self.x = 0.0
        self.t_depart = None
        self.t_arret = 0.0
        self.prio_demandee = False
        self.prio_liberee = False
        self.tick_n = 0

    def basculer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn.setText("▶ Démarrer")
        else:
            self.timer.start(TICK_MS)
            self.btn.setText("⏸ Pause")

    # ---------- simulation ----------
    def avancer(self):
        if self.t_depart is None:
            self.t_depart = time.monotonic()
        avant = self.x + LONGUEUR

        # Feu rouge/orange et on arrive sur la ligne d'arrêt -> on s'arrête
        if (self.etat_feux["EO"] != "vert" and avant <= carte.LIGNE_STOP_EO
                and avant + VITESSE > carte.LIGNE_STOP_EO):
            self.x = carte.LIGNE_STOP_EO - LONGUEUR
            self.t_arret += TICK_MS / 1000
            self.lbl_etat.setText(f"🛑 Arrêté au feu {self.etat_feux['EO']}")
        else:
            self.x += VITESSE
            self.lbl_etat.setText("🚑 En route")

        # V2I : demande de priorité à l'approche du carrefour
        distance = carte.LIGNE_STOP_EO - (self.x + LONGUEUR)
        if (self.chk_prio.isChecked() and not self.prio_demandee
                and 0 <= distance <= DISTANCE_DETECTION):
            self.prio_demandee = True
            self.reseau.envoyer({"type": "DEMANDE_PRIORITE", "id_vehicule": self.ident,
                                 "id_carrefour": self.id_carrefour, "direction": "EO"})
        # Carrefour dégagé -> on libère
        if self.prio_demandee and not self.prio_liberee and self.x > carte.CENTRE + carte.DEMI_ROUTE:
            self.prio_liberee = True
            self.reseau.envoyer({"type": "FIN_PRIORITE", "id_vehicule": self.ident,
                                 "id_carrefour": self.id_carrefour})

        # Position envoyée 1 tick sur 2 (10 msg/s)
        self.tick_n += 1
        if self.tick_n % 2 == 0:
            self.reseau.envoyer({"type": "POSITION", "id": self.ident,
                                 "x": self.x + LONGUEUR / 2, "y": carte.Y_VOIE_EST,
                                 "vitesse": VITESSE * 1000 / TICK_MS})

        # Fin du trajet -> stats + on recommence
        if self.x > carte.TAILLE:
            self.n_trajet += 1
            duree = time.monotonic() - self.t_depart
            mode = "AVEC priorité" if self.prio_demandee else "SANS priorité"
            self.lbl_stats.setText(f"Trajet n°{self.n_trajet} ({mode}) : {duree:.1f} s "
                                   f"dont {self.t_arret:.1f} s à l'arrêt")
            print(f"[STAT] trajet={self.n_trajet} mode={mode} duree={duree:.2f}s arret={self.t_arret:.2f}s")
            self.reinit_trajet()
        self.maj_position()

    def maj_position(self):
        self.vehicule.setPos(self.x, carte.Y_VOIE_EST - 10)

    # ---------- réseau (slot, thread IHM) ----------
    def traiter_message(self, msg: dict):
        if msg.get("type") == "ETAT_FEU" and msg.get("id_carrefour") == self.id_carrefour:
            self.etat_feux = msg["feux"]
            carte.maj_feux(self.feux, self.etat_feux)

    def perte_connexion(self):
        self.timer.stop()
        QMessageBox.warning(self, "Réseau", "Connexion au serveur perdue.")


def main():
    parser = argparse.ArgumentParser(description="Client véhicule OzdAka")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT_DEFAUT)
    parser.add_argument("--id", default="AMB1")
    parser.add_argument("--carrefour", default="C1")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    try:
        reseau = ClientReseau(args.host, args.port, "vehicule", args.id)
    except OSError as e:
        QMessageBox.critical(None, "Réseau", f"Serveur injoignable ({args.host}:{args.port})\n{e}")
        return 1
    fen = FenetreVehicule(reseau, args.id, args.carrefour)
    reseau.start()
    fen.show()
    code = app.exec()
    reseau.arreter()
    return code


if __name__ == "__main__":
    sys.exit(main())
