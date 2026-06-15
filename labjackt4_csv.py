"""
Script de test - LabJack T4 avec enregistrement CSV
Lecture continue des entrees analogiques AIN0-AIN3 (+/-10V, bornes a vis HV),
affichage en temps reel ET enregistrement dans un fichier CSV horodate.
"""

import time
import csv
from datetime import datetime
from labjack import ljm

# --- Parametres ---
channels = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s = 0.5  # periode d'echantillonnage (en secondes)

# Nom de fichier CSV avec horodatage (ex: mesures_20260615_103245.csv)
nom_fichier = f"mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# --- Connexion au T4 ---
handle = ljm.openS("T4", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print("Connecte au LabJack:")
print(f"  Type appareil      : {info[0]}")
print(f"  Numero de serie    : {info[2]}")
print("-" * 40)
print(f"Enregistrement dans : {nom_fichier}")
print("Lecture en cours (Ctrl+C pour arreter)...")
print("Temps [s]\t" + "\t".join(channels))

# --- Ouverture du fichier CSV ---
fichier_csv = open(nom_fichier, "w", newline="")
writer = csv.writer(fichier_csv)

# Ligne d'en-tete : horodatage absolu + temps relatif + une colonne par voie
writer.writerow(["horodatage", "temps_s"] + channels)

t0 = time.time()
try:
    while True:
        values = ljm.eReadNames(handle, len(channels), channels)
        t = time.time() - t0
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        # Affichage console
        ligne_affichage = f"{t:8.2f}\t" + "\t".join(f"{v:7.4f}" for v in values)
        print(ligne_affichage)

        # Ecriture CSV
        writer.writerow([horodatage, f"{t:.3f}"] + [f"{v:.6f}" for v in values])
        fichier_csv.flush()  # ecrit immediatement sur le disque (securite)

        time.sleep(periode_s)

except KeyboardInterrupt:
    print("\nArret demande par l'utilisateur.")

finally:
    fichier_csv.close()
    ljm.close(handle)
    print(f"Fichier enregistre : {nom_fichier}")
    print("Connexion fermee.")