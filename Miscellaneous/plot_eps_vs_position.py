# -*- coding: utf-8 -*-
"""
plot_eps_vs_sweep.py

A partir d'un ENSEMBLE de fichiers CSV (un fichier = un run/point de
mesure a une position nominale donnee, ex.
matching_run_CA_32p18_CG_30p79.csv), extrait la position finale
(pos_a, pos_g) et les valeurs finales de eps_a / eps_g de chaque
fichier, puis trace :

  1) eps_a et eps_g en fonction de Cg (pos_g mesuree)
  2) eps_a et eps_g en fonction de Ca (pos_a mesuree)

Chaque fichier CSV doit avoir les colonnes :
    t_ms, VA, VG, V+, pos_a, pos_g, eps_a, eps_g, erreur, vel_a, vel_g
(format produit par log_match_to_csv.py)

Hypothese de resume par fichier : on prend la MOYENNE des N dernieres
lignes valides (N_FIN, defaut 5) comme valeur "finale"/en regime
etabli, plus robuste au bruit qu'une seule derniere ligne. Si le
fichier contient moins de N_FIN lignes, on utilise tout ce qui est
disponible.

On utilise la position NOMINALE (extraite du nom de fichier), pas la
position mesuree pos_a/pos_g : celle-ci a une echelle incoherente avec
les positions reelles attendues (probable souci de calibration du
capteur de position), donc la consigne nominale est plus fiable comme
abscisse ici. Une ligne pointillee verticale marque la position du
point de match (fichier contenant "_match" dans son nom) sur chaque
graphe.

Usage :
    python3 plot_eps_vs_sweep.py
(configure CSV_DIR et CSV_PATTERN ci-dessous si besoin)
"""

import csv
import glob
import os
import re

import numpy as np
import matplotlib.pyplot as plt

# =============================================================================
# CONFIGURATION -- a adapter
# =============================================================================
CSV_DIR = "."                                   # dossier contenant les fichiers CSV
CSV_PATTERN = "matching_run_CA_*_CG_*.csv"      # motif de nom de fichier a balayer
N_FIN = 5                                       # nb de dernieres lignes valides moyennees par fichier
CA_MATCH = 32.18                                # position Ca du point de match (mm)
CG_MATCH = 30.79                                # position Cg du point de match (mm)

MOTIF_NOM = re.compile(r"CA_(\d+)p(\d+)_CG_(\d+)p(\d+)")


def parser_nom_fichier(nom):
    """Extrait (Ca_nominal, Cg_nominal) depuis le nom de fichier, pour info.
    Retourne (None, None) si le motif n'est pas trouve."""
    m = MOTIF_NOM.search(os.path.basename(nom))
    if not m:
        return None, None
    ca = float(f"{m.group(1)}.{m.group(2)}")
    cg = float(f"{m.group(3)}.{m.group(4)}")
    return ca, cg


def charger_lignes_valides(path):
    """Charge toutes les lignes valides (pos_a, pos_g, eps_a, eps_g
    numeriques) d'un fichier CSV. Retourne un tableau structure ou
    None si aucune ligne valide."""
    pos_a, pos_g, eps_a, eps_g = [], [], [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pa = float(row["pos_a"])
                pg = float(row["pos_g"])
                ea = float(row["eps_a"])
                eg = float(row["eps_g"])
            except (ValueError, KeyError, TypeError):
                continue
            if any(np.isnan(v) for v in (pa, pg, ea, eg)):
                continue
            pos_a.append(pa)
            pos_g.append(pg)
            eps_a.append(ea)
            eps_g.append(eg)
    if not pos_a:
        return None
    return (np.array(pos_a), np.array(pos_g), np.array(eps_a), np.array(eps_g))


def valeur_finale(fichier, n_fin):
    """Retourne (pos_a_final, pos_g_final, eps_a_final, eps_g_final)
    moyennes sur les n_fin dernieres lignes valides du fichier, ou
    None si le fichier n'a aucune ligne exploitable."""
    donnees = charger_lignes_valides(fichier)
    if donnees is None:
        return None
    pos_a, pos_g, eps_a, eps_g = donnees
    n = min(n_fin, len(pos_a))
    return (pos_a[-n:].mean(), pos_g[-n:].mean(),
            eps_a[-n:].mean(), eps_g[-n:].mean())


def trouver_valeur_dominante(valeurs, tol=0.15):
    """Trouve la valeur qui se repete le plus (a tol pres) dans une
    liste -- utilisee pour detecter la valeur 'fixe' d'un sweep parmi
    des positions nominales issues des noms de fichiers.
    Retourne (valeur_moyenne_du_cluster, tol) ou (None, tol) si la
    liste est vide."""
    valeurs = np.array([v for v in valeurs if v is not None])
    if len(valeurs) == 0:
        return None, tol
    meilleur_compte = -1
    meilleure_valeur = valeurs[0]
    for v in valeurs:
        compte = np.sum(np.abs(valeurs - v) < tol)
        if compte > meilleur_compte:
            meilleur_compte = compte
            meilleure_valeur = v
    cluster = valeurs[np.abs(valeurs - meilleure_valeur) < tol]
    return cluster.mean(), tol


def tracer(x, eps_a, eps_g, nom_axe, fichier_sortie, x_match=None):
    ordre = np.argsort(x)
    x_tri, ea_tri, eg_tri = x[ordre], eps_a[ordre], eps_g[ordre]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(x_tri, ea_tri, color="#028090", linewidth=1.2, marker="o",
            markersize=5, label=r"$\varepsilon_a$")
    ax.plot(x_tri, eg_tri, color="#F45B69", linewidth=1.2, marker="o",
            markersize=5, label=r"$\varepsilon_g$")
    ax.axhline(0, color="gray", linewidth=0.7, linestyle="--")

    if x_match is not None:
        ax.axvline(x_match, color="black", linewidth=1.0, linestyle=":",
                   label=f"{nom_axe}$_{{match}}$ = {x_match:.2f} mm")

    ax.set_xlabel(f"{nom_axe} nominal (mm)")
    ax.set_ylabel(r"$\varepsilon$")
    ax.set_title(rf"$\varepsilon_a$, $\varepsilon_g$ en fonction de {nom_axe}")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, linewidth=0.4, alpha=0.5)

    plt.savefig(fichier_sortie, dpi=200, bbox_inches="tight")
    print(f"Figure enregistree : {fichier_sortie}")
    plt.close(fig)


def main():
    fichiers = sorted(glob.glob(os.path.join(CSV_DIR, CSV_PATTERN)))
    if not fichiers:
        print(f"Aucun fichier trouve avec le motif '{CSV_PATTERN}' dans '{CSV_DIR}'.")
        return

    print(f"{len(fichiers)} fichier(s) trouve(s).")

    # --- Etape 1 : charger la valeur finale de chaque fichier + sa position nominale ---
    entrees = []  # liste de dicts : fichier, ca_nom, cg_nom, pos_a, pos_g, eps_a, eps_g
    ignores = []

    for fichier in fichiers:
        res = valeur_finale(fichier, N_FIN)
        ca_nom, cg_nom = parser_nom_fichier(fichier)
        if res is None:
            ignores.append(os.path.basename(fichier))
            continue
        pa, pg, ea, eg = res
        entrees.append(dict(fichier=fichier, ca_nom=ca_nom, cg_nom=cg_nom,
                             pos_a=pa, pos_g=pg, eps_a=ea, eps_g=eg))
        label_nom = f"(nominal Ca={ca_nom}, Cg={cg_nom})" if ca_nom is not None else ""
        print(f"  {os.path.basename(fichier):45s} -> pos_a={pa:6.3f} pos_g={pg:6.3f} "
              f"eps_a={ea:7.4f} eps_g={eg:7.4f}  {label_nom}")

    if ignores:
        print(f"\n{len(ignores)} fichier(s) ignore(s) (aucune ligne exploitable) : {ignores}")

    if not entrees:
        print("Aucune donnee exploitable au total.")
        return

    # --- Etape 2 : detecter automatiquement les deux groupes de sweep ---
    # Groupe "sweep Ca" (Cg reste fixe pendant que Ca varie) : on detecte
    # la valeur de Cg nominal qui se repete le plus parmi tous les fichiers.
    # Groupe "sweep Cg" (Ca reste fixe pendant que Cg varie) : symetrique.
    cg_nominaux = [e["cg_nom"] for e in entrees]
    ca_nominaux = [e["ca_nom"] for e in entrees]
    cg_fixe, tol = trouver_valeur_dominante(cg_nominaux)
    ca_fixe, _ = trouver_valeur_dominante(ca_nominaux)

    if cg_fixe is None or ca_fixe is None:
        print("\n⚠️  Impossible de detecter les groupes de sweep depuis les noms de "
              "fichiers (motif CA_xxpxx_CG_xxpxx non trouve). Verifie les noms.")
        return

    groupe_sweep_ca = [e for e in entrees if e["cg_nom"] is not None and abs(e["cg_nom"] - cg_fixe) < tol]
    groupe_sweep_cg = [e for e in entrees if e["ca_nom"] is not None and abs(e["ca_nom"] - ca_fixe) < tol]

    print(f"\nGroupe 'sweep Ca' detecte (Cg nominal ~= {cg_fixe:.2f} mm fixe) : "
          f"{len(groupe_sweep_ca)} fichier(s)")
    for e in groupe_sweep_ca:
        print(f"    {os.path.basename(e['fichier'])}")

    print(f"\nGroupe 'sweep Cg' detecte (Ca nominal ~= {ca_fixe:.2f} mm fixe) : "
          f"{len(groupe_sweep_cg)} fichier(s)")
    for e in groupe_sweep_cg:
        print(f"    {os.path.basename(e['fichier'])}")

    non_classes = [e for e in entrees if e not in groupe_sweep_ca and e not in groupe_sweep_cg]
    if non_classes:
        print(f"\n⚠️  {len(non_classes)} fichier(s) n'appartiennent a aucun des deux groupes "
              f"detectes et seront exclus des graphes :")
        for e in non_classes:
            print(f"    {os.path.basename(e['fichier'])} (Ca_nom={e['ca_nom']}, Cg_nom={e['cg_nom']})")

    # --- Etape 3 : tracer chaque graphe avec uniquement le groupe pertinent ---
    # Axe x = position NOMINALE (issue du nom de fichier), pas mesuree :
    # pos_a/pos_g mesures ont une echelle incoherente avec les positions
    # reelles attendues (probable souci de calibration du capteur de
    # position), donc on utilise la valeur de consigne comme abscisse.
    # Les lignes pointillees de match utilisent les constantes CA_MATCH
    # / CG_MATCH definies en haut du fichier.

    if groupe_sweep_ca:
        ca_arr = np.array([e["ca_nom"] for e in groupe_sweep_ca])
        eps_a_arr = np.array([e["eps_a"] for e in groupe_sweep_ca])
        eps_g_arr = np.array([e["eps_g"] for e in groupe_sweep_ca])
        tracer(ca_arr, eps_a_arr, eps_g_arr, "Ca", "eps_vs_Ca_sweep.png", x_match=CA_MATCH)
    else:
        print("\nPas de fichiers dans le groupe 'sweep Ca' -- graphe eps_vs_Ca non genere.")

    if groupe_sweep_cg:
        cg_arr = np.array([e["cg_nom"] for e in groupe_sweep_cg])
        eps_a_arr = np.array([e["eps_a"] for e in groupe_sweep_cg])
        eps_g_arr = np.array([e["eps_g"] for e in groupe_sweep_cg])
        tracer(cg_arr, eps_a_arr, eps_g_arr, "Cg", "eps_vs_Cg_sweep.png", x_match=CG_MATCH)
    else:
        print("\nPas de fichiers dans le groupe 'sweep Cg' -- graphe eps_vs_Cg non genere.")


if __name__ == "__main__":
    main()