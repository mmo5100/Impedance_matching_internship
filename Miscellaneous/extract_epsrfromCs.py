"""
Calcul de C(position) a partir d'une formule lineaire 
puis conversion en eps_r via le modele plan-plan.

Formule utilisee :
    Cs(x) = 300 pF - x * 5.217 pF/mm      (x = position en mm)

Puis :
    eps_r = Cs * D_GAP / (EPS0 * AIRE)

Usage :
    python3 calc_epsr_formula.py 10 15 20 25 30 35 40
    (liste de positions en mm, separees par des espaces)

    ou, sans argument, une liste de positions par defaut est utilisee.
"""

import sys
import csv
import numpy as np

EPS0 = 8.8541878128e-12       # permittivite du vide (F/m)
AIRE = np.pi * (86e-3) ** 2   # aire des electrodes (m^2) -- a ajuster si besoin
D_GAP = 0.010286              # distance entre electrodes (m) -- a ajuster si besoin

C0_PF = 300.0        # pF, valeur a x=0
PENTE_PF_PAR_MM = 5.217  # pF/mm


def C_formula(x_mm):
    """Cs(x) = 300 pF - x*5.217 pF/mm, retourne C en Farads."""
    C_pF = C0_PF - x_mm * PENTE_PF_PAR_MM
    return C_pF * 1e-12


def eps_r_from_C(C_farads):
    return (C_farads * D_GAP) / (EPS0 * AIRE)


def main():
    if len(sys.argv) > 1:
        positions = [float(a) for a in sys.argv[1:]]
    else:
        # positions par defaut (celles deja mesurees au VNA)
        positions = [10.0, 15.0, 20.0, 20.6, 25.0, 30.0, 35.0, 37.5, 40.0,
                     44.75, 45.0, 45.25, 50.0, 55.0, 58.0]

    rows = []
    print(f"{'position (mm)':>14} {'C (pF)':>10} {'eps_r':>10}")
    for x in positions:
        C = C_formula(x)
        C_pF = C * 1e12
        eps_r = eps_r_from_C(C)
        flag = "  <-- C negatif ou nul, formule hors domaine !" if C_pF <= 0 else ""
        print(f"{x:>14.2f} {C_pF:>10.3f} {eps_r:>10.3f}{flag}")
        rows.append([x, C_pF, eps_r])

    out_csv = "eps_r_formule_directe.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["position_mm", "C_pF", "eps_r"])
        writer.writerows(rows)
    print(f"\nResultats sauvegardes dans : {out_csv}")


if __name__ == "__main__":
    main()