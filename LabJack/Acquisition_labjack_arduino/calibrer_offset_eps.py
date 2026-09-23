"""
Computes the calibration constants needed by neutral_point.ino from a grid
of CSV captures produced by acquisition_1_labjack_arduino.py:

  1) EPS_A_OFFSET / EPS_G_OFFSET, from the file taken at the TRUE matched
     position (found manually with the VNA). At that position eps_a/eps_g
     should read exactly 0; in practice they don't, due to residual
     detector/reference mismatches. Subtracting this offset in the
     firmware makes "eps_calibre = 0" coincide with the real physical
     match, rather than an arbitrary raw-signal zero.

  2) Local sensitivities d(eps_a)/d(Ca), d(eps_g)/d(Ca), d(eps_a)/d(Cg),
     d(eps_g)/d(Cg), computed from the two grid points closest to the
     match on each sweep axis (Ca swept with Cg held near match, and vice
     versa). These are used to:
       - confirm SWAP_VA_VG (Ca should dominate eps_a, Cg should dominate
         eps_g -- if it's the other way around, flip the flag),
       - confirm the sign of the K_V gain in the control law (a negative
         sensitivity d(eps)/d(position) means a POSITIVE K_V is the
         correct convergent direction, and vice versa).

USAGE:
    python calibrer_offset_eps.py [dossier]

Expects filenames of the form:
    ..._CA_<xx>p<xx>_CG_<yy>p<yy>.csv   (grid points, position in mm)
    ..._match...CA_<xx>p<xx>_CG_<yy>p<yy>.csv   (the true match point --
        filename must contain 'match', case-insensitive)

Defaults to the current directory if no folder is given. Also works with
just a single match file present (offsets only, no sensitivities).
"""

import sys
import os
import re
import glob
import pandas as pd
import numpy as np

DOSSIER = sys.argv[1] if len(sys.argv) > 1 else "."

PATTERN = re.compile(r"CA_?(\d+p\d+)_CG_?(\d+p\d+)", re.IGNORECASE)


def parse_positions(filename):
    m = PATTERN.search(filename)
    if not m:
        return None
    ca_mm = float(m.group(1).replace("p", "."))
    cg_mm = float(m.group(2).replace("p", "."))
    return ca_mm, cg_mm


def load_summary(path):
    df = pd.read_csv(path)
    if "eps_a" not in df.columns or "eps_g" not in df.columns:
        return None
    return {
        "n": len(df),
        "position_Ca_V": df["position_Ca"].mean(),
        "position_Cg_V": df["position_Cg"].mean(),
        "eps_a_mean": df["eps_a"].mean(),
        "eps_a_std": df["eps_a"].std(),
        "eps_g_mean": df["eps_g"].mean(),
        "eps_g_std": df["eps_g"].std(),
    }


def main():
    files = sorted(glob.glob(os.path.join(DOSSIER, "*.csv")))
    rows = []
    for f in files:
        name = os.path.basename(f)
        pos = parse_positions(name)
        if pos is None:
            continue
        summ = load_summary(f)
        if summ is None:
            continue
        row = {"file": name, "Ca_mm": pos[0], "Cg_mm": pos[1],
               "is_match": "match" in name.lower()}
        row.update(summ)
        rows.append(row)

    if not rows:
        print(f"No usable CSV files found in '{DOSSIER}' "
              f"(expected filenames containing 'CA_<x>p<x>_CG_<y>p<y>').")
        sys.exit(1)

    grid = pd.DataFrame(rows)
    print(f"Loaded {len(grid)} file(s) from '{DOSSIER}':\n")
    print(grid[["file", "Ca_mm", "Cg_mm", "n", "eps_a_mean", "eps_g_mean"]]
          .to_string(index=False))

    match_rows = grid[grid["is_match"]]
    if match_rows.empty:
        print("\nNo file with 'match' in its name found -- cannot compute "
              "EPS_A_OFFSET/EPS_G_OFFSET. Provide a match-point capture.")
        sys.exit(1)
    match = match_rows.iloc[0]

    print(f"\n=== Match point ({match['file']}) ===")
    print(f"  Ca={match['Ca_mm']}mm  Cg={match['Cg_mm']}mm  n={match['n']}")
    print(f"  eps_a: mean={match['eps_a_mean']:.6f}  std={match['eps_a_std']:.6f}")
    print(f"  eps_g: mean={match['eps_g_mean']:.6f}  std={match['eps_g_std']:.6f}")

    eps_a_offset = match["eps_a_mean"]
    eps_g_offset = match["eps_g_mean"]

    # --- Sensitivities: nearest non-match points on each sweep axis ---
    ca_axis = grid[(~grid["is_match"]) & np.isclose(grid["Cg_mm"], match["Cg_mm"], atol=0.5)]
    cg_axis = grid[(~grid["is_match"]) & np.isclose(grid["Ca_mm"], match["Ca_mm"], atol=0.5)]

    d_eps_a_dCa = d_eps_g_dCa = d_eps_a_dCg = d_eps_g_dCg = None

    if len(ca_axis) >= 2:
        below = ca_axis[ca_axis["Ca_mm"] < match["Ca_mm"]].sort_values("Ca_mm")
        above = ca_axis[ca_axis["Ca_mm"] > match["Ca_mm"]].sort_values("Ca_mm")
        if not below.empty and not above.empty:
            p1, p2 = below.iloc[-1], above.iloc[0]
            dCa = p2["Ca_mm"] - p1["Ca_mm"]
            d_eps_a_dCa = (p2["eps_a_mean"] - p1["eps_a_mean"]) / dCa
            d_eps_g_dCa = (p2["eps_g_mean"] - p1["eps_g_mean"]) / dCa
            print(f"\n=== Ca sweep, points used: {p1['Ca_mm']}mm / {p2['Ca_mm']}mm ===")
            print(f"  d(eps_a)/d(Ca) = {d_eps_a_dCa:.5f} /mm")
            print(f"  d(eps_g)/d(Ca) = {d_eps_g_dCa:.5f} /mm")

    if len(cg_axis) >= 2:
        below = cg_axis[cg_axis["Cg_mm"] < match["Cg_mm"]].sort_values("Cg_mm")
        above = cg_axis[cg_axis["Cg_mm"] > match["Cg_mm"]].sort_values("Cg_mm")
        if not below.empty and not above.empty:
            p1, p2 = below.iloc[-1], above.iloc[0]
            dCg = p2["Cg_mm"] - p1["Cg_mm"]
            d_eps_a_dCg = (p2["eps_a_mean"] - p1["eps_a_mean"]) / dCg
            d_eps_g_dCg = (p2["eps_g_mean"] - p1["eps_g_mean"]) / dCg
            print(f"\n=== Cg sweep, points used: {p1['Cg_mm']}mm / {p2['Cg_mm']}mm ===")
            print(f"  d(eps_a)/d(Cg) = {d_eps_a_dCg:.5f} /mm")
            print(f"  d(eps_g)/d(Cg) = {d_eps_g_dCg:.5f} /mm")

    if None not in (d_eps_a_dCa, d_eps_g_dCa, d_eps_a_dCg, d_eps_g_dCg):
        print("\n=== SWAP_VA_VG check ===")
        ratio_a = abs(d_eps_a_dCa) / abs(d_eps_a_dCg) if d_eps_a_dCg else float("inf")
        ratio_g = abs(d_eps_g_dCg) / abs(d_eps_g_dCa) if d_eps_g_dCa else float("inf")
        print(f"  |d(eps_a)/d(Ca)| / |d(eps_a)/d(Cg)| = {ratio_a:.2f}  "
              f"(>1 means Ca dominates eps_a, as expected if SWAP_VA_VG=false)")
        print(f"  |d(eps_g)/d(Cg)| / |d(eps_g)/d(Ca)| = {ratio_g:.2f}  "
              f"(>1 means Cg dominates eps_g, as expected if SWAP_VA_VG=false)")
        swap_recommended = not (ratio_a > 1 and ratio_g > 1)
        print(f"  -> SWAP_VA_VG should be: {'true' if swap_recommended else 'false'}")

        print("\n=== K_V sign check ===")
        sign_a = "+K_V (no negation)" if d_eps_a_dCa < 0 else "-K_V (negate)"
        sign_g = "+K_V (no negation)" if d_eps_g_dCg < 0 else "-K_V (negate)"
        print(f"  d(eps_a)/d(Ca) = {d_eps_a_dCa:.5f}  -> correct sign for Ca channel: {sign_a}")
        print(f"  d(eps_g)/d(Cg) = {d_eps_g_dCg:.5f}  -> correct sign for Cg channel: {sign_g}")

    print("\n=== Paste into neutral_point.ino ===")
    print(f"const double EPS_A_OFFSET = {eps_a_offset:.6f};")
    print(f"const double EPS_G_OFFSET = {eps_g_offset:.6f};")
    print()
    print("Applied as:")
    print("  double eps_a = eps_a_brut - EPS_A_OFFSET;")
    print("  double eps_g = eps_g_brut - EPS_G_OFFSET;")


if __name__ == "__main__":
    main()