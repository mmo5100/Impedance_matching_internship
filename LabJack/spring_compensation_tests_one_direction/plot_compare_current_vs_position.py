#!/usr/bin/env python3
"""
Compare le courant (AIN2) en fonction de la position (AIN0) entre deux
fichiers CSV d'acquisition (meme format que d'habitude : horodatage,
temps_s, AIN0, AIN1, AIN2, AIN3, courant, position, trigger).

Usage:
    python compare_courant_position.py fichier1.csv fichier2.csv
    python compare_courant_position.py fichier1.csv fichier2.csv --label1 "Avant" --label2 "Apres"
"""

import argparse
import matplotlib.pyplot as plt
import pandas as pd


def charger(csv_path, col_position="AIN0", col_courant="AIN2"):
    df = pd.read_csv(csv_path)
    return df[col_position], df[col_courant]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fichier1", help="Premier fichier CSV")
    parser.add_argument("fichier2", help="Deuxieme fichier CSV")
    parser.add_argument("--label1", default=None, help="Legende pour le fichier 1")
    parser.add_argument("--label2", default=None, help="Legende pour le fichier 2")
    parser.add_argument("--col-position", default="AIN0", help="Nom de la colonne position (defaut: AIN0)")
    parser.add_argument("--col-courant", default="AIN2", help="Nom de la colonne courant (defaut: AIN2)")
    parser.add_argument("--out", default="comparaison_courant_position.png", help="Nom du fichier image de sortie")
    args = parser.parse_args()

    label1 = args.label1 or args.fichier1
    label2 = args.label2 or args.fichier2

    pos1, cour1 = charger(args.fichier1, args.col_position, args.col_courant)
    pos2, cour2 = charger(args.fichier2, args.col_position, args.col_courant)

    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(pos1, cour1, ".", markersize=3, alpha=0.6, label=label1, color="tab:blue")
    ax.plot(pos2, cour2, ".", markersize=3, alpha=0.6, label=label2, color="tab:orange")

    ax.set_xlabel(f"Position - {args.col_position} [V]")
    ax.set_ylabel(f"Current - {args.col_courant} [V]")
    ax.set_title("Comparison current vs position")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    #fig.savefig(args.out, dpi=150)
    #print(f"Graphique enregistre dans : {args.out}")

    plt.show()


if __name__ == "__main__":
    main()