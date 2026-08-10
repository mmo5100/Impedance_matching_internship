"""
Computes EPS_A_OFFSET / EPS_G_OFFSET calibration constants from a CSV
capture taken while Ca/Cg are held at the TRUE matched position (found
manually with the VNA).

At the true match point, eps_a and eps_g should read exactly 0. In
practice they don't -- whatever the measured mean is at this point is a
calibration offset caused by residual detector/reference mismatches
(the same kind of small residual seen when cross-checking VA between the
LabJack and the Arduino). Subtracting this offset in the firmware makes
"eps = 0" coincide with the real physical match point, rather than
correcting the detectors themselves (which is fragile and hard to fully
nail down -- calibrating directly against the true match point is more
robust).

USAGE:
    python calibrer_offset_eps.py [chemin_csv]

Defaults to 'mesures_1_labjack_arduino.csv' in the current directory
(the file produced by acquisition_1_labjack_arduino.py), if no path is
given.
"""

import sys
import pandas as pd
import numpy as np

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "mesures_1_labjack_arduino.csv"


def main():
    df = pd.read_csv(CSV_PATH)

    if "eps_a" not in df.columns or "eps_g" not in df.columns:
        print(f"'{CSV_PATH}' does not contain 'eps_a'/'eps_g' columns -- wrong file?")
        sys.exit(1)

    n = len(df)
    eps_a_mean = df["eps_a"].mean()
    eps_a_std = df["eps_a"].std()
    eps_g_mean = df["eps_g"].mean()
    eps_g_std = df["eps_g"].std()

    print(f"Loaded {n} rows from '{CSV_PATH}'.\n")

    print("=== eps_a at the matched position ===")
    print(f"  mean = {eps_a_mean:.6f}")
    print(f"  std  = {eps_a_std:.6f}")
    if n > 1 and eps_a_std > 0 and abs(eps_a_mean) < 3 * eps_a_std:
        print("  (mean is within ~3 sigma of 0 -- offset may already be negligible)")

    print("\n=== eps_g at the matched position ===")
    print(f"  mean = {eps_g_mean:.6f}")
    print(f"  std  = {eps_g_std:.6f}")
    if n > 1 and eps_g_std > 0 and abs(eps_g_mean) < 3 * eps_g_std:
        print("  (mean is within ~3 sigma of 0 -- offset may already be negligible)")

    print("\n=== Paste into the Arduino sketch (constants) ===")
    print(f"const double EPS_A_OFFSET = {eps_a_mean:.6f};")
    print(f"const double EPS_G_OFFSET = {eps_g_mean:.6f};")
    print()
    print("Then apply as:")
    print("  eps_a_calibre = eps_a_brut - EPS_A_OFFSET;")
    print("  eps_g_calibre = eps_g_brut - EPS_G_OFFSET;")


if __name__ == "__main__":
    main()