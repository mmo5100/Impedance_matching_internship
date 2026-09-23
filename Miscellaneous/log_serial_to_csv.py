"""
log_serial_to_csv.py

Lit la sortie serie du sketch mesure_noise_floor.ino (format CSV :
t_ms,eps_a,eps_g) et l'enregistre dans un fichier .csv, puis calcule
moyenne/ecart-type et detecte les glitches (echantillons aberrants).

Installation :
    pip install pyserial

Usage :
    python log_serial_to_csv.py COM5 --duree 20 --out mesures.csv
    (remplacer COM5 par le port reel -- sur Linux/Mac : /dev/ttyACM0 ou /dev/ttyUSB0)
"""

import argparse
import csv
import sys
import time

import serial


def lire_serie(port, baudrate, duree_s, out_path):
    print(f"Ouverture de {port} @ {baudrate} bauds...")
    ser = serial.Serial(port, baudrate, timeout=1)
    time.sleep(2)  # laisser le temps a l'Arduino de rebooter apres ouverture du port

    lignes_valides = []
    t_fin = time.time() + duree_s if duree_s else None

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_ms", "eps_a_brut", "eps_g_brut", "eps_a_filtre", "eps_g_filtre"])

        print(f"Enregistrement en cours -> {out_path}")
        if duree_s:
            print(f"Duree : {duree_s}s (Ctrl+C pour arreter avant)")
        else:
            print("Duree illimitee -- Ctrl+C pour arreter")

        try:
            while t_fin is None or time.time() < t_fin:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                parts = raw.split(",")
                # on ignore les lignes d'entete/info qui ne sont pas du CSV numerique
                if len(parts) != 5:
                    continue
                try:
                    t_ms = int(parts[0])
                    vals = [float(p) for p in parts[1:]]
                except ValueError:
                    continue
                writer.writerow([t_ms] + vals)
                lignes_valides.append((t_ms, *vals))
        except KeyboardInterrupt:
            print("\nArret demande par l'utilisateur.")

    ser.close()
    print(f"{len(lignes_valides)} echantillons enregistres dans {out_path}")
    return lignes_valides


def stats_classiques(vals):
    n = len(vals)
    moy = sum(vals) / n
    var = sum((v - moy) ** 2 for v in vals) / n
    return moy, var ** 0.5


def mediane(vals):
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def mad(vals, med):
    # Median Absolute Deviation, mis a l'echelle pour approximer sigma
    # sous hypothese gaussienne (facteur 1.4826). Beaucoup plus robuste
    # aux outliers que l'ecart-type classique, car la mediane elle-meme
    # n'est quasi pas affectee par quelques valeurs aberrantes.
    ecarts = [abs(v - med) for v in vals]
    return 1.4826 * mediane(ecarts)


def analyser(lignes, seuil_glitch_mad=8.0):
    if not lignes:
        print("Aucune donnee a analyser.")
        return

    eps_a_brut = [l[1] for l in lignes]
    eps_g_brut = [l[2] for l in lignes]
    eps_a_filtre = [l[3] for l in lignes]
    eps_g_filtre = [l[4] for l in lignes]

    print("\n=== SIGNAL BRUT (avant filtre median-3) ===")
    moy_ab, sigma_ab = stats_classiques(eps_a_brut)
    moy_gb, sigma_gb = stats_classiques(eps_g_brut)
    print(f"eps_a_brut : moyenne={moy_ab:.5f}  sigma={sigma_ab:.5f}")
    print(f"eps_g_brut : moyenne={moy_gb:.5f}  sigma={sigma_gb:.5f}")

    med_ab, med_gb = mediane(eps_a_brut), mediane(eps_g_brut)
    mad_ab, mad_gb = mad(eps_a_brut, med_ab), mad(eps_g_brut, med_gb)
    glitches_brut = 0
    for a, g in zip(eps_a_brut, eps_g_brut):
        if (mad_ab > 0 and abs(a - med_ab) > seuil_glitch_mad * mad_ab) or \
           (mad_gb > 0 and abs(g - med_gb) > seuil_glitch_mad * mad_gb):
            glitches_brut += 1
    print(f"Glitches detectes (brut, seuil={seuil_glitch_mad}xMAD) : {glitches_brut}/{len(lignes)} ({100*glitches_brut/len(lignes):.2f}%)")

    print("\n=== SIGNAL FILTRE (median-3, applique dans le firmware) ===")
    moy_af, sigma_af = stats_classiques(eps_a_filtre)
    moy_gf, sigma_gf = stats_classiques(eps_g_filtre)
    print(f"eps_a_filtre : moyenne={moy_af:.5f}  sigma={sigma_af:.5f}")
    print(f"eps_g_filtre : moyenne={moy_gf:.5f}  sigma={sigma_gf:.5f}")

    med_af, med_gf = mediane(eps_a_filtre), mediane(eps_g_filtre)
    mad_af, mad_gf = mad(eps_a_filtre, med_af), mad(eps_g_filtre, med_gf)
    glitches_filtre = 0
    for a, g in zip(eps_a_filtre, eps_g_filtre):
        if (mad_af > 0 and abs(a - med_af) > seuil_glitch_mad * mad_af) or \
           (mad_gf > 0 and abs(g - med_gf) > seuil_glitch_mad * mad_gf):
            glitches_filtre += 1
    print(f"Glitches detectes (filtre, seuil={seuil_glitch_mad}xMAD) : {glitches_filtre}/{len(lignes)} ({100*glitches_filtre/len(lignes):.2f}%)")

    print("\n=== Suggestion EPS_DEADBAND (3-5 sigma SUR SIGNAL FILTRE, pire des deux axes) ===")
    sigma_max_filtre = max(sigma_af, sigma_gf)
    print(f"3 sigma : {3 * sigma_max_filtre:.4f}")
    print(f"5 sigma : {5 * sigma_max_filtre:.4f}")

    if glitches_filtre > 0:
        print(f"\n⚠️  {glitches_filtre} glitch(es) subsistent malgre le filtre median-3.")
        print("   Si ce nombre reste significatif (>quelques pourcents), envisager une")
        print("   fenetre de filtre plus large (median-5) ou investiguer la cause externe.")
    else:
        print("\n✅ Le filtre median-3 elimine tous les glitches detectes sur cette session.")


def main():
    parser = argparse.ArgumentParser(description="Log serie CSV depuis mesure_noise_floor.ino")
    parser.add_argument("port", help="Port serie, ex: COM5 ou /dev/ttyACM0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--duree", type=float, default=20.0, help="Duree d'enregistrement en secondes (0 = illimite)")
    parser.add_argument("--out", default="mesures.csv", help="Fichier CSV de sortie")
    args = parser.parse_args()

    lignes = lire_serie(args.port, args.baudrate, args.duree, args.out)
    analyser(lignes)


if __name__ == "__main__":
    main()