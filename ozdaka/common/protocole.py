"""Protocole OzdAka : 1 message = 1 objet JSON sur une ligne, terminé par '\n'.

Messages :
  REGISTER          client -> serveur     {"type", "role": "vehicule"|"carrefour", "id"}
  POSITION          vehicule -> carrefours {"type", "id", "x", "y", "vitesse"}
  DEMANDE_PRIORITE  vehicule -> carrefour  {"type", "id_vehicule", "id_carrefour", "direction": "NS"|"EO"}
  FIN_PRIORITE      vehicule -> carrefour  {"type", "id_vehicule", "id_carrefour"}
  ETAT_FEU          carrefour -> vehicules {"type", "id_carrefour", "feux": {"NS": couleur, "EO": couleur}, "mode"}
"""
import json

PORT_DEFAUT = 5000
ENCODAGE = "utf-8"


def encoder(msg: dict) -> bytes:
    """dict -> octets prêts à envoyer sur la socket."""
    return (json.dumps(msg) + "\n").encode(ENCODAGE)


class LecteurMessages:
    """Découpe le flux TCP en messages. TCP ne garantit pas qu'un recv() = 1 message,
    donc on accumule dans un buffer et on coupe sur les '\n'."""

    def __init__(self):
        self.buffer = b""

    def ajouter(self, data: bytes) -> list:
        self.buffer += data
        messages = []
        while b"\n" in self.buffer:
            ligne, self.buffer = self.buffer.split(b"\n", 1)
            if not ligne.strip():
                continue
            try:
                messages.append(json.loads(ligne.decode(ENCODAGE)))
            except (json.JSONDecodeError, UnicodeDecodeError):
                print("[!] Trame invalide ignorée :", ligne[:80])
        return messages
