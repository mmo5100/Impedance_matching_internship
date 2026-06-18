"""
    b_total(C) = b_capa(C) + b_self_fixe
    b_capa(C)      = Z0 * w*C / (1 - w^2*Ls_serie*C)      (varie avec C)
    b_self_fixe    = -Z0 * w*Cs / (1 - w^2*Ls_serie*Cs)   (CONSTANTE, fixee par ls)

"""

import numpy as np
import matplotlib.pyplot as plt

# ============================================================================
# PARAMETRES PHYSIQUES
# ============================================================================
f_mhz = 37.5
f = f_mhz * 1e6
c_light = 3e8
Z0 = 50.0
w = 2 * np.pi * f
beta = w / c_light

Ls_serie = 70e-9        # H, inductance serie mesuree (First Results->70nH)


if f_mhz == 25:
    Cs_neutre = 128.3e-12
    
if f_mhz == 29:
    Cs_neutre = 133.3e-12
 
if f_mhz == 32.5 or f_mhz==32:
    Cs_neutre = 135.1e-12   
    
if f_mhz == 38:
    Cs_neutre = 138.9e-12 
    
if f_mhz == 37.5:
    Cs_neutre = 138.9e-12   


Ca_min, Ca_max = 40e-12, 205e-12   # plage de travail des condensateurs (papier Design)
Cg_min, Cg_max = 40e-12, 205e-12


def raw(C, Ls=Ls_serie):
    """Y = 1/(jwLs + 1/jwC), en Siemens : w*C / (1 - w^2*Ls*C)."""
    return w * C / (1 - w ** 2 * Ls * C)


# ----------------------------------------------------------------------------
# ls FIXE, calcule UNE FOIS depuis Cs -- ne depend jamais de C
# ----------------------------------------------------------------------------
def ls_from_Cs(Cs):
    """Longueur electrique [m] du stub inductif fixe, tel que b_total(Cs)=0."""
    cible = Z0 * raw(Cs)                 # cot(beta*ls) = Z0*raw(Cs)
    theta = np.arctan(1.0 / cible)        # dans ]-pi/2, pi/2]
    if theta <= 0:
        theta += np.pi  # ramener dans ]0, pi[ (ls > 0)
        
    print(raw(Cs))
    return theta / beta


#ls = 0.46 #soit on impose ls 
ls = ls_from_Cs(Cs_neutre) #soit on la calcule à partir de la formule en commentaire
b_self_fixe = -Z0 * raw(Cs_neutre)        
#b_self_fixe = -(1/np.tan(beta*ls)) #quand on a ls imposé   
#print ("iciiiiiiiiiiiiiiiii")
#print(np.tan(beta*ls))
#print(b_self_fixe)


print(f"--- Modele du stub a {f_mhz} MHz (Ls_serie={Ls_serie*1e9:.0f} nH) ---")
print(f"Cs neutre choisi   : {Cs_neutre*1e12:.1f} pF")
print(f"ls (self fixe)     : {ls*1000:.1f} mm  ")
print(f"b_self_fixe        : {b_self_fixe:.4f}")
print()


def b_total(C):
    """Susceptance normalisee totale du stub = capa variable + self fixe."""
    return Z0 * raw(C) + b_self_fixe


# ============================================================================
# RESEAU ABCD 
# ============================================================================
def ABCD(b_a, b_g, theta):
    """A,B,C,D du reseau {shunt b_a}--{ligne theta}--{shunt b_g}"""
    c, s = np.cos(theta), np.sin(theta)
    A = c - b_g * s
    B = 1j * Z0 * s
    C_ = 1j * ((b_a + b_g) * c + (1 - b_a * b_g) * s) / Z0
    D = c - b_a * s
    return A, B, C_, D


def rhoA_matched(Ca, Cg, lt):
    """
    Calcul de rhoA tq yg=1
    """
    A, B, C_, D = ABCD(b_total(Ca), b_total(Cg), beta * lt)
    zA_ohm = (B + A * Z0) / (C_ * Z0 + D)
    return (zA_ohm - Z0) / (zA_ohm + Z0)



def grille_accessible(lt, n=300):
    """Renvoie le tableau de tous les rhoA atteints en balayant Ca et Cg chacun sur n valeurs."""
    Ca_v = np.linspace(Ca_min, Ca_max, n)
    Cg_v = np.linspace(Cg_min, Cg_max, n)
    Ca_g, Cg_g = np.meshgrid(Ca_v, Cg_v)
    return rhoA_matched(Ca_g, Cg_g, lt).flatten()


def gamma2min(lt, n=220, n_phase_bins=360):
    """
    Le plus grand |rhoA|^2 qui annule la reflexion au generateur. 
    """
    pts = grille_accessible(lt, n=n)
    r = np.abs(pts)
    phi = np.mod(np.angle(pts), 2 * np.pi)
    bins = np.floor(phi / (2 * np.pi) * n_phase_bins).astype(int)
    bins = np.clip(bins, 0, n_phase_bins - 1)
    r_max_par_phase = np.full(n_phase_bins, np.nan)
    for k in range(n_phase_bins):
        sel = r[bins == k]
        if sel.size:
            r_max_par_phase[k] = sel.max()
    if np.any(np.isnan(r_max_par_phase)):
        return 0.0, pts  # au moins une direction jamais atteinte -> domaine nul
    r_min = r_max_par_phase.min()
    return r_min ** 2 * 100, pts


# ============================================================================
# BALAYAGE DE lt POUR TROUVER L'OPTIMUM
# ============================================================================
print("--- Balayage de lt (grossier) ---")
lt_candidats = np.linspace(0.5, 1.6, 25)
scores = {}
for lt_c in lt_candidats:
    g2, _ = gamma2min(lt_c, n=120, n_phase_bins=90)
    scores[lt_c] = g2
    print(f"  lt={lt_c:.3f} m   Gamma2min={g2:5.1f} %")

lt_grossier = max(scores, key=scores.get)

# Raffinement autour du meilleur candidat grossier
print(f"\n--- Raffinement autour de lt={lt_grossier:.3f} m ---")
lt_fins = np.linspace(max(0.3, lt_grossier - 0.05), lt_grossier + 0.05, 21)
scores_fins = {}
for lt_c in lt_fins:
    g2, _ = gamma2min(lt_c, n=220, n_phase_bins=180)
    scores_fins[lt_c] = g2

lt_opt = max(scores_fins, key=scores_fins.get)
g2_opt = scores_fins[lt_opt]

print(f"\n=> lt optimal : {lt_opt:.3f} m   (Gamma2min = {g2_opt:.1f} %)")

# ============================================================================
# FIGURE 2a -- reproduction pour lt_opt
# ============================================================================
N_FIG = 220
Ca_v = np.linspace(Ca_min, Ca_max, N_FIG)
Cg_v = np.linspace(Cg_min, Cg_max, N_FIG)
Ca_g, Cg_g = np.meshgrid(Ca_v, Cg_v)
rho_g = rhoA_matched(Ca_g, Cg_g, lt_opt)
g2_final, _ = gamma2min(lt_opt, n=300, n_phase_bins=240)
 
fig, ax = plt.subplots(figsize=(7.5, 7.5))
 

N_COURBES = 9
idx_courbes = np.linspace(0, N_FIG - 1, N_COURBES).astype(int)
for k, i in enumerate(idx_courbes):
    epais = 2.0 if i in (0, N_FIG - 1) else 0.6
    ax.plot(rho_g[i, :].real, rho_g[i, :].imag, color="blue", lw=epais,
            label="Cg = cste, Ca varie" if k == 0 else None)
    ax.plot(rho_g[:, i].real, rho_g[:, i].imag, color="green", lw=epais,
            label="Ca = cste, Cg varie" if k == 0 else None)
 
# Disque Gamma2min (rayon plus petit sur toutes les phases)
r_opt = np.sqrt(g2_final / 100)
theta = np.linspace(0, 2 * np.pi, 300)
ax.fill(r_opt * np.cos(theta), r_opt * np.sin(theta), color="0.75", alpha=0.8, zorder=0,
        label=f"$\\Gamma^2_{{min}}$ = {g2_final:.1f} %  (rayon={r_opt:.3f})")
 
ax.plot(np.cos(theta), np.sin(theta), color="gray", lw=1, ls=":", label=r"$|\rho_A|=1$")
ax.axhline(0, color="gray", lw=0.6, label="b = 0")
ax.axvline(0, color="gray", lw=0.6)
 
# Repere Smith (admittance) -- cercle g=1 classique {y=1+jb, b variable},
# centre (-0.5,0), rayon 0.5.
theta_g1 = np.linspace(0, 2 * np.pi, 200)
g1_circle = -0.5 + 0.5 * np.exp(1j * theta_g1)
ax.plot(g1_circle.real, g1_circle.imag, color="red", lw=1, ls="--", label="g = 1")
 
ax.set_xlabel(r"Re($\rho_A$)")
ax.set_ylabel(r"Im($\rho_A$)")
ax.set_title(f"Domaine accessible dans le plan $\\rho_A$ -- {f_mhz} MHz, lt={lt_opt:.3f} m\n"
             f"(Ls_serie={Ls_serie*1e9:.0f} nH, Ca,Cg in [{Ca_min*1e12:.0f},{Ca_max*1e12:.0f}] pF)")
ax.set_xlim(-1.05, 1.05)
ax.set_ylim(-1.05, 1.05)
ax.set_aspect("equal")
ax.legend(loc="upper left", fontsize=8.5)
ax.grid(alpha=0.2)
 
plt.tight_layout()
#plt.savefig("figure2a_domaine_accessible.png", dpi=130) # pour save la fig


# ============================================================================
# DECISION ENTRE LONGUEURS MECANIQUES DISPOS
# ============================================================================
DELTA_LT = 0.061  # ecart electrique/mecanique, Table 1 papier Design

options = {"350 mm": 0.350 + DELTA_LT, "915 mm": 0.915 + DELTA_LT}

print("\n" + "=" * 60)
print(f"DECISION -- longueurs mecaniques disponibles ({f_mhz} MHz)")
print("=" * 60)
print(f"{'Option':>8}  {'lt_elec [m]':>12}  {'Gamma2min':>10}  {'Ecart a l-opt':>14}")
g2_options = {}
for nom, lt_val in options.items():
    g2, _ = gamma2min(lt_val, n=220, n_phase_bins=180)
    g2_options[nom] = g2
    ecart = abs(lt_val - lt_opt) * 1000
    print(f"{nom:>8}  {lt_val:>12.3f}  {g2:>9.1f}%  {ecart:>11.0f} mm")

meilleure = max(g2_options, key=g2_options.get)
print(f"\n=> CHOISIR : {meilleure}  (Gamma2min = {g2_options[meilleure]:.1f}%)")

plt.show()