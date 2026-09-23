"""
log_match_to_csv.py

Lit la sortie serie du sketch boucle_fermee_consolidee.ino et
l'enregistre dans un CSV utilisable par plot_eps_vs_position.py.

Format REEL observe sur le port serie (une ligne par echantillon,
paires cle=valeur separees par des espaces, PAS de virgules, PAS de
t_ms fourni par le firmware) :

    VA=2.3350 VG=2.1163 V+=2.0281 pos_a=0.7977 pos_g=4.2132 eps_a=0.0666 eps_g=-0.1188 erreur=0.01855 vel_a=0.156 vel_g=-0.654

Le script extrait chaque paire cle=valeur par regex (peu importe
l'ordre dans lequel elles arrivent), et genere lui-meme t_ms comme le
temps ecoule (en ms) depuis le debut de l'enregistrement, puisque le
firmware n'en envoie pas.

Installation :
    pip install pyserial

Usage :
    python log_match_to_csv.py COM5 --duree 30 --out matching_run.csv
    (remplacer COM5 par le port reel -- sur Linux/Mac : /dev/ttyACM0 ou /dev/ttyUSB0)

    --duree 0 pour un enregistrement illimite (Ctrl+C pour arreter)
"""

import argparse
import csv
import re
import time

import serial

# Noms des colonnes attendues (cles telles qu'elles apparaissent avant
# le '=' dans chaque ligne serie). L'ordre ici determine l'ordre des
# colonnes dans le CSV de sortie (t_ms est ajoute automatiquement en
# premiere colonne).
NOMS_COLONNES = ["VA", "VG", "V+", "pos_a", "pos_g", "eps_a", "eps_g", "erreur", "vel_a", "vel_g"]

# Regex pour extraire des paires cle=valeur du type "pos_a=0.7977" ou
# "V+=2.0281" ou "eps_g=-0.1188". \S+? (non-greedy) pour la cle,
# nombre signe/decimal pour la valeur.
MOTIF_PAIRE = re.compile(r"(\S+?)=(-?\d+(?:\.\d+)?)")


def parser_ligne(raw):
    """Extrait un dict {cle: valeur_float} depuis une ligne serie.
    Retourne None si la ligne ne contient pas toutes les cles attendues."""
    paires = MOTIF_PAIRE.findall(raw)
    if not paires:
        return None
    valeurs = {}
    for cle, val in paires:
        try:
            valeurs[cle] = float(val)
        except ValueError:
            continue
    if not all(cle in valeurs for cle in NOMS_COLONNES):
        return None
    return valeurs


def lire_serie(port, baudrate, duree_s, out_path):
    print(f"Ouverture de {port} @ {baudrate} bauds...")
    ser = serial.Serial(port, baudrate, timeout=1)
    time.sleep(2)  # laisser le temps a l'Arduino de rebooter apres ouverture du port

    lignes_valides = 0
    lignes_ignorees = 0
    t_debut = time.time()
    t_fin = t_debut + duree_s if duree_s else None

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_ms"] + NOMS_COLONNES)

        print(f"Enregistrement en cours -> {out_path}")
        if duree_s:
            print(f"Duree : {duree_s}s (Ctrl+C pour arreter avant)")
        else:
            print("Duree illimitee -- Ctrl+C pour arreter")

        try:
            while t_fin is None or time.time() < t_fin:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                valeurs = parser_ligne(raw)
                if valeurs is None:
                    lignes_ignorees += 1
                    continue
                t_ms = int((time.time() - t_debut) * 1000)
                writer.writerow([t_ms] + [valeurs[cle] for cle in NOMS_COLONNES])
                lignes_valides += 1
        except KeyboardInterrupt:
            print("\nArret demande par l'utilisateur.")

    ser.close()
    print(f"{lignes_valides} echantillons enregistres dans {out_path}")
    if lignes_ignorees:
        print(f"{lignes_ignorees} ligne(s) ignoree(s) (format inattendu -- "
              f"normal si le firmware imprime aussi des messages d'info/debug)")
    if lignes_valides == 0:
        print("\n⚠️  Aucune ligne valide recue. Verifie que :")
        print("   - le firmware boucle_fermee_consolidee.ino envoie bien des lignes cle=valeur sur Serial")
        print("   - les cles envoyees correspondent (au moins) a NOMS_COLONNES :")
        print(f"     {NOMS_COLONNES}")
        print("   - le baudrate correspond a celui configure dans le sketch (Serial.begin(...))")
    return lignes_valides


def main():
    parser = argparse.ArgumentParser(description="Log serie CSV depuis boucle_fermee_consolidee.ino")
    parser.add_argument("port", help="Port serie, ex: COM5 ou /dev/ttyACM0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--duree", type=float, default=30.0, help="Duree d'enregistrement en secondes (0 = illimite)")
    parser.add_argument("--out", default="matching_run.csv", help="Fichier CSV de sortie")
    args = parser.parse_args()

    lire_serie(args.port, args.baudrate, args.duree, args.out)


if __name__ == "__main__":
    main()