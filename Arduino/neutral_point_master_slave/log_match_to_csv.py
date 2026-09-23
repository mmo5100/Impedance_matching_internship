# -*- coding: utf-8 -*-
"""
log_match_to_csv.py

Enregistre en continu les lignes Serial du firmware (VA, VG, V+, pos_a,
pos_g, eps_a, eps_g, erreur, vel_a, vel_g) dans un fichier CSV, et
s'arrete automatiquement des que le matching est considere termine :
eps_a et eps_g sous EPS_DEADBAND ET vel_a/vel_g quasi nuls, pendant
plusieurs echantillons consecutifs (pour eviter de s'arreter sur un
passage transitoire par zero).

Usage :
    pip install pyserial
    python3 log_match_to_csv.py COM5 --out matching_run.csv

Le script s'arrete aussi apres --timeout secondes (par defaut 120s) si
le match n'est jamais atteint, avec un avertissement clair.
"""

import argparse
import csv
import re
import sys
import time

import serial

# --- Criteres de "match termine" -- coherents avec le firmware ---
EPS_DEADBAND_DEFAUT = 0.13     # meme valeur que EPS_DEADBAND dans le firmware
VEL_SEUIL_DEFAUT = 0.01        # vitesse consideree comme "arretee"
N_ECHANTILLONS_CONSECUTIFS = 20  # ~2s a 10Hz (le firmware imprime toutes les 100ms)

# Extrait les paires cle=valeur de chaque ligne Serial, quel que soit
# leur ordre exact (robuste a un reordonnancement futur du firmware).
PATTERN_CLE_VALEUR = re.compile(r"([A-Za-z_]+\+?)=(-?\d+\.?\d*)")


def parser_ligne(ligne):
    """Renvoie un dict {cle: valeur_float} ou None si la ligne n'est pas exploitable."""
    paires = PATTERN_CLE_VALEUR.findall(ligne)
    if len(paires) < 5:  # ligne d'info/debug, pas une ligne de donnees
        return None
    try:
        return {cle: float(val) for cle, val in paires}
    except ValueError:
        return None


def matching_est_stable(valeurs, eps_deadband, vel_seuil):
    requis = ("eps_a", "eps_g", "vel_a", "vel_g")
    if not all(k in valeurs for k in requis):
        return False
    return (
        abs(valeurs["eps_a"]) < eps_deadband
        and abs(valeurs["eps_g"]) < eps_deadband
        and abs(valeurs["vel_a"]) < vel_seuil
        and abs(valeurs["vel_g"]) < vel_seuil
    )


def enregistrer(port, baudrate, out_path, eps_deadband, vel_seuil, timeout_s):
    print(f"Ouverture de {port} @ {baudrate} bauds...")
    ser = serial.Serial(port, baudrate, timeout=1)
    time.sleep(2)  # laisser le temps a l'Arduino de rebooter apres ouverture du port

    compteur_stable = 0
    colonnes = None
    lignes_ecrites = 0
    t_debut = time.time()

    with open(out_path, "w", newline="") as f:
        writer = None

        print(f"Enregistrement en cours -> {out_path}")
        print(f"Arret automatique des que le match est stable ({N_ECHANTILLONS_CONSECUTIFS} echantillons consecutifs)")
        print(f"Timeout de securite : {timeout_s}s")

        try:
            while True:
                if time.time() - t_debut > timeout_s:
                    print(f"\n⚠️  Timeout de {timeout_s}s atteint -- le match n'a jamais ete detecte comme stable.")
                    print("   Verifie EPS_DEADBAND, ou augmente --timeout si la convergence est juste lente.")
                    break

                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue

                valeurs = parser_ligne(raw)
                if valeurs is None:
                    continue  # ligne d'info/debug, on l'ignore

                if writer is None:
                    colonnes = ["t_ms"] + sorted(valeurs.keys())
                    writer = csv.writer(f)
                    writer.writerow(colonnes)

                t_ms = int((time.time() - t_debut) * 1000)
                writer.writerow([t_ms] + [valeurs.get(c, "") for c in colonnes[1:]])
                lignes_ecrites += 1

                if matching_est_stable(valeurs, eps_deadband, vel_seuil):
                    compteur_stable += 1
                else:
                    compteur_stable = 0

                if compteur_stable >= N_ECHANTILLONS_CONSECUTIFS:
                    print(f"\n Match stable detecte apres {lignes_ecrites} echantillons ({t_ms/1000:.1f}s).")
                    print(f"   eps_a={valeurs['eps_a']:.4f}  eps_g={valeurs['eps_g']:.4f}  "
                          f"pos_a={valeurs.get('pos_a', float('nan')):.3f}  pos_g={valeurs.get('pos_g', float('nan')):.3f}")
                    break

        except KeyboardInterrupt:
            print("\nArret manuel demande par l'utilisateur (Ctrl+C).")

    ser.close()
    print(f"{lignes_ecrites} echantillons enregistres dans {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Enregistre la trajectoire du matching jusqu'a convergence")
    parser.add_argument("port", help="Port serie, ex: COM5 ou /dev/ttyACM0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--out", default="matching_run.csv", help="Fichier CSV de sortie")
    parser.add_argument("--eps-deadband", type=float, default=EPS_DEADBAND_DEFAUT,
                         help="Doit correspondre a EPS_DEADBAND dans le firmware")
    parser.add_argument("--vel-seuil", type=float, default=VEL_SEUIL_DEFAUT,
                         help="Vitesse en dessous de laquelle on considere le moteur arrete")
    parser.add_argument("--timeout", type=float, default=120.0,
                         help="Duree max d'enregistrement en secondes (securite)")
    args = parser.parse_args()

    enregistrer(args.port, args.baudrate, args.out, args.eps_deadband, args.vel_seuil, args.timeout)


if __name__ == "__main__":
    main()