"""
Reconstruction of the double stub tuner (Ca - lt - Cg, ls stub short-circuited)
with pyRFtk -- simulation only (circuit construction + Sij plot).

Topology:

    antenna ---[Ca]--- (lt) ---[Cg]---[coude 460mm]---[coude 460mm]---[915mm]--- generator
                |                |
               (sc)             (sc)

  - Ca, Cg: variable capacitors, MODELED as rfRLC (capacitance + series
    inductance Ls_serie).
  - lt: transmission line (rfTRL) between the two stubs.
  - On the generator side, after the Cg/lt junction: 2 elbows of 460 mm
    each, then a straight 915 mm line, before reaching the external
    'generateur' port.
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
lt = 0.415        # m -- electrical length between the two stubs
ls = 0.460        # m -- fixed stub length (imposed)
Ls_serie = 70e-9  # H, measured series inductance of the capacitors

print(f"lt = {lt*1000:.1f} mm, ls = {ls*1000:.1f} mm (imposed)")


# ============================================================================
# PYRFTK CIRCUIT CONSTRUCTION
# ============================================================================
def construire_circuit(Ca, Cg, lt_val=lt):
    """
    Builds the double-stub circuit (Ca - lt - Cg). Ca/Cg are modeled as
    rfRLC, each in series with a fixed stub (ls) short-circuited at its
    far end. Returns a 2-port circuit: 'antenne', 'generateur'.
    """
    ct = rfCircuit(Zbase=Z0)

    # Ca stub (shunt): one port goes to the node, the other to the fixed
    # stub ls, short-circuited at its far end
    ct.addblock('Ca', rfRLC(Cs=Ca, Ls=Ls_serie, ports=['noeud', 'scA']))
    ct.terminate('Ca.scA', Z=0.)
    ct.addblock('lsA', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsA.sc', Z=0.)

    # lt line
    ct.addblock('lt', rfTRL(L=lt_val, Z0TL=Z0, ports=['cotA', 'cotG']))

    # antenna-side shunt junction: 3 ports at the same node (external
    # 'antenne', Ca.noeud, lsA.noeud, lt.cotA)
    ct.connect('antenne', 'Ca.noeud', 'lsA.noeud', 'lt.cotA')

    # Cg stub (shunt), same principle
    ct.addblock('Cg', rfRLC(Cs=Cg, Ls=Ls_serie, ports=['noeud', 'scG']))
    ct.terminate('Cg.scG', Z=0.)
    ct.addblock('lsG', rfTRL(L=ls, Z0TL=Z0, ports=['noeud', 'sc']))
    ct.terminate('lsG.sc', Z=0.)

    # generator side: after the Cg/lt junction, the physical line continues
    # with 2 elbows of 460 mm each, then a straight 915 mm line, before
    # reaching the actual external 'generateur' port
    ct.addblock('coude1_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('coude2_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('ligne_g', rfTRL(L=0.915, Z0TL=Z0, ports=['in', 'out']))

    ct.connect('coude1_g.in', 'Cg.noeud', 'lsG.noeud', 'lt.cotG')
    ct.connect('coude1_g.out', 'coude2_g.in')
    ct.connect('coude2_g.out', 'ligne_g.in')
    ct.connect('generateur', 'ligne_g.out')

    # 'antenne' and 'generateur' are the ONLY remaining external ports
    return ct


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
    Ca_test = 122.78e-12
    Cg_test = 150.37e-12

    ct = construire_circuit(Ca_test, Cg_test, lt)

    print('\nFull pyRFtk circuit:')
    print(ct.asstr(-1))

    S_f = ct.getS(f_hz)
    print(f"\nS at {f_mhz} MHz (ports ['antenne','generateur']):")
    for i, pi in enumerate(['antenne', 'generateur']):
        for j, pj in enumerate(['antenne', 'generateur']):
            s = S_f[i, j]
            print(f"  S_{pi}->{pj} = {abs(s):.4f} @ {np.angle(s, deg=True):6.1f} deg")

    fHzs = np.linspace(10e6, 70e6, 201)
    plotSij(ct, fHzs, title=f'Full circuit - Ca={Ca_test*1e12:.1f}pF, Cg={Cg_test*1e12:.1f}pF')

    pl.show()