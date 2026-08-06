"""
Comparison of pyRFtk (analytical model) vs the VNA measurement grid (Ca,Cg),
and an empirical map of |Gamma_G|^2 -- WITHOUT running HFSS for every point.

Corresponds to discussion points 1, 3, 4:
  1) Compare the analytical pyRFtk model (circuit_pyrftk.py) against EVERY
     measured point of the (Ca,Cg) grid, not just a handful of HFSS points.
  3) Build an empirical 2D map of |Gamma_G|^2 directly from the VNA
     measurements (measured equivalent of map_operational_domain.py).
  4) Recommend a small set of representative points (corners + center +
     worst pyRFtk/VNA discrepancies) to validate under HFSS, instead of the
     whole grid.

REQUIREMENTS:
  - .s2p files are named "CA_<xx>p<xx>_CG<yy>p<yy>.s2p", where <xx>p<xx>
    encodes a value in mm with 'p' standing in for the decimal point
    (e.g. "CA_20p00_CG45p00.s2p" -> Ca=20.00 mm, Cg=45.00 mm).
  - lire_touchstone() comes from VNA/read_touchstone.py (already in the repo).
  - construire_circuit() comes from PyRFtk/circuit_pyrftk.py (already in the
    repo) -- takes Ca, Cg in FARADS and returns a 2-port circuit
    ['antenne', 'generateur'].

VNA PORT CONVENTION (check/adjust if needed):
  port 1 = generator, port 2 = antenna (convention used elsewhere in the
  repo). So:
    S11 measured (VNA)  <-> S[1,1] of the pyRFtk model (index 'generateur')
    S22 measured (VNA)  <-> S[0,0] of the pyRFtk model (index 'antenne')
  If your convention is reversed, set INVERSER_PORTS = True below.
"""

import os
import re
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def trouver_racine_depot(depart=None, max_remontees=6):
    """
    Walks up from 'depart' (defaults to this script's own directory) until
    it finds a directory that contains both PyRFtk/circuit_pyrftk.py and
    VNA/read_touchstone.py -- so this script works no matter where it is
    placed inside the repo.
    """
    if depart is None:
        depart = os.path.dirname(os.path.abspath(__file__))
    courant = depart
    for _ in range(max_remontees):
        a = os.path.join(courant, "PyRFtk", "circuit_pyrftk.py")
        b = os.path.join(courant, "VNA", "read_touchstone.py")
        if os.path.isfile(a) and os.path.isfile(b):
            return courant
        parent = os.path.dirname(courant)
        if parent == courant:  # filesystem root reached
            break
        courant = parent
    raise RuntimeError(
        "Could not automatically locate the repo root (a directory "
        "containing both PyRFtk/circuit_pyrftk.py and "
        "VNA/read_touchstone.py). Check that this script is somewhere "
        "INSIDE the Impedance_matching_internship repo, or set REPO_ROOT "
        "manually below."
    )


try:
    REPO_ROOT = trouver_racine_depot()
except RuntimeError as e:
    print(e)
    sys.exit(1)

sys.path.append(os.path.join(REPO_ROOT, "PyRFtk"))
sys.path.append(os.path.join(REPO_ROOT, "VNA"))

import circuit_pyrftk  # noqa: E402
from read_touchstone import lire_touchstone          # noqa: E402
from circuit_pyrftk import construire_circuit  # noqa: E402

# ============================================================================
# PARAMETERS TO ADJUST
# ============================================================================
DOSSIER_MESURES = os.path.join(REPO_ROOT, "VNA")  # folder with the grid .s2p files
F_CIBLE_HZ = 38e6                     # frequency at which to compare
INVERSER_PORTS = False                # see port convention above

# lt (length between the 2 stubs) and ls (fixed stub length) are both
# IMPOSED here (not auto-computed by circuit_pyrftk.py):
LT_VAL = 0.415   # m -- <-- SET your imposed value for lt here
LS_VAL = 0.915   # m -- <-- SET your imposed value for ls here

# construire_circuit() reads 'ls' as a global variable of the
# circuit_pyrftk module (not a parameter) -- so we overwrite the value
# computed by ls_from_Cs() at module load time, BEFORE any call to
# construire_circuit().
circuit_pyrftk.ls = LS_VAL
print(f"lt imposed at {LT_VAL*1000:.1f} mm, ls imposed at {LS_VAL*1000:.1f} mm "
      f"(values automatically computed by circuit_pyrftk.py are ignored).")

# Historical Cs(x) formula ("Design" paper, section 3.1)
def Cs_from_x_mm(x_mm):
    return (300.0 - x_mm * 5.217) * 1e-12  # F


# ============================================================================
# FILENAME PARSING
# ============================================================================
PATTERN = re.compile(r"CA_(\d+)p(\d+)_CG(\d+)p(\d+)\.s2p", re.IGNORECASE)


def parser_nom_fichier(nom):
    m = PATTERN.search(nom)
    if not m:
        return None
    ca_int, ca_dec, cg_int, cg_dec = m.groups()
    ca_mm = float(f"{ca_int}.{ca_dec}")
    cg_mm = float(f"{cg_int}.{cg_dec}")
    return ca_mm, cg_mm


def index_freq_le_plus_proche(freq_hz, cible_hz):
    return int(np.argmin(np.abs(freq_hz - cible_hz)))


# ============================================================================
# MAIN LOOP: walks through all .s2p files in the folder, compares to pyRFtk
# ============================================================================
def comparer_grille(dossier=DOSSIER_MESURES, f_cible_hz=F_CIBLE_HZ, lt_val=LT_VAL):
    lignes = []

    fichiers = sorted(f for f in os.listdir(dossier) if f.lower().endswith(".s2p"))
    if not fichiers:
        print(f"No .s2p file found in '{dossier}'.")
        return pd.DataFrame()

    for nom in fichiers:
        parsed = parser_nom_fichier(nom)
        if parsed is None:
            print(f"  [!] Unrecognized filename, skipped: {nom}")
            continue
        ca_mm, cg_mm = parsed

        chemin = os.path.join(dossier, nom)
        res = lire_touchstone(chemin)
        k = index_freq_le_plus_proche(res["freq_hz"], f_cible_hz)
        S_mes = res["S"][k]  # measured 2x2 matrix, port1=generator, port2=antenna

        if INVERSER_PORTS:
            s_gen_mes = S_mes[1, 1]
            s_ant_mes = S_mes[0, 0]
        else:
            s_gen_mes = S_mes[0, 0]
            s_ant_mes = S_mes[1, 1]

        Ca_F = Cs_from_x_mm(ca_mm)
        Cg_F = Cs_from_x_mm(cg_mm)
        ct = construire_circuit(Ca_F, Cg_F, lt_val)
        S_mod = ct.getS(f_cible_hz)  # ports ['antenne', 'generateur']
        s_ant_mod = S_mod[0, 0]
        s_gen_mod = S_mod[1, 1]

        dB = lambda z: 20 * np.log10(max(abs(z), 1e-12))

        lignes.append({
            "fichier": nom,
            "Ca_mm": ca_mm,
            "Cg_mm": cg_mm,
            "freq_MHz_reelle": res["freq_hz"][k] / 1e6,
            "|S_gen|_mes_dB": dB(s_gen_mes),
            "|S_gen|_mod_dB": dB(s_gen_mod),
            "ecart_gen_dB": dB(s_gen_mes) - dB(s_gen_mod),
            "|S_ant|_mes_dB": dB(s_ant_mes),
            "|S_ant|_mod_dB": dB(s_ant_mod),
            "ecart_ant_dB": dB(s_ant_mes) - dB(s_ant_mod),
            "Gamma2_G_mesure": abs(s_gen_mes) ** 2,
        })

    return pd.DataFrame(lignes)


# ============================================================================
# PARITY PLOT: measured vs modeled |S_gen| (direct model validation)
# ============================================================================
def tracer_parite(df, chemin_sortie="parite_pyrftk_vs_vna.pdf"):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df["|S_gen|_mes_dB"], df["|S_gen|_mod_dB"], s=25, alpha=0.7)

    lo = min(df["|S_gen|_mes_dB"].min(), df["|S_gen|_mod_dB"].min())
    hi = max(df["|S_gen|_mes_dB"].max(), df["|S_gen|_mod_dB"].max())
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, label="y = x (perfect agreement)")

    ax.set_xlabel("|S_gen| measured [dB]")
    ax.set_ylabel("|S_gen| pyRFtk model [dB]")
    ax.set_title("Parity: pyRFtk vs VNA")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    plt.savefig(chemin_sortie, dpi=150)
    print(f"Parity plot saved: {chemin_sortie}")
    plt.show()


# ============================================================================
# SIDE-BY-SIDE HEATMAPS: measurement vs model, shared color scale
# ============================================================================
def tracer_heatmaps_comparees(df, chemin_sortie="heatmaps_mesure_vs_modele.pdf"):
    pivot_mes = df.pivot(index="Ca_mm", columns="Cg_mm", values="|S_gen|_mes_dB")
    pivot_mod = df.pivot(index="Ca_mm", columns="Cg_mm", values="|S_gen|_mod_dB")

    vmin = min(pivot_mes.min().min(), pivot_mod.min().min())
    vmax = max(pivot_mes.max().max(), pivot_mod.max().max())

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
    for ax, pivot, titre in zip(axes, [pivot_mes, pivot_mod], ["Measurement (VNA)", "Model (pyRFtk)"]):
        im = ax.pcolormesh(pivot.columns, pivot.index, pivot.values,
                            shading="auto", cmap="viridis_r", vmin=vmin, vmax=vmax)
        ax.set_xlabel("Cg [mm]")
        ax.set_title(titre)
    axes[0].set_ylabel("Ca [mm]")
    fig.colorbar(im, ax=axes, label="|S_gen| [dB]", shrink=0.85)
    fig.suptitle(f"|S_gen| at {F_CIBLE_HZ/1e6:.1f} MHz -- measurement vs model")
    plt.savefig(chemin_sortie, dpi=150, bbox_inches="tight")
    print(f"Side-by-side heatmaps saved: {chemin_sortie}")
    plt.show()


# ============================================================================
# HISTOGRAM OF THE pyRFtk - VNA DISCREPANCY
# ============================================================================
def tracer_histogramme_ecart(df, chemin_sortie="histogramme_ecart.pdf"):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(df["ecart_gen_dB"], bins=20, edgecolor="black", alpha=0.8)
    ax.axvline(df["ecart_gen_dB"].median(), color="red", linestyle="--",
               label=f"median = {df['ecart_gen_dB'].median():.2f} dB")
    ax.set_xlabel("|S_gen| discrepancy, measured - model [dB]")
    ax.set_ylabel("Number of points")
    ax.set_title("Distribution of the pyRFtk vs VNA discrepancy")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(chemin_sortie, dpi=150)
    print(f"Histogram saved: {chemin_sortie}")
    plt.show()


# ============================================================================
# EMPIRICAL 2D MAP OF |Gamma_G|^2 (point 3)
# ============================================================================
def tracer_carte_gamma2(df, chemin_sortie="carte_gamma2_mesure.pdf"):
    pivot = df.pivot(index="Ca_mm", columns="Cg_mm", values="Gamma2_G_mesure")
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.pcolormesh(pivot.columns, pivot.index, pivot.values, shading="auto", cmap="viridis_r")
    fig.colorbar(im, ax=ax, label="|Gamma_G|^2 (measured)")
    ax.set_xlabel("Cg [mm]")
    ax.set_ylabel("Ca [mm]")
    ax.set_title(f"Measured map of |Gamma_G|^2 at {F_CIBLE_HZ/1e6:.1f} MHz")
    plt.tight_layout()
    plt.savefig(chemin_sortie, dpi=150)
    print(f"Map saved: {chemin_sortie}")
    plt.show()


# ============================================================================
# SUGGESTED POINTS FOR HFSS VALIDATION (point 4)
# ============================================================================
def suggerer_points_hfss(df, n_pires=3):
    if df.empty:
        return []

    ca_min, ca_max = df["Ca_mm"].min(), df["Ca_mm"].max()
    cg_min, cg_max = df["Cg_mm"].min(), df["Cg_mm"].max()
    ca_mid = df["Ca_mm"].median()
    cg_mid = df["Cg_mm"].median()

    coins_et_centre = [
        (ca_min, cg_min), (ca_min, cg_max),
        (ca_max, cg_min), (ca_max, cg_max),
        (ca_mid, cg_mid),
    ]

    df_tri = df.reindex(df["ecart_gen_dB"].abs().sort_values(ascending=False).index)
    pires = list(zip(df_tri["Ca_mm"].head(n_pires), df_tri["Cg_mm"].head(n_pires)))

    points = coins_et_centre + [p for p in pires if p not in coins_et_centre]

    print("\n=== Suggested points for HFSS validation ===")
    for ca, cg in points:
        print(f"  Ca={ca:.2f} mm, Cg={cg:.2f} mm")
    return points


# ============================================================================
if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else DOSSIER_MESURES

    print(f"Comparing pyRFtk vs VNA on '{dossier}' at {F_CIBLE_HZ/1e6:.2f} MHz...")
    df = comparer_grille(dossier)

    if df.empty:
        sys.exit(1)

    df = df.sort_values(["Ca_mm", "Cg_mm"]).reset_index(drop=True)
    chemin_csv = "comparaison_pyrftk_vs_vna.csv"
    df.to_csv(chemin_csv, index=False)
    print(f"\nFull table saved: {chemin_csv} ({len(df)} points)")

    print("\n=== pyRFtk vs VNA discrepancy statistics (|S_gen| in dB) ===")
    print(df["ecart_gen_dB"].describe())

    tracer_carte_gamma2(df)
    tracer_parite(df)
    tracer_heatmaps_comparees(df)
    tracer_histogramme_ecart(df)
    suggerer_points_hfss(df)