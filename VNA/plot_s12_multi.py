"""
Affiche le paramètre S12 (module en dB) de plusieurs fichiers .s2p
sur un même graphe
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
from pathlib import Path
import re


def label_depuis_nom(nom_fichier):
    """Extrait une position du type '10p00' dans le nom de fichier et la
    convertit en label 'XX.XXmm' (ex: 'meas_capa_10p00' -> '10.00mm').
    Si aucun motif ne correspond, retourne le nom de fichier tel quel.
    """
    m = re.search(r"(\d+)p(\d+)", nom_fichier)
    if m:
        entier, decimal = m.groups()
        return f"{entier}.{decimal}mm"
    return nom_fichier


def lire_s2p(chemin):
    """Parse un fichier Touchstone .s2p (2 ports) sans dépendance externe.

    Retourne : freq_Hz (array), S (array complexe de forme (N, 2, 2))
    """
    freq_unit_mult = {"HZ": 1, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    fmt = "MA"  
    unit_mult = 1e9  
    data_lines = []

    with open(chemin, "r") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("!"):
                continue  
            if ligne.startswith("#"):
                tokens = ligne[1:].split()
                for tok in tokens:
                    tok_up = tok.upper()
                    if tok_up in freq_unit_mult:
                        unit_mult = freq_unit_mult[tok_up]
                    if tok_up in ("RI", "MA", "DB"):
                        fmt = tok_up
                continue
            data_lines.append(ligne)

    valeurs = []
    for ligne in data_lines:
        valeurs.extend(float(x) for x in ligne.split())
    valeurs = np.array(valeurs)

    
    valeurs = valeurs.reshape(-1, 9)
    freq_Hz = valeurs[:, 0] * unit_mult

    def to_complex(a, b, fmt):
        if fmt == "RI":
            return a + 1j * b
        elif fmt == "MA":
            return a * np.exp(1j * np.deg2rad(b))
        elif fmt == "DB":
            mag = 10 ** (a / 20)
            return mag * np.exp(1j * np.deg2rad(b))

    s11 = to_complex(valeurs[:, 1], valeurs[:, 2], fmt)
    s21 = to_complex(valeurs[:, 3], valeurs[:, 4], fmt)
    s12 = to_complex(valeurs[:, 5], valeurs[:, 6], fmt)
    s22 = to_complex(valeurs[:, 7], valeurs[:, 8], fmt)

    S = np.zeros((len(freq_Hz), 2, 2), dtype=complex)
    S[:, 0, 0] = s11
    S[:, 1, 0] = s21
    S[:, 0, 1] = s12
    S[:, 1, 1] = s22

    return freq_Hz, S


# ---------------------------------------------------------------------------
# 1) Liste des fichiers .s2p à tracer
# ---------------------------------------------------------------------------

dossier = Path("./Mesures_capa_only_HFSS")  # <-- adapter le chemin du dossier
fichiers = sorted(dossier.glob("*.s2p"))

if len(fichiers) == 0:
    raise FileNotFoundError(
        f"Aucun fichier .s2p trouvé dans {dossier}. "
        "Vérifiez le chemin ou renseignez la liste `fichiers` manuellement."
    )

if len(fichiers) != 15:
    print(f"Attention : {len(fichiers)} fichiers trouvés (15 attendus).")

# ---------------------------------------------------------------------------
# 2) Lecture et tracé du S12 pour chaque fichier
# ---------------------------------------------------------------------------

fig, ax_mag = plt.subplots(1, 1, figsize=(10, 6))
cmap = plt.get_cmap("viridis", len(fichiers))

freq_min, freq_max = np.inf, -np.inf

for i, f in enumerate(fichiers):
    freq_Hz, S = lire_s2p(f)
    freq_MHz = freq_Hz / 1e6
    freq_min = min(freq_min, freq_MHz.min())
    freq_max = max(freq_max, freq_MHz.max())

    s12_db = 20 * np.log10(np.abs(S[:, 0, 1]))

    label = label_depuis_nom(f.stem)
    ax_mag.plot(freq_MHz, s12_db, color=cmap(i), label=label)

# ---------------------------------------------------------------------------
# 3) Mise en forme du graphe
# ---------------------------------------------------------------------------

ax_mag.set_xlabel("Frequency (MHz)")
ax_mag.set_ylabel("S12 (dB)")
ax_mag.set_title("S12 for 10 HFSS s2p")
ax_mag.grid(True, which="major", alpha=0.4)
ax_mag.grid(True, which="minor", alpha=0.15)


ax_mag.set_xlim(freq_min, freq_max)
ax_mag.xaxis.set_major_locator(MultipleLocator(5))
ax_mag.xaxis.set_minor_locator(MultipleLocator(1))
ax_mag.tick_params(axis="x", which="major", length=6)
ax_mag.tick_params(axis="x", which="minor", length=3)

ax_mag.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=7, ncol=1)

plt.tight_layout()
#plt.savefig("S12_comparaison.png", dpi=150, bbox_inches="tight")
plt.show()