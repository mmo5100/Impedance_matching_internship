# -*- coding: utf-8 -*-
"""
position_map.py

Scatter plot in capacitor-position space (Ca on the x-axis, Cg on the
y-axis). Each starting position gets its own base color (like the Smith
chart script), and every marker is additionally shaded from light
(poor match) to dark (good match) according to its S11 (dB), using a
scale common to the whole dataset.

For each tested starting position, three points are plotted:
  - a circle at the initial position (pos_init)
  - a triangle at the position found by the GENERATOR (pos_gen)
  - a square at the position found by the VNA (pos_vna)

Usage: edit the DATA list below with your own (Ca, Cg) positions and
S11 (dB) values, then run: python3 position_map.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D

# =============================================================================
# DATA -- edit with your own measurements
# Each entry: label, pos_init (Ca,Cg mm) + s11_init (dB),
#             pos_gen (Ca,Cg mm) + s11_gen (dB),
#             pos_vna (Ca,Cg mm) + s11_vna (dB)
# Any of the three points can be omitted (e.g. "pos_init": None) if not
# available -- it will simply be skipped.
# =============================================================================
DATA = [
    {"label": "(40,40)", "pos_init": (40, 40),      "s11_init": -10.52,
                          "pos_gen": (53, 36.69),    "s11_gen": -4.59,
                          "pos_vna": (52.02, 36.66), "s11_vna": -4.42},
    {"label": "(35,35)", "pos_init": (35, 35),      "s11_init": -8.37,
                          "pos_gen": (28.87, 31.42), "s11_gen": -13.1,
                          "pos_vna": (26.78, 30.72), "s11_vna": -17.64},
    {"label": "(20,30)", "pos_init": (20, 30),      "s11_init": -1.42,
                          "pos_gen": (29.05, 31.17), "s11_gen": -11.7,
                          "pos_vna": (27.15, 31.22), "s11_vna": -26.67},
    {"label": "(30,20)", "pos_init": (30, 20),      "s11_init": -0.95,
                          "pos_gen": (7.08, 7.03),   "s11_gen": -0.3,
                          "pos_vna": (4.80, 7.12),   "s11_vna": -0.32},
    {"label": "(30,30)", "pos_init": (30, 30),      "s11_init": -7.27,
                          "pos_gen": (29.95, 30.02), "s11_gen": -7.62,
                          "pos_vna": (26.57, 30.52), "s11_vna": -14.98},
]

LOAD_LABEL = "Load: 50||50 -> 25 \u03a9"

MARKER_STYLES = {
    "init": ("o", 5, "Initial position"),
    "gen":  ("^", 5, "Generator position"),
    "vna":  ("s", 4.5, "VNA position"),
}


# =============================================================================
# Shades a base color from light (poor match, less negative dB) to dark
# (good match, more negative dB). t=0 -> lightest tint, t=1 -> full color.
# =============================================================================
def shade_color(base_color, t, light_amount=0.75):
    base_rgb = np.array(mcolors.to_rgb(base_color))
    white = np.array([1.0, 1.0, 1.0])
    light_rgb = white * light_amount + base_rgb * (1 - light_amount)
    return tuple(light_rgb + (base_rgb - light_rgb) * t)


def compute_s11_db_range(data):
    values = []
    for entry in data:
        for kind in ("init", "gen", "vna"):
            s11 = entry.get(f"s11_{kind}")
            if s11 is not None:
                values.append(s11)
    return min(values), max(values)


# =============================================================================
# Draws a blank white strip below the main plot, with each point's own
# (already-shaded) color placed at its real S11 (dB) value -- a concrete
# legend/verification of the color-vs-match-quality relationship.
# =============================================================================
def draw_value_strip(ax, data, db_min, db_max, cmap_name="tab10"):
    cmap = plt.get_cmap(cmap_name)
    spread = db_max - db_min

    def t_for(db):
        if spread < 1e-9:
            return 1.0
        return (db_max - db) / spread

    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("black")
        spine.set_linewidth(0.6)
    ax.axhline(0.5, color="lightgray", linewidth=0.8, zorder=1)

    n_ticks = 6
    for i in range(n_ticks):
        t = i / (n_ticks - 1)
        db_val = db_max - t * (db_max - db_min)
        ax.plot([t, t], [0, -0.18], color="black", linewidth=0.8,
                 transform=ax.transAxes, clip_on=False)
        ax.text(t, -0.28, f"{db_val:.1f}", ha="center", va="top",
                fontsize=7, transform=ax.transAxes)

    for i, entry in enumerate(data):
        base_color = entry.get("color", cmap(i % cmap.N))
        for kind, (marker, size, _) in MARKER_STYLES.items():
            s11 = entry.get(f"s11_{kind}")
            if s11 is None:
                continue
            t = t_for(s11)
            shaded = shade_color(base_color, t)
            ax.plot(t, 0.5, marker=marker, markersize=size + 1, color=shaded,
                    markeredgecolor="black", markeredgewidth=0.5, zorder=5,
                    transform=ax.transAxes, clip_on=False)

    ax.text(0.5, -0.75, "S11 (dB)", ha="center", va="top", fontsize=8,
            transform=ax.transAxes)
    ax.text(0.0, -1.15, "Poorer match", ha="left", va="top",
            fontsize=8, transform=ax.transAxes)
    ax.text(1.0, -1.15, "Better match", ha="right", va="top",
            fontsize=8, transform=ax.transAxes)
    ax.set_title("Actual point colors, placed by S11 (dB)", fontsize=9, pad=6)


def main():
    db_min, db_max = compute_s11_db_range(DATA)
    spread = db_max - db_min

    def t_for(db):
        # more negative dB (better match) -> t close to 1 (darker)
        if spread < 1e-9:
            return 1.0
        return (db_max - db) / spread

    cmap = plt.get_cmap("tab10")

    fig = plt.figure(figsize=(8, 8.3))
    gs = fig.add_gridspec(2, 1, height_ratios=[10, 0.4], hspace=0.5)
    ax = fig.add_subplot(gs[0])
    ax_scale = fig.add_subplot(gs[1])

    color_legend_handles = []
    for i, entry in enumerate(DATA):
        base_color = entry.get("color", cmap(i % cmap.N))

        for kind, (marker, size, _) in MARKER_STYLES.items():
            pos = entry.get(f"pos_{kind}")
            s11 = entry.get(f"s11_{kind}")
            if pos is None or s11 is None:
                continue
            shaded = shade_color(base_color, t_for(s11))
            ax.plot(pos[0], pos[1], marker=marker, markersize=size * 2,
                     color=shaded, markeredgecolor="black",
                     markeredgewidth=0.6, zorder=5)

        color_legend_handles.append(mpatches.Patch(color=base_color, label=entry["label"]))

    ax.set_xlabel("Ca position (mm)")
    ax.set_ylabel("Cg position (mm)")
    ax.set_aspect("equal")
    ax.grid(True, linewidth=0.4, alpha=0.5, zorder=0)

    if LOAD_LABEL:
        ax.set_title(LOAD_LABEL, fontsize=11, color="dimgray")

    shape_handles = [
        Line2D([0], [0], marker=m, color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=8, label=lbl)
        for m, _, lbl in MARKER_STYLES.values()
    ]

    leg1 = ax.legend(handles=color_legend_handles, title="Starting position",
                      loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9)
    ax.add_artist(leg1)
    ax.legend(handles=shape_handles, title="Point type", loc="upper left",
              bbox_to_anchor=(1.02, 0.55), fontsize=9)

    draw_value_strip(ax_scale, DATA, db_min, db_max)

    plt.savefig("position_map.pdf", bbox_inches="tight")
    print("Figure saved: position_map.pdf")


if __name__ == "__main__":
    main()