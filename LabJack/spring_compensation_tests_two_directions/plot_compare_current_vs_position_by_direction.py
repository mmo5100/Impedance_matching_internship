#!/usr/bin/env python3
"""
Compare le courant (AIN2) en fonction de la position (AIN0) entre deux
fichiers CSV d'acquisition (meme format que le script d'acquisition avec
pile de compensation : horodatage, temps_s, AIN0, AIN1, AIN2, AIN3,
courant, position, commande_V_reelle, commande_V_DAC, phase).

L'"offset" positif/negatif fait reference au sens de la commande reelle
envoyee au moteur (V_reel = V_DAC - OFFSET_PILE) : phase "aller"
(commande > 0) vs phase "retour" (commande < 0). Une regression
polynomiale d'ordre 2 (quadratique) courant(position) est calculee
separement pour ces deux sens, pour chacun des deux fichiers. Les
points de repos (commande == 0, pas de mouvement commande) sont exclus
des regressions. Les coefficients sont imprimes dans le terminal et les
courbes ajustees sont superposees au nuage de points.

Usage:
    python compare_courant_position.py fichier1.csv fichier2.csv
    python compare_courant_position.py fichier1.csv fichier2.csv --label1 "Avant" --label2 "Apres"
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


def charger(csv_path, col_position, col_courant, col_commande):
    df = pd.read_csv(csv_path)
    if col_commande not in df.columns:
        raise SystemExit(
            f"Colonne de commande '{col_commande}' introuvable dans {csv_path}. "
            f"Colonnes disponibles : {list(df.columns)}"
        )
    return df[col_position], df[col_courant], df[col_commande]


def regression_quadratique(pos, cour, commande, label, plage_min, plage_max):
    """
    Calcule une regression quadratique (ordre 2) courant(position),
    separement pour commande > 0 (offset/sens positif) et commande < 0
    (offset/sens negatif). Les points au repos (commande == 0) sont
    exclus, ainsi que les points dont la position est hors de
    [plage_min, plage_max]. Retourne un dict {nom_zone: coeffs} et
    imprime les coefficients.
    """
    pos = np.asarray(pos, dtype=float)
    cour = np.asarray(cour, dtype=float)
    commande = np.asarray(commande, dtype=float)

    masque_plage = (pos >= plage_min) & (pos <= plage_max)

    resultats = {}

    for nom_zone, masque_cmd in (("positif", commande > 0), ("negatif", commande < 0)):
        masque = masque_cmd & masque_plage
        n_pts = masque.sum()
        if n_pts < 3:
            print(f"[{label}] Sens de commande {nom_zone} : pas assez de points "
                  f"({n_pts}) pour une regression d'ordre 2, ignoree.")
            resultats[nom_zone] = None
            continue

        coeffs = np.polyfit(pos[masque], cour[masque], 2)
        a, b, c = coeffs
        print(f"[{label}] Regression quadratique - commande {nom_zone} "
              f"(n={n_pts} points) : "
              f"courant = {a:.6g} * position^2 + {b:.6g} * position + {c:.6g}")

        resultats[nom_zone] = coeffs

    return resultats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fichier1", help="Premier fichier CSV")
    parser.add_argument("fichier2", help="Deuxieme fichier CSV")
    parser.add_argument("--label1", default=None, help="Legende pour le fichier 1")
    parser.add_argument("--label2", default=None, help="Legende pour le fichier 2")
    parser.add_argument("--col-position", default="AIN0", help="Nom de la colonne position (defaut: AIN0)")
    parser.add_argument("--col-courant", default="AIN2", help="Nom de la colonne courant (defaut: AIN2)")
    parser.add_argument("--col-commande", default="commande_V_reelle",
                         help="Nom de la colonne de commande reelle, dont le signe definit "
                              "l'offset positif/negatif (defaut: commande_V_reelle)")
    parser.add_argument("--plage-min", type=float, default=-3.0,
                         help="Borne basse de position incluse dans la regression (defaut: -1.0 V)")
    parser.add_argument("--plage-max", type=float, default=6.0,
                         help="Borne haute de position incluse dans la regression (defaut: 8.0 V)")
    parser.add_argument("--out", default="comparaison_courant_position.png", help="Nom du fichier image de sortie")
    args = parser.parse_args()

    label1 = args.label1 or args.fichier1
    label2 = args.label2 or args.fichier2

    pos1, cour1, cmd1 = charger(args.fichier1, args.col_position, args.col_courant, args.col_commande)
    pos2, cour2, cmd2 = charger(args.fichier2, args.col_position, args.col_courant, args.col_commande)

    print("=" * 70)
    print("Coefficients des regressions quadratiques (courant = a*x^2 + b*x + c)")
    print("Zones definies par le signe de la commande reelle (sens de deplacement)")
    print(f"Regression limitee a la plage de position [{args.plage_min:g}, {args.plage_max:g}] V")
    print("=" * 70)
    coeffs1 = regression_quadratique(pos1, cour1, cmd1, label1, args.plage_min, args.plage_max)
    coeffs2 = regression_quadratique(pos2, cour2, cmd2, label2, args.plage_min, args.plage_max)
    print("=" * 70)

    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(pos1, cour1, ".", markersize=3, alpha=0.6, label=label1, color="tab:blue")
    ax.plot(pos2, cour2, ".", markersize=3, alpha=0.6, label=label2, color="tab:orange")

    # Superposition des courbes de regression
    couleurs = {
        (label1, "positif"): "navy",
        (label1, "negatif"): "royalblue",
        (label2, "positif"): "darkorange",
        (label2, "negatif"): "peru",
    }

    for label, pos, commande, coeffs in (
        (label1, pos1, cmd1, coeffs1),
        (label2, pos2, cmd2, coeffs2),
    ):
        pos = np.asarray(pos, dtype=float)
        commande = np.asarray(commande, dtype=float)
        masque_plage = (pos >= args.plage_min) & (pos <= args.plage_max)
        for nom_zone, coefs in coeffs.items():
            if coefs is None:
                continue
            if nom_zone == "positif":
                x_zone = pos[(commande > 0) & masque_plage]
            else:
                x_zone = pos[(commande < 0) & masque_plage]
            if x_zone.size == 0:
                continue
            x_fit = np.linspace(x_zone.min(), x_zone.max(), 200)
            y_fit = np.polyval(coefs, x_fit)
            ax.plot(
                x_fit, y_fit, "-", linewidth=2,
                color=couleurs[(label, nom_zone)],
                label=f"{label} - fit quad. (commande {nom_zone})",
            )

    ax.set_xlabel(f"Position - {args.col_position} [V]")
    ax.set_ylabel(f"Current - {args.col_courant} [V]")
    ax.set_title("Comparison current vs position (par sens de commande)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    #fig.savefig(args.out, dpi=150)
    #print(f"Graphique enregistre dans : {args.out}")

    plt.show()


if __name__ == "__main__":
    main()