"""
Script de test - LabJack T4 avec visualisation en direct + CSV
Lecture continue des entrees analogiques AIN0-AIN3 (+/-10V, bornes a vis HV),
affichage graphique en temps reel (fenetre glissante) ET enregistrement CSV.
"""

import time
import csv
from collections import deque
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from labjack import ljm

# --- Parametres ---
channels = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s = 0.5       # periode d'echantillonnage visee (en secondes)
fenetre_points = 120  # nombre de points affiches a l'ecran (60 s a 0.5 s/pt)

nom_fichier = f"mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# --- Connexion au T4 ---
handle = ljm.openS("T4", "USB", "ANY")
info = ljm.getHandleInfo(handle)
print("Connecte au LabJack:")
print(f"  Type appareil   : {info[0]}")
print(f"  Numero de serie : {info[2]}")
print(f"Enregistrement dans : {nom_fichier}")
print("Fermer la fenetre du graphique pour arreter.")

# --- Fichier CSV ---
fichier_csv = open(nom_fichier, "w", newline="")
writer = csv.writer(fichier_csv)
writer.writerow(["horodatage", "temps_s"] + channels)

# --- Buffers pour le graphique (fenetre glissante) ---
temps_buf = deque(maxlen=fenetre_points)
valeurs_buf = {ch: deque(maxlen=fenetre_points) for ch in channels}

# --- Mise en place de la figure ---
fig, ax = plt.subplots(figsize=(9, 5))
lignes = {}
for ch in channels:
    (ligne,) = ax.plot([], [], label=ch)
    lignes[ch] = ligne

ax.set_xlabel("Temps [s]")
ax.set_ylabel("Tension [V]")
ax.set_title("LabJack T4 - lecture en direct (AIN0-AIN3)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

t0 = time.time()


def mise_a_jour(frame):
    """Lit une nouvelle valeur, met a jour le CSV et le graphique."""
    values = ljm.eReadNames(handle, len(channels), channels)
    t = time.time() - t0
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    # Ecriture CSV
    writer.writerow([horodatage, f"{t:.3f}"] + [f"{v:.6f}" for v in values])
    fichier_csv.flush()

    # Mise a jour des buffers
    temps_buf.append(t)
    for ch, v in zip(channels, values):
        valeurs_buf[ch].append(v)

    # Mise a jour des courbes
    for ch in channels:
        lignes[ch].set_data(temps_buf, valeurs_buf[ch])

    # Ajustement automatique des axes
    if len(temps_buf) > 1:
        ax.set_xlim(temps_buf[0], temps_buf[-1])
    toutes_valeurs = [v for buf in valeurs_buf.values() for v in buf]
    if toutes_valeurs:
        marge = 0.05
        vmin, vmax = min(toutes_valeurs), max(toutes_valeurs)
        if vmax - vmin < 0.01:  # eviter un axe Y degenere si signal plat
            vmin, vmax = vmin - 0.05, vmax + 0.05
        ax.set_ylim(vmin - marge, vmax + marge)

    return list(lignes.values())


ani = animation.FuncAnimation(
    fig, mise_a_jour, interval=periode_s * 1000, blit=False, cache_frame_data=False
)

try:
    plt.tight_layout()
    plt.show()
finally:
    fichier_csv.close()
    ljm.close(handle)
    print(f"Fichier enregistre : {nom_fichier}")
    print("Connexion fermee.")