"""
Script de test - LabJack T4 avec visualisation en direct + CSV + trigger
- 4 graphiques AIN0-AIN3 en fonction du temps (fenetre glissante)
- 1 graphique courant (AIN2) vs position (AIN0) en temps reel
- Trigger sur front montant/descendant
- Enregistrement CSV
"""
import time
import csv
from collections import deque
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.animation as animation
from labjack import ljm

# ===========================================================================
# Parametres generaux
# ===========================================================================
channels    = ["AIN0", "AIN1", "AIN2", "AIN3"]
periode_s   = 0.001
fenetre_pts = 10000
nom_fichier = f"mesures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ===========================================================================
# Parametres courant / position
# ===========================================================================
CURRENT_CHANNEL  = "AIN2"   # canal mesure courant
POSITION_CHANNEL = "AIN0"   # canal mesure position

CURRENT_SCALE   = 1.0    # V -> A  (adapter selon ton capteur)
CURRENT_OFFSET  = 0.0
POSITION_SCALE  = 1.0    # V -> mm (adapter selon ton capteur)
POSITION_OFFSET = 0.0

CURRENT_LABEL  = "Courant [A]"
POSITION_LABEL = "Position [mm]"

DUREE_ACQUISITION_S = 10.0

# ===========================================================================
# Parametres du trigger
# ===========================================================================
TRIGGER_CHANNEL   = "AIN0"
TRIGGER_THRESHOLD = 2
TRIGGER_EDGE      = "rising"   # "rising" ou "falling"

# ===========================================================================
# Connexion au T4
# ===========================================================================
handle = ljm.openS("T4", "USB", "ANY")
info   = ljm.getHandleInfo(handle)
print("Connecte au LabJack:")
print(f"  Type appareil   : {info[0]}")
print(f"  Numero de serie : {info[2]}")
print(f"Enregistrement dans : {nom_fichier}")
print(f"Trigger : {TRIGGER_EDGE} sur {TRIGGER_CHANNEL} @ {TRIGGER_THRESHOLD} V")
print("Fermer la fenetre pour arreter.")

# ===========================================================================
# Fichier CSV
# ===========================================================================
fichier_csv = open(nom_fichier, "w", newline="")
writer      = csv.writer(fichier_csv)
writer.writerow(
    ["horodatage", "temps_s"] + channels
    + ["courant_conv", "position_conv", "trigger"]
)

# ===========================================================================
# Buffers
# ===========================================================================
temps_buf    = deque(maxlen=fenetre_pts)
valeurs_buf  = {ch: deque(maxlen=fenetre_pts) for ch in channels}
courant_buf  = deque(maxlen=fenetre_pts)
position_buf = deque(maxlen=fenetre_pts)
trigger_buf  = deque(maxlen=fenetre_pts)

# ===========================================================================
# Figure : GridSpec  2 lignes
#   Ligne 0 : AIN0 | AIN1 | AIN2 | AIN3   (4 colonnes egales)
#   Ligne 1 : courant vs position           (toute la largeur)
# ===========================================================================
fig = plt.figure(figsize=(14, 8))
gs  = gridspec.GridSpec(2, 4, figure=fig, hspace=0.5, wspace=0.35)

couleurs = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
lignes   = {}
markers  = {}

# --- Ligne du haut : 4 graphes temporels ---
for col, (ch, col_) in enumerate(zip(channels, couleurs)):
    ax = fig.add_subplot(gs[0, col])
    (ligne,) = ax.plot([], [], color=col_, lw=1.2)
    lignes[ch]  = (ax, ligne)
    markers[ch] = []

    ax.set_title(ch, fontsize=10, fontweight="bold", color=col_)
    ax.set_xlabel("Temps [s]", fontsize=8)
    ax.set_ylabel("Tension [V]", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=7)

    if ch == TRIGGER_CHANNEL:
        ax.axhline(TRIGGER_THRESHOLD, color="black", lw=1,
                   ls="--", alpha=0.6, label=f"seuil {TRIGGER_THRESHOLD} V")
        ax.legend(fontsize=7, loc="upper right")

# --- Ligne du bas : courant vs position ---
ax_iv = fig.add_subplot(gs[1, :])
(ligne_iv,) = ax_iv.plot([], [], color="tab:purple", lw=1.5,
                          marker="o", markersize=2, alpha=0.8)
ax_iv.set_xlabel(POSITION_LABEL, fontsize=10)
ax_iv.set_ylabel(CURRENT_LABEL, fontsize=10)
ax_iv.set_title(
    f"Courant ({CURRENT_CHANNEL}) en fonction de la position ({POSITION_CHANNEL})",
    fontsize=10, fontweight="bold", color="tab:purple"
)
ax_iv.grid(True, alpha=0.3)
ax_iv.tick_params(labelsize=8)

fig.suptitle(
    f"LabJack T4 — lecture en direct  |  trigger {TRIGGER_EDGE} "
    f"sur {TRIGGER_CHANNEL} @ {TRIGGER_THRESHOLD} V",
    fontsize=12
)

# ===========================================================================
# Detection de front
# ===========================================================================
_valeur_prec = None

def detecter_trigger(valeur):
    global _valeur_prec
    if _valeur_prec is None:
        _valeur_prec = valeur
        return False
    trig = False
    if TRIGGER_EDGE == "rising"  and _valeur_prec < TRIGGER_THRESHOLD <= valeur:
        trig = True
    if TRIGGER_EDGE == "falling" and _valeur_prec >= TRIGGER_THRESHOLD > valeur:
        trig = True
    _valeur_prec = valeur
    return trig

# ===========================================================================
# Mise a jour animation
# ===========================================================================
t0 = time.time()

def mise_a_jour(frame):
    
    
    values     = ljm.eReadNames(handle, len(channels), channels)
    t          = time.time() - t0
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    # ── Arrêt automatique ──────────────────────────────────────────
    if t >= DUREE_ACQUISITION_S:
        ani.event_source.stop()
        plt.close(fig)
        return [ligne for (_, ligne) in lignes.values()] + [ligne_iv]
    

    val_dict = dict(zip(channels, values))

    # Conversion courant / position
    courant  = val_dict[CURRENT_CHANNEL]  * CURRENT_SCALE  + CURRENT_OFFSET
    position = val_dict[POSITION_CHANNEL] * POSITION_SCALE + POSITION_OFFSET

    # Trigger
    trig_evt = detecter_trigger(val_dict[TRIGGER_CHANNEL])

    # CSV
    writer.writerow(
        [horodatage, f"{t:.6f}"]
        + [f"{v:.6f}" for v in values]
        + [f"{courant:.6f}", f"{position:.6f}", int(trig_evt)]
    )
    fichier_csv.flush()

    # Buffers
    temps_buf.append(t)
    courant_buf.append(courant)
    position_buf.append(position)
    trigger_buf.append(1 if trig_evt else 0)
    for ch, v in zip(channels, values):
        valeurs_buf[ch].append(v)

    # --- Graphes temporels ---
    for ch in channels:
        ax, ligne = lignes[ch]
        ligne.set_data(temps_buf, valeurs_buf[ch])

        if len(temps_buf) > 1:
            ax.set_xlim(temps_buf[0], temps_buf[-1])

        buf = valeurs_buf[ch]
        if buf:
            vmin, vmax = min(buf), max(buf)
            if vmax - vmin < 0.01:
                vmin, vmax = vmin - 0.05, vmax + 0.05
            marge = max(0.05 * (vmax - vmin), 0.05)
            ax.set_ylim(vmin - marge, vmax + marge)

        if trig_evt:
            vl = ax.axvline(t, color="black", lw=1, ls=":", alpha=0.7)
            markers[ch].append(vl)

        if len(temps_buf) > 1:
            xmin = temps_buf[0]
            for vl in markers[ch][:]:
                if vl.get_xdata()[0] < xmin:
                    vl.remove()
                    markers[ch].remove(vl)

    # --- Graphe courant vs position ---
    ligne_iv.set_data(position_buf, courant_buf)

    if position_buf:
        pmin, pmax = min(position_buf), max(position_buf)
        cmin, cmax = min(courant_buf),  max(courant_buf)
        if pmax - pmin < 1e-3: pmin, pmax = pmin - 0.1, pmax + 0.1
        if cmax - cmin < 1e-3: cmin, cmax = cmin - 0.1, cmax + 0.1
        mp = 0.05 * (pmax - pmin)
        mc = 0.05 * (cmax - cmin)
        ax_iv.set_xlim(pmin - mp, pmax + mp)
        ax_iv.set_ylim(cmin - mc, cmax + mc)

    return [ligne for (_, ligne) in lignes.values()] + [ligne_iv]


ani = animation.FuncAnimation(
    fig,
    mise_a_jour,
    interval=periode_s * 1000,
    blit=False,
    cache_frame_data=False,
)

try:
    plt.tight_layout()
    plt.show()
finally:
    fichier_csv.close()
    ljm.close(handle)
    print(f"Fichier enregistre : {nom_fichier}")
    print("Connexion fermee.")