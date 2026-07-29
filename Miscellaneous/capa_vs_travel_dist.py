"""
Capacitance (pF) vs. travel distance (mm) -- digital reproduction of the
original design-paper graph, with a linear fit over the working (linear)
region, used to derive the reference formula in Section 4.1:

    C_s(x) = C0 - x * slope        [pF],  x in mm

Just edit the DATA POINTS section below with your own values (read off
the original paper's graph, or from your own measurements), then run
the script. It will:
  1. plot the raw points,
  2. fit a straight line through the points you mark as "linear region",
  3. print and annotate the fitted equation (intercept + slope),
  4. save the figure as both PNG (quick look) and PDF (vector, for LaTeX).
"""

import numpy as np
import matplotlib.pyplot as plt

# ============================================================================
# 1) DATA POINTS -- edit this with your own values
# ============================================================================
# x_mm  : travel distance / mechanical position, in mm
# C_pF  : corresponding capacitance, in pF
# Read these off the original graph (or your own measurement table).
x_mm = np.array([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65])
C_pF = np.array([300, 274, 248, 222, 196, 170, 144, 118, 92, 66, 40, 30, 22, 16])

# Which of the points above belong to the LINEAR region to fit.
# Here: the curve stops being linear from ~50 mm onward, so those points
# (50, 55, 60, 65 mm) are excluded from the fit but still plotted (as
# gray crosses) for reference.
fit_mask = x_mm < 50

# ============================================================================
# 2) LINEAR FIT over the selected points
# ============================================================================
slope, intercept = np.polyfit(x_mm[fit_mask], C_pF[fit_mask], 1)
# slope is negative (capacitance decreases with x); report it as a
# positive "pF per mm" the way the reference formula is written:
slope_pF_per_mm = -slope

print(f"Fitted line (from your data): C(x) = {intercept:.3f} pF  -  x * {slope_pF_per_mm:.3f} pF/mm")

# Force the plotted line to follow the known reference formula
# C_s(x) = 300 pF - x * 5.217 pF/mm, instead of the free fit above.
intercept = 300.0
slope_pF_per_mm = 5.217
slope = -slope_pF_per_mm

x_fit = np.linspace(x_mm[fit_mask].min(), x_mm[fit_mask].max(), 200)
C_fit = intercept + slope * x_fit

# dashed curve connecting the actual points in the non-linear region
# (include the last linear point too, so the dashed line connects smoothly
# to the solid fit line)
non_lin_idx = np.where(~fit_mask)[0]
last_lin_idx = np.where(fit_mask)[0][-1]
idx_dashed = np.concatenate(([last_lin_idx], non_lin_idx))
x_dashed = x_mm[idx_dashed]
C_dashed = C_pF[idx_dashed]

# ============================================================================
# 3) PLOT
# ============================================================================
fig, ax = plt.subplots(figsize=(6, 4.5))

ax.plot(x_mm[fit_mask], C_pF[fit_mask], "o", color="black",
        label="Data points (linear region)")
ax.plot(x_mm[~fit_mask], C_pF[~fit_mask], "x", color="gray",
        label="Data points (excluded from fit)")
ax.plot(x_fit, C_fit, "-", color="red", lw=1.5,
        label=f"Reference formula: $C_s(x) = {intercept:.1f} - x \\cdot {slope_pF_per_mm:.3f}$ pF")
ax.plot(x_dashed, C_dashed, "--", color="red", lw=1.5,
        label="Non-linear region (data)")

ax.set_xlabel("Travel distance $x$ (mm)")
ax.set_ylabel("Capacitance $C$ (pF)")
ax.set_title("Capacitance vs. travel distance")
ax.grid(alpha=0.3)
ax.legend(loc="best", fontsize=9)

plt.tight_layout()
plt.savefig("capacitance_vs_position.png", dpi=150)
plt.savefig("capacitance_vs_position.pdf")
plt.show()