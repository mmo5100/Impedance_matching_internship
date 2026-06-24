"""
Created on 23 Jun 2026

@author: frederic.durodie@gmail.com

+-------------+----------------------------------------------------------------+
| Date        | Comment                                                        |
+=============+================================================================+
| 23 Jun 2026 | Created                                                        |
+-------------+----------------------------------------------------------------+

in this example we explore the use of touchstone to complement the description
of a circuit 

"""

__updated__ = "2026-06-23 03:16:35"

import os
os.environ['OPENBLAS_NUM_THREADS']='{:d}'.format(2)

import matplotlib.pyplot as pl
import numpy as np

import sys
sys.path.insert(0,'/home/frederic/git/pyrftk/src')

from pyRFtk import rfCircuit, rfObject, rfTRL

import re

#===================================================================================================

def plotSij(circuit, fHzs, title = 'title'):
    pl.figure(title)
    SS = circuit.getS(fHzs)
    for c, (i,j) in {'r':(0,0),'m':(0,1),'c':(1,0),'b':(1,1)}.items():
        pl.plot(fHzs/1e6, SS[:,i,j].real,c,label = f'Re S$_{{{i+1},{j+1}}}$')
        pl.plot(fHzs/1e6, SS[:,i,j].imag,c+':',label = f'Im S$_{{{i+1},{j+1}}}$')
    pl.xlabel('frequency [MHz]')
    pl.title('Re and Im of S$_{ij}$')
    pl.suptitle(title)
    pl.ylim(top=1, bottom=-1)
    pl.legend(loc='best')
    pl.grid()
    pl.tight_layout()

#===================================================================================================

def readvar(s):
    # split off the units
    try:
        val, unit= re.findall('([+-]?[0-9]+[\.[0-9]*]?)([A-Za-z]+)', s)[0]
    except:
        raise ValueError(f'could not understand {s} as a value, unit pair')
    
    if unit in ['mm']:
        return float(val)/1000
    elif unit in ['m', 'ohm']:
        return float(val)
    else:
        return None

#===================================================================================================

# rfObject is an object that can read a touchtone file

# this is a 1m long conical stub: at the short circuit the Zc = 50 Ohm while at the T 
# the impedance is 20 Ohm.
# the legs of the T are 

Path2TSF = 'Conical Stub_HFSSDesign1.s2p'
obj = rfObject(touchstone=Path2TSF)

plotSij(obj, obj.fs, title = 'Touchstone Sij')

# Ansys HFSS writes the parameters used in the touchstone and we can access them
print(obj.variables)
print(obj)

# let's recreate this using pyRFtk

L = readvar(obj.variables['L'])
L2 = readvar(obj.variables['L2'])
OD = readvar(obj.variables['OD'])
ID1 = OD * np.exp(-readvar(obj.variables['Zsc'])/60)
ID2 = OD * np.exp(-readvar(obj.variables['Ztop'])/60)

print(L, L2, OD, ID1, ID2)

Zbase = readvar(obj.variables['Ztop'])
                
ct = rfCircuit(Zbase=Zbase)
ct.addblock('Cone', rfTRL(L=L, OD=OD, ID=[ID1, ID2]))
ct.addblock('Tee1', rfTRL(L=L2, OD=OD, ID=ID2))
ct.addblock('Tee2', rfTRL(L=L2, OD=OD, ID=ID2))
ct.connect('Cone.2', 'Tee1.1', 'Tee2.1')
ct.connect('Tee1.2', '2')
ct.connect('Tee2.2', '1')
ct.terminate('Cone.1', Z=0)

print(ct.asstr(-1))

fHzs = np.linspace(25e6, 75e6, 51)

plotSij(ct, fHzs, 'Circuit Sij')

pl.show()
