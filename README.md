# Impedance Matching Internship — TEXTOR ICRH Automatic Matching Device

## Contexte

Le dispositif étudié est un second double "stub tuner" (deux condensateurs
variables $C_a$, $C_g$ + selfs de compensation), placé entre le générateur
RF et le double stub tuner principal, qui corrige en temps réel
l'accord d'impédance vu par le générateur via deux signaux d'erreur
$\varepsilon_a$, $\varepsilon_g$.


## Prérequis

```bash
pip install labjack-ljm numpy matplotlib
```

Le pilote LJM (bas niveau) doit également être installé — voir
[support LabJack](https://support.labjack.com/) ou via Kipling.

## Utilisation

### 1. Acquisition LabJack T4

```bash
python test_labjack_t4.py        # affichage console uniquement
python test_labjack_t4_csv.py    # + enregistrement mesures_AAAAMMJJ_HHMMSS.csv
python test_labjack_t4_live.py   # + graphique temps reel (fenetre glissante)
```

- Voies lues : `AIN0`–`AIN3` (bornes HV, ±10 V).


### 2. Simulation de la dynamique du dispositif

```bash
python simulation_matching_device.py
```

Reproduit qualitativement les Figures 3-4 du papier "Design" : convergence
des positions $x_a, x_g$, signaux d'erreur $\varepsilon_a, \varepsilon_g$ et
$|\rho_G|$ vers la spécification du générateur (2,7 %), à partir d'une
condition initiale $\rho_{A0}$ (module + phase, modifiable dans le fichier).



### 3. Pont simulation <-> LabJack (DAC)

```bash
python export_simulation_csv.py   # genere signaux_test.csv (150 points)
python playback_dac_t4.py         # rejoue eps_a -> DAC0, eps_g -> DAC1 (0-5V)
```

### 4. Cartographie du domaine opérationnel

```bash
python map_operational_domain.py
```

Balaie $\rho_A$ (module × phase) et trace, dans le plan $\rho_A$, le temps
de convergence vers $|\rho_G|<2{,}7\%$ — analogue (qualitatif) de la
Figure 2a du papier "Design". Génère `carte_domaine_operationnel.png`.

