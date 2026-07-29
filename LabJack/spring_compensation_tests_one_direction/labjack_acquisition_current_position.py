import time
import csv
from datetime import datetime
import matplotlib.pyplot as plt
from collections import deque
from labjack import ljm


import winsound  # Windows uniquement

# ── Signal sonore avant acquisition ───────────────────────────────────────




# Paramètres
channels           = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s          = 0.001
DUREE_ACQUISITION  = 5
CURRENT_CHANNEL    = "AIN2"
POSITION_CHANNEL   = "AIN0"
CURRENT_SCALE      = 1.0 ; CURRENT_OFFSET  = 0.0
POSITION_SCALE     = 1.0 ; POSITION_OFFSET = 0.0
TRIGGER_CHANNEL    = "AIN0"
TRIGGER_THRESHOLD  = 2
TRIGGER_EDGE       = "rising"
nom_fichier        = f"mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# Connexion
handle = ljm.openS("T4", "USB", "ANY")
print(f"Acquisition de {DUREE_ACQUISITION} s à {1/periode_s:.0f} Hz...")

# Fichier CSV
fichier_csv = open(nom_fichier, "w", newline="")
writer = csv.writer(fichier_csv)
writer.writerow(["horodatage", "temps_s"] + channels + ["courant", "position", "trigger"])

# Stockage complet
data = {ch: [] for ch in channels}
temps_list    = []
courant_list  = []
position_list = []
trigger_list  = []

# Trigger
_valeur_prec = None
def detecter_trigger(v):
    global _valeur_prec
    if _valeur_prec is None:
        _valeur_prec = v; return False
    trig = False
    if TRIGGER_EDGE == "rising"  and _valeur_prec < TRIGGER_THRESHOLD <= v: trig = True
    if TRIGGER_EDGE == "falling" and _valeur_prec >= TRIGGER_THRESHOLD > v: trig = True
    _valeur_prec = v
    return trig

# ── Boucle d'acquisition pure (pas de graphique) ──────────────────────────
print("Acquisition dans 3 secondes...")
time.sleep(1); print("3...")
time.sleep(1); print("2...")
time.sleep(1); print("1...")
winsound.Beep(1000, 500)   # fréquence 1000 Hz, durée 500 ms
print("GO — acquisition en cours")

t0 = time.perf_counter()
try:
    while True:
        t_debut = time.perf_counter()
        t       = t_debut - t0
        if t >= DUREE_ACQUISITION:
            break

        values     = ljm.eReadNames(handle, len(channels), channels)
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        val_dict   = dict(zip(channels, values))

        courant  = val_dict[CURRENT_CHANNEL]  * CURRENT_SCALE  + CURRENT_OFFSET
        position = val_dict[POSITION_CHANNEL] * POSITION_SCALE + POSITION_OFFSET
        trig_evt = detecter_trigger(val_dict[TRIGGER_CHANNEL])

        # CSV
        writer.writerow(
            [horodatage, f"{t:.6f}"]
            + [f"{v:.6f}" for v in values]
            + [f"{courant:.6f}", f"{position:.6f}", int(trig_evt)]
        )

        # Stockage
        temps_list.append(t)
        courant_list.append(courant)
        position_list.append(position)
        trigger_list.append(trig_evt)
        for ch, v in zip(channels, values):
            data[ch].append(v)

        # Attente période
        elapsed = time.perf_counter() - t_debut
        reste   = periode_s - elapsed
        if reste > 0:
            time.sleep(reste)

finally:
    fichier_csv.close()
    ljm.close(handle)
    print(f"{len(temps_list)} points acquis en {temps_list[-1]:.3f} s")
    print(f"Fichier : {nom_fichier}")

# ── Affichage après acquisition ────────────────────────────────────────────
import matplotlib.gridspec as gridspec

fig = plt.figure(figsize=(14, 8))
gs  = gridspec.GridSpec(2, 4, figure=fig, hspace=0.5, wspace=0.35)
couleurs = ["tab:blue", "tab:orange", "tab:green", "tab:red"]

# Graphes temporels
for col, (ch, col_) in enumerate(zip(channels, couleurs)):
    ax = fig.add_subplot(gs[0, col])
    ax.plot(temps_list, data[ch], color=col_, lw=0.8)
    # Marqueurs trigger
    for i, trig in enumerate(trigger_list):
        if trig:
            ax.axvline(temps_list[i], color="black", lw=1, ls=":", alpha=0.7)
    if ch == TRIGGER_CHANNEL:
        ax.axhline(TRIGGER_THRESHOLD, color="black", lw=1, ls="--",
                   alpha=0.6, label=f"seuil {TRIGGER_THRESHOLD} V")
        ax.legend(fontsize=7)
    ax.set_title(ch, fontsize=10, fontweight="bold", color=col_)
    ax.set_xlabel("Temps [s]", fontsize=8)
    ax.set_ylabel("Tension [V]", fontsize=8)
    ax.grid(True, alpha=0.3)

# Courant vs position
ax_iv = fig.add_subplot(gs[1, :])
ax_iv.plot(position_list, courant_list, color="tab:purple",
           lw=1, marker="o", markersize=1.5, alpha=0.7)
ax_iv.set_xlabel("Position [mm]", fontsize=10)
ax_iv.set_ylabel("Tension [V]", fontsize=10)
ax_iv.set_title(f"Courant ({CURRENT_CHANNEL}) vs Position ({POSITION_CHANNEL})",
                fontsize=10, fontweight="bold", color="tab:purple")
ax_iv.grid(True, alpha=0.3)

fig.suptitle(f"Acquisition {DUREE_ACQUISITION} s — {len(temps_list)} points", fontsize=12)
plt.tight_layout()
plt.show()