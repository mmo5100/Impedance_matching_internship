"""
Reconstruction du double stub tuner (Ca - lt - Cg, stub ls en court-circuit)
avec pyRFtk -- VERSION "VNA" : Ca et Cg ne sont plus modelises
analytiquement (rfRLC) mais charges DIRECTEMENT depuis des fichiers .s2p
mesures au VNA (entree = cote noeud/jonction, sortie = de l'autre cote
du condensateur).

Topologie (identique a circuit_pyrftk.py, seuls Ca et Cg changent) :

    antenne ---[Ca : mesure VNA .s2p]---[lsA : stub, sc a l'extremite]
        |
       (lt)
        |
    generateur ---[Cg : mesure VNA .s2p]---[lsG : stub, sc a l'extremite]

  - Ca, Cg : chacun est un rfObject 2 ports charge depuis un .s2p mesure.
    Son port de sortie ('scA'/'scG') se connecte a l'ENTREE du stub fixe
    correspondant (lsA/lsG) -- le condensateur et le stub sont donc EN
    SERIE, et le court-circuit n'est applique qu'a l'EXTREMITE du stub
    (pas directement sur le port de sortie du condensateur).
  - lsA, lsG : stubs fixes, restent modelises analytiquement (rfTRL
    court-circuite a leur extremite), car le .s2p ne couvre que le
    condensateur.
  - lt : ligne de transmission (rfTRL) entre les deux stubs.
"""

 
import sys
import re
import numpy as np
import matplotlib.pyplot as pl
from pyRFtk import rfCircuit, rfTRL, rfObject
 
# ============================================================================
# PARAMETRES PHYSIQUES (identiques a circuit_pyrftk.py)
# ============================================================================
f_mhz = 38
f_hz = f_mhz * 1e6
Z0 = 50.0
lt = 0.415          # m -- A AJUSTER
Ls_serie = 70e-9  # H, inductance serie mesuree -- ne sert plus qu'au calcul de ls (stub fixe)
ls = 0.460
 
# Valeur "neutre" (Table 1, papier Design) -- sert a calculer ls fixe
Cs_neutre_table = {25.0: 128.3e-12, 29.0: 133.3e-12, 32.5: 135.1e-12, 38.0: 138.9e-12}
Cs_neutre = Cs_neutre_table[f_mhz]
 
 
# ============================================================================
# UTILITAIRE D'AFFICHAGE (repris de l'exemple pyRFtk touchstone)
# ============================================================================
 
def plotSij(circuit, fHzs, title='title'):
    pl.figure(title)
    SS = circuit.getS(fHzs)
    for c, (i, j) in {'r': (0, 0), 'm': (0, 1), 'c': (1, 0), 'b': (1, 1)}.items():
        pl.plot(fHzs / 1e6, SS[:, i, j].real, c, label=f'Re S$_{{{i+1},{j+1}}}$')
        #pl.plot(fHzs / 1e6, SS[:, i, j].imag, c + ':', label=f'Im S$_{{{i+1},{j+1}}}$')
    pl.xlabel('frequency [MHz]')
    pl.title('Re and Im of S$_{ij}$')
    pl.suptitle(title)
    pl.ylim(top=1, bottom=-1)
    pl.legend(loc='best')
    pl.grid()
    pl.tight_layout()
 
 
# ============================================================================
# CONSTRUCTION DU CIRCUIT PYRFTK -- VERSION VNA
# ============================================================================
 
def construire_circuit(chemin_s2p_Ca, chemin_s2p_Cg, lt_val=lt):
    """
    Construit le circuit sauf que Ca et
    Cg sont chacun un rfObject charge depuis un .s2p mesure au VNA au
    lieu d'un rfRLC analytique. Le condensateur et son stub fixe sont
    connectes EN SERIE ; le court-circuit n'est applique qu'a
    l'extremite du stub (pas directement sur le port de sortie du
    condensateur).
    """
    ct = rfCircuit(Zbase=Z0)
 
    # --- branche Ca : condensateur MESURE (VNA) en SERIE avec le stub fixe
    #     ls, le court-circuit n'etant applique qu'a l'extremite du stub
    #     (et non directement sur le port de sortie du condensateur) ---
    ct.addblock('Ca', rfObject(touchstone=chemin_s2p_Ca, ports=['noeud', 'scA']))
    ct.addblock('lsA', rfTRL(L=ls, Z0TL=Z0, ports=['in', 'sc']))
    ct.terminate('lsA.sc', Z=0.)
    ct.connect('Ca.scA', 'lsA.in')
 
    # ligne lt
    ct.addblock('lt', rfTRL(L=lt_val, Z0TL=Z0, ports=['cotA', 'cotG']))
 
    # jonction shunt cote antenne : antenne, Ca.noeud (entree de la branche
    # Ca-lsA en serie) et lt.cotA
    ct.connect('antenne', 'Ca.noeud', 'lt.cotA')
 
    # --- branche Cg : condensateur MESURE (VNA) en SERIE avec le stub fixe
    #     ls, meme logique que pour Ca ---
    ct.addblock('Cg', rfObject(touchstone=chemin_s2p_Cg, ports=['noeud', 'scG']))
    ct.addblock('lsG', rfTRL(L=ls, Z0TL=Z0, ports=['in', 'sc']))
    ct.terminate('lsG.sc', Z=0.)
    ct.connect('Cg.scG', 'lsG.in')
 
    # --- cote generateur : apres la jonction Cg/lt, la ligne physique
    #     continue avec 2 coudes de 46 cm chacun puis une ligne droite de
    #     91.5 cm, avant d'atteindre le vrai port externe 'generateur' ---
    ct.addblock('coude1_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('coude2_g', rfTRL(L=0.460, Z0TL=Z0, ports=['in', 'out']))
    ct.addblock('ligne_g', rfTRL(L=0.915, Z0TL=Z0, ports=['in', 'out']))
 
    ct.connect('Cg.noeud', 'lt.cotG', 'coude1_g.in')
    ct.connect('coude1_g.out', 'coude2_g.in')
    ct.connect('coude2_g.out', 'ligne_g.in')
    ct.connect('generateur', 'ligne_g.out')
 
    # 'antenne' et 'generateur' sont les SEULS ports externes restants
    return ct
 
 
# ============================================================================
# UTILISATION -- juste les resultats de simu (Sij), pas de matching
# ============================================================================
if __name__ == "__main__":
    # Chemins vers tes fichiers .s2p mesures au VNA (Ca puis Cg), passes en
    # arguments de ligne de commande :
    #   python circuit_pyRFtk_VNA.py chemin\vers\Ca_25mm.s2p chemin\vers\Cg_25mm.s2p
    if len(sys.argv) == 3:
        chemin_s2p_Ca = sys.argv[1]
        chemin_s2p_Cg = sys.argv[2]
    else:
        # Valeurs par defaut si aucun argument n'est passe -- A ADAPTER
        # avec les vrais chemins de tes fichiers .s2p sur cette machine.
        chemin_s2p_Ca = "VNA\Mesures_capa_only_HFSS\capav6+stub_v2_10p00.s2p"
        chemin_s2p_Cg = "VNA\Mesures_capa_only_HFSS\capav6+stub_v2_10p00.s2p"
        print(f"Aucun argument passe, utilisation des chemins par defaut "
              f"(a adapter) : {chemin_s2p_Ca}, {chemin_s2p_Cg}")
 
    ct = construire_circuit(chemin_s2p_Ca, chemin_s2p_Cg, lt)
 
    print('\nCircuit pyRFtk complet (Ca/Cg = mesures VNA) :')
    print(ct.asstr(-1))
 
    fHzs = np.linspace(10e6, 70e6, 201)
    plotSij(ct, fHzs, title=f'Circuit complet VNA - Ca={chemin_s2p_Ca}, Cg={chemin_s2p_Cg}')
 
    pl.show()
