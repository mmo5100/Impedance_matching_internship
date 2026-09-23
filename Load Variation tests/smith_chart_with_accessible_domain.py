# -*- coding: utf-8 -*-
"""
smith_chart.py

Plots a Smith chart (normalized impedance, default Z0 = 50 ohms) showing,
for each tested position:
  - a small circle marker at the initial position (Z_init), where available
  - a square marker at the position found by the VNA (Z_vna)

Only the VNA-verified match is shown (not the RF-generator-converged
position): the generator and VNA sources were found to give measurably
different results under otherwise identical conditions (most likely related
to differing harmonic content), and this discrepancy has not been
elucidated. Until it is, only the VNA-based match -- which by its nature
directly and unambiguously indicates whether a load is matched -- is
reported here.

Each entry in DATA gets its own base color (automatically assigned from a
colormap, or a fixed color if provided). Every marker is additionally shaded
from light to dark according to its reflection coefficient magnitude
|Gamma|, using a COMMON scale across the whole dataset: the darkest marker
overall is the one with the smallest |Gamma| (best match), the lightest is
the one with the largest |Gamma| (worst match). The scale bar at the bottom
of the figure is graduated in actual S11 (dB) values.

Usage: edit the DATA list below with your own R+jX values (in ohms),
then run: python3 smith_chart.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors

# =============================================================================
# DATA -- edit with your own measurements
# Each entry: label, Z_init (R+jX ohms, optional), Z_vna (R+jX ohms)
# Z_init is omitted for loads where only S11_init in dB was available (a dB
# magnitude alone doesn't determine a unique point on the Smith chart, since
# the phase is unknown) -- the initial-position marker is then left out
# rather than guessed.
# Z_vna = position found by an independent VNA search (local optimum) --
# the only match position reported here (see module docstring).
# =============================================================================
DATA = [
    {"label": "(40,40)", "Z_init": 61.5 - 4.23j,   "Z_vna": 48.5 + 12.32j},
    {"label": "(35,35)", "Z_init": 80.61 - 38.0j,  "Z_vna": 48.88 + 11.07j},
    {"label": "(20,30)", "Z_init": 9.44 + 86.2j,   "Z_vna": 45.12 + 16.40j},
    {"label": "(30,20)", "Z_init": 172.0 - 443.2j, "Z_vna": 13.76 - 185.7j},
    {"label": "(30,30)", "Z_init": 46.34 + 25.03j, "Z_vna": 44.77 + 12.0j},
]
 
LOAD_LABEL = "Load: 50.46 + j0.306"





Z0 = 50.0  # reference characteristic impedance (ohms)

# Input mismatch domain (Section 2.2): the largest disk, centered at the
# origin of the reflection-coefficient plane, that is fully correctable by
# the double-stub assembly. Radius = sqrt(Gamma^2_min).
GAMMA2_MIN = 0.483
DOMAIN_RADIUS = GAMMA2_MIN ** 0.5


# =============================================================================
# Draws the shaded input mismatch domain disk, identical in meaning to the
# grey disk of Figure 3 (Section 2.2), so the reader can see at a glance
# whether the initial/match positions fall inside the correctable region.
# =============================================================================
def draw_input_mismatch_domain(ax, radius=DOMAIN_RADIUS):
    theta = np.linspace(0, 2 * np.pi, 200)
    ax.fill(radius * np.cos(theta), radius * np.sin(theta),
            color="0.6", alpha=0.35, zorder=0.5,
            label=f"$\\Gamma^2_{{\\min}} = {radius**2*100:.1f}\\%$ (radius={radius:.3f})")



# =============================================================================
# Impedance -> reflection coefficient conversion (Smith chart frame)
# =============================================================================
def z_to_gamma(z, z0=Z0):
    return (z - z0) / (z + z0)


# =============================================================================
# Shades a base color from light (poor match, large |Gamma|) to dark (good
# match, small |Gamma|). t=0 -> lightest tint, t=1 -> full/darkest color.
# =============================================================================
def shade_color(base_color, t, light_amount=0.75):
    base_rgb = np.array(mcolors.to_rgb(base_color))
    white = np.array([1.0, 1.0, 1.0])
    light_rgb = white * light_amount + base_rgb * (1 - light_amount)
    return tuple(light_rgb + (base_rgb - light_rgb) * t)


# =============================================================================
# Computes the global min/max S11 (dB) across every available point (init,
# vna) of every entry in DATA, so that shading and the scale bar share one
# common, meaningful reference across the whole dataset.
# =============================================================================
def compute_s11_db_range(data, z0=Z0):
    db_values = []
    for entry in data:
        for key in ("Z_init", "Z_vna"):
            if key not in entry:
                continue
            mag = abs(z_to_gamma(entry[key], z0))
            mag = max(mag, 1e-6)  # avoid log(0)
            db_values.append(20 * np.log10(mag))
    return min(db_values), max(db_values)


# =============================================================================
# Draws a light-to-dark scale below the chart, explaining the shading:
# darker = better match (smaller |Gamma|), lighter = worse match, within
# each position's own color.
# =============================================================================
def draw_value_strip(ax, data, db_min, db_max, z0=Z0, cmap_name="tab10"):
    cmap = plt.get_cmap(cmap_name)
    spread = db_max - db_min

    def t_for(db):
        if spread < 1e-9:
            return 1.0
        return (db_max - db) / spread

    # --- Blank white background, framed like the previous scale bar ---
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

    marker_shapes = {"Z_init": ("o", 6), "Z_vna": ("s", 6)}

    # --- Numeric S11 (dB) graduation: left = least negative (worst),
    # right = most negative (best) ---
    n_ticks = 6
    for i in range(n_ticks):
        t = i / (n_ticks - 1)
        db_val = db_max - t * (db_max - db_min)
        ax.plot([t, t], [0, -0.18], color="black", linewidth=0.8,
                 transform=ax.transAxes, clip_on=False)
        ax.text(t, -0.28, f"{db_val:.1f}", ha="center", va="top",
                fontsize=9, transform=ax.transAxes)

    # --- Each point's own (already-shaded) color, placed at its real S11 ---
    for i, entry in enumerate(data):
        base_color = entry.get("color", cmap(i % cmap.N))
        for key, (marker, size) in marker_shapes.items():
            if key not in entry:
                continue
            mag = max(abs(z_to_gamma(entry[key], z0)), 1e-6)
            db = 20 * np.log10(mag)
            t = t_for(db)
            shaded = shade_color(base_color, t)
            ax.plot(t, 0.5, marker=marker, markersize=size, color=shaded,
                    markeredgecolor="black", markeredgewidth=0.5, zorder=5,
                    transform=ax.transAxes, clip_on=False)

    ax.text(0.5, -0.75, "S11 (dB)", ha="center", va="top", fontsize=10,
            transform=ax.transAxes)
    ax.text(0.0, -1.15, "Poorer match", ha="left", va="top",
            fontsize=10, transform=ax.transAxes)
    ax.text(1.0, -1.15, "Better match", ha="right", va="top",
            fontsize=10, transform=ax.transAxes)


# =============================================================================
# Draws the Smith chart grid (constant-resistance circles, constant-
# reactance arcs) -- manual implementation, no external dependency
# (pySmithPlot, scikit-rf, etc.), to keep the script portable.
# =============================================================================
def draw_smith_grid(ax, z0=Z0):
    theta = np.linspace(0, 2 * np.pi, 400)

    # Unit circle (chart boundary)
    ax.plot(np.cos(theta), np.sin(theta), color="black", linewidth=1.4, zorder=1)

    # --- Constant-resistance circles r = R/Z0 ---
    r_values = [0, 0.2, 0.5, 1, 2, 5]
    for r in r_values:
        cx = r / (1 + r)
        radius = 1 / (1 + r)
        ax.plot(cx + radius * np.cos(theta), radius * np.sin(theta),
                color="gray", linewidth=0.7, zorder=1)

        label_x = (r - 1) / (r + 1)
        ax.text(label_x, -0.035, f"{r:g}", fontsize=9, ha="center", va="top",
                 color="dimgray", zorder=6)

    # --- Constant-reactance arcs x = X/Z0 (positive and negative) ---
    x_values = [0.2, 0.5, 1, 2, 5]
    for x in list(x_values) + [-v for v in x_values]:
        cx = 1
        cy = 1 / x
        radius = abs(1 / x)
        t = np.linspace(0, 2 * np.pi, 800)
        xx = cx + radius * np.cos(t)
        yy = cy + radius * np.sin(t)
        mask = xx**2 + yy**2 <= 1.0001
        ax.plot(xx[mask], yy[mask], color="gray", linewidth=0.7, zorder=1)

        boundary_angle = np.arctan2(2 * x, x**2 - 1)
        lx, ly = 1.09 * np.cos(boundary_angle), 1.09 * np.sin(boundary_angle)
        sign = "+" if x > 0 else "-"
        ax.text(lx, ly, f"{sign}j{abs(x):g}", fontsize=9, ha="center",
                 va="center", color="dimgray", zorder=6)

    # Horizontal axis (zero reactance, X=0)
    ax.plot([-1, 1], [0, 0], color="gray", linewidth=0.7, zorder=1)

    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")


# =============================================================================
# Plots the points for each position in DATA (initial + VNA match only)
# =============================================================================
def plot_positions(ax, data, db_min, db_max, z0=Z0, cmap_name="tab10"):
    cmap = plt.get_cmap(cmap_name)
    legend_handles = []
    spread = db_max - db_min

    def t_for(mag):
        mag = max(mag, 1e-6)
        db = 20 * np.log10(mag)
        if spread < 1e-9:
            return 1.0
        return (db_max - db) / spread

    for i, entry in enumerate(data):
        color = entry.get("color", cmap(i % cmap.N))

        if "Z_init" in entry:
            g_init = z_to_gamma(entry["Z_init"], z0)
            color_init = shade_color(color, t_for(abs(g_init)))
            ax.plot(g_init.real, g_init.imag, marker="o", markersize=7,
                    color=color_init, markeredgecolor="black",
                    markeredgewidth=0.6, zorder=5)

        g_vna = z_to_gamma(entry["Z_vna"], z0)
        color_vna = shade_color(color, t_for(abs(g_vna)))
        ax.plot(g_vna.real, g_vna.imag, marker="s", markersize=6.5,
                color=color_vna, markeredgecolor="black", markeredgewidth=0.6,
                zorder=5)

        legend_handles.append(mpatches.Patch(color=color, label=entry["label"]))

    return legend_handles


# =============================================================================
# Legend explaining marker shapes (initial position vs. VNA-verified match)
# =============================================================================
def marker_legend():
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=8, label="Initial position"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=7.5,
               label="VNA-verified match"),
    ]
    return handles


# =============================================================================
def main():
    db_min, db_max = compute_s11_db_range(DATA)

    # Larger figure and font sizes throughout, per the "one figure, readable
    # without zooming" guidance: each load gets its own full-size figure.
    fig = plt.figure(figsize=(10, 12))
    gs = fig.add_gridspec(2, 1, height_ratios=[10, 0.4], hspace=0.4)
    ax = fig.add_subplot(gs[0])
    ax_scale = fig.add_subplot(gs[1])

    draw_smith_grid(ax)
    draw_input_mismatch_domain(ax)
    color_legend = plot_positions(ax, DATA, db_min, db_max)
    shape_legend = marker_legend()

    leg1 = ax.legend(handles=color_legend, title="Starting position",
                      loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=11,
                      title_fontsize=12)
    ax.add_artist(leg1)
    leg2 = ax.legend(handles=shape_legend, title="Point type", loc="upper left",
              bbox_to_anchor=(1.02, 0.55), fontsize=11, title_fontsize=12)
    ax.add_artist(leg2)

    domain_handle = mpatches.Patch(color="0.6", alpha=0.35,
                                    label=f"$\\Gamma^2_{{\\min}} = {DOMAIN_RADIUS**2*100:.1f}\\%$\n(radius={DOMAIN_RADIUS:.3f})")
    ax.legend(handles=[domain_handle], loc="upper left", bbox_to_anchor=(1.02, 0.30),
              fontsize=10)

    # Renamed: these are key positions, not continuous time-domain
    # trajectories (only three discrete points are available per run).
    ax.set_title("Key Matching Positions at 38 MHz", fontsize=16)

    if LOAD_LABEL:
        ax.text(0.5, 1.05, LOAD_LABEL, ha="center", va="bottom", fontsize=13,
                color="dimgray", transform=ax.transAxes)

    draw_value_strip(ax_scale, DATA, db_min, db_max)

    plt.savefig("smith_chart.pdf", bbox_inches="tight")
    print("Figure saved: smith_chart.pdf")


if __name__ == "__main__":
    main()