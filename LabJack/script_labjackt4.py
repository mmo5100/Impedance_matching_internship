"""
Script de test - LabJack T4
Lecture continue des entrées analogiques AIN0-AIN3 (+/-10V, bornes a vis HV)
et affichage en temps reel. Sert a verifier la communication avant de
brancher des signaux du dispositif.
"""

import time
from labjack import ljm

# --- Connexion au T4 ---
# "ANY", "ANY", "ANY" : detection automatique du premier T4 trouve en USB
handle = ljm.openS("T4", "USB", "ANY")

info = ljm.getHandleInfo(handle)
print("Connecte au LabJack:")
print(f"  Type appareil      : {info[0]}")
print(f"  Numero de serie    : {info[2]}")
print(f"  Adresse IP         : {ljm.numberToIP(info[3])}")
print(f"  Port               : {info[4]}")
print(f"  Vitesse max paquet : {info[5]}")
print("-" * 40)

# --- Configuration des voies a lire ---
# AIN0-AIN3 : bornes HV, plage +/-10V (T4)
channels = ["AIN0", "AIN1", "AIN2", "AIN3"]

# (Optionnel) Forcer la plage explicitement a +/-10V sur chaque voie
# Decommenter si besoin :
# for ch in channels:
#     ljm.eWriteName(handle, f"{ch}_RANGE", 10.0)

# --- Boucle de lecture continue ---
print("Lecture en cours (Ctrl+C pour arreter)...")
print("Temps [s]\t" + "\t".join(channels))

t0 = time.time()
try:
    while True:
        values = ljm.eReadNames(handle, len(channels), channels)
        t = time.time() - t0
        ligne = f"{t:8.2f}\t" + "\t".join(f"{v:7.4f}" for v in values)
        print(ligne)
        time.sleep(0.5)  # frequence d'affichage : 2 Hz

except KeyboardInterrupt:
    print("\nArret demande par l'utilisateur.")

finally:
    ljm.close(handle)
    print("Connexion fermee.")