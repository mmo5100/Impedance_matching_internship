"""
Boucle fermee SEMI-AUTOMATIQUE : mesure VNA -> calcul (Ca, Cg) -> servos.

Le VNA est pilote a la main (PC Windows 8 dedie, pas de controle a distance) :
1. Tu fais une mesure et tu exportes un fichier .s5p
2. Ce script lit ce fichier, en extrait Gamma_A = S22 (port 2 = antenne),
   calcule les (Ca, Cg) qui annulent la reflexion au generateur, convertit
   en angles servo, et les envoie a accord_servo.ino
3. Tu refais une mesure (le dispositif a bouge), tu re-exportes, le script
   relit le MEME chemin de fichier et recommence

Convention des ports VNA (8 ports, 5 actifs) :
    port 1 = generateur, port 2 = antenne, port 3 = V2, port 4 = V1, port 5 = V+
Gamma_A est pris directement comme S22 (mesure brute au port antenne).

Modele RF repris de calcul_lt_1m.py (methode Mobius/vectorisee, ABCD).
lt FIXE a 0.91 m (32.5 MHz, Table 1 papier Design) -- a changer ci-dessous
si la longueur mecanique montee est differente.
"""

import time
import numpy as np
import serial

from read_touchstone import lire_touchstone

# ============================================================================
# PARAMETRES PHYSIQUES (repris de calcul_lt_1m.py)
# ============================================================================
f_mhz = 32.5
f = f_mhz * 1e6
c_light = 3e8
Z0 = 50.0
w = 2 * np.pi * f
beta = w / c_light

Ls_serie = 70e-9        # H, inductance serie mesuree
Cs_neutre = 135.1e-12   # F, Table 1 a 32.5 MHz

lt = 0.91   # m, longueur electrique FIXE -- A AJUSTER si montage different

Ca_min, Ca_max = 40e-12, 205e-12   # plage de travail des condensateurs
Cg_min, Cg_max = 40e-12, 205e-12

# --- Liaison serie vers accord_servo.ino ---
PORT_SERIE = "COM5"
BAUD = 9600

# --- Mapping mecanique (mm) -> angle servo (deg) -- PROVISOIRE, non calibre ---
ANGLE_MIN, ANGLE_MAX = 0.0, 180.0


def raw(C, Ls=Ls_serie):
    """Y = 1/(jwLs + 1/jwC), en Siemens."""
    return w * C / (1 - w ** 2 * Ls * C)


b_self_fixe = -Z0 * raw(Cs_neutre)


def b_total(C):
    """Susceptance normalisee totale du stub = capa variable + self fixe."""
    return Z0 * raw(C) + b_self_fixe


def ABCD(b_a, b_g, theta):
    """A,B,C,D du reseau {shunt b_a}--{ligne theta}--{shunt b_g}."""
    c, s = np.cos(theta), np.sin(theta)
    A = c - b_g * s
    B = 1j * Z0 * s
    C_ = 1j * ((b_a + b_g) * c + (1 - b_a * b_g) * s) / Z0
    D = c - b_a * s
    return A, B, C_, D


def rhoA_matched(Ca, Cg, lt_val):
    """Calcul de rhoA tel que yG=1, pour des Ca, Cg donnes (vectorise)."""
    A, B, C_, D = ABCD(b_total(Ca), b_total(Cg), beta * lt_val)
    zA_ohm = (B + A * Z0) / (C_ * Z0 + D)
    return (zA_ohm - Z0) / (zA_ohm + Z0)


def trouver_Ca_Cg(rhoA_cible, lt_val=lt, n=300):
    """
    Inversion : a partir d'un Gamma_A cible (mesure), trouve le (Ca, Cg)
    de la grille qui s'en approche le plus.

    Methode : on calcule rhoA_matched(Ca, Cg, lt) sur toute la grille
    (Mobius, vectorise -- meme principe que calcul_lt_1m.py), puis on
    cherche le point de la grille le plus proche de rhoA_cible. Pas de
    fsolve : direct, robuste, rapide.

    Retourne (Ca, Cg, residu) -- residu = |rhoA_grille - rhoA_cible|,
    a verifier : si trop grand, rhoA_cible est hors du domaine accessible
    par le dispositif a cette longueur lt.
    """
    Ca_v = np.linspace(Ca_min, Ca_max, n)
    Cg_v = np.linspace(Cg_min, Cg_max, n)
    Ca_g, Cg_g = np.meshgrid(Ca_v, Cg_v)
    rho_g = rhoA_matched(Ca_g, Cg_g, lt_val)

    ecart = np.abs(rho_g - rhoA_cible)
    idx = np.unravel_index(np.argmin(ecart), ecart.shape)

    Ca_best = Ca_g[idx]
    Cg_best = Cg_g[idx]
    residu = ecart[idx]
    return Ca_best, Cg_best, residu


def C_to_angle(C):
    """Convertit une capacite [F] en angle servo [deg], clippe a [0,180]."""
    frac = (C - Ca_min) / (Ca_max - Ca_min)
    angle = ANGLE_MIN + frac * (ANGLE_MAX - ANGLE_MIN)
    return max(0.0, min(180.0, angle))


def lire_gamma_A(chemin_s5p):
    """Lit le fichier .s5p et renvoie Gamma_A = S22 a la frequence f_mhz."""
    res = lire_touchstone(chemin_s5p)
    f_hz_mesure = res["freq_hz"]
    idx_f = np.argmin(np.abs(f_hz_mesure - f))
    f_trouvee_mhz = f_hz_mesure[idx_f] / 1e6

    # S22 : indices 0-based -> port 2 = indice 1
    gamma_A = res["S"][idx_f, 1, 1]
    return gamma_A, f_trouvee_mhz


def envoyer_angles(ser, angle_a, angle_g):
    """Envoie une trame angle_a,angle_g a l'Arduino et lit la reponse."""
    trame = f"{angle_a:.1f},{angle_g:.1f}\n"
    ser.write(trame.encode())
    reponse = ser.readline().decode(errors="replace").strip()
    return reponse


# ============================================================================
# BOUCLE SEMI-AUTOMATIQUE
# ============================================================================
if __name__ == "__main__":
    CHEMIN_S5P = "Autotuning_Measurement_Line_G_L_VCG_VCL_DCFwd.s5p"   # A MODIFIER : chemin du fichier exporte par le VNA

    print(f"--- Boucle fermee semi-automatique ({f_mhz} MHz, lt={lt:.3f} m) ---")
    print(f"Fichier VNA relu a chaque iteration : {CHEMIN_S5P}")
    print("[!] Mapping Ca/Cg -> angle PROVISOIRE, non calibre mecaniquement.\n")

    ser = serial.Serial(PORT_SERIE, BAUD, timeout=2)
    time.sleep(2)
    print("Port serie ouvert. Message Arduino :")
    print(" ", ser.readline().decode(errors="replace").strip())

    try:
        while True:
            input("\n>>> Fais ta mesure VNA, exporte le .s5p, puis appuie sur Entree...")

            try:
                gamma_A, f_trouvee = lire_gamma_A(CHEMIN_S5P)
            except FileNotFoundError:
                print(f"  [!] Fichier introuvable : {CHEMIN_S5P} -- reessaie.")
                continue

            print(f"  Frequence mesuree la plus proche : {f_trouvee:.3f} MHz")
            print(f"  Gamma_A mesure (S22) : |Gamma_A|={abs(gamma_A):.4f}  "
                  f"phase={np.angle(gamma_A, deg=True):.1f} deg")

            Ca, Cg, residu = trouver_Ca_Cg(gamma_A)
            print(f"  Ca trouve = {Ca*1e12:.1f} pF   Cg trouve = {Cg*1e12:.1f} pF")
            print(f"  Residu |rho_grille - rho_cible| = {residu:.4f}"
                  + ("  [!] grand : hors domaine accessible ?" if residu > 0.05 else ""))

            angle_a = C_to_angle(Ca)
            angle_g = C_to_angle(Cg)
            reponse = envoyer_angles(ser, angle_a, angle_g)
            print(f"  -> angle_a={angle_a:.1f}  angle_g={angle_g:.1f}   reponse Arduino : {reponse}")

    except KeyboardInterrupt:
        print("\nArret demande par l'utilisateur.")

    finally:
        ser.close()
        print("Port serie ferme.")