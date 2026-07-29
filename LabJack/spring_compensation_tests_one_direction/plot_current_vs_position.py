#!/usr/bin/env python3
"""
Trace le courant (AIN2) en fonction de la position (AIN0) à partir d'un
fichier CSV d'acquisition (colonnes : horodatage, temps_s, AIN0, AIN1, AIN2,
AIN3, courant, position, trigger).

Usage:
    python plot_courant_position.py chemin_vers_fichier.csv
"""

import sys
import matplotlib.pyplot as plt
import pandas as pd


def main(csv_path: str, out_path: str = "courant_vs_position.png"):
    # Lecture du CSV
    df = pd.read_csv(csv_path)

    # AIN0 = position, AIN2 = courant (comme demandé). On peut aussi utiliser
    # directement les colonnes "courant" et "position" si elles sont identiques.
    position = df["AIN0"]
    courant = df["AIN2"]

    fig, ax = plt.subplots(figsize=(9, 6))

    # Nuage de points, coloré selon l'ordre temporel pour visualiser un aller-retour
    sc = ax.scatter(position, courant, c=df["temps_s"], cmap="viridis", s=6)
    ax.plot(position, courant, color="gray", alpha=0.2, linewidth=0.5)

    ax.set_xlabel("Position - AIN0 (V)")
    ax.set_ylabel("Courant - AIN2 (A ou V selon calibration)")
    ax.set_title("Courant en fonction de la position")
    ax.grid(True, alpha=0.3)

    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Temps (s)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Graphique enregistré dans : {out_path}")

    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python plot_courant_position.py chemin_vers_fichier.csv")
        sys.exit(1)
    main(sys.argv[1])