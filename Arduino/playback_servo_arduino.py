"""
Rejeu des signaux simules (x_a_mm -> servo Ca, x_g_mm -> servo Cg) via
liaison serie vers accord_servo.ino.

Lit signaux_test.csv (genere par export_simu_csv.py) et envoie les
positions successives, converties en angles servo, sur le port serie,
avec un pas de temps "playback_dt" choisi.

============================================================================
MISE A L'ECHELLE (a adapter selon la calibration mecanique reelle)
============================================================================
Les positions x_a_mm, x_g_mm du CSV :

    X_MIN_MM = 18.0 mm  (Cs ~ 205 pF)
    X_MAX_MM = 50.0 mm  (Cs ~ 40 pF) 

On les ramene lineairement sur la plage angulaire du servo (0-180 deg) via :

    angle = ANGLE_MIN + (x - X_MIN_MM)/(X_MAX_MM - X_MIN_MM) * (ANGLE_MAX - ANGLE_MIN)

  x = X_MIN_MM -> angle = ANGLE_MIN (0 deg)
  x = X_MAX_MM -> angle = ANGLE_MAX (180 deg)


Correspondance PROVISOIRE, pas encore calibree sur le montage reel.
A ajuster (ou inverser ANGLE_MIN/ANGLE_MAX) apres verification mecanique.

============================================================================
"""

import csv
import time
import serial

# --- Parametres ---
PORT = "COM5"        # A MODIFIER : voir Outils > Port dans l'IDE Arduino
BAUD = 9600
nom_fichier = "signaux_test.csv"
playback_dt = 0.05    # secondes entre deux points (ralenti vs simulation)
n_repetitions = 1     # nombre de fois ou rejouer la sequence (0 = infini)

# Plage mecanique (mm) -- cf simu_matching_device.py (x_min, x_max)
X_MIN_MM, X_MAX_MM = 18.0, 50.0
# Plage angulaire servo (deg) -- PROVISOIRE, a recalibrer sur le vrai montage
ANGLE_MIN, ANGLE_MAX = 0.0, 180.0


def x_to_angle(x_mm):
    """Convertit une position mecanique [mm] en angle servo [deg], avec clipping."""
    x_c = max(min(X_MIN_MM, X_MAX_MM), min(max(X_MIN_MM, X_MAX_MM), x_mm))
    frac = (x_c - X_MIN_MM) / (X_MAX_MM - X_MIN_MM)
    angle = ANGLE_MIN + frac * (ANGLE_MAX - ANGLE_MIN)
    return max(0.0, min(180.0, angle))  # securite supplementaire cote PC


# --- Lecture du CSV ---
with open(nom_fichier) as f:
    rows = list(csv.DictReader(f))

print(f"{len(rows)} points charges depuis {nom_fichier}")
print(f"Duree du rejeu : {len(rows) * playback_dt:.1f} s par repetition")
print("servo Ca <- x_a_mm   |   servo Cg <- x_g_mm")
print(f"Mise a l'echelle : x in [{X_MIN_MM},{X_MAX_MM}] mm -> angle in [{ANGLE_MIN},{ANGLE_MAX}] deg")
print("[!] Mapping PROVISOIRE -- aucune calibration mecanique reelle effectuee.")

# --- Connexion serie ---
ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)  # laisser le temps a l'Arduino de redemarrer

print(f"\nPort {PORT} ouvert. Message de demarrage :")
print(" ", ser.readline().decode(errors="replace").strip())
print("Ctrl+C pour arreter (les servos resteront a la derniere position envoyee).")

try:
    rep = 0
    while True:
        for row in rows:
            angle_a = x_to_angle(float(row["x_a_mm"]))
            angle_g = x_to_angle(float(row["x_g_mm"]))

            trame = f"{angle_a:.1f},{angle_g:.1f}\n"
            ser.write(trame.encode())
            reponse = ser.readline().decode(errors="replace").strip()

            t_ms = float(row["t_s"]) * 1e3
            print(f"  t_sim={t_ms:6.1f} ms   angle_a={angle_a:6.1f}  angle_g={angle_g:6.1f}   -> {reponse}")
            time.sleep(playback_dt)

        rep += 1
        if n_repetitions and rep >= n_repetitions:
            break
        print(f"-- repetition {rep + 1} --")

except KeyboardInterrupt:
    print("\nArret demande par l'utilisateur.")

finally:
    ser.close()
    print("Port serie ferme.")