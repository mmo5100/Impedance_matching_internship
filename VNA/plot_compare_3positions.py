"""
plot_s12_compare_3positions.py
--------------------------------
One figure, 3 stacked subplots: each subplot compares |S12| (measured vs.
simulated/HFSS) at ONE capacitor position (e.g. 10p00, 25p00, 44p75 mm) --
reproducing the report's Figure 11 style, extended to 3 positions.

Usage
-----
    python plot_s12_compare_3positions.py \\
        --pair meas_capa_10p00.s2p capav6_stub_10p00.s2p --label 10p00 \\
        --pair meas_capa_25p00.s2p capav6_stub_25p00.s2p --label 25p00 \\
        --pair meas_capa_44p75.s2p capav6_stub_44p75.s2p --label 44p75

You must give exactly 3 --pair (each: measured_file simulated_file) and,
optionally, one --label per pair (used as the subplot title, e.g. the
position). If you omit --label, the measured file's name is used instead.

Optional:
    --target-freq-mhz F     vertical dashed reference line (default: 38)
    --out FILE              output image (default: s12_compare_3positions.png)
"""

import argparse
import sys

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


def basename(path):
    return path.split('/')[-1].split('\\')[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", nargs=2, action="append", metavar=("MEASURED", "SIMULATED"),
                     required=True,
                     help="Measured and simulated .s2p file for one position. "
                          "Give this flag exactly 3 times.")
    ap.add_argument("--label", action="append", default=[],
                     help="Subplot title for each --pair, in the same order "
                          "(e.g. '10p00'). Optional; defaults to the measured filename.")
    ap.add_argument("--target-freq-mhz", type=float, default=38.0,
                     help="Vertical reference line frequency (default: 38)")
    ap.add_argument("--out", default="s12_compare_3positions.png",
                     help="Output image filename")
    args = ap.parse_args()

    if len(args.pair) != 3:
        ap.error(f"Exactly 3 --pair arguments are required, got {len(args.pair)}.")

    labels = args.label if args.label else [basename(p[0]) for p in args.pair]
    if len(labels) != 3:
        ap.error("If you give --label, you must give exactly 3 (one per --pair).")

    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    for ax, (meas_path, sim_path), label in zip(axes, args.pair, labels):
        f_meas, S_meas, _ = parse_touchstone_2port(meas_path)
        f_sim, S_sim, _ = parse_touchstone_2port(sim_path)

        s12_meas_db = 20 * np.log10(np.abs(S_meas["S12"]) + 1e-15)
        s12_sim_db = 20 * np.log10(np.abs(S_sim["S12"]) + 1e-15)

        ax.plot(f_meas / 1e6, s12_meas_db, color="tab:blue",
                label=basename(meas_path))
        ax.plot(f_sim / 1e6, s12_sim_db, color="tab:orange",
                label=basename(sim_path))
        ax.axvline(args.target_freq_mhz, color='gray', linestyle='--', linewidth=0.8)
        ax.set_ylabel("|S12| [dB]")
        ax.set_title(f"Position: {label}", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    axes[-1].set_xlabel("Frequence [MHz]")
    fig.suptitle("Measured vs. simulated |S12| at 3 capacitor positions")
    fig.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Saved {args.out}")
    plt.show()


if __name__ == "__main__":
    main()