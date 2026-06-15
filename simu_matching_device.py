"""
Simulation simplifiee de la dynamique du dispositif d'accord automatique
ICRH-TEXTOR (d'apres Durodie & Vervier, "Design of an Automatic Matching
Device for TEXTOR's ICRH System", 1992).

Objectif : reproduire QUALITATIVEMENT le comportement dynamique decrit dans
le papier (positions/vitesses des condensateurs, signaux d'erreur, temps de
stabilisation), afin de disposer d'un outil de reference et, plus tard, de
generer des signaux de test (eps_a, eps_g, |rho_G|, x_a, x_g) injectables
via les sorties DAC du LabJack T4.

============================================================================
SIMPLIFICATIONS ASSUMEES (a affiner avec les donnees reelles / ton encadrant)
============================================================================
1. Modele RF :
   - Chaque "stub" (condensateur + inductance serie + stub inductif) est
     represente par une susceptance shunt b_stub(C), NULLE a une valeur de
     capacite "neutre" C_neutral (cf Table 1 - First Results, ~135 pF a
     32.5 MHz), avec une inductance serie Ls = 70 nH (valeur MESUREE,
     papier First Results, plus realiste que les 20 nH supposes en
     conception).
   - Le reseau {stub Ca} -- {ligne lt} -- {stub Cg} relie le port "antenne"
     (charge rhoA) au port "generateur" (admittance normalisee yG).

2. Signaux d'erreur :
   - eps_g ~ b_G  (partie imaginaire de yG)
   - eps_a ~ (g_G - 1)  (ecart de la partie reelle de yG a 1)
   Ce sont des APPROXIMATIONS qui respectent les deux criteres du papier
   (zero unique en yG=1, signe constant de la derivee), mais PAS la formule
   exacte linearisee en V1, V2, V+ (qui depend de l1, l2 ET de details de
   calibration electronique non disponibles ici).

3. Dynamique (section 4 du papier - celle-ci est fidele) :
   - vitesse demandee = k_v * eps_i, clippee a +/- v_max * (1 - |rho_G|)
   - acceleration = k_a * (v_demandee - v_actuelle), clippee a +/- a_max
   - v_max = 0.25 m/s, a_max = 50 m/s^2, k_a = 50/0.05 = 1000 s^-1
     (valeurs donnees dans le papier)
   - k_v est un GAIN A CALIBRER (le papier le donne en (m/s)/kV, mais nos
     eps_a, eps_g sont sans dimension ; k_v=1.0 donne des ordres de
     grandeur de temps de stabilisation comparables aux Figures 3-4).
============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt

# --- Parametres RF (32.5 MHz) ---
f = 32.5e6
c_light = 3e8
Z0 = 50.0
beta = 2 * np.pi * f / c_light

lt = 0.91              # m, longueur electrique entre les deux stubs (Table 1, Design)
Ls_series = 70e-9      # H, inductance serie mesuree (Table 1, First Results)
C_neutral = 135.1e-12  # F, valeur "neutre" du condensateur a 32.5 MHz (Table 1, Design)

x0_mm = 35.0           # mm, position centrale de depart (Cs ~ 117-135 pF)
x_min, x_max = 18.0, 50.0  # mm, plage de travail 40-205 pF (papier "Design")


def Cs_from_x(x_mm):
    """Capacite [F] en fonction de la position x [mm] (fiche COMET CV7W300FSC)."""
    return (300.0 - x_mm * 5.217) * 1e-12


def b_stub(C):
    """Susceptance normalisee (B*Z0) du stub, nulle a C_neutral."""
    w = 2 * np.pi * f

    def raw(Cc):
        return w * Cc / (1 - (w ** 2) * Ls_series * Cc)

    return Z0 * (raw(C) - raw(C_neutral))


def abcd_line(theta):
    """Matrice ABCD d'une ligne sans pertes, longueur electrique theta=beta*l."""
    return np.array([[np.cos(theta), 1j * Z0 * np.sin(theta)],
                      [1j * np.sin(theta) / Z0, np.cos(theta)]], dtype=complex)


def abcd_shunt(B):
    """Matrice ABCD d'une susceptance shunt B (normalisee, B*Z0)."""
    return np.array([[1, 0], [1j * B / Z0, 1]], dtype=complex)


def yG(Ca, Cg, rhoA):
    """Admittance normalisee vue au port 'generateur' du dispositif."""
    zA = (1 + rhoA) / (1 - rhoA)        # normalisee (/Z0)
    zA_ohm = zA * Z0                    # ABCD ci-dessous est en ohms
    M = abcd_shunt(b_stub(Ca)) @ abcd_line(beta * lt) @ abcd_shunt(b_stub(Cg))
    A, B, C_, D = M.flatten()
    # zA_ohm = (A*zG_ohm+B)/(C*zG_ohm+D)  ->  zG_ohm = (B - zA_ohm*D)/(zA_ohm*C - A)
    zG_ohm = (B - zA_ohm * D) / (zA_ohm * C_ - A)
    zG = zG_ohm / Z0                    # retour en normalise
    return 1.0 / zG


def error_signals(Ca, Cg, rhoA):
    """Retourne (eps_a, eps_g, rho_G) -- voir simplifications en en-tete."""
    y = yG(Ca, Cg, rhoA)
    eps_g = y.imag
    eps_a = y.real - 1.0
    rho_g = (y - 1) / (y + 1)
    return eps_a, eps_g, rho_g


# --- Parametres de dynamique (papier "Design", section 4) ---
v_max = 0.25      # m/s
a_max = 50.0      # m/s^2
k_a = 50.0 / 0.05  # s^-1  (= 1000)
k_v = 1.0          # GAIN A CALIBRER (eps sans dimension -> m/s)


def simulate(rhoA0, rhoA1=None, t_switch=None, t_max=0.15, dt=1e-4):
    """
    Simule la convergence du dispositif depuis l'etat neutre (x0_mm, x0_mm).

    rhoA0       : coefficient de reflexion complexe impose a t=0
    rhoA1       : (optionnel) nouvelle valeur de rhoA a partir de t_switch
    t_switch    : instant du changement [s]
    t_max, dt   : duree totale et pas de temps de la simulation [s]
    """
    n = int(t_max / dt)
    t = np.arange(n) * dt

    x_a = np.full(n, x0_mm)
    x_g = np.full(n, x0_mm)
    v_a = np.zeros(n)
    v_g = np.zeros(n)
    eps_a_arr = np.zeros(n)
    eps_g_arr = np.zeros(n)
    rho_gen = np.zeros(n)

    for i in range(1, n):
        rhoA = rhoA0 if (rhoA1 is None or t[i] < t_switch) else rhoA1

        Ca = Cs_from_x(x_a[i - 1])
        Cg = Cs_from_x(x_g[i - 1])
        eps_a, eps_g, rho_g = error_signals(Ca, Cg, rhoA)
        eps_a_arr[i - 1], eps_g_arr[i - 1] = eps_a, eps_g
        rho_gen[i - 1] = abs(rho_g)

        # vitesse demandee, clippee selon |rho_G| (cf V-/V+ au generateur)
        # NOTE : dans ce modele simplifie, eps_a et eps_g ont des sens de
        # variation opposes par rapport a leur condensateur respectif sur
        # la plage de travail (40-205 pF) -> signes de feedback differents.
        # Ces signes sont EMPIRIQUES (propres a ce modele de substitution),
        # a NE PAS reporter directement sur l'electronique reelle.
        vmax_i = v_max * max(0.05, 1 - abs(rho_g))
        v_dem_a = np.clip(+k_v * eps_a, -vmax_i, vmax_i)
        v_dem_g = np.clip(-k_v * eps_g, -vmax_i, vmax_i)

        # acceleration limitee
        acc_a = np.clip(k_a * (v_dem_a - v_a[i - 1]), -a_max, a_max)
        acc_g = np.clip(k_a * (v_dem_g - v_g[i - 1]), -a_max, a_max)

        v_a[i] = v_a[i - 1] + acc_a * dt
        v_g[i] = v_g[i - 1] + acc_g * dt

        x_a[i] = np.clip(x_a[i - 1] + v_a[i] * dt * 1000.0, x_min, x_max)  # m/s -> mm/s
        x_g[i] = np.clip(x_g[i - 1] + v_g[i] * dt * 1000.0, x_min, x_max)

    eps_a_arr[-1], eps_g_arr[-1], rg = error_signals(
        Cs_from_x(x_a[-1]), Cs_from_x(x_g[-1]), rhoA0 if rhoA1 is None else rhoA1
    )
    rho_gen[-1] = abs(rg)

    return {
        "t": t, "x_a": x_a, "x_g": x_g, "v_a": v_a, "v_g": v_g,
        "eps_a": eps_a_arr, "eps_g": eps_g_arr, "rho_gen": rho_gen,
    }


if __name__ == "__main__":
    # Exemple inspire de la Figure 2 (papier Design) :
    # reset a l'etat neutre, rhoA = 0.425 / 235 deg
    rhoA0 = 0.425 * np.exp(1j * np.deg2rad(235))
    res = simulate(rhoA0, t_max=0.15)

    fig, axs = plt.subplots(3, 1, figsize=(8, 8), sharex=True)

    axs[0].plot(res["t"] * 1e3, res["x_a"], label="x_a")
    axs[0].plot(res["t"] * 1e3, res["x_g"], label="x_g")
    axs[0].set_ylabel("Position [mm]")
    axs[0].legend()
    axs[0].grid(alpha=0.3)

    axs[1].plot(res["t"] * 1e3, res["eps_a"], label="eps_a")
    axs[1].plot(res["t"] * 1e3, res["eps_g"], label="eps_g")
    axs[1].set_ylabel("Signaux d'erreur [u.a.]")
    axs[1].legend()
    axs[1].grid(alpha=0.3)

    axs[2].plot(res["t"] * 1e3, res["rho_gen"])
    axs[2].axhline(0.027, color="r", ls="--", label="spec generateur (2.7%)")
    axs[2].set_ylabel("|rho_G|")
    axs[2].set_xlabel("Temps [ms]")
    axs[2].legend()
    axs[2].grid(alpha=0.3)

    plt.tight_layout()
    plt.show()