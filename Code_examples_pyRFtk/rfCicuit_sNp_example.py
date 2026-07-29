"""
Created on Jun 26, 2026

@author: frederic.durodie@gmail.com

+-------------+----------------------------------------------------------------+
| Date        | Comment                                                        |
+=============+================================================================+
| Jun 26, 2026 | Created                                                        |
+-------------+----------------------------------------------------------------+

in this example we explore the use of touchstone to complement the description
of a circuit 


"""

__updated__ = "2026-06-26 02:06:14"

import os 
os.environ['OPENBLAS_NUM_THREADS']='{:d}'.format(2)

import numpy as np
import matplotlib.pyplot as pl


import sys
# this is already done through the Eclipse settings
sys.path.insert(0,'/home/frederic/git/pyrftk/src') 

from pyRFtk import rfCircuit, rfTRL, rfObject, rfRLC, WriteTSF  # @UnresolvedImport
from pyRFtk.config import logit, logident


from pyRFtk import rfCircuit, rfTRL, rfObject, plotVSWs # @UnresolvedImport
from pyRFtk.config import logit, logident

import re 

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
obj = rfObject(touchstone=Path2TSF, Zbase=20)

# Ansys HFSS writes the parameters used in the touchstone and we can access them
print(obj.variables)
print(obj)

# let's recreate this using pyRFtk

L = readvar(obj.variables['L'])
L2 = readvar(obj.variables['L2'])
OD = readvar(obj.variables['OD'])
ID1 = OD * np.exp(-readvar(obj.variables['Zsc'])/60)
ID2 = OD * np.exp(-readvar(obj.variables['Ztop'])/60)
L = L - 0.9 * ID2
L2 = L2 - 0.3 * ID2

print(L, L2, OD, ID1, ID2)

Zbase = readvar(obj.variables['Ztop'])
                
ct = rfCircuit(sNp=Path2TSF, Zbase=Zbase)
print(ct.sNp)
ct.addblock('Tee1', rfTRL(L=L2, OD=OD, ID=ID2))
ct.addblock('Cone', rfTRL(L=L, OD=OD, ID=[ID2, ID1]), relpos=L2)
ct.addblock('Tee2', rfTRL(L=L2, OD=OD, ID=ID2),relpos=L2)
ct.connect('Cone.1', 'Tee1.2', 'Tee2.1')
ct.connect('Tee1.1', '1')
ct.connect('Tee2.2', '2')
ct.terminate('Cone.2', Z=0)

print(ct.asstr(-1))

fHzs = np.linspace(25e6, 75e6, 51)

fig, axs = pl.subplots(2, 2, sharex=True, num='sNp vs no sNp')
Ss_no_sNp = ct.getS(fHzs, flags={'sNp':False})
Ss_sNp = ct.getS(fHzs, flags={'sNp':True})
for k in range(4):
    i,j = k//2, k%2
    pl.sca(axs[i,j])
    pl.plot(fHzs/1e6, np.abs(Ss_no_sNp[:,i,j]),'r',label = f'|S$_{{{i+1},{j+1}}}$| no sNp')
    pl.plot(fHzs/1e6, np.abs(Ss_sNp[:,i,j]),'b',label = f'|S$_{{{i+1},{j+1}}}$| sNp')
    pl.title(f'|S$_{{{i+1},{j+1}}}$|')  
    pl.xlabel('frequency [MHz]')
    pl.grid()
    pl.legend(loc='best')
    
pl.suptitle('sNp vs no sNp')
pl.tight_layout()

# now we use the stub in a circuit

ct2 = rfCircuit(Zbase=20)
ct2.addblock('Stub1', ct)
ct2.addblock('TL1', rfTRL(L=1., Z0TL=20), relpos=2*L2)
ct2.addblock('Stub2', ct, relpos=2*L2+1)
ct2.connect('Stub1.2', 'TL1.1')
ct2.connect('Stub2.1', 'TL1.2')
ct2.terminate('Stub1.1', RC=0.)

print('sNp=False:',ct2.getS(40e6, flags={'sNp':False}))
print('sNp=True:',ct2.getS(40e6, flags={'sNp':True}))
# print(ct2)

Vmax, where, VSWs = ct2.maxV(40e6, {'Stub2.2':1}, flags={'sNp':True})
print(f'max voltage = {Vmax:.3f} at {where}')    
pl.figure(num='max voltage')
plotVSWs(VSWs)

Vmax2, where2, VSWs2 = ct2.maxV(40e6, {'Stub2.2':1}, flags={'sNp':False})
print(f'max voltage = {Vmax:.3f} at {where}')    
pl.figure(num='max voltage (no sNp)')
plotVSWs(VSWs2)

# create a circuit that does not know about the internals of the stub

ct3 = rfCircuit(Zbase=20)
ct3.addblock('Stub1', obj, ports=[1,2])
ct3.addblock('TL1', rfTRL(L=1., Z0TL=20 ), relpos=2*L2)
ct3.addblock('Stub2', obj, ports=[1,2], relpos=4*L2 +1) 
print(ct3)
ct3.connect('Stub1.2', 'TL1.1')
ct3.connect('Stub2.2', 'TL1.2')
ct3.terminate('Stub1.1', RC=0.)
# ct3.connect('Stub2.2','2')
print(ct3)
Vmax3, where3, VSWs3 = ct3.maxV(40e6, {'Stub2.1':1})
print(f'max voltage = {Vmax3:.3f} at {where3}')   
plotVSWs(VSWs3, num='max voltage 2', plotnodes=True)
pl.show()

