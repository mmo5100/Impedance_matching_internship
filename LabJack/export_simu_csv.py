"""
Export des signaux simules vers CSV, pour rejeu ulterieur via les sorties
DAC du LabJack T4 (voir playback_dac_t4.py).

Utilise la simulation simplifiee de simulation_matching_device.py
(doit se trouver dans le meme dossier).
"""

import csv
import numpy as np
import simu_matching_device as sim

# --- Choix du scenario a exporter ---
# (modifie ces valeurs selon le cas que tu veux tester)
rhoA0 = 0.425 * np.exp(1j * np.deg2rad(235))
rhoA1 = None      # ex: 0.425*np.exp(1j*np.deg2rad(127))
t_switch = None   # ex: 0.08
t_max = 0.15

nom_fichier = "signaux_test.csv"

# --- Simulation ---
res = sim.simulate(rhoA0, rhoA1=rhoA1, t_switch=t_switch, t_max=t_max)

# --- Sous-echantillonnage ---
# La simulation a un pas dt=1e-4s (trop fin pour le DAC via USB).
# On reduit a N_POINTS points repartis sur toute la duree.
N_POINTS = 150
idx = np.linspace(0, len(res["t"]) - 1, N_POINTS).astype(int)

with open(nom_fichier, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["t_s", "x_a_mm", "x_g_mm", "eps_a", "eps_g", "rho_gen"])
    for i in idx:
        writer.writerow([
            f"{res['t'][i]:.5f}",
            f"{res['x_a'][i]:.4f}",
            f"{res['x_g'][i]:.4f}",
            f"{res['eps_a'][i]:.6f}",
            f"{res['eps_g'][i]:.6f}",
            f"{res['rho_gen'][i]:.6f}",
        ])

print(f"{N_POINTS} points exportes dans {nom_fichier}")
print(f"  eps_a : min={res['eps_a'].min():.3f}  max={res['eps_a'].max():.3f}")
print(f"  eps_g : min={res['eps_g'].min():.3f}  max={res['eps_g'].max():.3f}")
print("(utilises pour la mise a l'echelle dans playback_dac_t4.py)")