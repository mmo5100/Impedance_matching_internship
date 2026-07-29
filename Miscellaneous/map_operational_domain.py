"""
Cartographie du domaine operationnel du dispositif (analogue de la Figure 2a
du papier "Design") : balayage 2D de rho_A (module, phase), simulation pour
chaque point, et carte du temps de convergence vers |rho_G| < spec.

Necessite simulation_matching_device.py dans le meme dossier.
"""

import numpy as np
import matplotlib.pyplot as plt
import simu_matching_device as sim

# --- Parametres du balayage ---
mags = np.linspace(0.0, 0.65, 14)          # |rho_A|
phases_deg = np.arange(0, 360, 15)         # phase de rho_A [deg]

SPEC = 0.027        # |rho_G| < 2.7% (spec generateur)
T_MAX = 0.12        # duree max simulee par point [s]
DT = 2e-4           # pas de temps (plus grossier que par defaut, pour la vitesse)

# --- Balayage ---
conv_time_ms = np.full((len(mags), len(phases_deg)), np.nan)

for i, m in enumerate(mags):
    for j, ph in enumerate(phases_deg):
        rhoA0 = m * np.exp(1j * np.deg2rad(ph))
        res = sim.simulate(rhoA0, t_max=T_MAX, dt=DT)
        idx = np.where(res["rho_gen"] < SPEC)[0]
        if len(idx) > 0:
            conv_time_ms[i, j] = res["t"][idx[0]] * 1e3
        # sinon : reste NaN -> "non converge dans le temps imparti"

print(f"{conv_time_ms.size} points simules.")
print(f"  converges : {np.sum(~np.isnan(conv_time_ms))}")
print(f"  non converges (dans {T_MAX*1e3:.0f} ms) : {np.sum(np.isnan(conv_time_ms))}")

# --- Trace de la carte (plan rho_A) ---
fig, ax = plt.subplots(figsize=(6, 6))

xs, ys, cs = [], [], []
xs_bad, ys_bad = [], []

for i, m in enumerate(mags):
    for j, ph in enumerate(phases_deg):
        x = m * np.cos(np.deg2rad(phases_deg[j]))
        y = m * np.sin(np.deg2rad(phases_deg[j]))
        t = conv_time_ms[i, j]
        if np.isnan(t):
            xs_bad.append(x)
            ys_bad.append(y)
        else:
            xs.append(x)
            ys.append(y)
            cs.append(t)

sc = ax.scatter(xs, ys, c=cs, cmap="viridis", s=60, vmin=0, vmax=T_MAX * 1e3,
                 label="converge (couleur = temps [ms])")
ax.scatter(xs_bad, ys_bad, c="red", marker="x", s=60,
           label=f"ne converge pas en {T_MAX*1e3:.0f} ms")

# Cercle de reference : |rho_A| correspondant a Gamma2min = 18.3% a 32.5MHz
r_ref = np.sqrt(0.183)
theta = np.linspace(0, 2 * np.pi, 200)
ax.plot(r_ref * np.cos(theta), r_ref * np.sin(theta), "k--", lw=1,
        label=f"|rho_A| = sqrt(0.183) = {r_ref:.3f}\n(domaine annonce, papier Design)")

ax.set_xlabel("Re(rho_A)")
ax.set_ylabel("Im(rho_A)")
ax.set_title("Carte de convergence dans le plan rho_A")
ax.set_aspect("equal")
ax.grid(alpha=0.3)
ax.legend(loc="upper left", fontsize=8)
fig.colorbar(sc, ax=ax, label="temps de convergence [ms]")

plt.tight_layout()
plt.savefig("carte_domaine_operationnel.png", dpi=120)
print("Figure enregistree : carte_domaine_operationnel.png")
plt.show()