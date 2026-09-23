"""
CALIBRATION POS_CA ET POS_CG VIA LABJACK T4
=============================================

Meme principe que calibration_pos_ca.ino, mais en lisant les positions via
le LabJack (pas de limite 0-5V contrairement a l'ADC Arduino -- utile car
pos_ca clippe sur l'Arduino en haut et en bas de la course, et pos_cg n'a
de toute facon aucun feedback cable sur l'Arduino faute de pin ADC libre).

UTILISATION :
    1. Deplace Ca OU Cg (via jog_interactif sur l'Arduino, manuellement,
       ou autre methode) vers une position, note ce que l'afficheur
       physique montre en mm.
    2. Capture le point avec le prefixe du condensateur concerne :
           ca 20.5      -> capture un point pour Ca a mm=20.5
           cg 30.2      -> capture un point pour Cg a mm=30.2
       Chaque point capture la tension mesuree au meme instant.
    3. Repete a au moins 4-5 positions bien differentes par condensateur,
       reparties sur toute la course (pas seulement la plage 40-205pF --
       on veut caracteriser toute la relation, meme la ou l'Arduino
       clippe pour Ca).
    4. Tape "fit ca" ou "fit cg" pour calculer la regression et les
       bornes de ce condensateur.
    5. Tape "reset ca" ou "reset cg" pour effacer les points de cet axe.
    6. Tape "save" pour sauvegarder tous les points dans un CSV.
    7. Tape "p" pour afficher les deux tensions actuelles (Ca et Cg).
    8. Tape "q" pour quitter.

Necessite : pip install labjack-ljm (+ driver LJM installe sur la machine)
"""

from labjack import ljm
import numpy as np
import csv
import time
from datetime import datetime

# -----------------------------------------------------------------------
# Configuration -- a adapter selon ton cablage LabJack
# -----------------------------------------------------------------------
CANAL_POS_CA = "AIN0"   # TODO : verifier/adapter selon le cablage reel
CANAL_POS_CG = "AIN1"   # TODO : verifier/adapter selon le cablage reel
N_SAMPLES = 30           # nombre de lectures moyennees par point
DELAI_ENTRE_LECTURES_S = 0.01

# Formule historique capacitance <-> position (mm), utilisee pour HFSS
# C(x) = 300 - 5.217*x  =>  x(C) = (300 - C) / 5.217
C_A0 = 300.0
C_A1 = 5.217
C_CIBLE_HAUT_PF = 205.0  # borne haute de capacitance (mm faible)
C_CIBLE_BAS_PF = 40.0    # borne basse de capacitance (mm elevee)

CSV_OUTPUT = "calibration_pos_ca_cg_labjack.csv"


def mm_depuis_pf(c_pf):
    return (C_A0 - c_pf) / C_A1


def lire_canal(handle, canal):
    """Moyenne de N_SAMPLES lectures pour reduire le bruit."""
    valeurs = []
    for _ in range(N_SAMPLES):
        v = ljm.eReadName(handle, canal)
        valeurs.append(v)
        time.sleep(DELAI_ENTRE_LECTURES_S)
    return float(np.mean(valeurs))


def calculer_fit(nom, pts_mm, pts_v):
    if len(pts_mm) < 2:
        print(f"Il faut au moins 2 points pour calculer le fit de {nom}.")
        return

    pts_mm_arr = np.array(pts_mm)
    pts_v_arr = np.array(pts_v)

    # Regression lineaire : pos_v = a*mm + b
    a, b = np.polyfit(pts_mm_arr, pts_v_arr, 1)

    y_pred = a * pts_mm_arr + b
    ss_res = np.sum((pts_v_arr - y_pred) ** 2)
    ss_tot = np.sum((pts_v_arr - np.mean(pts_v_arr)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 1.0

    print()
    print(f"=== RESULTAT DU FIT -- {nom.upper()} ===")
    print(f"pos_{nom}_v = {a:.6f} * mm + {b:.6f}")
    print(f"R^2 = {r2:.5f}")
    if r2 < 0.98:
        print("ATTENTION : R^2 faible, la relation ne semble pas bien lineaire.")
        print("Verifie les points (erreur de saisie ? mesure au mauvais moment ?).")

    mm_haut = mm_depuis_pf(C_CIBLE_HAUT_PF)  # 205pF -> mm faible
    mm_bas = mm_depuis_pf(C_CIBLE_BAS_PF)    # 40pF  -> mm elevee

    v_a_mm_haut = a * mm_haut + b
    v_a_mm_bas = a * mm_bas + b

    print()
    print(f"=== PLAGE 40-205 pF -- {nom.upper()} (tension REELLE, pas clippee) ===")
    print(f"205 pF -> {mm_haut:.2f} mm -> pos_{nom}_v={v_a_mm_haut:.4f} V")
    print(f"40  pF -> {mm_bas:.2f} mm -> pos_{nom}_v={v_a_mm_bas:.4f} V")

    v_min = min(v_a_mm_haut, v_a_mm_bas)
    v_max = max(v_a_mm_haut, v_a_mm_bas)
    plage_v = v_max - v_min

    print()
    print(f"Plage totale a couvrir ({nom}) : {plage_v:.3f} V")
    if plage_v > 5.0:
        print("ATTENTION : cette plage depasse 5V -- un offset fixe (pile) ne")
        print("suffira JAMAIS a la faire rentrer dans la fenetre 0-5V de l'ADC")
        print("Arduino, quel que soit son reglage. Il faut soit :")
        print("  - comprimer le signal avec un pont diviseur resistif avant l'ADC,")
        print("  - soit renoncer a une coupure dure Arduino sur toute la plage")
        print("    et utiliser un handshake digital pilote par ce script LabJack")
        print("    a la place (voir discussion precedente).")
    else:
        print("Cette plage rentre dans une fenetre de 5V -- un offset fixe bien")
        print("choisi pourrait fonctionner (a ajuster : offset = -v_min).")

    print()
    print(f"=== Points utilises ({nom}) ===")
    for mm, v in zip(pts_mm, pts_v):
        print(f"  mm={mm:.3f}  pos_{nom}_v={v:.4f}")


def sauvegarder_csv(pts_mm_ca, pts_v_ca, pts_mm_cg, pts_v_cg):
    ts = datetime.now().isoformat()
    with open(CSV_OUTPUT, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["condensateur", "mm", "pos_v", "timestamp"])
        for mm, v in zip(pts_mm_ca, pts_v_ca):
            writer.writerow(["ca", mm, v, ts])
        for mm, v in zip(pts_mm_cg, pts_v_cg):
            writer.writerow(["cg", mm, v, ts])
    print(f"Sauvegarde dans {CSV_OUTPUT}")


def main():
    print("=== CALIBRATION POS_CA ET POS_CG VIA LABJACK ===")
    print(f"Canal Ca : {CANAL_POS_CA}  |  Canal Cg : {CANAL_POS_CG}  (a verifier selon ton cablage)")
    print("Connexion au LabJack...")

    handle = ljm.openS("T4", "ANY", "ANY")
    info = ljm.getHandleInfo(handle)
    print(f"Connecte : {info}")
    print()
    print("Deplace Ca ou Cg, note la position mm affichee physiquement, capture avec :")
    print("  ca <mm>   |   cg <mm>")
    print("Autres commandes : fit ca | fit cg | reset ca | reset cg | save | p | q")
    print()

    pts_mm_ca, pts_v_ca = [], []
    pts_mm_cg, pts_v_cg = [], []

    try:
        while True:
            cmd = input("> ").strip()

            if cmd == "":
                continue

            parts = cmd.split()
            mot_cle = parts[0].lower()

            if mot_cle == "q":
                break

            elif mot_cle == "p":
                v_ca = lire_canal(handle, CANAL_POS_CA)
                v_cg = lire_canal(handle, CANAL_POS_CG)
                print(f"pos_ca_v = {v_ca:.4f} V   pos_cg_v = {v_cg:.4f} V")

            elif mot_cle == "save":
                sauvegarder_csv(pts_mm_ca, pts_v_ca, pts_mm_cg, pts_v_cg)

            elif mot_cle == "fit" and len(parts) == 2:
                cible = parts[1].lower()
                if cible == "ca":
                    calculer_fit("ca", pts_mm_ca, pts_v_ca)
                elif cible == "cg":
                    calculer_fit("cg", pts_mm_cg, pts_v_cg)
                else:
                    print("Utilise 'fit ca' ou 'fit cg'.")

            elif mot_cle == "reset" and len(parts) == 2:
                cible = parts[1].lower()
                if cible == "ca":
                    pts_mm_ca, pts_v_ca = [], []
                    print("Points Ca effaces.")
                elif cible == "cg":
                    pts_mm_cg, pts_v_cg = [], []
                    print("Points Cg effaces.")
                else:
                    print("Utilise 'reset ca' ou 'reset cg'.")

            elif mot_cle in ("ca", "cg") and len(parts) == 2:
                try:
                    mm = float(parts[1])
                except ValueError:
                    print("Format attendu : 'ca <mm>' ou 'cg <mm>', ex: 'ca 20.5'")
                    continue

                if mot_cle == "ca":
                    v = lire_canal(handle, CANAL_POS_CA)
                    pts_mm_ca.append(mm)
                    pts_v_ca.append(v)
                    print(f"[CA] Point ajoute #{len(pts_mm_ca)} : mm={mm:.3f}  pos_ca_v={v:.4f}")
                else:
                    v = lire_canal(handle, CANAL_POS_CG)
                    pts_mm_cg.append(mm)
                    pts_v_cg.append(v)
                    print(f"[CG] Point ajoute #{len(pts_mm_cg)} : mm={mm:.3f}  pos_cg_v={v:.4f}")

            else:
                print("Commande non reconnue.")
                print("Utilise : 'ca <mm>' | 'cg <mm>' | 'fit ca' | 'fit cg' | 'reset ca' | 'reset cg' | 'save' | 'p' | 'q'")

    finally:
        ljm.close(handle)
        print("Connexion LabJack fermee.")


if __name__ == "__main__":
    main()