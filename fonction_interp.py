"""
Interpolation de ls_elec (longueur electrique mesuree de la self) en
fonction de la frequence, pour une longueur mecanique FIXE ls_mech=915mm
(Table 2, papier "First Results").
"""

from scipy.interpolate import interp1d

freq = [25, 29, 32.5, 38]
lst = [1.19, 1.22, 1.28, 1.39]   # m -- VERIFIER : papier donne 1.29 a 38MHz, pas 1.39

f_lineaire = interp1d(freq, lst, kind="linear", fill_value="extrapolate")


def ls_elec_mesure(f_mhz):
    """
    Longueur electrique [m] de la self, mesuree pour ls_mech=915mm fixe,
    interpolee (ou extrapolee lineairement si hors plage) depuis les 4
    points mesures.

    ATTENTION : valable seulement pour CETTE longueur mecanique (915mm) --
    ne permet PAS de deduire ls_mech pour un ls_elec cible quelconque (la
    relation electrique<->mecanique n'est pas un simple decalage constant).
    """
    if f_mhz < min(freq) or f_mhz > max(freq):
        print(f"  [!] {f_mhz} MHz hors de la plage mesuree "
              f"({min(freq)}-{max(freq)} MHz) -- extrapolation lineaire, "
              f"fiabilite non garantie au-dela des points mesures.")
    return float(f_lineaire(f_mhz))


if __name__ == "__main__":
    for f in [25, 29, 32.5, 38, 37.5, 40, 20]:
        print(f"f={f:>5} MHz  ->  ls_elec = {ls_elec_mesure(f)*1000:.1f} mm")