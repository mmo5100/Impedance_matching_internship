"""
Combined acquisition using ONLY 1 LabJack T4 + the Arduino (2 cables
total).

  LabJack (bipolar +-10V, handles negative signals -- all 4 channels used) :
      AIN0=VA (duplicate, cross-check)   AIN1=VG   AIN2=position_Ca   AIN3=position_Cg
  Arduino (arduino_stream.ino, unipolar 0-5V ADC) :
      A0=VA (duplicate, cross-check)   A2=V+

Both positions live on the LabJack since either can be negative. V+ has
no spare LabJack channel and stays solely on the Arduino (confirmed
positive). VA is measured by BOTH devices, used to catch
synchronization/timing issues between the two independently-clocked
sources, not just calibration drift:
  1) diff_va        = VA_LJ - VA_arduino, logged every row.
  2) arduino_lag_s   = how old the Arduino sample being used actually is
                        relative to the LabJack read, in seconds.
Large values of either should be treated as "this row's Arduino-sourced
fields (V+ here) may not represent the same instant as the LabJack fields".
"""

import sys
import time
import csv
import math
import serial
from labjack import ljm
 
# ============================================================================
# PARAMETERS TO ADJUST
# ============================================================================
SERIAL_LJ = "ANY"    # <-- set the real serial number of the LabJack, e.g. "470012345"
ARDUINO_PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
ARDUINO_BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
 
PERIOD_S = 0.05       # sampling period (s) -- 20 Hz
N_SAMPLES = 200        # stop automatically after this many samples (None = run forever, Ctrl+C to stop)
CSV_PATH = "mesures_1_labjack_arduino.csv"
CROSS_CHECK_TOL_V = 0.05  # warn if a duplicated signal differs by more than this
LAG_WARN_S = 0.2          # warn if the Arduino sample is older than this
 
# RF parameters (same as the Arduino error-signal computation)
FREQ_HZ = 38e6
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
              "position_Ca", "position_Cg",
              "VA_arduino", "diff_va", "arduino_lag_s"]
 
 
def compute_eps(VA, VG, Vplus):
    VA_minus_Vp = VA - Vplus
    VG_minus_Vp = VG - Vplus
    sVA = VG_minus_Vp if SWAP_VA_VG else VA_minus_Vp
    sVG = VA_minus_Vp if SWAP_VA_VG else VG_minus_Vp
    eps_a = sVA * SIN_2BL2 - sVG * SIN_2BL1
    eps_g = sVA * COS_2BL2 - sVG * COS_2BL1
    return eps_a, eps_g
 
 
def read_latest_from_arduino(ser, last_vplus, last_va, last_update_t):
    """Drains the serial buffer and returns the most recent V+ and VA
    values found, plus the wall-clock time they were received (so the
    caller can compute how 'stale' they are)."""
    vplus, va, t_update = last_vplus, last_va, last_update_t
    while ser.in_waiting:
        line = ser.readline().decode(errors="replace").strip()
        if line.startswith("VPLUS,"):
            try:
                vplus = float(line[len("VPLUS,"):])
                t_update = time.time()
            except ValueError:
                pass
        elif line.startswith("VA,"):
            try:
                va = float(line[len("VA,"):])
                t_update = time.time()
            except ValueError:
                pass
        # lines starting with '#' or anything else are ignored here
    return vplus, va, t_update
 
 
def main():
    print(f"Opening LabJack (serial={SERIAL_LJ})...")
    h = ljm.openS("T4", "ANY", SERIAL_LJ)
    info = ljm.getHandleInfo(h)
    print(f"LabJack connected, serial={info[2]}")
 
    print(f"Opening Arduino on {ARDUINO_PORT} at {ARDUINO_BAUD} baud...")
    ser = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=0)
    time.sleep(2)  # let the Arduino reset after the port opens
 
    if N_SAMPLES is not None:
        print(f"Logging to '{CSV_PATH}'. Will stop automatically after {N_SAMPLES} samples "
              f"(or Ctrl+C to stop earlier).\n")
    else:
        print(f"Logging to '{CSV_PATH}'. Press Ctrl+C to stop.\n")
 
    names_lj = ["AIN0", "AIN1", "AIN2", "AIN3"]  # VA (duplicate), VG, position_Ca, position_Cg
    Vplus_arduino = float("nan")
    VA_arduino = float("nan")
    arduino_update_t = time.time()
    n_taken = 0
 
    try:
        with open(CSV_PATH, "a", newline="") as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(CSV_HEADER)
 
            while N_SAMPLES is None or n_taken < N_SAMPLES:
                t0 = time.time()
 
                VA_lj, VG, position_Ca, position_Cg = ljm.eReadNames(h, len(names_lj), names_lj)
                Vplus_arduino, VA_arduino, arduino_update_t = read_latest_from_arduino(
                    ser, Vplus_arduino, VA_arduino, arduino_update_t)
 
                eps_a, eps_g = compute_eps(VA_lj, VG, Vplus_arduino)
                diff_va = VA_lj - VA_arduino
                arduino_lag_s = t0 - arduino_update_t
 
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                row = [ts, VA_lj, VG, Vplus_arduino, eps_a, eps_g, position_Ca, position_Cg,
                       VA_arduino, diff_va, arduino_lag_s]
                w.writerow(row)
                f.flush()
                n_taken += 1
 
                warn = ""
                if abs(diff_va) > CROSS_CHECK_TOL_V:
                    warn += "  *** VA CROSS-CHECK MISMATCH ***"
                if arduino_lag_s > LAG_WARN_S:
                    warn += f"  *** ARDUINO DATA STALE ({arduino_lag_s:.2f}s) ***"
 
                sample_tag = f"[{n_taken}/{N_SAMPLES}] " if N_SAMPLES is not None else ""
                print(f"{sample_tag}VA={VA_lj:8.4f} VG={VG:8.4f} V+={Vplus_arduino:8.4f} "
                      f"eps_a={eps_a:8.4f} eps_g={eps_g:8.4f} "
                      f"pos_Ca={position_Ca:8.4f} pos_Cg={position_Cg:8.4f} "
                      f"VA_ard={VA_arduino:8.4f} lag={arduino_lag_s:.3f}s{warn}")
 
                elapsed = time.time() - t0
                sleep_time = PERIOD_S - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
 
            if N_SAMPLES is not None:
                print(f"\nDone: {n_taken} samples collected, stopping automatically.")
 
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ljm.close(h)
        ser.close()
 
 
if __name__ == "__main__":
    main()
