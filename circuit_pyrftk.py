"""
Reconstruction du double stub tuner (Ca - lt - Cg, stub ls en court-circuit)
avec pyRFtk, pour comparaison/validation croisee avec le modele ABCD ecrit
a la main dans calcul_lt_1m.py.

Topologie (cf TomasCircuit.py comme modele de reference) :

    antenne ---[Ca]--- (lt) ---[Cg]--- generateur
                |                |
               (sc)             (sc)

  - Ca, Cg : condensateurs variables, MODELISES comme rfRLC (capacite +
    self serie Ls_serie), exactement comme b_total(C) = b_capa(C) + b_self_fixe
    dans calcul_lt_1m.py -- SAUF que dans pyRFtk le "+b_self_fixe" (stub fixe
    ls) n'existe pas nativement dans rfRLC : on l'ajoute comme un STUB
    SEPARE (ligne ls en court-circuit), connecte au meme noeud que Ca/Cg.
  - lt : ligne de transmission (rfTRL) entre les deux stubs.

ATTENTION : ce script n'a pas pu etre execute dans cet environnement
(pas d'acces reseau pour installer pyRFtk) -- a tester et corriger de ton
cote. La logique est construite a partir du code source de rfCircuit.py
et de l'exemple TomasCircuit.py que tu as fournis.
"""

import numpy as np
from pyRFtk import rfCircuit, rfTRL, rfRLC

# ============================================================================
# PARAMETRES PHYSIQUES (identiques a calcul_lt_1m.py)
# ============================================================================
f_mhz = 25
f_hz = f_mhz * 1e6
Z0 = 50.0
lt = 1.0          # m -- A AJUSTER selon le cas teste (cf calcul_lt_1m.py)
Ls_serie = 70e-9  # H, inductance serie mesuree (meme valeur que calcul_lt_1m.py)


# Valeur "neutre" (Table 1, papier Design) -- sert a calculer ls fixe
Cs_neutre_table = {25.0: 128.3e-12, 29.0: 133.3e-12, 32.5: 135.1e-12, 38.0: 138.9e-12}
Cs_neutre = Cs_neutre_table[f_mhz]


# ============================================================================
# CALCUL DE ls COMME DANS calcul_lt_1m.py
# ============================================================================


def ls_from_Cs(Cs, f_hz=f_hz, Z0=Z0, Ls=Ls_serie):
    """Longueur electrique [m] du stub fixe ls, tel que b_total(Cs)=0
    (repris identique a calcul_lt_1m.py -- sert a definir le stub fixe
    qu'on ajoutera comme ligne separee dans pyRFtk)."""
    w = 2 * np.pi * f_hz
    c_light = 3e8
    beta = w / c_light
    raw_Cs = w * Cs / (1 - w**2 * Ls * Cs)
    cible = Z0 * raw_Cs
    theta = np.arctan(1.0 / cible)
    if theta <= 0:
        theta += np.pi
    return theta / beta


ls = ls_from_Cs(Cs_neutre)
print(f"Stub fixe ls calcule (même méthode que pour calcul_lt_1m) : {ls*1000:.1f} mm (a {f_mhz} MHz, Cs_neutre={Cs_neutre*1e12:.1f} pF)")


def raw_lt1m(C, Ls=Ls_serie):
    """Y = 1/(jwLs + 1/jwC), en Siemens (identique a raw() de calcul_lt_1m.py)."""
    w = 2 * np.pi * f_hz
    return w * C / (1 - w ** 2 * Ls * C)


_b_self_fixe_lt1m = -Z0 * raw_lt1m(Cs_neutre)


def b_total_lt1m(C):
    """Susceptance normalisee totale = capa variable + self fixe
    (identique a b_total() de calcul_lt_1m.py)."""
    return Z0 * raw_lt1m(C) + _b_self_fixe_lt1m


def ABCD_lt1m(b_a, b_g, theta):
    """A,B,C,D du reseau {shunt b_a}--{ligne theta}--{shunt b_g}
    (identique a ABCD() de calcul_lt_1m.py)."""
    c, s = np.cos(theta), np.sin(theta)
    A = c - b_g * s
    B = 1j * Z0 * s
    C_ = 1j * ((b_a + b_g) * c + (1 - b_a * b_g) * s) / Z0
    D = c - b_a * s
    return A, B, C_, D


def rhoA_matched_lt1m(Ca, Cg, lt_val):
    """Calcul de rhoA tq yg=1 (identique a rhoA_matched() de calcul_lt_1m.py)."""
    w = 2 * np.pi * f_hz
    c_light = 3e8
    beta = w / c_light
    A, B, C_, D = ABCD_lt1m(b_total_lt1m(Ca), b_total_lt1m(Cg), beta * lt_val)
    zA_ohm = (B + A * Z0) / (C_ * Z0 + D)
    return (zA_ohm - Z0) / (zA_ohm + Z0)



# ============================================================================
# CONSTRUCTION DU CIRCUIT PYRFTK
# ============================================================================

def construire_circuit(Ca, Cg, lt_val=lt):
    """
    Construit le circuit 
    """
    ct = rfCircuit(Zbase=Z0)

    # stub Ca (shunt) : un port va vers le noeud, l'autre vers le stub fixe ls en court-circuit
    ct.addblock('Ca', rfRLC(Cs=Ca, Ls=Ls_serie, ports=['noeud', 'scA']))
    ct.terminate('Ca.scA', Z=0.)
    ct.addblock('lsA', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsA.sc', Z=0.)

    # ligne lt
    ct.addblock('lt', rfTRL(L=lt_val, Z0TL=Z0, ports=['cotA', 'cotG']))

    # jonction shunt cote antenne : 3 ports au meme noeud (antenne externe,
    # Ca.noeud, lsA.noeud, lt.cotA) 
    ct.connect('antenne', 'Ca.noeud', 'lsA.noeud', 'lt.cotA')

    # stub Cg (shunt), meme principe
    ct.addblock('Cg', rfRLC(Cs=Cg, Ls=Ls_serie, ports=['noeud', 'scG']))
    ct.terminate('Cg.scG', Z=0.)
    ct.addblock('lsG', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsG.sc', Z=0.)

    ct.connect('generateur', 'Cg.noeud', 'lsG.noeud', 'lt.cotG')

    # 'antenne' et 'generateur' sont les SEULS ports externes restants
    return ct


def rhoA_matched_pyrftk(Ca, Cg, lt_val=lt, f_hz=f_hz):
    """
    Calcule rhoA tel que vu depuis l'antenne quand le generateur voit
    yG=1 (adaptation parfaite). Donc quand yG=1 <=> rhoG=0. Et donc,
    (rhoA = S11 + S12*S21*rhoG/(1-S22*rhoG)) se simplifie directement
    a rhoA = S11.
    """
    ct = construire_circuit(Ca, Cg, lt_val)
    S = ct.getS(f_hz)  # matrice S 2x2, ports dans l'ordre ['antenne','generateur']
    # S11 = reflexion au port antenne QUAND le port generateur est charge
    # par Z0 (rhoG=0, cad yG=1) -- c'est exactement rhoA_matched de
    # calcul_lt_1m.py
    return S[0, 0]


# ============================================================================
# COMPARAISON DIRECTE AVEC calcul_lt_1m.py (meme appel, meme parametres)
# ============================================================================
if __name__ == "__main__":
    # Choisis quelques points de comparaison
    Ca_test = 122.78e-12
    Cg_test = 150.37e-12

    rho_pyrftk = rhoA_matched_pyrftk(Ca_test, Cg_test)

    
    rho_lt1m = rhoA_matched_lt1m(Ca_test, Cg_test, lt)

    print("\n" + "=" * 60)
    print(f"COMPARAISON -- Ca={Ca_test*1e12:.2f}pF, Cg={Cg_test*1e12:.2f}pF, "
          f"lt={lt}m, f={f_mhz}MHz")
    print("=" * 60)
    print(f"{'Source':<20} {'|rhoA|':>10} {'phase [deg]':>14}")
    print(f"{'calcul_lt_1m.py':<20} {abs(rho_lt1m):>10.4f} {np.angle(rho_lt1m, deg=True):>14.1f}")
    print(f"{'pyRFtk':<20} {abs(rho_pyrftk):>10.4f} {np.angle(rho_pyrftk, deg=True):>14.1f}")
    print("-" * 60)
    print(f"{'Ecart':<20} {abs(abs(rho_lt1m)-abs(rho_pyrftk)):>10.4f} "
          f"{abs(np.angle(rho_lt1m,deg=True)-np.angle(rho_pyrftk,deg=True)):>14.1f}")