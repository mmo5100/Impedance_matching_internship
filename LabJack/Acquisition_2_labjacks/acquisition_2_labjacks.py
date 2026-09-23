"""
Simultaneous acquisition from TWO LabJack T4 units, in parallel, to read
VA, VG, V+, position_Ca, position_Cg -- ALL genuinely bipolar (+-10V), no
clipping of negative signals like on the Arduino's unipolar ADC.

Each T4 has 4 dedicated high-voltage analog inputs (AIN0-AIN3, +-10V,
12-bit). Channel plan used here (adjust SIGNAL_MAP below if wired
differently):

  LabJack #1 (SERIAL_LJ1) : AIN0=VA        AIN1=VG       AIN2=Vplus  AIN3=spare
  LabJack #2 (SERIAL_LJ2) : AIN0=position_Ca  AIN1=position_Cg  AIN2=Vplus (DUPLICATE, cross-check)  AIN3=spare

V+ is wired to BOTH LabJacks (LJ1.AIN2 and LJ2.AIN2) so the two devices'
readings can be compared directly -- if they ever disagree by more than a
small tolerance, it flags a synchronization or calibration issue between
the two units rather than a real signal change.

The Arduino keeps driving the DAC (Ca/Cg position commands via
neutral_point.ino) but is no longer used for acquisition.

REQUIREMENTS:
  pip install labjack-ljm
  LJM driver installed (already used elsewhere in this repo).

USAGE:
  python acquisition_2_labjacks.py
"""

import time
import csv
import math
from labjack import ljm

# ============================================================================
# PARAMETERS TO ADJUST
# ============================================================================
SERIAL_LJ1 = "ANY"   # <-- set the real serial number of LabJack #1, e.g. "470012345"
SERIAL_LJ2 = "ANY"   # <-- set the real serial number of LabJack #2

PERIOD_S = 0.05       # sampling period (s) -- 20 Hz here, adjust as needed
CSV_PATH = "mesures_2_labjacks.csv"
CROSS_CHECK_TOL_V = 0.05  # print a warning if the two V+ readings differ by more than this

# RF parameters (same as the Arduino error-signal computation)
FREQ_HZ = 28e6
C_LIGHT = 299792458.0
L1_M = 1.35
L2_M = 1.85
BETA = 2.0 * math.pi * FREQ_HZ / C_LIGHT
SIN_2BL1 = math.sin(2.0 * BETA * L1_M)
COS_2BL1 = math.cos(2.0 * BETA * L1_M)
SIN_2BL2 = math.sin(2.0 * BETA * L2_M)
COS_2BL2 = math.cos(2.0 * BETA * L2_M)
SWAP_VA_VG = False

CSV_HEADER = ["timestamp_pc", "VA", "VG", "Vplus", "eps_a", "eps_g",
              "position_Ca", "position_Cg", "Vplus_LJ2_check", "diff_Vplus"]


def compute_eps(VA, VG, Vplus):
    VA_minus_Vp = VA - Vplus
    VG_minus_Vp = VG - Vplus
    sVA = VG_minus_Vp if SWAP_VA_VG else VA_minus_Vp
    sVG = VA_minus_Vp if SWAP_VA_VG else VG_minus_Vp
    eps_a = sVA * SIN_2BL2 - sVG * SIN_2BL1
    eps_g = sVA * COS_2BL2 - sVG * COS_2BL1
    return eps_a, eps_g


def main():
    print(f"Opening LabJack #1 (serial={SERIAL_LJ1})...")
    h1 = ljm.openS("T4", "ANY", SERIAL_LJ1)
    print(f"Opening LabJack #2 (serial={SERIAL_LJ2})...")
    h2 = ljm.openS("T4", "ANY", SERIAL_LJ2)

    info1 = ljm.getHandleInfo(h1)
    info2 = ljm.getHandleInfo(h2)
    print(f"LabJack #1 connected, serial={info1[2]}")
    print(f"LabJack #2 connected, serial={info2[2]}")
    print(f"Logging to '{CSV_PATH}'. Press Ctrl+C to stop.\n")

    names_lj1 = ["AIN0", "AIN1", "AIN2"]  # VA, VG, Vplus
    names_lj2 = ["AIN0", "AIN1", "AIN2"]  # position_Ca, position_Cg, Vplus (duplicate)

    try:
        with open(CSV_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(CSV_HEADER)

            while True:
                t0 = time.time()

                VA, VG, Vplus = ljm.eReadNames(h1, len(names_lj1), names_lj1)
                position_Ca, position_Cg, Vplus_lj2 = ljm.eReadNames(h2, len(names_lj2), names_lj2)

                eps_a, eps_g = compute_eps(VA, VG, Vplus)
                diff_vplus = Vplus - Vplus_lj2

                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                row = [ts, VA, VG, Vplus, eps_a, eps_g, position_Ca, position_Cg,
                       Vplus_lj2, diff_vplus]
                w.writerow(row)
                f.flush()

                warn = "  *** CROSS-CHECK MISMATCH ***" if abs(diff_vplus) > CROSS_CHECK_TOL_V else ""
                print(f"VA={VA:8.4f} VG={VG:8.4f} V+={Vplus:8.4f} "
                      f"eps_a={eps_a:8.4f} eps_g={eps_g:8.4f} "
                      f"pos_Ca={position_Ca:8.4f} pos_Cg={position_Cg:8.4f} "
                      f"V+_LJ2={Vplus_lj2:8.4f} diff={diff_vplus:+.4f}{warn}")

                elapsed = time.time() - t0
                sleep_time = PERIOD_S - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ljm.close(h1)
        ljm.close(h2)


if __name__ == "__main__":
    main()