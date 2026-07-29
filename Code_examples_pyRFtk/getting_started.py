"""
Created on 20 Jun 2026

@author: frederic.durodie@gmail.com

+-------------+----------------------------------------------------------------+
| Date        | Comment                                                        |
+=============+================================================================+
| 20 Jun 2026 | Created                                                        |
+-------------+----------------------------------------------------------------+

collection of examples for the use of the pyRFtk package

"""

__updated__ = "2026-06-23 07:47:25"

# it is noticed that 2 threads for numpy/openblas is the optimum for the typical
# size of matrices that need to be manipulated.
# this must be set before importing numpy

import os
os.environ['OPENBLAS_NUM_THREADS']='{:d}'.format(2)

import matplotlib.pyplot as pl
import numpy as np

import sys
# sys.path.insert(0,'/home/frederic/git/prrftk/pyRFtk/src'Quand sera tu au labo de nouveau ? )

from pyRFtk import rfRLC, rfTRL, rfCircuit, plotVSWs

# in pyRFtk there are primitive building blocks:
#
# rfObject, rfTRL, rfRLC, rfCoupler and rfArcObj
#
# and container object :
#
# rfCircuit 
#
# which can contain the objects aboves as well as instances of itself
#
# aside from its constructor method each object has a getS(f, Zbase) and a maxV(f, E) method

# example 1

# create an RLC object: it has two ports 's' and 'p' for resp. series side and parallel side
#
#   (s) --- Rs -- Ls -- Cs -- + -- + -- + -- (p)
#                             |    |    |
#                             Rp   Lp   Cp
#                             |    |    |
#                            Gnd  Gnd  Gnd
#
# although by default the reference impedance is 50 Ohm we will explicitly set it
# we will consider a single Cs capacitor (all quantities in pyRFtk are SI
# to get all the info printed we use the .asstr (as a string) method with the parameter -1.

RLC = rfRLC(Cs=100e-12, Zbase=50)
print(RLC.asstr(-1))

# we want the S matrix at 40MHz of this 2-port (s, p):

print(RLC.getS(40e6),'\n') # if we do not specificy a reference impedance it will be the object's one

# next we create a 50Ohm TL using rfTRL
#
# we can set its lenght, its OD  and e.g. its characteristic impedance:

TL1 = rfTRL(L=4, OD = 0.230, Z0TL = 50) # here we did not specify Zbase  so it will be 50 Ohm

# again we can print some info about TL1

print(TL1)           # the short form
print(TL1.asstr(-1)) # the full info

# get the S matrix at 40MHz

print(TL1.getS(40e6),'\n')

# now we can create a circuit and add the RLC and TL1 objects to it

ct = rfCircuit(Zbase=50) # explicitly set the refernce impedance to 50 Ohm

# Add the RLC and TL1 objects

ct.addblock('TL1', TL1) # we labeled the TL1 object to "TL1"
ct.addblock('RLC', RLC, relpos=4) # and the RLC object to "RLC" and positioned it a the end of TL1

# and make some connections "TL1.2" is port 2 of TL1 and likewise for "RLC.s"

ct.connect('TL1.2','RLC.s')

# now we short circuit the p port of the RLC object

ct.terminate('RLC.p', Z=0)

# we can print some info about ct

print(ct) # short form
print(ct.asstr(-1)) # long form

print(ct.getS(40e6))

# let make a figure of how the S11 of ct vs. frequency (let make a function
# so we can reuse it)

def plotS11(circuit, fHzs, title = 'title'):
    pl.figure(title)
    SS = circuit.getS(fHzs)
    pl.plot(fHzs/1e6, SS[:,0,0].real,'r',label = 'Re S$_{11}$')
    pl.plot(fHzs/1e6, SS[:,0,0].imag,'b',label = 'Im S$_{11}$')
    pl.xlabel('frequency [MHz]')
    pl.title('Re and Im of S$_{11}$')
    pl.suptitle(title)
    pl.ylim(top=1, bottom=-1)
    pl.legend(loc='best')
    pl.grid()
    pl.tight_layout()

fHzs = np.linspace(20e6, 80e6, 61)
plotS11(ct, fHzs, 'example 1 with Cs = 100pF')

# now suppose we want the result for Cs = 50pF instead 100pF:

ct.set('RLC.Cs', 50e-12)
plotS11(ct, fHzs, 'example 1 with Cs = 50pF')

# what is the VSW on TL1 if we excite the circuit with 1V forward voltage wave

Vmax, where, VSWs = ct.maxV(40e6, E={'TL1.1':1})

plotVSWs(VSWs,num='VSW')
print(f'maximum voltage is {Vmax}V at {where}')
print(ct.asstr(-1)) # long form
pl.show()


