# -*- coding: utf-8 -*-
"""
estimer_delta_l.py

Estime DELTA_L1_M et DELTA_L2_M (correction des longueurs electriques
l1, l2 utilisees dans le calcul de eps_a/eps_g, cf. Durodie 1992) a
partir des fichiers de sweep DEJA ENREGISTRES (matching_run_CA_*_CG_*.csv),
sans nouvelle mesure.

Principe :
  - Chaque fichier de sweep contient les tensions BRUTES VA, VG, V+
    (pas seulement eps_a/eps_g deja calcules avec les anciens l1/l2).
  - On peut donc recalculer eps_a, eps_g pour n'importe quel (l1_eff,
    l2_eff) candidat a partir de sVA = VA - V+, sVG = VG - V+ :
        eps_a_brut = sVA*sin(2*beta*l2_eff) - sVG*sin(2*beta*l1_eff)
        eps_g_brut = sVA*cos(2*beta*l2_eff) - sVG*cos(2*beta*l1_eff)
    (sans les offsets EPS_A_OFFSET/EPS_G_OFFSET, qui ne sont qu'un
    decalage additif constant et n'affectent pas les pentes utilisees
    pour l'optimisation)
  - Objectif : trouver (DELTA_L1_M, DELTA_L2_M) qui minimisent le
    couplage croise :
        - pente de eps_g_brut en fonction de Ca, dans le groupe
          "sweep Ca" (Cg nominal fixe) -- devrait etre ~0
        - pente de eps_a_brut en fonction de Cg, dans le groupe
          "sweep Cg" (Ca nominal fixe) -- devrait etre ~0
  - Une fois (DELTA_L1_M, DELTA_L2_M) trouves, les nouveaux
    EPS_A_OFFSET / EPS_G_OFFSET sont calcules directement a partir du
    fichier "_match" (VA, VG, V+ a ce point), de sorte que
    eps_a = eps_g = 0 exactement a ce point avec les nouveaux l1/l2.

Hypothese : chaque fichier de sweep correspond a une position fixe
(nominale) de (Ca, Cg) maintenue pendant l'enregistrement -- on prend
donc la MOYENNE des N_FIN dernieres lignes valides de VA, VG, V+
comme valeur representative du point.

Usage :
    python3 estimer_delta_l.py
(configure CSV_DIR, CSV_PATTERN, N_FIN, bornes de recherche ci-dessous)
"""

import csv
import glob
import os
import re

import numpy as np
from scipy.optimize import minimize

# =============================================================================
# CONFIGURATION -- a adapter
# =============================================================================
CSV_DIR = "."
CSV_PATTERN = "matching_run_CA_*_CG_*.csv"
N_FIN = 5

FREQ_HZ = 38e6
C_LIGHT = 299792458.0
L1_M = 1.35
L2_M = 1.85
BETA = 2.0 * np.pi * FREQ_HZ / C_LIGHT

SWAP_VA_VG = False  # doit correspondre exactement au reglage du firmware

# Bornes de recherche pour Delta l1, Delta l2 (en metres). Restées
# volontairement petites : on cherche une correction de calibration
# fine, pas un multiple de la longueur d'onde (lambda/2 ~ 3.95 m a 38MHz,
# donc une recherche trop large risquerait de tomber sur un optimum
# "equivalent" mais physiquement absurde).
BORNE_DELTA_L = 0.30  # +/- 30 cm

# Poids de regularisation : penalise legerement les grandes valeurs de
# Delta l1/l2, pour eviter de tomber sur une solution "degeneree" qui
# exploite la periodicite des sin/cos (annule numeriquement les pentes
# sans correspondre a une correction physique raisonnable). Mettre a 0
# pour desactiver.
POIDS_REGULARISATION = 1e-3

MOTIF_NOM = re.compile(r"CA_(\d+)p(\d+)_CG_(\d+)p(\d+)")


def parser_nom_fichier(nom):
    m = MOTIF_NOM.search(os.path.basename(nom))
    if not m:
        return None, None
    ca = float(f"{m.group(1)}.{m.group(2)}")
    cg = float(f"{m.group(3)}.{m.group(4)}")
    return ca, cg


def trouver_valeur_dominante(valeurs, tol=0.15):
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


def charger_va_vg_vplus_finaux(fichier, n_fin):
    """Moyenne des n_fin dernieres lignes valides de VA, VG, V+."""
    VA, VG, Vp = [], [], []
    with open(fichier, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                va = float(row["VA"])
                vg = float(row["VG"])
                vp = float(row["V+"])
            except (ValueError, KeyError, TypeError):
                continue
            if any(np.isnan(v) for v in (va, vg, vp)):
                continue
            VA.append(va)
            VG.append(vg)
            Vp.append(vp)
    if not VA:
        return None
    n = min(n_fin, len(VA))
    return (np.mean(VA[-n:]), np.mean(VG[-n:]), np.mean(Vp[-n:]))


def calc_eps_brut(l1_eff, l2_eff, sVA, sVG):
    """eps_a, eps_g SANS offset, pour un l1_eff/l2_eff donne."""
    sin2bl1 = np.sin(2.0 * BETA * l1_eff)
    cos2bl1 = np.cos(2.0 * BETA * l1_eff)
    sin2bl2 = np.sin(2.0 * BETA * l2_eff)
    cos2bl2 = np.cos(2.0 * BETA * l2_eff)
    eps_a = sVA * sin2bl2 - sVG * sin2bl1
    eps_g = sVA * cos2bl2 - sVG * cos2bl1
    return eps_a, eps_g


def main():
    fichiers = sorted(glob.glob(os.path.join(CSV_DIR, CSV_PATTERN)))
    if not fichiers:
        print(f"Aucun fichier trouve avec le motif '{CSV_PATTERN}' dans '{CSV_DIR}'.")
        return
    print(f"{len(fichiers)} fichier(s) trouve(s).")

    entrees = []
    for fichier in fichiers:
        res = charger_va_vg_vplus_finaux(fichier, N_FIN)
        ca_nom, cg_nom = parser_nom_fichier(fichier)
        if res is None or ca_nom is None:
            print(f"  IGNORE (donnees ou nom illisible) : {os.path.basename(fichier)}")
            continue
        VA, VG, Vp = res
        sVA = VA - Vp
        sVG = VG - Vp
        if SWAP_VA_VG:
            sVA, sVG = sVG, sVA
        entrees.append(dict(fichier=fichier, ca_nom=ca_nom, cg_nom=cg_nom,
                             sVA=sVA, sVG=sVG,
                             est_match="_match" in os.path.basename(fichier).lower()))

    if not entrees:
        print("Aucune donnee exploitable.")
        return

    # --- Detection des deux groupes de sweep (meme logique que plot_eps_vs_sweep.py) ---
    cg_fixe, tol = trouver_valeur_dominante([e["cg_nom"] for e in entrees])
    ca_fixe, _ = trouver_valeur_dominante([e["ca_nom"] for e in entrees])
    groupe_sweep_ca = [e for e in entrees if abs(e["cg_nom"] - cg_fixe) < tol]
    groupe_sweep_cg = [e for e in entrees if abs(e["ca_nom"] - ca_fixe) < tol]

    print(f"Groupe 'sweep Ca' (Cg~={cg_fixe:.2f} fixe) : {len(groupe_sweep_ca)} fichier(s)")
    print(f"Groupe 'sweep Cg' (Ca~={ca_fixe:.2f} fixe) : {len(groupe_sweep_cg)} fichier(s)")

    ca_arr = np.array([e["ca_nom"] for e in groupe_sweep_ca])
    sVA_ca = np.array([e["sVA"] for e in groupe_sweep_ca])
    sVG_ca = np.array([e["sVG"] for e in groupe_sweep_ca])

    cg_arr = np.array([e["cg_nom"] for e in groupe_sweep_cg])
    sVA_cg = np.array([e["sVA"] for e in groupe_sweep_cg])
    sVG_cg = np.array([e["sVG"] for e in groupe_sweep_cg])

    # --- Fonction objectif : somme des carres des pentes de couplage croise ---
    def objectif(params):
        d_l1, d_l2 = params
        l1_eff = L1_M + d_l1
        l2_eff = L2_M + d_l2

        _, eps_g_ca = calc_eps_brut(l1_eff, l2_eff, sVA_ca, sVG_ca)   # eps_g pdt sweep Ca
        eps_a_cg, _ = calc_eps_brut(l1_eff, l2_eff, sVA_cg, sVG_cg)   # eps_a pdt sweep Cg

        pente_g_vs_ca = np.polyfit(ca_arr, eps_g_ca, 1)[0] if len(ca_arr) >= 2 else 0.0
        pente_a_vs_cg = np.polyfit(cg_arr, eps_a_cg, 1)[0] if len(cg_arr) >= 2 else 0.0

        return pente_g_vs_ca**2 + pente_a_vs_cg**2 + POIDS_REGULARISATION * (d_l1**2 + d_l2**2)

    # --- Recherche grossiere (grille) pour eviter un minimum local, puis affinage ---
    grille = np.linspace(-BORNE_DELTA_L, BORNE_DELTA_L, 61)
    meilleur_obj = np.inf
    meilleur_point = (0.0, 0.0)
    for d_l1 in grille:
        for d_l2 in grille:
            val = objectif((d_l1, d_l2))
            if val < meilleur_obj:
                meilleur_obj = val
                meilleur_point = (d_l1, d_l2)

    print(f"\nMeilleur point sur grille grossiere : "
          f"DELTA_L1_M={meilleur_point[0]:.4f}  DELTA_L2_M={meilleur_point[1]:.4f}  "
          f"(objectif={meilleur_obj:.6e})")

    # --- Diagnostic : pentes avant/apres correction (definie ici pour etre
    # utilisee par le tableau de compromis ci-dessous) ---
    def pentes(d_l1, d_l2):
        l1_eff, l2_eff = L1_M + d_l1, L2_M + d_l2
        _, eps_g_ca = calc_eps_brut(l1_eff, l2_eff, sVA_ca, sVG_ca)
        eps_a_cg, _ = calc_eps_brut(l1_eff, l2_eff, sVA_cg, sVG_cg)
        p1 = np.polyfit(ca_arr, eps_g_ca, 1)[0]
        p2 = np.polyfit(cg_arr, eps_a_cg, 1)[0]
        return p1, p2

    # --- Analyse de compromis : objectif optimal vs taille de correction
    # autorisee. Si l'optimum "colle" systematiquement a la borne quelle
    # que soit sa valeur, c'est le signe qu'il n'y a pas de minimum reel
    # a l'interieur d'une plage physiquement raisonnable -- le couplage
    # croise n'est alors probablement pas explicable par Delta l1/l2 seuls.
    print("\n=== Analyse de compromis : reduction du couplage vs taille de correction ===")
    print(f"{'Borne (m)':>10s}  {'DL1 trouve':>11s}  {'DL2 trouve':>11s}  "
          f"{'colle-bord?':>11s}  {'d(eps_g)/dCa':>13s}  {'d(eps_a)/dCg':>13s}")
    bornes_test = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]
    resultats_compromis = []
    for borne in bornes_test:
        def objectif_sans_reg(params):
            d_l1, d_l2 = params
            l1_eff, l2_eff = L1_M + d_l1, L2_M + d_l2
            _, eps_g_ca_ = calc_eps_brut(l1_eff, l2_eff, sVA_ca, sVG_ca)
            eps_a_cg_, _ = calc_eps_brut(l1_eff, l2_eff, sVA_cg, sVG_cg)
            p1 = np.polyfit(ca_arr, eps_g_ca_, 1)[0] if len(ca_arr) >= 2 else 0.0
            p2 = np.polyfit(cg_arr, eps_a_cg_, 1)[0] if len(cg_arr) >= 2 else 0.0
            return p1**2 + p2**2

        res_b = minimize(objectif_sans_reg, x0=(0.0, 0.0), method="Nelder-Mead",
                          bounds=[(-borne, borne), (-borne, borne)],
                          options=dict(xatol=1e-7, fatol=1e-12))
        dl1_b, dl2_b = res_b.x
        colle_bord = (abs(abs(dl1_b) - borne) < 1e-3) or (abs(abs(dl2_b) - borne) < 1e-3)
        p1_b, p2_b = pentes(dl1_b, dl2_b)
        resultats_compromis.append((borne, dl1_b, dl2_b, colle_bord, p1_b, p2_b))
        print(f"{borne:10.2f}  {dl1_b:11.4f}  {dl2_b:11.4f}  "
              f"{'OUI' if colle_bord else 'non':>11s}  {p1_b:+13.6f}  {p2_b:+13.6f}")

    print("\nSi la colonne 'colle-bord' reste 'OUI' meme pour des bornes larges (0.20-0.30 m),")
    print("cela confirme qu'il n'y a pas de minimum interieur : Delta l1/l2 seuls ne semblent")
    print("pas pouvoir expliquer completement le couplage observe. Choisis alors une borne")
    print("OU le couplage est deja bien reduit ET qui reste physiquement plausible (quelques")
    print("cm, disons <=0.05 m) plutot que de pousser la borne toujours plus loin.")

    # Point retenu pour la suite (calcul des offsets) : le premier de la
    # table ou l'optimum ne colle PAS au bord (minimum interieur genuin),
    # sinon repli conservateur sur la borne la plus petite testee (0.01 m).
    interieurs = [r for r in resultats_compromis if not r[3]]
    if interieurs:
        borne_ret, d_l1_opt, d_l2_opt, _, _, _ = interieurs[0]
        print(f"\n-> Point retenu pour les offsets : premier minimum interieur trouve "
              f"(borne={borne_ret} m).")
    else:
        borne_ret, d_l1_opt, d_l2_opt, _, _, _ = resultats_compromis[0]
        print(f"\n⚠️  Aucun minimum interieur trouve dans la plage testee -- repli conservateur "
              f"sur la borne la plus petite ({borne_ret} m). A adapter manuellement si besoin "
              f"en te basant sur le tableau ci-dessus.")

    p1_avant, p2_avant = pentes(0.0, 0.0)
    p1_apres, p2_apres = pentes(d_l1_opt, d_l2_opt)
    print(f"\nCouplage croise avec le point retenu (DELTA_L1_M={d_l1_opt:.4f}, "
          f"DELTA_L2_M={d_l2_opt:.4f}) :")
    print(f"  d(eps_g)/d(Ca)  AVANT : {p1_avant:+.6f}   APRES : {p1_apres:+.6f}")
    print(f"  d(eps_a)/d(Cg)  AVANT : {p2_avant:+.6f}   APRES : {p2_apres:+.6f}")

    # --- Nouveaux offsets a partir du fichier "_match" ---
    match_entree = next((e for e in entrees if e["est_match"]), None)
    if match_entree is not None:
        l1_eff, l2_eff = L1_M + d_l1_opt, L2_M + d_l2_opt
        eps_a_match, eps_g_match = calc_eps_brut(l1_eff, l2_eff,
                                                  match_entree["sVA"], match_entree["sVG"])
        print(f"\nFichier de match utilise : {os.path.basename(match_entree['fichier'])}")
        print(f"Nouveaux offsets a utiliser dans le firmware (avec DELTA_L1_M/DELTA_L2_M ci-dessus) :")
        print(f"  const double EPS_A_OFFSET = {eps_a_match:.6f};")
        print(f"  const double EPS_G_OFFSET = {eps_g_match:.6f};")
    else:
        print("\n⚠️  Aucun fichier '_match' trouve -- impossible de calculer les nouveaux offsets.")
        print("   Renomme ton fichier de match pour qu'il contienne 'match' dans son nom, ou")
        print("   calcule les offsets manuellement avec calibrer_offset_eps.py apres avoir")
        print("   flashe le firmware avec les DELTA_L1_M/DELTA_L2_M trouves ci-dessus.")


if __name__ == "__main__":
    main()