"""
Lecture de fichiers Touchstone (.sNp) exportes par un VNA.
"""

import numpy as np

UNITES_FREQ = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}


def lire_touchstone(chemin):
    """
    Lit un fichier .sNp (N quelconque) et renvoie un dict :

      {
        "freq_hz" : np.array, frequences en Hz (dans l'ordre du fichier),
        "S"       : np.array complexe, shape (n_freq, N, N) -- S[k] est la
                    matrice S complete a la frequence k (S[k][i,j] = S_(i+1)(j+1)),
        "z0"      : impedance de reference [Ohm],
        "n_ports" : N,
      }
    """
    ext = chemin.lower().rsplit(".", 1)[-1]
    if not (ext.startswith("s") and ext.endswith("p") and ext[1:-1].isdigit()):
        raise ValueError(f"Extension '.{ext}' non reconnue (attendu .sNp, ex: .s1p, .s2p, .s8p)")
    n_ports = int(ext[1:-1])

    unite_freq, fmt, z0 = "GHZ", "MA", 50.0   # defauts Touchstone
    option_lue = False
    tokens = []  # tous les nombres des lignes de donnees, mis a plat

    with open(chemin) as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("!"):
                continue
            if ligne.startswith("#"):
                option_lue = True
                mots = ligne[1:].split()
                i = 0
                while i < len(mots):
                    m = mots[i].upper()
                    if m in UNITES_FREQ:
                        unite_freq = m
                    elif m in ("MA", "DB", "RI"):
                        fmt = m
                    elif m == "R" and i + 1 < len(mots):
                        z0 = float(mots[i + 1])
                        i += 1
                    i += 1
                continue
            tokens.extend(float(x) for x in ligne.replace(",", ".").split())

    if not option_lue:
        print("  [!] Pas de ligne d'option '#' trouvee dans le fichier -- "
              "valeurs par defaut Touchstone utilisees (GHz, MA, R=50).")

    n_par_freq = 1 + 2 * n_ports ** 2
    if len(tokens) % n_par_freq != 0:
        raise ValueError(f"erreur")
    n_freq = len(tokens) // n_par_freq
    data = np.array(tokens).reshape(n_freq, n_par_freq)

    freq_hz = data[:, 0] * UNITES_FREQ[unite_freq]
    paires = data[:, 1:].reshape(n_freq, n_ports ** 2, 2)

    if fmt == "RI":
        s_lin = paires[:, :, 0] + 1j * paires[:, :, 1]
    elif fmt == "MA":
        s_lin = paires[:, :, 0] * np.exp(1j * np.deg2rad(paires[:, :, 1]))
    elif fmt == "DB":
        mag = 10 ** (paires[:, :, 0] / 20)
        s_lin = mag * np.exp(1j * np.deg2rad(paires[:, :, 1]))
    else:
        raise ValueError(f"erreur")

    if n_ports == 2:   # SEULE exception Touchstone : S11, S21, S12, S22
        S11, S21, S12, S22 = (s_lin[:, k] for k in range(4))
        S = np.empty((n_freq, 2, 2), dtype=complex)
        S[:, 0, 0], S[:, 1, 0], S[:, 0, 1], S[:, 1, 1] = S11, S21, S12, S22
    else:              # N=1 ou N>=3 : ordre "ligne de la matrice" S11,S12,...,SNN
        S = s_lin.reshape(n_freq, n_ports, n_ports)

    return {"freq_hz": freq_hz, "S": S, "z0": z0, "n_ports": n_ports}


def extraire_sous_reseau(resultat, ports):
    """
    Extrait, a partir d'un resultat de lire_touchstone() a N ports, le
    sous-reseau S correspondant uniquement aux ports demandes (numerotation
    Touchstone, A PARTIR DE 1 -- ex: ports=[1,2,3,4,5] pour les 5 premiers
    ports d'un VNA 8 ports).
    """
    idx = [p - 1 for p in ports]
    if min(idx) < 0 or max(idx) >= resultat["n_ports"]:
        raise ValueError(f"Ports non valides")
    S_sub = resultat["S"][:, idx, :][:, :, idx]
    return {"freq_hz": resultat["freq_hz"], "S": S_sub, "z0": resultat["z0"], "n_ports": len(ports)}


if __name__ == "__main__":
    import sys
    import matplotlib.pyplot as plt

    # === Fichier Touchstone ===
    CHEMIN_FICHIER = "Autotuning_Measurement_Line_G_L_VCG_VCL_DCFwd.s5p"

    # (On peut aussi lancer "python lire_touchstone.py votre_fichier.sNp"
    chemin = sys.argv[1] if len(sys.argv) > 1 else CHEMIN_FICHIER
    res = lire_touchstone(chemin)
    f_mhz = res["freq_hz"] / 1e6

    print(f"Fichier        : {chemin}")
    print(f"Nb de ports    : {res['n_ports']}")
    print(f"Z0 reference   : {res['z0']:.1f} Ohm")
    print(f"Nb de points   : {len(f_mhz)}")
    print(f"Plage freq     : {f_mhz.min():.4f} - {f_mhz.max():.4f} MHz")

    N = res["n_ports"]

    
    
    
    PARAMS_A_AFFICHER = None
    if PARAMS_A_AFFICHER is None:
        if N == 5:
            PARAMS_A_AFFICHER = [(1, 1), (2, 2), (2, 1), (4, 1), (3, 1), (5, 1)]
        else:
            PARAMS_A_AFFICHER = [(i, i) for i in range(1, N + 1)]
            if N >= 2:
                PARAMS_A_AFFICHER.append((2, 1))
 
    # Tableau recapitulatif de TOUS les parametres S a la 1ere frequence
    print(f"\nTous les parametres S a f={f_mhz[0]:.3f} MHz (|S| lineaire, angle deg) :")
    for i in range(N):
        for j in range(N):
            s = res["S"][0, i, j]
            print(f"  S{i+1}{j+1} = {abs(s):.4f} @ {np.angle(s, deg=True):6.1f} deg")
 
   
 
    fig, ax = plt.subplots(figsize=(8, 5))
    for (i, j) in PARAMS_A_AFFICHER:
        Sij = res["S"][:, i - 1, j - 1]
        ax.plot(f_mhz, 20 * np.log10(np.abs(Sij)), label=f"|S{i}{j}| [dB]")
    ax.set_xlabel("Frequence [MHz]")
    ax.set_ylabel("Amplitude [dB]")
    ax.set_title(chemin)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()