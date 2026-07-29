"""
Acquisition rapide multi-voies + commande/trigger moteur (impulsion retardée)
- DAC0 : commande = trigger : reste à 0V jusqu'à t=T0_TRIGGER, passe alors à
         V_TRIGGER (1V), reste à ce niveau pendant DUREE_TRIGGER secondes,
         puis retombe à 0V et y reste jusqu'à la fin.
- AIN0 : lecture position (loggée, informative)
- AIN1..AIN3 : autres voies acquises (ex. courant sur AIN2)
"""

import time
import csv
from datetime import datetime
from labjack import ljm
import signal
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import winsound  # Windows uniquement

# ─────────────────────────────────────────────
# GESTION CTRL+C (arrêt propre anticipé)
# ─────────────────────────────────────────────
arret = False
def handler(sig, frame):
    global arret
    arret = True

signal.signal(signal.SIGINT, handler)

# ─────────────────────────────────────────────
# PARAMÈTRES — MODE SIMULATION (test avec le LabJack seul)
# ─────────────────────────────────────────────
SIMULATION  = False   # True = génère un signal de test sur DAC1 (relier DAC1→AIN0 avec un fil)
SIMU_STEP   = 0.05    # V/iter, vitesse de la rampe
SIMU_MIN    = 0.0     # V   borne basse de la rampe (sortie DAC1)
SIMU_MAX    = 5.0     # V   borne haute de la rampe (sortie DAC1)

# ─────────────────────────────────────────────
# PARAMÈTRES — ACQUISITION
# ─────────────────────────────────────────────
channels           = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s          = 0.001
DUREE_ACQUISITION  = 5
CURRENT_CHANNEL    = "AIN2"
POSITION_CHANNEL   = "AIN0"
CURRENT_SCALE      = 1.0 ; CURRENT_OFFSET  = 0.0
POSITION_SCALE     = 1.0 ; POSITION_OFFSET = 0.0

# ─────────────────────────────────────────────
# PARAMÈTRES — COMMANDE / TRIGGER (DAC0)
# ─────────────────────────────────────────────
DAC_CHANNEL     = "DAC0"
V_TRIGGER       = 1.2   # V   niveau de la commande/trigger
T0_TRIGGER      = 1.0   # s   délai avant activation du trigger après le GO
DUREE_TRIGGER   = 3     # s   durée de l'impulsion (à partir de T0_TRIGGER)

nom_fichier = f"boucle_position2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ─────────────────────────────────────────────
# CONNEXION
# ─────────────────────────────────────────────
handle = ljm.openS("T4", "USB", "ANY")
print(f"Acquisition de {DUREE_ACQUISITION} s à {1/periode_s:.0f} Hz...")
print(f"  Commande/trigger : {V_TRIGGER} V de t={T0_TRIGGER}s à t={T0_TRIGGER+DUREE_TRIGGER}s (sur {DAC_CHANNEL}), puis 0V")
if SIMULATION:
    print(f"  Mode SIMULATION : rampe {SIMU_MIN}-{SIMU_MAX} V générée sur DAC1")
    print(f"    → Relier un fil DAC1 → AIN0 sur le LabJack pour tester sans hardware externe.")
print(f"  CSV : {nom_fichier}")
print("-" * 55)

ljm.eWriteName(handle, DAC_CHANNEL, 0.0)  # au repos avant démarrage

simu_val    = SIMU_MIN
simu_montee = True
if SIMULATION:
    ljm.eWriteName(handle, "DAC1", simu_val)

# Stockage complet acquisition
data = {ch: [] for ch in channels}
temps_list     = []
courant_list   = []
position_list  = []
trigger_list   = []   # état 0/1
commande_list  = []   # tension réelle envoyée sur DAC_CHANNEL

# ─────────────────────────────────────────────
# FICHIER CSV
# ─────────────────────────────────────────────
fichier_csv = open(nom_fichier, "w", newline="")
writer = csv.writer(fichier_csv)
writer.writerow(
    ["horodatage", "temps_s"] + channels +
    ["courant", "position", "commande_V", "trigger"]
)

# ─────────────────────────────────────────────
# COMPTE À REBOURS + BIP + DÉMARRAGE COMMANDE/TRIGGER
# ─────────────────────────────────────────────
print("Acquisition dans 3 secondes...")
time.sleep(1); print("3...")
time.sleep(1); print("2...")
time.sleep(1); print("1...")
winsound.Beep(1000, 500)
print("GO — acquisition en cours")

v_commande    = 0.0
trigger_actif = False
trigger_fini  = False

t0 = time.perf_counter()

try:
    while not arret:
        t_debut = time.perf_counter()
        t       = t_debut - t0
        if t >= DUREE_ACQUISITION:
            break

        # --- Génération du signal de test (mode simulation) ---
        if SIMULATION:
            if simu_montee:
                simu_val += SIMU_STEP
                if simu_val >= SIMU_MAX:
                    simu_val = SIMU_MAX
                    simu_montee = False
            else:
                simu_val -= SIMU_STEP
                if simu_val <= SIMU_MIN:
                    simu_val = SIMU_MIN
                    simu_montee = True
            ljm.eWriteName(handle, "DAC1", simu_val)

        # --- Lecture voies ---
        values     = ljm.eReadNames(handle, len(channels), channels)
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        val_dict   = dict(zip(channels, values))

        courant  = val_dict[CURRENT_CHANNEL]  * CURRENT_SCALE  + CURRENT_OFFSET
        position = val_dict[POSITION_CHANNEL] * POSITION_SCALE + POSITION_OFFSET

        # --- Activation du trigger à t = T0_TRIGGER ---
        if not trigger_actif and not trigger_fini and t >= T0_TRIGGER:
            ljm.eWriteName(handle, DAC_CHANNEL, V_TRIGGER)
            v_commande    = V_TRIGGER
            trigger_actif = True

        # --- Extinction du trigger à t = T0_TRIGGER + DUREE_TRIGGER : retombe à 0V, définitif ---
        elif trigger_actif and t >= T0_TRIGGER + DUREE_TRIGGER:
            ljm.eWriteName(handle, DAC_CHANNEL, 0.0)
            v_commande    = 0.0
            trigger_actif = False
            trigger_fini  = True

        # --- CSV ---
        writer.writerow(
            [horodatage, f"{t:.6f}"]
            + [f"{v:.6f}" for v in values]
            + [f"{courant:.6f}", f"{position:.6f}", f"{v_commande:+.3f}", int(trigger_actif)]
        )

        # --- Stockage pour affichage ---
        temps_list.append(t)
        courant_list.append(courant)
        position_list.append(position)
        trigger_list.append(trigger_actif)
        commande_list.append(v_commande)
        for ch, v in zip(channels, values):
            data[ch].append(v)

        # --- Attente période ---
        elapsed = time.perf_counter() - t_debut
        reste   = periode_s - elapsed
        if reste > 0:
            time.sleep(reste)

finally:
    fichier_csv.close()
    ljm.eWriteName(handle, DAC_CHANNEL, 0.0)
    if SIMULATION:
        ljm.eWriteName(handle, "DAC1", 0.0)
    ljm.close(handle)
    print(f"Commande/trigger remis à 0V, connexion fermée.")
    if len(temps_list):
        print(f"{len(temps_list)} points acquis en {temps_list[-1]:.3f} s")
    print(f"Fichier : {nom_fichier}")

# ─────────────────────────────────────────────
# AFFICHAGE APRÈS ACQUISITION
# ─────────────────────────────────────────────
if len(temps_list) >= 2:
    fig = plt.figure(figsize=(14, 8))
    gs  = gridspec.GridSpec(2, 4, figure=fig, hspace=0.5, wspace=0.35)
    couleurs = ["tab:blue", "tab:orange", "tab:green", "tab:red"]

    # Graphes temporels des 4 voies
    for col, (ch, col_) in enumerate(zip(channels, couleurs)):
        ax = fig.add_subplot(gs[0, col])
        ax.plot(temps_list, data[ch], color=col_, lw=0.8)
        ax.set_title(ch, fontsize=10, fontweight="bold", color=col_)
        ax.set_xlabel("Temps [s]", fontsize=8)
        ax.set_ylabel("Tension [V]", fontsize=8)
        ax.grid(True, alpha=0.3)

    # Commande / Trigger (un seul et même signal, DAC0)
    ax_cmd = fig.add_subplot(gs[1, :2])
    ax_cmd.plot(temps_list, commande_list, color="black", lw=1.2, drawstyle="steps-post")
    ax_cmd.set_title(f"Commande / Trigger ({DAC_CHANNEL})", fontsize=10, fontweight="bold")
    ax_cmd.set_xlabel("Temps [s]", fontsize=8)
    ax_cmd.set_ylabel("Tension [V]", fontsize=8)
    ax_cmd.grid(True, alpha=0.3)

    # Courant vs position
    ax_iv = fig.add_subplot(gs[1, 2:])
    ax_iv.plot(position_list, courant_list, color="tab:purple",
               lw=1, marker="o", markersize=1.5, alpha=0.7)
    ax_iv.set_xlabel("Position [V]", fontsize=10)
    ax_iv.set_ylabel("Courant [V]", fontsize=10)
    ax_iv.set_title(f"Courant ({CURRENT_CHANNEL}) vs Position ({POSITION_CHANNEL})",
                    fontsize=10, fontweight="bold", color="tab:purple")
    ax_iv.grid(True, alpha=0.3)

    fig.suptitle(f"Acquisition {DUREE_ACQUISITION} s — {len(temps_list)} points", fontsize=12)
    plt.tight_layout()
    plt.show()