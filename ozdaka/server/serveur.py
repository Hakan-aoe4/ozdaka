"""Serveur central OzdAka : 1 thread par client, routage des messages JSON.

Lancement (depuis la racine du projet) :  python -m server.serveur --port 5000
"""
import argparse
import socket
import threading

from common.protocole import encoder, LecteurMessages, PORT_DEFAUT

clients = {}                # id -> {"role": ..., "sock": ...}
verrou = threading.Lock()   # protège `clients` et les envois


def envoyer_a(ident: str, msg: dict):
    with verrou:
        c = clients.get(ident)
        if c is None:
            print(f"[!] Destinataire inconnu : {ident}")
            return
        try:
            c["sock"].sendall(encoder(msg))
        except OSError:
            pass


def envoyer_role(role: str, msg: dict):
    data = encoder(msg)
    with verrou:
        for c in clients.values():
            if c["role"] == role:
                try:
                    c["sock"].sendall(data)
                except OSError:
                    pass


def router(emetteur: str, msg: dict):
    t = msg.get("type")
    if t == "POSITION":
        envoyer_role("carrefour", msg)
    elif t in ("DEMANDE_PRIORITE", "FIN_PRIORITE"):
        print(f"[V2I] {t} : {msg['id_vehicule']} -> {msg['id_carrefour']}")
        envoyer_a(msg["id_carrefour"], msg)
    elif t == "ETAT_FEU":
        envoyer_role("vehicule", msg)
    else:
        print(f"[?] Type inconnu de {emetteur} : {t}")


def gerer_client(sock: socket.socket, addr):
    lecteur = LecteurMessages()
    ident = None
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            for msg in lecteur.ajouter(data):
                if msg.get("type") == "REGISTER":
                    ident = msg["id"]
                    with verrou:
                        clients[ident] = {"role": msg["role"], "sock": sock}
                    print(f"[+] {msg['role']} '{ident}' connecté depuis {addr[0]}:{addr[1]}")
                elif ident is None:
                    print(f"[!] Message avant REGISTER ignoré ({addr})")
                else:
                    router(ident, msg)
    except OSError:
        pass
    finally:
        with verrou:
            if ident and clients.get(ident, {}).get("sock") is sock:
                del clients[ident]
        sock.close()
        print(f"[-] '{ident or addr}' déconnecté")


def main():
    parser = argparse.ArgumentParser(description="Serveur central OzdAka")
    parser.add_argument("--port", type=int, default=PORT_DEFAUT)
    args = parser.parse_args()

    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur.bind(("0.0.0.0", args.port))
    serveur.listen()
    print(f"Serveur OzdAka en écoute sur le port {args.port} (Ctrl+C pour arrêter)")

    try:
        while True:
            sock, addr = serveur.accept()
            threading.Thread(target=gerer_client, args=(sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nArrêt du serveur")
    finally:
        serveur.close()


if __name__ == "__main__":
    main()
