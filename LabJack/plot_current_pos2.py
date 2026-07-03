import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ── Fichiers à analyser ────────────────────────────────────────────────────
# Modifie ces chemins selon tes fichiers CSV
FILES = {
    "mesures_2_25.03.csv":   "2h25m03s",
    "mesures_2_48.46_2.csv": "2h48m46s",
}

POSITION_CHANNEL = "AIN0"
CURRENT_CHANNEL  = "AIN2"
N_BINS           = 30       # nombre de tranches de position

# ── Graphe : courant moyen par tranche de position ─────────────────────────
fig, axes = plt.subplots(1, len(FILES), figsize=(7 * len(FILES), 5))
if len(FILES) == 1:
    axes = [axes]

for ax, (fname, label) in zip(axes, FILES.items()):
    df  = pd.read_csv(fname)
    pos = df[POSITION_CHANNEL].values
    cur = df[CURRENT_CHANNEL].values * 1000  # en mV

    # Moyenne et écart-type par bin de position
    bins = np.linspace(pos.min(), pos.max(), N_BINS + 1)
    idx  = np.digitize(pos, bins)
    centers, means, stds = [], [], []
    for i in range(1, len(bins)):
        mask = idx == i
        if mask.sum() > 3:
            centers.append((bins[i - 1] + bins[i]) / 2)
            means.append(np.mean(cur[mask]))
            stds.append(np.std(cur[mask]))

    centers = np.array(centers)
    means   = np.array(means)
    stds    = np.array(stds)

    ax.errorbar(centers, means, yerr=stds, fmt="o-",
                color="tab:purple", capsize=3, linewidth=1.5, markersize=4)
    ax.axhline(0, color="k",   linewidth=0.8, linestyle="--", label="zéro")
    ax.axhline(means.mean(), color="r", linewidth=1, linestyle="--",
               label=f"moy = {means.mean():.2f} mV")
    ax.set_xlabel("Position AIN0 (V)")
    ax.set_ylabel("Courant moyen (mV)")
    ax.set_title(f"Courant moyen par position — {label}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
#plt.savefig("courant_moyen_position.png", dpi=150)
plt.show()
#print("Graphe sauvegardé : courant_moyen_position.png")