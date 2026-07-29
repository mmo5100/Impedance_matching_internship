"""
Adaptation de rfCicuit_sNp_example.py pour le double-stub tuner ICRH TEXTOR.
"""

import os
os.environ['OPENBLAS_NUM_THREADS'] = '{:d}'.format(2)

import re
import numpy as np
import matplotlib.pyplot as pl

from pyRFtk import rfCircuit, rfObject, rfTRL, rfRLC, plotVSWs


# ===========================================================================
# Utilitaires
# ===========================================================================

def readvar(s):
    try:
        val, unit = re.findall(r'([+-]?[0-9]+\.?[0-9]*)([A-Za-z]+)', s)[0]
    except (IndexError, ValueError):
        raise ValueError(f'Impossible de lire {s!r}')
    val = float(val)
    if unit == 'mm':   return val / 1000.0
    elif unit in ('m', 'ohm'): return val
    else: raise ValueError(f'Unite inconnue : {unit}')


def plotS11(circuit, fHzs, title='S11', flags=None):
    flags = flags or {}
    SS = circuit.getS(fHzs, flags=flags)
    pl.figure(title)
    pl.plot(fHzs / 1e6, SS[:, 0, 0].real, 'r',  label='Re S$_{11}$')
    pl.plot(fHzs / 1e6, SS[:, 0, 0].imag, 'b--', label='Im S$_{11}$')
    pl.xlabel('f [MHz]')
    pl.ylim(-1, 1)
    pl.legend()
    pl.grid(alpha=0.3)
    pl.suptitle(title)
    pl.tight_layout()


# ===========================================================================
# Parametres physiques
# ===========================================================================

PATH_S3P = 'capav3_HFSSDesign1.s3p'

# Longueur du stub court-circuite 
ls_mec = 0.460        # [m]  

# Longueur de la ligne de transmission entre les deux capas
lt = 0.915             # [m]  

# Valeurs initiales des condensateurs COMET (en Farads)
C1 = 150e-12          # [F]
C2 = 150e-12          # [F]

# Frequence cible
f_cible = 32.5e6      # [Hz]


# ===========================================================================
# 1. Charger le s3p et extraire les dimensions
# ===========================================================================

obj = rfObject(touchstone=PATH_S3P) #attention ici les resultats ne vont pas etre bons car c'est le snp qui n'était pas adapté à 50 ohms

Hperp_v   = readvar(obj.variables['Hperp_v'])
H2_v      = readvar(obj.variables['H2_v'])
Rperp_c   = readvar(obj.variables['Rperp_c'])
Rperp_v   = readvar(obj.variables['Rperp_v'])
Rlittle_c = readvar(obj.variables['Rlittle_c'])
Rint_v    = readvar(obj.variables['Rint_v'])

Z0_tige  = (377/2*np.pi) * np.log(Rperp_v   / Rperp_c) 
Z0_port3 = (377/2*np.pi) * np.log(Rint_v    / Rlittle_c)

print(f"Z0_tige  = {Z0_tige:.2f} ohm")
print(f"Z0_port3 = {Z0_port3:.2f} ohm")


# ===========================================================================
# 2. Construire ct_capa : jonction 3 ports avec mode sNp
#
#    sNp=True  --> utilise le fichier HFSS comme reference
#    sNp=False --> utilise uniquement les blocs analytiques rfTRL
# ===========================================================================

ct_capa = rfCircuit(Zbase=Z0_tige)


ct_capa.addblock('tigeA',     rfTRL(L=Hperp_v / 2, Z0TL=Z0_tige))
ct_capa.addblock('tigeB',     rfTRL(L=Hperp_v / 2, Z0TL=Z0_tige))
ct_capa.addblock('electrode', rfTRL(L=H2_v,         Z0TL=Z0_port3))

ct_capa.connect('tigeA.2', 'tigeB.1', 'electrode.1')
ct_capa.connect('tigeA.1',     '1')
ct_capa.connect('tigeB.2',     '2')
ct_capa.connect('electrode.2', '3')

print('\nJonction ct_capa :')
print(ct_capa.asstr(-1))


# ===========================================================================
# 3. Comparer sNp vs analytique sur la jonction seule
# ===========================================================================

# Comparaison manuelle : obj (HFSS) vs ct_capa (analytique)
fHzs = np.linspace(25e6, 75e6, 51)

SS_ana  = ct_capa.getS(fHzs)          # analytique
SS_hfss = obj.getS(fHzs)              # HFSS (obj lit déjà le .s3p)

fig, axs = pl.subplots(3, 3, sharex=True, num='Jonction : HFSS vs analytique')
for i in range(3):
    for j in range(3):
        pl.sca(axs[i, j])
        pl.plot(fHzs/1e6, np.abs(SS_ana[:,i,j]),  'r',   label='analytique')
        pl.plot(fHzs/1e6, np.abs(SS_hfss[:,i,j]), 'b--', label='HFSS')
        pl.title(f'|S$_{{{i+1},{j+1}}}$|', fontsize=9)
        pl.grid(alpha=0.3)
        if i == 2: pl.xlabel('f [MHz]')
axs[0,0].legend(fontsize=7)
pl.suptitle('Jonction 3 ports : HFSS vs analytique')
pl.tight_layout()


# ===========================================================================
# 4. Circuit complet : double-stub tuner
# ===========================================================================

ct_full = rfCircuit(Zbase=Z0_tige)

# --- Premiere branche ---
ct_full.addblock('Capa1',  ct_capa)
ct_full.addblock('COMET1', rfRLC(Cs=C1))           # condensateur COMET en serie
ct_full.addblock('Stub1',  rfTRL(L=ls_mec, Z0TL=Z0_tige))

ct_full.connect('Capa1.3',  'COMET1.s')
ct_full.connect('COMET1.p', 'Stub1.1')
ct_full.terminate('Stub1.2', Z=0)                  # court-circuit

# --- Ligne de transmission entre les deux capas ---
ct_full.addblock('LT', rfTRL(L=lt, Z0TL=Z0_tige))

# --- Deuxieme branche ---
ct_full.addblock('Capa2',  ct_capa)
ct_full.addblock('COMET2', rfRLC(Cs=C2))
ct_full.addblock('Stub2',  rfTRL(L=ls_mec, Z0TL=Z0_tige))

ct_full.connect('Capa2.3',  'COMET2.s')
ct_full.connect('COMET2.p', 'Stub2.1')
ct_full.terminate('Stub2.2', Z=0)

# --- Connexions de la ligne principale ---
ct_full.connect('Capa1.2', 'LT.1')
ct_full.connect('LT.2',    'Capa2.1')
ct_full.connect('Capa1.1', '1')
ct_full.connect('Capa2.2', '2')

print('\nCircuit double-stub complet :')
print(ct_full.asstr(-1))


# ===========================================================================
# 5. S11 du circuit complet : sNp vs analytique
# ===========================================================================


plotS11(ct_full, fHzs, title='Double-stub : analytique')

# ===========================================================================
# 6. Effet de la variation de C1 (sNp=True)
# ===========================================================================

pl.figure('S11 vs C1 (sNp)')
for C_val in [50e-12, 100e-12, 150e-12, 200e-12, 300e-12]:
    ct_full.set('COMET1.Cs', C_val)
    SS = ct_full.getS(fHzs)
    pl.plot(fHzs/1e6, np.abs(SS[:, 0, 0]),
            label=f'C1={C_val*1e12:.0f} pF')

ct_full.set('COMET1.Cs', C1)   # remettre la valeur initiale
pl.xlabel('f [MHz]')
pl.ylabel('|S$_{11}$|')
pl.ylim(0, 1)
pl.legend(fontsize=8)
pl.grid(alpha=0.3)
pl.suptitle(f'Effet de C1 (C2={C2*1e12:.0f} pF, ls={ls_mec*1e3:.0f} mm)')
pl.tight_layout()


# ===========================================================================
# 7. Distribution de tension sur la ligne a f_cible
# ===========================================================================

Vmax, where, VSWs = ct_full.maxV(
    f_cible,
    E={'1': 1, '2': 0}   # port 2 = charge adaptee (antenne matchee)
)

print(f'\nTension max = {Vmax:.3f} V en {where}')

pl.figure('Distribution de tension')
plotVSWs(VSWs)
pl.suptitle(f'VSW a {f_cible/1e6:.1f} MHz (C1={C1*1e12:.0f} pF, C2={C2*1e12:.0f} pF)')
pl.tight_layout()

pl.show()