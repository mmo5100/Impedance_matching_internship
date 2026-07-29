"""
Acquisition rapide multi-voies + commande/trigger moteur (impulsion retardée)
- DAC0 : commande = trigger. Le LabJack T4 ne peut sortir que du 0..5V (positif),
         or on a besoin de descendre en tension négative pour piloter le moteur
         dans l'autre sens. On insère donc une PILE de 3V en série sur la sortie
         DAC0, montée en SOUSTRACTIF : V_reel = V_DAC - OFFSET_PILE.
         => plage réelle utilisable : [-OFFSET_PILE, +5V-OFFSET_PILE] = [-3V, +2V]
         Tout le code ci-dessous raisonne en "tension réelle" (V_reel) désirée,
         et convertit automatiquement en V_DAC à envoyer au LabJack.
- AIN0 : lecture position (loggée, informative)
-AIN2 : lecture courant 
- AIN1,AIN3 : autres voies acquises (ex. courant sur AIN2)
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
SIMU_STEP   = 0.05    # V/iter, vitesse de la rampe (en tension réelle)
SIMU_MIN    = -3.0    # V RÉEL   borne basse de la rampe simulée (comme pour SEQUENCE)
SIMU_MAX    =  2.0    # V RÉEL   borne haute de la rampe simulée


# ─────────────────────────────────────────────
# PARAMÈTRES — ACQUISITION
# ─────────────────────────────────────────────
channels           = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s          = 0.001
DUREE_ACQUISITION  = 9
CURRENT_CHANNEL    = "AIN2"
POSITION_CHANNEL   = "AIN0"
CURRENT_SCALE      = 1.0 ; CURRENT_OFFSET  = 0.0
POSITION_SCALE     = 1.0 ; POSITION_OFFSET = 0.0

# ─────────────────────────────────────────────
# PARAMÈTRES — PILE DE COMPENSATION (tensions négatives)
# ─────────────────────────────────────────────
OFFSET_PILE   = 3   # V   tension de la pile, montée en soustractif sur DAC0
                       #     V_reel = V_DAC - OFFSET_PILE  <=>  V_DAC = V_reel + OFFSET_PILE
DAC_MIN_HW    = 0.0   # V   plage physique de sortie du LabJack T4 (DAC0/DAC1)
DAC_MAX_HW    = 5.0   # V

def v_reel_vers_dac(v_reel):
    """Convertit une tension réelle désirée (côté moteur, après la pile) en
    tension à envoyer sur DAC0, et vérifie qu'elle reste dans la plage du LabJack."""
    v_dac = v_reel + OFFSET_PILE
    if not (DAC_MIN_HW <= v_dac <= DAC_MAX_HW):
        raise ValueError(
            f"Tension réelle demandée {v_reel:+.3f} V hors plage atteignable : "
            f"V_DAC calculé = {v_dac:.3f} V, doit être dans [{DAC_MIN_HW}, {DAC_MAX_HW}] V "
            f"(plage réelle utilisable : [{DAC_MIN_HW - OFFSET_PILE:+.1f}, {DAC_MAX_HW - OFFSET_PILE:+.1f}] V)"
        )
    return v_dac

# Conversion des bornes de simulation (réel -> DAC), une fois OFFSET_PILE/v_reel_vers_dac définis
SIMU_MIN_DAC = v_reel_vers_dac(SIMU_MIN)
SIMU_MAX_DAC = v_reel_vers_dac(SIMU_MAX)

# ─────────────────────────────────────────────
# PARAMÈTRES — COMMANDE / TRIGGER (DAC0)
# ─────────────────────────────────────────────
DAC_CHANNEL = "DAC0"

# Séquence de consignes : liste de (t_debut, duree, v_reel).
# - t_debut et duree sont en secondes, à partir du "GO" (t=0).
# - v_reel est la tension RÉELLE désirée (après la pile) : positive pour aller
#   dans un sens, négative pour aller dans l'autre.
# - Entre les phases (et après la dernière), la commande retombe à 0V réel.
SEQUENCE = [
    (1.0, 3.0,  1.2),   # t=1.0s à 4.0s : +1.2V réel (sens "aller")
    (5.0, 3.0, -1.2),   # t=5.0s à 8.0s : -1.2V réel (sens "retour")
]

# Vérifie à l'avance que toutes les tensions demandées sont atteignables,
# et pré-calcule les tensions DAC correspondantes.
V_REPOS_DAC = v_reel_vers_dac(0.0)   # DAC à envoyer pour obtenir 0V réel au repos
SEQUENCE_DAC = [
    (t_debut, duree, v_reel, v_reel_vers_dac(v_reel))
    for (t_debut, duree, v_reel) in SEQUENCE
]

nom_fichier = f"boucle_position2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ─────────────────────────────────────────────
# CONNEXION
# ─────────────────────────────────────────────
handle = ljm.openS("T4", "USB", "ANY")
print(f"Acquisition de {DUREE_ACQUISITION} s à {1/periode_s:.0f} Hz...")
print(f"  Pile de compensation : {OFFSET_PILE} V (soustractif) -> plage réelle "
      f"[{DAC_MIN_HW - OFFSET_PILE:+.1f}, {DAC_MAX_HW - OFFSET_PILE:+.1f}] V")
print(f"  Séquence de commande sur {DAC_CHANNEL} (repos = {V_REPOS_DAC:.3f} V DAC) :")
for (t_debut, duree, v_reel, v_dac) in SEQUENCE_DAC:
    print(f"    t={t_debut:.3f}s -> t={t_debut+duree:.3f}s : {v_reel:+.3f} V réel "
          f"(= {v_dac:.3f} V DAC)")
if SIMULATION:
    print(f"  Mode SIMULATION : rampe {SIMU_MIN:+.2f} V à {SIMU_MAX:+.2f} V réel "
          f"(= {SIMU_MIN_DAC:.3f} à {SIMU_MAX_DAC:.3f} V DAC) générée sur DAC1")
    print(f"    → Relier un fil DAC1 → AIN0 sur le LabJack pour tester sans hardware externe.")
print(f"  CSV : {nom_fichier}")
print("-" * 55)

ljm.eWriteName(handle, DAC_CHANNEL, V_REPOS_DAC)  # au repos (0V réel) avant démarrage

simu_val    = SIMU_MIN_DAC
simu_montee = True
if SIMULATION:
    ljm.eWriteName(handle, "DAC1", simu_val)

# Stockage complet acquisition
data = {ch: [] for ch in channels}
temps_list     = []
courant_list   = []
position_list  = []
trigger_list   = []   # état 0/1
commande_list  = []   # tension RÉELLE (côté moteur, après la pile) envoyée

# ─────────────────────────────────────────────
# FICHIER CSV
# ─────────────────────────────────────────────
fichier_csv = open(nom_fichier, "w", newline="")
writer = csv.writer(fichier_csv)
writer.writerow(
    ["horodatage", "temps_s"] + channels +
    ["courant", "position", "commande_V_reelle", "commande_V_DAC", "phase"]
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

v_commande_reel = 0.0
v_commande_dac  = V_REPOS_DAC
phase_courante  = None   # index de la phase active dans SEQUENCE_DAC, ou None si repos

t0 = time.perf_counter()

try:
    while not arret:
        t_debut = time.perf_counter()
        t       = t_debut - t0
        if t >= DUREE_ACQUISITION:
            break

        # --- Génération du signal de test (mode simulation) ---
        # simu_val est en tension DAC (déjà convertie depuis SIMU_MIN/SIMU_MAX réels)
        if SIMULATION:
            if simu_montee:
                simu_val += SIMU_STEP
                if simu_val >= SIMU_MAX_DAC:
                    simu_val = SIMU_MAX_DAC
                    simu_montee = False
            else:
                simu_val -= SIMU_STEP
                if simu_val <= SIMU_MIN_DAC:
                    simu_val = SIMU_MIN_DAC
                    simu_montee = True
            ljm.eWriteName(handle, "DAC1", simu_val)

        # --- Lecture voies ---
        values     = ljm.eReadNames(handle, len(channels), channels)
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        val_dict   = dict(zip(channels, values))

        courant  = val_dict[CURRENT_CHANNEL]  * CURRENT_SCALE  + CURRENT_OFFSET
        position = val_dict[POSITION_CHANNEL] * POSITION_SCALE + POSITION_OFFSET
        if SIMULATION:
            # AIN0 lit la tension DAC1 brute (pas de vraie pile sur ce fil de test) ;
            # on la reconvertit en "réel" pour rester cohérent avec SIMU_MIN/SIMU_MAX.
            position = position - OFFSET_PILE

        # --- Détermine quelle phase de la séquence doit être active à l'instant t ---
        # (parcourt SEQUENCE_DAC pour trouver la phase dont l'intervalle contient t ;
        #  s'il n'y en a aucune, on est au repos = 0V réel)
        nouvelle_phase = None
        for i, (t_debut_phase, duree_phase, v_reel_phase, v_dac_phase) in enumerate(SEQUENCE_DAC):
            if t_debut_phase <= t < t_debut_phase + duree_phase:
                nouvelle_phase = i
                break

        if nouvelle_phase != phase_courante:
            if nouvelle_phase is not None:
                _, _, v_reel_phase, v_dac_phase = SEQUENCE_DAC[nouvelle_phase]
                ljm.eWriteName(handle, DAC_CHANNEL, v_dac_phase)
                v_commande_reel = v_reel_phase
                v_commande_dac  = v_dac_phase
            else:
                ljm.eWriteName(handle, DAC_CHANNEL, V_REPOS_DAC)
                v_commande_reel = 0.0
                v_commande_dac  = V_REPOS_DAC
            phase_courante = nouvelle_phase

        # --- CSV ---
        writer.writerow(
            [horodatage, f"{t:.6f}"]
            + [f"{v:.6f}" for v in values]
            + [f"{courant:.6f}", f"{position:.6f}",
               f"{v_commande_reel:+.3f}", f"{v_commande_dac:.3f}",
               phase_courante if phase_courante is not None else -1]
        )

        # --- Stockage pour affichage ---
        temps_list.append(t)
        courant_list.append(courant)
        position_list.append(position)
        trigger_list.append(phase_courante if phase_courante is not None else -1)
        commande_list.append(v_commande_reel)
        for ch, v in zip(channels, values):
            data[ch].append(v)

        # --- Attente période ---
        elapsed = time.perf_counter() - t_debut
        reste   = periode_s - elapsed
        if reste > 0:
            time.sleep(reste)

finally:
    fichier_csv.close()
    ljm.eWriteName(handle, DAC_CHANNEL, V_REPOS_DAC)  # retour à 0V réel, PAS 0V DAC
    if SIMULATION:
        ljm.eWriteName(handle, "DAC1", 0.0)
    ljm.close(handle)
    print(f"Commande/trigger remis à 0V réel ({V_REPOS_DAC:.3f} V sur {DAC_CHANNEL}), connexion fermée.")
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

    # Commande / Trigger (tension réelle après la pile, DAC0)
    ax_cmd = fig.add_subplot(gs[1, :2])
    ax_cmd.plot(temps_list, commande_list, color="black", lw=1.2, drawstyle="steps-post")
    ax_cmd.axhline(0, color="grey", lw=0.6, ls="--")
    ax_cmd.set_title(f"Commande / Trigger réelle (via pile {OFFSET_PILE}V sur {DAC_CHANNEL})",
                     fontsize=10, fontweight="bold")
    ax_cmd.set_xlabel("Temps [s]", fontsize=8)
    ax_cmd.set_ylabel("Tension réelle [V]", fontsize=8)
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