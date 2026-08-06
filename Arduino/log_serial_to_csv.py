"""
Reads the CSV-formatted output of mesure_moyenne_eps.ino over serial and
writes it to two real .csv files: one with every individual sample, one
with the per-cycle averages.

Expected Arduino output format (see mesure_moyenne_eps.ino):
  '#'    prefix -> human-readable comment, ignored here
  'DATA' prefix -> DATA,cycle,sample_index,VA,VG,Vplus,eps_a,eps_g
  'AVG'  prefix -> AVG,cycle,n_samples,VA_avg,VG_avg,Vplus_avg,eps_a_avg,eps_g_avg

Usage:
    python log_serial_to_csv.py [PORT] [BAUD]

Defaults: PORT='COM5', BAUD=115200 -- adjust to your setup, or pass them
as command-line arguments, e.g.:
    python log_serial_to_csv.py COM5 115200
"""

import sys
import csv
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

DATA_CSV = "mesures_eps_data.csv"
AVG_CSV = "mesures_eps_avg.csv"

DATA_HEADER = ["timestamp_pc", "cycle", "sample_index", "VA", "VG", "Vplus", "eps_a", "eps_g", "position_Ca", "position_Cg"]
AVG_HEADER = ["timestamp_pc", "cycle", "n_samples", "VA_avg", "VG_avg", "Vplus_avg", "eps_a_avg", "eps_g_avg", "position_Ca_avg", "position_Cg_avg"]


def main():
    print(f"Opening {PORT} at {BAUD} baud...")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # let the Arduino reset after the port opens

    data_new = True
    avg_new = True

    print(f"Logging samples to '{DATA_CSV}' and averages to '{AVG_CSV}'.")
    print("Press Ctrl+C to stop.\n")

    try:
        with open(DATA_CSV, "a", newline="") as f_data, \
             open(AVG_CSV, "a", newline="") as f_avg:

            w_data = csv.writer(f_data)
            w_avg = csv.writer(f_avg)

            if data_new and f_data.tell() == 0:
                w_data.writerow(DATA_HEADER)
            if avg_new and f_avg.tell() == 0:
                w_avg.writerow(AVG_HEADER)

            while True:
                raw = ser.readline().decode(errors="replace").strip()
                if not raw:
                    continue

                if raw.startswith("#"):
                    print(raw)
                    continue

                if raw.startswith("DATA,"):
                    fields = raw[len("DATA,"):].split(",")
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    w_data.writerow([ts] + fields)
                    f_data.flush()
                    print(raw)

                elif raw.startswith("AVG,"):
                    fields = raw[len("AVG,"):].split(",")
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    w_avg.writerow([ts] + fields)
                    f_avg.flush()
                    print(raw)

                else:
                    # Unrecognized line, print for visibility but don't log
                    print(raw)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()