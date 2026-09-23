"""
plot_compare_current_vs_position_by_direction.py
-------------------------------------------------
Compare motor current vs. capacitor position for two acquisitions
(e.g. "without springs" vs. "springs back"), splitting each sweep
into its forward and backward direction (round-trip sweep -> 2 branches).

Usage
-----
    python plot_compare_current_vs_position_by_direction.py file1.csv file2.csv

Optional arguments
-------------------
    --pos-col NAME     Force the column name used for position
                        (default: auto-detect a column containing "AIN0"
                        or "position", case-insensitive)
    --cur-col NAME      Force the column name used for current
                        (default: auto-detect a column containing "AIN2"
                        or "current", case-insensitive)
    --labels L1 L2      Custom legend labels for file1 / file2
                        (default: derived from the file names)
    --smooth N          Rolling-median window (in samples) used only to
                        determine sweep direction robustly (default: 5)
    --out FILE          Output image file (default: current_vs_position_compare.png)

The script does NOT assume a fixed column order: it inspects the header
of each CSV and tries to find the right columns automatically. If it
can't find them, it prints the available column names so you can re-run
with --pos-col / --cur-col.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def find_column(columns, keywords):
    """Return the first column whose name contains one of the keywords
    (case-insensitive). Returns None if nothing matches."""
    for kw in keywords:
        for c in columns:
            if kw.lower() in str(c).lower():
                return c
    return None


def load_and_prepare(path, pos_col=None, cur_col=None, smooth=5):
    """Load one CSV, auto-detect (or use forced) position/current columns,
    and split the data into 'forward' and 'backward' sweep branches."""
    df = pd.read_csv(path)

    if pos_col is None:
        pos_col = find_column(df.columns, ["AIN0", "position", "pos"])
    if cur_col is None:
        cur_col = find_column(df.columns, ["AIN2", "current", "courant"])

    if pos_col is None or cur_col is None:
        print(f"\n[!] Could not auto-detect columns in '{path}'.")
        print(f"    Available columns: {list(df.columns)}")
        print("    Re-run with --pos-col / --cur-col to specify them explicitly.")
        sys.exit(1)

    pos = df[pos_col].to_numpy(dtype=float)
    cur = df[cur_col].to_numpy(dtype=float)

    # Smooth the position with a rolling median just to get a robust
    # sign of the local slope (this is only used to classify direction,
    # the raw, unsmoothed data is what gets plotted).
    pos_series = pd.Series(pos)
    pos_smooth = pos_series.rolling(window=max(1, smooth), center=True,
                                     min_periods=1).median().to_numpy()

    d = np.gradient(pos_smooth)
    # Avoid a direction flip on exact-zero-slope samples (holds, plateaus):
    # forward-fill the last nonzero sign.
    sign = np.sign(d)
    last = 1.0
    for i in range(len(sign)):
        if sign[i] == 0:
            sign[i] = last
        else:
            last = sign[i]

    forward_mask = sign > 0
    backward_mask = ~forward_mask

    return {
        "pos_col": pos_col,
        "cur_col": cur_col,
        "pos": pos,
        "cur": cur,
        "forward": forward_mask,
        "backward": backward_mask,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare Ca current vs. position for two acquisitions, "
                    "split by sweep direction (forward/backward).")
    parser.add_argument("file1", help="First CSV file (e.g. without springs)")
    parser.add_argument("file2", help="Second CSV file (e.g. springs back)")
    parser.add_argument("--pos-col", default=None,
                        help="Column name to use for position (both files)")
    parser.add_argument("--cur-col", default=None,
                        help="Column name to use for current (both files)")
    parser.add_argument("--labels", nargs=2, default=None,
                        metavar=("LABEL1", "LABEL2"),
                        help="Legend labels for file1 / file2")
    parser.add_argument("--smooth", type=int, default=5,
                        help="Rolling-median window (samples) for direction detection")
    parser.add_argument("--out", default="current_vs_position_compare.png",
                        help="Output image filename")
    parser.add_argument("--xlim", type=float, nargs=2, default=[-6, 8],
                        metavar=("XMIN", "XMAX"),
                        help="X-axis (position) display range in volts (default: -6 6)")
    parser.add_argument("--ylim", type=float, nargs=2, default=[-3, 3],
                        metavar=("YMIN", "YMAX"),
                        help="Y-axis (current) display range in volts (default: -6 6)")
    args = parser.parse_args()

    if args.labels:
        label1, label2 = args.labels
    else:
        label1 = os.path.splitext(os.path.basename(args.file1))[0]
        label2 = os.path.splitext(os.path.basename(args.file2))[0]

    d1 = load_and_prepare(args.file1, args.pos_col, args.cur_col, args.smooth)
    d2 = load_and_prepare(args.file2, args.pos_col, args.cur_col, args.smooth)

    print(f"File 1 ({args.file1}): position column = '{d1['pos_col']}', "
          f"current column = '{d1['cur_col']}', {len(d1['pos'])} points")
    print(f"File 2 ({args.file2}): position column = '{d2['pos_col']}', "
          f"current column = '{d2['cur_col']}', {len(d2['pos'])} points")

    fig, ax = plt.subplots(figsize=(8, 6))

    ms = 4  # marker size, matching the small-dot style of Figure 5 in the report

    # File 1 -- orange family
    ax.scatter(d1["pos"][d1["forward"]], d1["cur"][d1["forward"]],
               s=ms, color="tab:orange", label=f"{label1} -- forward")
    ax.scatter(d1["pos"][d1["backward"]], d1["cur"][d1["backward"]],
               s=ms, color="darkred", label=f"{label1} -- backward")

    # File 2 -- blue family
    ax.scatter(d2["pos"][d2["forward"]], d2["cur"][d2["forward"]],
               s=ms, color="tab:blue", label=f"{label2} -- forward")
    ax.scatter(d2["pos"][d2["backward"]], d2["cur"][d2["backward"]],
               s=ms, color="navy", label=f"{label2} -- backward")

    ax.set_xlabel(f"Position -- {d1['pos_col']}")
    ax.set_ylabel(f"Current -- {d1['cur_col']}")
    ax.set_title("Comparison of Ca current vs. position\n(with vs. without spring compensation, by sweep direction)")
    ax.set_xlim(args.xlim)
    ax.set_ylim(args.ylim)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"\nSaved plot to: {args.out}")
    plt.show()


if __name__ == "__main__":
    main()