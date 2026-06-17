"""
  Trouver (b_a, b_g) dans [b_min, b_max] tel que y_G(b_a, b_g, rhoA) = 1

Comparaison des longueurs mecaniques 350 mm et 915 mm pour une frequence donnee.
"""

import numpy as np
from scipy.optimize import fsolve
import matplotlib.pyplot as plt
import simu_matching_device as sim

# ================================================================
# PARAMETRES à modifier
# ================================================================
f_mhz = 32.5
rhoA  = 0.425 * np.exp(1j * np.deg2rad(235))  # exemple du papier

# ================================================================
# GRANDEURS DEPENDANT DE LA FREQUENCE
# ================================================================
c_light = 3e8
Ls      = 20e-9 # 70nH = valeur dans le papier first result dans le papier design c'est 20nH 
w       = 2 * np.pi * f_mhz * 1e6
beta_f  = w / c_light


C_neutral_table = {25.0: 128.3e-12, 29.0: 133.3e-12, 32.5: 135.1e-12, 38.0: 138.9e-12} # valeurs du Cneutral en fonction de frequence papier design
C_neutral_f = C_neutral_table.get(f_mhz, sim.C_neutral)


def b_stub_f(C):
    """Susceptance normalisee du stub a la frequence f_mhz."""
    raw_C = w * C / (1 - w**2 * Ls * C)
    raw_N = w * C_neutral_f / (1 - w**2 * Ls * C_neutral_f)
    return sim.Z0 * (raw_C - raw_N)

b_min = b_stub_f(sim.Cs_from_x(sim.x_max))  # x=50mm -> C~40pF
b_max = b_stub_f(sim.Cs_from_x(sim.x_min))  # x=18mm -> C~205pF


#lt optimal en fponction de la fréquence (papier design)
lt_optimal_papier = {25.0: 1.28, 29.0: 1.05, 32.5: 0.91, 38.0: 0.74}
lt_ref = lt_optimal_papier.get(f_mhz, sim.lt)


print(f"Frequence : {f_mhz} MHz")
print(f"rhoA      : |rhoA| = {abs(rhoA):.3f},  phase = {np.angle(rhoA, deg=True):.1f} deg")
print(f"lt optimal    : {lt_ref:.3f} m  (Table 1 papier a {f_mhz} MHz)")
print(f"b_min     : {b_min:.4f}  (x=50mm)")
print(f"b_max     : {b_max:.4f}  (x=18mm)")
print()

# ================================================================
# FONCTION RESIDUS 
# ================================================================
def residus(params, lt_val, rhoA_val):
    """
    Retourne [Re(yG)-1, Im(yG)] pour (b_a, b_g) donnes,
    a la longueur lt_val et pour le desaccord rhoA_val.
    """
    b_a, b_g = params
    c      = np.cos(beta_f * lt_val)
    s      = np.sin(beta_f * lt_val)
    A      = c - b_g * s
    B      = 1j * s * sim.Z0
    C_     = 1j * ((b_a + b_g) * c + (1 - b_a * b_g) * s) / sim.Z0
    D      = c - b_a * s
    zA_ohm = (1 + rhoA_val) / (1 - rhoA_val) * sim.Z0
    zG_ohm = (B - zA_ohm * D) / (zA_ohm * C_ - A)
    yG     = 1.0 / (zG_ohm / sim.Z0)
    return [yG.real - 1.0, yG.imag] #adaptation parfaite quand le residu vaut [0,0]

# ================================================================
# GRILLE : carte du residu pour rhoA donne, lt du module sim
# ================================================================

n        = 100
b_a_vals = np.linspace(b_min, b_max, n)
b_g_vals = np.linspace(b_min, b_max, n)
erreur   = np.zeros((n, n))

for i, b_a in enumerate(b_a_vals):
    for j, b_g in enumerate(b_g_vals):
        res = residus([b_a, b_g], lt_ref, rhoA)
        erreur[i, j] = np.sqrt(res[0]**2 + res[1]**2)

idx      = np.unravel_index(np.argmin(erreur), erreur.shape)
b_a_best = b_a_vals[idx[0]]
b_g_best = b_g_vals[idx[1]]
print(f"Grille (lt_ref={lt_ref:.3f}m) :")
print(f"  Meilleur point : b_a={b_a_best:.4f}, b_g={b_g_best:.4f}")
print(f"  Residu minimal : {erreur[idx]:.4f}")

# ================================================================
# FSOLVE : solution precise pour rhoA donne, lt du module sim
# ================================================================
solutions = []
for b_a0 in np.linspace(b_min, b_max, 8):
    for b_g0 in np.linspace(b_min, b_max, 8):
        try:
            sol, _, ier, _ = fsolve(
                residus, [b_a0, b_g0],
                args=(lt_ref, rhoA),
                full_output=True
            )
            if ier == 1:
                b_a, b_g = sol
                if b_min <= b_a <= b_max and b_min <= b_g <= b_max:
                    res = residus([b_a, b_g], lt_ref, rhoA)
                    if abs(res[0]) < 1e-8 and abs(res[1]) < 1e-8:
                        nouveau = all(
                            abs(s[0]-b_a) > 1e-4 or abs(s[1]-b_g) > 1e-4
                            for s in solutions
                        )
                        if nouveau:
                            solutions.append((b_a, b_g))
        except Exception:
            pass

print(f"\nfsolve (lt_ref={lt_ref:.3f}m) : {len(solutions)} solution(s) trouvee(s)")
for i, (b_a, b_g) in enumerate(solutions):
    res = residus([b_a, b_g], lt_ref, rhoA)
    print(f"  Sol {i+1} : b_a={b_a:.4f}  b_g={b_g:.4f}  "
          f"residu={np.sqrt(res[0]**2+res[1]**2):.2e}")

# ================================================================
# GRAPHIQUE : carte du residu
# ================================================================
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.contourf(b_a_vals, b_g_vals, np.log10(erreur.T + 1e-10),
                 levels=50, cmap="viridis_r")
ax.contour(b_a_vals, b_g_vals, np.log10(erreur.T + 1e-10),
           levels=[-1], colors="red", linestyles="--", linewidths=2)
for i, (b_a, b_g) in enumerate(solutions):
    ax.plot(b_a, b_g, "r*", ms=15,
            label=f"Sol {i+1} : b_a={b_a:.3f}, b_g={b_g:.3f}")
ax.set_xlabel("b_a")
ax.set_ylabel("b_g")
ax.set_title(f"Residu |yG-1|  -  {f_mhz} MHz, "
             f"|rhoA|={abs(rhoA):.3f}, lt papier ={lt_ref:.2f}m")
ax.legend(fontsize=9)
fig.colorbar(im, ax=ax, label="log10(|yG-1|)")
plt.tight_layout()
#plt.savefig(f"resolution_ba_bg_{int(f_mhz)}MHz.png", dpi=120) 
#print(f"\nFigure enregistree : resolution_ba_bg_{int(f_mhz)}MHz.png")   #décommenter pour save dans le projet

# ================================================================
# DECISION : 350 mm vs 915 mm
# ================================================================
DELTA_LT = 0.061 #vient table papier design
N_PHASES = 36 # 10° entre chaque phase
R_TEST   = np.linspace(0.02, 0.65, 40) #valeur min à max de rhoA + nombre de points de resolution 
options  = {"350 mm": 0.350 + DELTA_LT,  "915 mm": 0.915 + DELTA_LT, } #si plus de longueurs dispos rajouter ici 
phases   = np.linspace(0, 2 * np.pi, N_PHASES, endpoint=False)

def gamma2min(lt_val):
    """
    (|rhoA|_max)^2
    Teste des valeurs de reflexion rhoA de plus en plus grandes en balayant des phases différentes de 0 à 360°.
    Retourne la puissance réfléchie maximale (en %) que le système est capable de corriger à 100% peut importe la phase. 
    Plus le pourcentage est grand, plus la longueur de la ligne choisie est robuste face aux désaccords.
    """
    best_r2 = 0.0
    for r in R_TEST:  #teste les modules du plus petit au plus grand 
        all_ok = True
        for ph in phases: #balayage des phases
            rhoA_test = r * np.exp(1j * ph)
            trouve    = False
            for b_a0 in np.linspace(b_min, b_max, 6):  #rechercher de b_a et b_g avec fsolve
                for b_g0 in np.linspace(b_min, b_max, 6):
                    try:
                        sol, _, ier, _ = fsolve(
                            residus, [b_a0, b_g0],
                            args=(lt_val, rhoA_test),
                            full_output=True
                        )
                        if ier == 1:   #si fsolve converge 
                            ba, bg = sol
                            if b_min <= ba <= b_max and b_min <= bg <= b_max:
                                res = residus([ba, bg], lt_val, rhoA_test)
                                if np.sqrt(res[0]**2 + res[1]**2) < 0.05:
                                    trouve = True
                    except Exception:
                        pass
                    if trouve:
                        break
                if trouve:
                    break
            if not trouve:
                all_ok = False
                break
        if all_ok:
            best_r2 = r ** 2
        else:
            break
    return best_r2 * 100

# ================================================================
# LONGUEUR IDEALE + DECISION : 350 mm vs 915 mm
# ================================================================
print()
print("=" * 55)
print(f"RESULTATS a {f_mhz} MHz")
print("=" * 55)

# Recherche de la longueur ideale -> passa 1 grossière 
lt_candidates_1 = np.linspace(0.3, 1.5, 25)
scores_lt = {}
for lt_c in lt_candidates_1:
    scores_lt[lt_c] = gamma2min(lt_c)


lt_best_1 = max(scores_lt, key=scores_lt.get)

# Passe 2 : fine autour du maximum trouve (+/- 50mm, 20 pts -> resolution ~5mm)
lt_candidates_2 = np.linspace(
    max(0.3, lt_best_1 - 0.05),
    min(1.5, lt_best_1 + 0.05),
    20
)
for lt_c in lt_candidates_2:
    if lt_c not in scores_lt:
        scores_lt[lt_c] = gamma2min(lt_c)


lt_ideal      = max(scores_lt, key=scores_lt.get)
lt_ideal_mech = (lt_ideal - DELTA_LT) * 1000

print(f"  LONGUEUR IDEALE : {lt_ideal_mech:.0f} mm (mecanique)")
print(f"     lt_elec      = {lt_ideal:.3f} m")
print(f"     theta        = {np.rad2deg(beta_f*lt_ideal):.1f} deg")
print(f"     T=tan(theta) = {np.tan(beta_f*lt_ideal):.3f}")
print(f"     Gamma2min    = {scores_lt[lt_ideal]:.1f}%")
print()

# Decision entre les options disponibles
print(f"  {'Option':>8}  {'lt_elec [m]':>12}  "
      f"{'theta [deg]':>12}  {'T':>6}  "
      f"{'Gamma2min':>10}  {'Ecart ideal':>12}")
print("-" * 72)

scores = {}
for name, lt_val in options.items():
    theta = beta_f * lt_val
    T     = np.tan(theta)
    g2    = gamma2min(lt_val)
    ecart = abs(lt_val - lt_ideal) * 1000
    scores[name] = g2
    print(f"  {name:>8}  {lt_val:>12.3f}  "
          f"{np.rad2deg(theta):>12.1f}  {T:>6.3f}  "
          f"{g2:>9.1f}%  {ecart:>9.0f} mm")

meilleure = max(scores, key=scores.get)
print()
print(f"  => CHOISIR : {meilleure}  "
      f"(Gamma2min = {scores[meilleure]:.1f}% )")

plt.show()
 
