"""
Reconstruction of the double stub tuner (Ca - lt - Cg, ls stub short-circuited)
with pyRFtk -- simulation only (circuit construction + Sij plot).
"""

import numpy as np
import matplotlib.pyplot as pl
from pyRFtk import rfCircuit, rfTRL, rfRLC

# ============================================================================
# PHYSICAL PARAMETERS
# ============================================================================
f_mhz = 38
f_hz = f_mhz * 1e6
Z0 = 50.0
lt = 0.415
ls = 0.460
Ls_serie = 70e-9

print(f"lt = {lt*1000:.1f} mm, ls = {ls*1000:.1f} mm (imposed)")


# ============================================================================
# CONVERSION position (mm) -> capacité (F)
# ============================================================================
def C_de_x(x_mm):
    C_pF = 300 - 5.217 * x_mm
    return C_pF * 1e-12


# ============================================================================
# PYRFTK CIRCUIT CONSTRUCTION
# ============================================================================
def construire_circuit(Ca_mm, Cg_mm, Z_antenne=None, lt_val=lt):
    """
    Ca_mm, Cg_mm : positions mécaniques (mm), converties en interne via C_de_x().
    """
    Ca = C_de_x(Ca_mm)
    Cg = C_de_x(Cg_mm)

    ct = rfCircuit(Zbase=Z0)

    ct.addblock('Ca', rfRLC(Cs=Ca, Ls=Ls_serie, ports=['noeud', 'scA']))
    ct.terminate('Ca.scA', Z=0.)
    ct.addblock('lsA', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsA.sc', Z=0.)

    ct.addblock('lt', rfTRL(L=lt_val, Z0TL=Z0, ports=['cotA', 'cotG']))

    ct.connect('antenne', 'Ca.noeud', 'lsA.noeud', 'lt.cotA')

    ct.addblock('Cg', rfRLC(Cs=Cg, Ls=Ls_serie, ports=['noeud', 'scG']))
    ct.terminate('Cg.scG', Z=0.)
    ct.addblock('lsG', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsG.sc', Z=0.)

    ct.addblock('coude1_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('coude2_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('ligne_g', rfTRL(L=0.915, Z0TL=Z0, ports=['in', 'out']))

    ct.connect('coude1_g.in', 'Cg.noeud', 'lsG.noeud', 'lt.cotG')
    ct.connect('coude1_g.out', 'coude2_g.in')
    ct.connect('coude2_g.out', 'ligne_g.in')
    ct.connect('generateur', 'ligne_g.out')

    if Z_antenne is not None:
        ct.terminate('antenne', Z=Z_antenne)

    return ct


def s11_gen(Ca_mm, Cg_mm, Z_antenne, f_hz=f_hz):
    ct = construire_circuit(Ca_mm, Cg_mm, Z_antenne=Z_antenne)
    S = ct.getS(f_hz)
    return S if np.isscalar(S) else S[0, 0]


# ============================================================================
# GRILLE DE CHARGES À COMPARER
# ============================================================================
charges = {
    '50 Ohm (nominal)':  50.0,
    '12.5 Ohm':          12.5,
    '25 Ohm':            25.0,
    '25+15j Ohm':        25 + 15j,
    '40-10j Ohm':        40 - 10j
}


# ============================================================================
# DISPLAY UTILITY
# ============================================================================
def plotSij(circuit, fHzs, title='title'):
    pl.figure(title)
    SS = circuit.getS(fHzs)
    for c, (i, j) in {'r': (0, 0), 'm': (0, 1), 'c': (1, 0), 'b': (1, 1)}.items():
        pl.plot(fHzs / 1e6, SS[:, i, j].real, c, label=f'Re S$_{{{i+1},{j+1}}}$')
    pl.xlabel('frequency [MHz]')
    pl.title('Re and Im of S$_{ij}$')
    pl.suptitle(title)
    pl.ylim(top=1, bottom=-1)
    pl.legend(loc='best')
    pl.grid()
    pl.tight_layout()


# ============================================================================
# SIMULATION
# ============================================================================
if __name__ == "__main__":
    Ca_mm_test = 31.39
    Cg_mm_test = 31.13
    Z_antenne_test = 50.0

    Ca_test = C_de_x(Ca_mm_test)
    Cg_test = C_de_x(Cg_mm_test)
    print(f"Ca = {Ca_mm_test} mm -> {Ca_test*1e12:.2f} pF")
    print(f"Cg = {Cg_mm_test} mm -> {Cg_test*1e12:.2f} pF")

    ct = construire_circuit(Ca_mm_test, Cg_mm_test, Z_antenne=Z_antenne_test)

    print('\nFull pyRFtk circuit:')
    print(ct.asstr(-1))

    S_f = ct.getS(f_hz)
    s11 = S_f if np.isscalar(S_f) else S_f[0, 0]
    print(f"\nS11 (vu du generateur) at {f_mhz} MHz, Z_antenne={Z_antenne_test}:")
    print(f"  |S11| = {abs(s11):.4f}  ({20*np.log10(abs(s11)):.2f} dB)  @ {np.angle(s11, deg=True):6.1f} deg")

    fHzs = np.linspace(10e6, 70e6, 201)
    S_sweep = ct.getS(fHzs)
    S11_sweep = S_sweep if S_sweep.ndim == 1 else S_sweep[:, 0, 0]

    pl.figure('S11 vs frequency')
    pl.plot(fHzs / 1e6, 20 * np.log10(np.abs(S11_sweep)), 'b')
    pl.axvline(f_mhz, color='gray', linestyle='--', label=f'{f_mhz} MHz')
    pl.xlabel('frequency [MHz]')
    pl.ylabel('S11 [dB]')
    pl.title(f'S11 vs freq — Ca={Ca_mm_test:.2f}mm ({Ca_test*1e12:.2f}pF), '
              f'Cg={Cg_mm_test:.2f}mm ({Cg_test*1e12:.2f}pF), Z_antenne={Z_antenne_test}')
    pl.grid()
    pl.legend()
    pl.tight_layout()

    pl.show()