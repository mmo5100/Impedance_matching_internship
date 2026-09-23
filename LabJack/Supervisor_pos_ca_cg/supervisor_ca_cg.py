"""
SUPERVISEUR DE SECURITE POS_CA / POS_CG VIA LABJACK
=====================================================

Tourne en continu en parallele de la boucle fermee Arduino. Lit pos_ca et
pos_cg via le LabJack (pas de limite 0-5V), convertit en mm avec la
calibration obtenue (calibration_pos_ca_cg_labjack.py), et pilote deux
sorties digitales du LabJack vers deux pins digitales de l'Arduino :

    LOW  (0V)   = position OK, dans la plage 40-205pF (avec marge)
    HIGH (3.3V) = hors plage OU deconnexion -- l'Arduino doit couper

Cote Arduino, utiliser INPUT_PULLUP : un fil debranche est lu HIGH par
defaut => comportement fail-safe (coupure par defaut si probleme).

⚠️ CABLAGE : relie FIO4 (Ca) et FIO5 (Cg) du LabJack a deux pins
   digitales libres de l'Arduino (ex: D6 et D7), ET assure-toi que la
   masse (GND) du LabJack et celle de l'Arduino sont bien communes.

⚠️ CALIBRATION : les coefficients ci-dessous viennent du fit obtenu avec
   calibration_pos_ca_cg_labjack.py -- a mettre a jour si tu recalibres.
"""

from labjack import ljm
import numpy as np
import time

# -----------------------------------------------------------------------
# Calibration obtenue (pos_v = a * mm + b) -- A METTRE A JOUR SI RECALIBRE
# -----------------------------------------------------------------------
CA_A, CA_B = 0.2712, -7.5517
CG_A, CG_B = 0.2742, -4.6294

# -----------------------------------------------------------------------
# Canaux LabJack
# -----------------------------------------------------------------------
CANAL_POS_CA = "AIN0"
CANAL_POS_CG = "AIN1"
CANAL_SORTIE_CA = "FIO4"   # vers pin digitale Arduino (ex: D6)
CANAL_SORTIE_CG = "FIO5"   # vers pin digitale Arduino (ex: D7)

# -----------------------------------------------------------------------
# Plage de fonctionnement souhaitee (40-205 pF), avec marge de securite
# -----------------------------------------------------------------------
C_A0, C_A1 = 300.0, 5.217  # C(x) = C_A0 - C_A1*x
MM_HAUT = (C_A0 - 205.0) / C_A1  # ~18.21mm (205pF)
MM_BAS = (C_A0 - 40.0) / C_A1    # ~49.84mm (40pF)

MARGE_MM = 2.0  # marge de securite a l'interieur de la plage nominale

MM_MIN_SUR = MM_HAUT + MARGE_MM  # coupure si position < ceci (trop pres de 205pF)
MM_MAX_SUR = MM_BAS - MARGE_MM   # coupure si position > ceci (trop pres de 40pF)

N_SAMPLES = 1              # reduit fortement -- le test isole a montre des plantages a haute frequence d'appels
DELAI_BOUCLE_S = 0.2        # ~10 appels/s au lieu de ~60, pour se rapprocher du rythme stable observe

# Seuil de vitesse (mm/s) en dessous duquel on considere qu'il n'y a pas de
# tendance claire de retour vers la zone sure (evite le bruit de mesure).
SEUIL_VITESSE_MM_S = 0.3

# Limite absolue de secours (mm) -- coupure INCONDITIONNELLE au-dela de ces
# bornes, quelle que soit la tendance, pour proteger la mecanique en dernier
# recours (a ajuster selon la course reelle mesuree lors de la calibration).
MM_ABSOLU_MIN = 5.0
MM_ABSOLU_MAX = 60.0

# Duree minimale (s) pendant laquelle on maintient l'autorisation une fois
# qu'une tendance de retour est detectee, pour eviter les coupures trop
# rapides qui empechent tout deplacement cumule reel.
DUREE_MIN_AUTORISATION_S = 1.5

# Si le systeme est bloque hors plage ET immobile (aucune tendance connue
# car rien ne bouge), on autorise periodiquement une courte fenetre de
# test pour voir si un mouvement se produit -- sinon rien ne peut jamais
# demarrer depuis un arret complet hors zone.
PERIODE_TEST_S = 4.0     # intervalle entre deux fenetres de test
DUREE_FENETRE_TEST_S = 1.0  # duree de chaque fenetre de test


def calculer_etat_securite(mm, mm_prec, dt, mm_min_sur, mm_max_sur):
    """
    Retourne True (sur, LOW) ou False (coupure, HIGH).

    Logique :
      - Dans la plage sure -> toujours sur.
      - Hors plage absolue (tres loin) -> toujours coupure, sans exception.
      - Hors plage sure mais dans la plage absolue -> sur SEULEMENT si la
        position est en train de revenir vers la plage sure (tendance
        mesuree empiriquement, sans supposer de convention de signe
        commande/deplacement).
    """
    if mm < MM_ABSOLU_MIN or mm > MM_ABSOLU_MAX:
        return False  # hors plage absolue -- coupure inconditionnelle

    if mm_min_sur <= mm <= mm_max_sur:
        return True  # dans la plage sure -- toujours autorise

    if mm_prec is None or dt <= 0:
        return False  # pas encore d'historique -- prudence, on coupe

    vitesse = (mm - mm_prec) / dt

    if mm < mm_min_sur:
        # trop bas -- autorise seulement si la position remonte
        return vitesse > SEUIL_VITESSE_MM_S
    else:
        # trop haut -- autorise seulement si la position redescend
        return vitesse < -SEUIL_VITESSE_MM_S


def lire_moyenne(handle, canal, n=N_SAMPLES):
    valeurs = [ljm.eReadName(handle, canal) for _ in range(n)]
    return float(np.mean(valeurs))


def mm_depuis_v(v, a, b):
    return (v - b) / a


def main():
    print("=== SUPERVISEUR DE SECURITE POS_CA / POS_CG ===")
    print(f"Plage sure Ca/Cg : {MM_MIN_SUR:.2f} mm a {MM_MAX_SUR:.2f} mm")
    print(f"(plage nominale {MM_HAUT:.2f}-{MM_BAS:.2f} mm, marge {MARGE_MM} mm)")
    print("Connexion au LabJack...")

    handle = ljm.openS("T4", "ANY", "ANY")
    print("Connecte. Superviseur actif -- Ctrl+C pour arreter.")
    print()

    etat_precedent_ca = None
    etat_precedent_cg = None
    mm_ca_prec, mm_cg_prec = None, None
    t_prec = None
    t_autorisation_ca = None  # instant ou l'autorisation temporaire a demarre
    t_autorisation_cg = None
    t_debut = time.time()

    try:
        while True:
            t_maintenant = time.time()
            dt = (t_maintenant - t_prec) if t_prec is not None else 0.0

            v_ca = lire_moyenne(handle, CANAL_POS_CA)
            v_cg = lire_moyenne(handle, CANAL_POS_CG)

            mm_ca = mm_depuis_v(v_ca, CA_A, CA_B)
            mm_cg = mm_depuis_v(v_cg, CG_A, CG_B)

            dans_plage_ca = MM_MIN_SUR <= mm_ca <= MM_MAX_SUR
            dans_plage_cg = MM_MIN_SUR <= mm_cg <= MM_MAX_SUR

            tendance_ok_ca = calculer_etat_securite(mm_ca, mm_ca_prec, dt, MM_MIN_SUR, MM_MAX_SUR)
            tendance_ok_cg = calculer_etat_securite(mm_cg, mm_cg_prec, dt, MM_MIN_SUR, MM_MAX_SUR)

            # Fenetre de test periodique : autorise brievement meme sans
            # tendance connue, pour permettre au systeme de "tenter" un
            # mouvement depuis un arret complet hors zone.
            temps_ecoule = t_maintenant - t_debut
            phase_cycle = temps_ecoule % PERIODE_TEST_S
            en_fenetre_test = phase_cycle < DUREE_FENETRE_TEST_S

            if dans_plage_ca:
                ca_ok = True
                t_autorisation_ca = None
            else:
                if tendance_ok_ca:
                    t_autorisation_ca = t_maintenant
                autorise_par_tendance = (t_autorisation_ca is not None and
                                          (t_maintenant - t_autorisation_ca) < DUREE_MIN_AUTORISATION_S)
                ca_ok = autorise_par_tendance or en_fenetre_test

            if dans_plage_cg:
                cg_ok = True
                t_autorisation_cg = None
            else:
                if tendance_ok_cg:
                    t_autorisation_cg = t_maintenant
                autorise_par_tendance = (t_autorisation_cg is not None and
                                          (t_maintenant - t_autorisation_cg) < DUREE_MIN_AUTORISATION_S)
                cg_ok = autorise_par_tendance or en_fenetre_test

            # Coupure absolue : ecrase tout le reste, sans exception.
            if mm_ca < MM_ABSOLU_MIN or mm_ca > MM_ABSOLU_MAX:
                ca_ok = False
            if mm_cg < MM_ABSOLU_MIN or mm_cg > MM_ABSOLU_MAX:
                cg_ok = False

            mm_ca_prec, mm_cg_prec = mm_ca, mm_cg
            t_prec = t_maintenant

            # LOW (0) = sur, HIGH (1) = coupure
            ljm.eWriteName(handle, CANAL_SORTIE_CA, 0 if ca_ok else 1)
            ljm.eWriteName(handle, CANAL_SORTIE_CG, 0 if cg_ok else 1)

            if ca_ok != etat_precedent_ca:
                print(f"[CA] mm={mm_ca:.2f}  {'OK' if ca_ok else 'HORS PLAGE -- COUPURE'}")
                etat_precedent_ca = ca_ok
            if cg_ok != etat_precedent_cg:
                print(f"[CG] mm={mm_cg:.2f}  {'OK' if cg_ok else 'HORS PLAGE -- COUPURE'}")
                etat_precedent_cg = cg_ok

            # DEBUG temporaire : affiche systematiquement, pas juste sur changement
            print(f"  debug: mm_ca={mm_ca:.2f} ca_ok={ca_ok}  mm_cg={mm_cg:.2f} cg_ok={cg_ok}")

            time.sleep(DELAI_BOUCLE_S)

    except KeyboardInterrupt:
        print("\nArret demande.")
    finally:
        # Securite : force la coupure en quittant, au cas ou l'Arduino
        # continuerait a lire une derniere valeur avant deconnexion.
        try:
            ljm.eWriteName(handle, CANAL_SORTIE_CA, 1)
            ljm.eWriteName(handle, CANAL_SORTIE_CG, 1)
        except Exception:
            pass
        ljm.close(handle)
        print("Connexion LabJack fermee (sorties forcees en coupure).")


if __name__ == "__main__":
    main()