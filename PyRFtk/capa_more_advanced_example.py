"""
Adaptation de more_advanced_example.py pour la jonction en croix (capa 3 ports).

Structure physique :
                        port 3 (electrode)
                            |
               [electrode : L=H2_v, Z0=Z0_port3]
                            |
    port 1 --[tigeA]-- noeud central --[tigeB]-- port 2
           L=Hperp_v/2        L=Hperp_v/2
           Z0=Z0_tige          Z0=Z0_tige

Le condensateur COMET n'est PAS dans ce modele : port 3 est ouvert.
"""

import os
os.environ['OPENBLAS_NUM_THREADS'] = '{:d}'.format(2)

import re
import numpy as np
import matplotlib.pyplot as pl

from pyRFtk import rfCircuit, rfObject, rfTRL


# ===========================================================================
# Utilitaires
# ===========================================================================

def readvar(s):
    """Convertit une chaine HFSS ('30mm', '8m', ...) en metres (float)."""
    try:
        val, unit = re.findall(r'([+-]?[0-9]+\.?[0-9]*)([A-Za-z]+)', s)[0]
    except (IndexError, ValueError):
        raise ValueError(f'Impossible de lire {s!r} comme valeur + unite')
    val = float(val)
    if unit == 'mm':
        return val / 1000.0
    elif unit in ('m', 'ohm'):
        return val
    else:
        raise ValueError(f'Unite inconnue : {unit}')


def plotSij_3ports(circuit, fHzs, title='Sij 3 ports'):
    SS = circuit.getS(fHzs)
    n = SS.shape[-1]

    colors = {(0,0):'r',      (0,1):'g',      (0,2):'b',
              (1,0):'m',      (1,1):'c',       (1,2):'k',
              (2,0):'orange', (2,1):'purple',  (2,2):'brown'}

    fig, axes = pl.subplots(n, n, figsize=(9, 7), sharex=True)
    fig.suptitle(title)
    for i in range(n):
        for j in range(n):
            ax = axes[i, j]
            c  = colors.get((i, j), 'k')
            ax.plot(fHzs / 1e6, SS[:, i, j].real,
                    color=c, linestyle='-',  lw=1.2, label='Re')
            ax.plot(fHzs / 1e6, SS[:, i, j].imag,
                    color=c, linestyle='--', lw=1.2, label='Im')
            ax.set_title(f'S$_{{{i+1},{j+1}}}$', fontsize=9)
            ax.set_ylim(-1, 1)
            ax.grid(alpha=0.3)
            if i == n - 1:
                ax.set_xlabel('f [MHz]')
    axes[0, 0].legend(loc='best', fontsize=7)
    fig.tight_layout()
    return fig


# ===========================================================================
# 1. Charger l'export HFSS
# ===========================================================================

PATH_S3P = 'capav6_HFSSDesign1.s3p'
obj = rfObject(touchstone=PATH_S3P)

print("Variables exportees par HFSS :")
for k, v in obj.variables.items():
    print(f"   {k} = {v}")
print()
print(obj)

plotSij_3ports(obj, obj.fs, title='Touchstone HFSS - jonction capa (3 ports)')

print("Variables disponibles :")
for k in obj.variables.keys():
    print(" ", k)


# ===========================================================================
# 2. Extraire les dimensions geometriques
# ===========================================================================

Hperp_v   = readvar(obj.variables['$Hperp_v'])   # longueur totale tige (ports 1-2)
H2_v      = readvar(obj.variables['$H2_v'])       # longueur branche electrode (port 3)
Rperp_c   = readvar(obj.variables['$Rperp_c'])    # rayon conducteur tige
Rperp_v   = readvar(obj.variables['$Rperp_v'])    # rayon vide tige
Rlittle_c = readvar(obj.variables['$Rlittle_c'])  # rayon conducteur electrode
Rint_v    = readvar(obj.variables['$Rint_v'])     # rayon vide electrode

# Impedances caracteristiques : Z0 = 60 * ln(R_ext / R_int)
Z0_tige   = 60.0 * np.log(Rperp_v   / Rperp_c)    # branches 1-2
Z0_port3  = 60.0 * np.log(Rint_v    / Rlittle_c)  # branche 3

print(f"\nDimensions extraites :")
print(f"   Hperp_v   = {Hperp_v*1e3:.1f} mm  (longueur totale tige)")
print(f"   H2_v      = {H2_v*1e3:.1f} mm  (longueur electrode)")
print(f"   Rperp_c   = {Rperp_c*1e3:.1f} mm  | Rperp_v  = {Rperp_v*1e3:.1f} mm")
print(f"   Rlittle_c = {Rlittle_c*1e3:.1f} mm  | Rint_v   = {Rint_v*1e3:.1f} mm")
print(f"\nImpedances calculees :")
print(f"   Z0_tige   = {Z0_tige:.2f} ohm  (a comparer au Port Impedance 1,2 du .s3p)")
print(f"   Z0_port3  = {Z0_port3:.2f} ohm  (a comparer au Port Impedance 3 du .s3p)")


# ===========================================================================
# 3. Reconstruire le circuit avec pyRFtk
#
#              port 3
#                |
#           [electrode]
#                |
# port 1 --[tigeA]--+--[tigeB]-- port 2
#
# ===========================================================================

ct = rfCircuit(Zbase=Z0_tige)

ct.addblock('tigeA',     rfTRL(L=Hperp_v / 2, Z0TL=Z0_tige))
ct.addblock('tigeB',     rfTRL(L=Hperp_v / 2, Z0TL=Z0_tige))
ct.addblock('electrode', rfTRL(L=H2_v,         Z0TL=Z0_port3))

# Noeud central en T
ct.connect('tigeA.2', 'tigeB.1', 'electrode.1')

# Ports externes
ct.connect('tigeA.1',     '1')
ct.connect('tigeB.2',     '2')
ct.connect('electrode.2', '3')

print('\nCircuit pyRFtk :')
print(ct.asstr(-1))

fHzs = np.linspace(25e6, 75e6, 51)
plotSij_3ports(ct, fHzs, title='Reconstruction pyRFtk - jonction capa (3 ports)')


# ===========================================================================
# 4. Comparaison chiffree a 32.5 MHz
# ===========================================================================

f_ref = 32.5e6
S_hfss   = obj.getS(np.array([f_ref]))[0]
S_pyrftk = ct.getS(np.array([f_ref]))[0]

print(f"\n{'='*65}")
print(f"COMPARAISON a f = {f_ref/1e6:.1f} MHz")
print(f"{'='*65}")
print(f"{'Sij':<6} {'|S| HFSS':>12} {'|S| pyRFtk':>12} {'ecart':>10}")
print(f"{'-'*65}")
for i in range(3):
    for j in range(3):
        sh = abs(S_hfss[i, j])
        sp = abs(S_pyrftk[i, j])
        print(f"S{i+1}{j+1}    {sh:>12.4f} {sp:>12.4f} {abs(sh-sp):>10.4f}")

pl.show()
