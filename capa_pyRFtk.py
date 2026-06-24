"""
Comparaison de la capacite simulee en HFSS avec une reconstruction analytique pyRFtk.
"""

import os
os.environ['OPENBLAS_NUM_THREADS'] = '{:d}'.format(2)

import re
import numpy as np
import matplotlib.pyplot as pl

from pyRFtk import rfCircuit, rfObject, rfTRL




def readvar(s):
    # split off the units
    try:
        val, unit = re.findall(r'([+-]?[0-9]+\.?[0-9]*)([A-Za-z]+)', s)[0]
    except (IndexError, ValueError):
        raise ValueError(f'could not understand {s!r} as a value, unit pair')

    val = float(val)
    if unit == 'mm':
        return val / 1000.0
    elif unit in ('m', 'ohm'):
        return val
    else:
        return None


def plotSij(circuit, fHzs, title='title', port_labels=None):
    """Trace Re/Im de tous les Sij"""
    SS = circuit.getS(fHzs)
    n = SS.shape[-1]
    if port_labels is None or len(port_labels) != n:
        port_labels = [str(i + 1) for i in range(n)]

    fig, axes = pl.subplots(n, n, figsize=(3.2 * n, 2.6 * n), sharex=True)
    fig.suptitle(title)
    for i in range(n):
        for j in range(n):
            ax = axes[i, j] if n > 1 else axes
            ax.plot(fHzs / 1e6, SS[:, i, j].real, 'r', lw=1, label='Re')
            ax.plot(fHzs / 1e6, SS[:, i, j].imag, 'b:', lw=1, label='Im')
            ax.set_title(f'S$_{{{port_labels[i]},{port_labels[j]}}}$', fontsize=9)
            ax.set_ylim(-1, 1)
            ax.grid(alpha=0.3)
            if i == n - 1:
                ax.set_xlabel('f [MHz]')
    axes_flat = list(axes.flat) if n > 1 else [axes]
    axes_flat[0].legend(loc='best', fontsize=8)
    fig.tight_layout()
    return fig


# ============================================================================
# 1. CHARGER L'EXPORT HFSS 
# ============================================================================

PATH_S3P = 'capav3_HFSSDesign1.s3p'  # nom du fichier

obj = rfObject(touchstone=PATH_S3P)

print("Variables exportees par HFSS :")
for k, v in obj.variables.items():
    print(f"   {k} = {v}")
print()
print(obj)

plotSij(obj, obj.fs, title='Touchstone HFSS - capa 3 ports',
        port_labels=['1 (gauche)', '2 (droite)', '3 (haut)'])


# ============================================================================
# 2. RECUPERER LES PARAMETRES GEOMETRIQUES DEPUIS LES VARIABLES HFSS
# ============================================================================
Rlittle_c = readvar(obj.variables['Rlittle_c'])  # rayon electrode (conducteur, port 3)
Rint_v    = readvar(obj.variables['Rint_v'])     # rayon du vide autour de l'electrode
Rperp_c   = readvar(obj.variables['Rperp_c'])    # rayon de la tige perpendiculaire (conducteur, ports 1-2)
Rperp_v   = readvar(obj.variables['Rperp_v'])    # rayon du vide autour de la tige ports 1-2
Hperp_v   = readvar(obj.variables['Hperp_v'])    # longueur totale de la tige (vide, ports 1<->2)
H2_v      = readvar(obj.variables['H2_v'])       



# Impedances caracteristiques (formule coax air, Z0 = 60*ln(D/d)) :
#   branches 1-2 (tige)     : D = Rperp_v, d = Rperp_c  -> ~24.3 ohm
#   branche 3 (electrode)   : D = Rint_v,  d = Rlittle_c -> ~41.6 ohm
# Il faudrait que idéalement ajuster ca dans HFSS pour que Z0 soit = 50 ohm
Z0_tige = 60.0 * np.log(Rperp_v / Rperp_c) if Rperp_v > Rperp_c else 50.0
Z0_port3 = 60.0 * np.log(Rint_v / Rlittle_c) if Rint_v > Rlittle_c else 50.0

print(f"\nZ0 estimee branches 1-2 (tige)      : {Z0_tige:.1f} ohm")
print(f"Z0 estimee branche 3 (electrode)    : {Z0_port3:.1f} ohm")


# ============================================================================
# 3. RECONSTRUCTION DU CIRCUIT AVEC PYRFTK
# ============================================================================
def construire_circuit_capa(Z0_tige_val, Z0_port3_val,
                             L_tige=Hperp_v, L_port3=H2_v):
    ct = rfCircuit(Zbase=Z0_tige_val)

    # 2 demi-troncons de la tige (branches 1 et 2 de la croix)
    ct.addblock('tigeA', rfTRL(L=L_tige / 2, Z0TL=Z0_tige_val,
                                ports=['p1', 'croix']))
    ct.addblock('tigeB', rfTRL(L=L_tige / 2, Z0TL=Z0_tige_val,
                                ports=['croix', 'p2']))

    # branche 3 : l'electrode 
    ct.addblock('electrode', rfTRL(L=L_port3, Z0TL=Z0_port3_val,
                                     ports=['croix', 'p3']))

    # jonction en croix : connecte les 3 branches entre elles
    ct.connect('tigeA.croix', 'tigeB.croix', 'electrode.croix')

    ct.connect('1', 'tigeA.p1')
    ct.connect('2', 'tigeB.p2')
    ct.connect('3', 'electrode.p3')

    return ct


ct = construire_circuit_capa(Z0_tige, Z0_port3)
print("\nCircuit pyRFtk construit :")
print(ct.asstr(-1))

plotSij(ct, obj.fs, title='Reconstruction pyRFtk - capa 3 ports',
        port_labels=['1 (gauche)', '2 (droite)', '3 (haut)'])


# ============================================================================
# 4. COMPARAISON CHIFFREE A UNE FREQUENCE DE REFERENCE (32.5 MHz)
# ============================================================================

f_ref = 32.5e6
S_touchstone = obj.getS(np.array([f_ref]))[0]
S_pyrftk = ct.getS(np.array([f_ref]))[0]

print(f"\n{'='*70}")
print(f"COMPARAISON a f = {f_ref/1e6:.1f} MHz")
print(f"{'='*70}")
print(f"{'Sij':<8} {'|S| Touchstone':>16} {'|S| pyRFtk':>14} {'ecart':>10}")
for i in range(3):
    for j in range(3):
        st = abs(S_touchstone[i, j])
        sp = abs(S_pyrftk[i, j])
        print(f"S{i+1}{j+1}     {st:>16.4f} {sp:>14.4f} {abs(st-sp):>10.4f}")

pl.show()
