"""
Visualisation rapide de la calibration pos_ca / pos_cg a partir du CSV
genere par calibration_pos_ca_cg_labjack.py.

Usage : python plot_calibration.py
(place ce script dans le meme dossier que le CSV, ou adapte CSV_PATH)
"""

import csv
import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = "calibration_pos_ca_cg_labjack.csv"

data = {"ca": {"mm": [], "v": []}, "cg": {"mm": [], "v": []}}

with open(CSV_PATH, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cond = row["condensateur"]
        data[cond]["mm"].append(float(row["mm"]))
        data[cond]["v"].append(float(row["pos_v"]))

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, cond, titre in zip(axes, ["ca", "cg"], ["Ca", "Cg"]):
    mm = np.array(data[cond]["mm"])
    v = np.array(data[cond]["v"])
    if len(mm) >= 2:
        a, b = np.polyfit(mm, v, 1)
        mm_fit = np.linspace(mm.min(), mm.max(), 100)
        ax.plot(mm_fit, a * mm_fit + b, "r--", label=f"fit: v={a:.4f}*mm+{b:.4f}")
    ax.plot(mm, v, "o", label="mesures")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("Tension pos (V)")
    ax.set_title(f"Calibration {titre}")
    ax.legend()
    ax.grid(True)

plt.tight_layout()
plt.savefig("calibration_pos_ca_cg_plot.png", dpi=150)
plt.show()
print("Graphique sauvegarde dans calibration_pos_ca_cg_plot.png")