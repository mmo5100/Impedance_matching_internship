"""
Log detector calibration for VA / VG / V+ 
=============================================================

Goal:
    From several measurement cycles ("=== Moyenne sur les mesures
    prises ===", copy-pasted as-is from the Arduino serial monitor),
    extract (VA_moy, VG_moy, Vplus_moy), fit a straight line
    V(P_dBm) = gain*P + offset for each channel over a power range
    considered linear, then compute the (gain_corr, offset_corr) 
    factors needed to bring VA and V+ onto the scale of VG 
    (reference channel).

"""

import re
import numpy as np

# ---------------------------------------------------------------------
# 1) Raw data (paste "=== Moyenne sur les mesures prises ===" blocks here)
# ---------------------------------------------------------------------
RAW_LOG = r"""
=== Moyenne sur les mesures prises ===
Puissance : 22 dBm
Nombre d'echantillons: 100
VA_moy    = 2.2982 V
VG_moy    = 2.5433 V
Vplus_moy = 2.8901 V
eps_a_moy = -0.1415   eps_g_moy = 0.3297

=== Moyenne sur les mesures prises ===
Puissance : 16 dBm
Nombre d'echantillons: 100
VA_moy    = 2.2383 V
VG_moy    = 2.2518 V
Vplus_moy = 2.6338 V
eps_a_moy = 0.0556   eps_g_moy = 0.2183

=== Moyenne sur les mesures prises ===
Puissance : 10 dBm
Nombre d'echantillons: 100
VA_moy    = 1.6064 V
VG_moy    = 1.6657 V
Vplus_moy = 2.1268 V
eps_a_moy = 0.0317   eps_g_moy = 0.2877

=== Moyenne sur les mesures prises ===
Puissance : 0.8dBm
Nombre d'echantillons: 100
VA_moy    = 0.6234 V
VG_moy    = 0.6746 V
Vplus_moy = 1.3028 V
eps_a_moy = 0.0675   eps_g_moy = 0.3753

=== Moyenne sur les mesures prises ===
Puissance : -5dBm
Nombre d'echantillons: 100
VA_moy    = 0.2074 V
VG_moy    = 0.2012 V
Vplus_moy = 0.8629 V
eps_a_moy = 0.1208   eps_g_moy = 0.3613

=== Moyenne sur les mesures prises ===
Puissance = -9dBm
Nombre d'echantillons: 100
VA_moy    = 0.0565 V
VG_moy    = 0.0113 V
Vplus_moy = 0.7098 V
eps_a_moy = 0.1595   eps_g_moy = 0.3596
"""

# ---------------------------------------------------------------------
# 2) Power range considered linear (adjust as needed)
#    -> here everything above 16 dBm is excluded (VA saturates beyond that)
# ---------------------------------------------------------------------
P_MIN_DBM = -9.0
P_MAX_DBM = 16.0

REFERENCE_CHANNEL = "VG"   # channel the others are aligned onto

# ---------------------------------------------------------------------
# 3) Log parsing
# ---------------------------------------------------------------------
def parse_log(raw_log):
    """Extract a list of dicts {P, VA, VG, V+} from the raw text."""
    blocks = raw_log.split("=== Moyenne sur les mesures prises ===")
    records = []
    for block in blocks:
        if not block.strip():
            continue
        p_match = re.search(r"Puissance\s*[:=]\s*([-+]?\d*\.?\d+)\s*dBm", block)
        va_match = re.search(r"VA_moy\s*=\s*([-+]?\d*\.?\d+)", block)
        vg_match = re.search(r"VG_moy\s*=\s*([-+]?\d*\.?\d+)", block)
        vp_match = re.search(r"Vplus_moy\s*=\s*([-+]?\d*\.?\d+)", block)
        if p_match and va_match and vg_match and vp_match:
            records.append({
                "P": float(p_match.group(1)),
                "VA": float(va_match.group(1)),
                "VG": float(vg_match.group(1)),
                "V+": float(vp_match.group(1)),
            })
    return records


def dedupe_records(records):
    """Remove cycles that are strictly identical to one already seen
    (e.g. logging error, or power not actually changed between two runs)."""
    seen = set()
    unique = []
    for r in records:
        key = (r["VA"], r["VG"], r["V+"])
        if key in seen:
            print(f"  [!] Cycle skipped (exact duplicate): P={r['P']} dBm -> "
                  f"VA={r['VA']}, VG={r['VG']}, V+={r['V+']}")
            continue
        seen.add(key)
        unique.append(r)
    return unique


# ---------------------------------------------------------------------
# 4) Linear fit + correction factors
# ---------------------------------------------------------------------
def fit_channels(records, p_min, p_max):
    kept = [r for r in records if p_min <= r["P"] <= p_max]
    dropped = [r for r in records if not (p_min <= r["P"] <= p_max)]

    if dropped:
        print("Points excluded from the fit (outside the linear range "
              f"[{p_min}, {p_max}] dBm):")
        for r in sorted(dropped, key=lambda x: x["P"]):
            print(f"  P={r['P']:6.2f} dBm  VA={r['VA']:.4f}  "
                  f"VG={r['VG']:.4f}  V+={r['V+']:.4f}")
        print()

    kept = sorted(kept, key=lambda r: r["P"])
    if len(kept) < 2:
        raise ValueError("Not enough points in the linear range to fit "
                          "(at least 2 are required).")

    P = np.array([r["P"] for r in kept])
    fits = {}
    print(f"Points used for the fit ({len(kept)}):")
    for r in kept:
        print(f"  P={r['P']:6.2f} dBm  VA={r['VA']:.4f}  "
              f"VG={r['VG']:.4f}  V+={r['V+']:.4f}")
    print()

    for ch in ["VA", "VG", "V+"]:
        V = np.array([r[ch] for r in kept])
        gain, offset = np.polyfit(P, V, 1)
        resid = V - (gain * P + offset)
        fits[ch] = {"gain": gain, "offset": offset, "residuals": resid}
    return fits


def correction_factors(fits, reference):
    """Compute (gain_corr, offset_corr) such that:
        V_corr = gain_corr * V_raw + offset_corr
    brings the channel onto the scale of the reference channel."""
    m_ref, b_ref = fits[reference]["gain"], fits[reference]["offset"]
    corrections = {}
    for ch, f in fits.items():
        if ch == reference:
            corrections[ch] = {"gain_corr": 1.0, "offset_corr": 0.0}
            continue
        m, b = f["gain"], f["offset"]
        gain_corr = m_ref / m
        offset_corr = b_ref - gain_corr * b
        corrections[ch] = {"gain_corr": gain_corr, "offset_corr": offset_corr}
    return corrections


# ---------------------------------------------------------------------
# 5) Main
# ---------------------------------------------------------------------
def main():
    records = parse_log(RAW_LOG)
    records = dedupe_records(records)
    print(f"\n{len(records)} measurement cycles found in the log.\n")

    fits = fit_channels(records, P_MIN_DBM, P_MAX_DBM)

    print("=== Linear fit results V(P_dBm) = gain*P + offset ===")
    for ch, f in fits.items():
        print(f"{ch:>3s} : gain = {f['gain']:.5f} V/dB   "
              f"offset = {f['offset']:.5f} V   "
              f"max residual = {np.max(np.abs(f['residuals'])):.4f} V")
    print()

    corr = correction_factors(fits, REFERENCE_CHANNEL)
    print(f"=== Correction factors (reference = {REFERENCE_CHANNEL}) ===")
    print("    V_corr = gain_corr * V_raw + offset_corr\n")
    for ch, c in corr.items():
        if ch == REFERENCE_CHANNEL:
            continue
        print(f"{ch:>3s} : gain_corr = {c['gain_corr']:.5f}   "
              f"offset_corr = {c['offset_corr']:.5f}")

    print("\n=== Paste into the Arduino sketch (constants) ===")
    for ch, c in corr.items():
        name = ch.replace("+", "PLUS")
        print(f"const float {name}_GAIN_CORR   = {c['gain_corr']:.5f}f;")
        print(f"const float {name}_OFFSET_CORR = {c['offset_corr']:.5f}f;")


if __name__ == "__main__":
    main()