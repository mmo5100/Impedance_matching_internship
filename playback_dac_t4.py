"""
Rejeu des signaux simules (eps_a -> DAC0, eps_g -> DAC1) via le LabJack T4.

Lit signaux_test.csv (genere par export_simulation_csv.py) et ecrit les
valeurs successives sur les sorties analogiques DAC0/DAC1 (plage 0-5V),
avec un pas de temps "playback_dt" choisi pour etre confortable a observer
(independant du pas de temps de la simulation, qui est trop fin pour le
debit USB).

============================================================================
MISE A L'ECHELLE (a adapter selon ce que tu veux injecter)
============================================================================
Les signaux eps_a, eps_g du modele sont SANS DIMENSION (~ -1 a +1 dans nos
scenarios). On les ramene lineairement sur la plage du DAC T4 (0-5V) via :

    DAC = DAC_MIN + (eps - EPS_MIN)/(EPS_MAX - EPS_MIN) * (DAC_MAX - DAC_MIN)

  eps = EPS_MIN  -> DAC = DAC_MIN (0V)
  eps = 0        -> DAC = 2.5V (si EPS_MIN=-1, EPS_MAX=+1)
  eps = EPS_MAX  -> DAC = DAC_MAX (5V)

Cette correspondance est ARBITRAIRE -- elle sert uniquement a generer un
signal de test "qui bouge de maniere realiste" pour ton electronique ou ton
acquisition. Si tu connais les niveaux reels attendus par l'electronique de
feedback, ajuste EPS_MIN/EPS_MAX/DAC_MIN/DAC_MAX en consequence.
============================================================================
"""

import csv
import time
from labjack import ljm

# --- Parametres ---
nom_fichier = "mesures_20260615_133746.csv"
playback_dt = 0.05   # secondes entre deux points (ralenti vs simulation)
n_repetitions = 1     # nombre de fois ou rejouer la sequence (0 = infini)

EPS_MIN, EPS_MAX = -1.0, 1.0
DAC_MIN, DAC_MAX = 0.0, 5.0


def scale(eps):
    """Convertit eps (sans dimension) en tension DAC [V], avec clipping."""
    eps_c = max(EPS_MIN, min(EPS_MAX, eps))
    frac = (eps_c - EPS_MIN) / (EPS_MAX - EPS_MIN)
    return DAC_MIN + frac * (DAC_MAX - DAC_MIN)


# --- Lecture du CSV ---
with open(nom_fichier) as f:
    rows = list(csv.DictReader(f))

print(f"{len(rows)} points charges depuis {nom_fichier}")
print(f"Duree du rejeu : {len(rows) * playback_dt:.1f} s par repetition")
print("DAC0 <- eps_a   |   DAC1 <- eps_g")
print(f"Mise a l'echelle : eps in [{EPS_MIN},{EPS_MAX}] -> DAC in [{DAC_MIN},{DAC_MAX}] V")

# --- Connexion au T4 ---
handle = ljm.openS("T4", "USB", "ANY")
info = ljm.getHandleInfo(handle)
print(f"Connecte au LabJack (S/N {info[2]})")
print("Ctrl+C pour arreter (les DAC seront remis a 0).")

try:
    rep = 0
    while True:
        for row in rows:
            v_a = scale(float(row["eps_a"]))
            v_g = scale(float(row["eps_g"]))
            ljm.eWriteNames(handle, 2, ["DAC0", "DAC1"], [v_a, v_g])
            t_ms = float(row["t_s"]) * 1e3
            print(f"  t_sim={t_ms:6.1f} ms   DAC0={v_a:.3f} V   DAC1={v_g:.3f} V")
            time.sleep(playback_dt)

        rep += 1
        if n_repetitions and rep >= n_repetitions:
            break
        print(f"-- repetition {rep + 1} --")

except KeyboardInterrupt:
    print("\nArret demande par l'utilisateur.")

finally:
    ljm.eWriteNames(handle, 2, ["DAC0", "DAC1"], [0.0, 0.0])
    ljm.close(handle)
    print("DAC remis a 0, connexion fermee.")