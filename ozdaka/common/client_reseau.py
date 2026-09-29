"""Client TCP réutilisable par le véhicule et le carrefour.

La réception tourne dans un QThread. Chaque message reçu est transmis à l'IHM
par le signal `message_recu` : on ne touche JAMAIS l'IHM depuis ce thread.
"""
import socket
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from common.protocole import encoder, LecteurMessages


class ClientReseau(QThread):
    message_recu = pyqtSignal(dict)
    connexion_perdue = pyqtSignal()

    def __init__(self, host: str, port: int, role: str, ident: str):
        super().__init__()
        # Lève OSError si le serveur n'est pas lancé -> géré dans le main
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.verrou_envoi = threading.Lock()
        self.actif = True
        self.envoyer({"type": "REGISTER", "role": role, "id": ident})

    def envoyer(self, msg: dict):
        """Appelable depuis le thread IHM. Le verrou évite que 2 envois se mélangent."""
        with self.verrou_envoi:
            try:
                self.sock.sendall(encoder(msg))
            except OSError:
                pass

    def run(self):
        lecteur = LecteurMessages()
        while self.actif:
            try:
                data = self.sock.recv(4096)
            except OSError:
                break
            if not data:  # serveur fermé
                break
            for msg in lecteur.ajouter(data):
                self.message_recu.emit(msg)
        if self.actif:
            self.connexion_perdue.emit()

    def arreter(self):
        self.actif = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.wait(1000)
