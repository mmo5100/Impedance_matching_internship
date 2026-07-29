"""
Comparaison generique de deux fichiers .s2p (2 ports) 
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt


def parse_touchstone_2port(path):
    freq_unit_map = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    freq_scale = 1e9
    fmt = "MA"
    r0 = 50.0

    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('!'):
                continue
            if line.startswith('#'):
                toks = line[1:].split()
                for i, t in enumerate(toks):
                    tu = t.upper()
                    if tu in freq_unit_map:
                        freq_scale = freq_unit_map[tu]
                    if tu in ("RI", "MA", "DB"):
                        fmt = tu
                    if tu == "R" and i + 1 < len(toks):
                        r0 = float(toks[i + 1])
                continue
            vals = list(map(float, line.split()))
            rows.append(vals)

    rows = np.array(rows)
    freq = rows[:, 0] * freq_scale

    def to_complex(a, b):
        if fmt == "RI":
            return a + 1j * b
        elif fmt == "MA":
            return a * np.exp(1j * np.deg2rad(b))
        elif fmt == "DB":
            return (10 ** (a / 20)) * np.exp(1j * np.deg2rad(b))

    S = {
        "S11": to_complex(rows[:, 1], rows[:, 2]),
        "S21": to_complex(rows[:, 3], rows[:, 4]),
        "S12": to_complex(rows[:, 5], rows[:, 6]),
        "S22": to_complex(rows[:, 7], rows[:, 8]),
    }
    return freq, S, r0


def shunt_impedance(S21, S12, r0):
    S = (S21 + S12) / 2
    return r0 * S / (2 * (1 - S))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file1")
    ap.add_argument("file2")
    ap.add_argument("--target-freq-mhz", type=float, default=32.5)
    args = ap.parse_args()

    f1, S1, r0_1 = parse_touchstone_2port(args.file1)
    f2, S2, r0_2 = parse_touchstone_2port(args.file2)

    name1 = args.file1.split('/')[-1].split('\\')[-1]
    name2 = args.file2.split('/')[-1].split('\\')[-1]

    S12_1_db = 20 * np.log10(np.abs(S1["S12"]) + 1e-15)
    S12_2_db = 20 * np.log10(np.abs(S2["S12"]) + 1e-15)
    ph1 = np.angle(S1["S12"], deg=True)
    ph2 = np.angle(S2["S12"], deg=True)
    Z1 = shunt_impedance(S1["S21"], S1["S12"], r0_1)
    Z2 = shunt_impedance(S2["S21"], S2["S12"], r0_2)

    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

    axes[0].plot(f1 / 1e6, S12_1_db, label=name1)
    axes[0].plot(f2 / 1e6, S12_2_db, label=name2)
    axes[0].axvline(args.target_freq_mhz, color='gray', linestyle='--', linewidth=0.8)
    axes[0].set_ylabel("|S12| [dB]")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(f1 / 1e6, ph1, label=name1)
    axes[1].plot(f2 / 1e6, ph2, label=name2)
    axes[1].axvline(args.target_freq_mhz, color='gray', linestyle='--', linewidth=0.8)
    axes[1].set_ylabel("Phase S12 [deg]")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(f1 / 1e6, np.imag(Z1), label=name1)
    axes[2].plot(f2 / 1e6, np.imag(Z2), label=name2)
    axes[2].axvline(args.target_freq_mhz, color='gray', linestyle='--', linewidth=0.8)
    axes[2].set_ylabel("Im(Z) [Ohm]")
    axes[2].set_xlabel("Frequence [MHz]")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    fig.suptitle("Comparaison S12")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()