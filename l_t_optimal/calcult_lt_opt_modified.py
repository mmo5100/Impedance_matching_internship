import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================================================================
# PHYSICAL PARAMETERS (unchanged from Mara's script)
# ============================================================================
f_mhz = 38
f = f_mhz * 1e6
c_light = 3e8
Z0 = 50.0
w = 2 * np.pi * f
beta = w / c_light

Ls_serie = 70e-9        # H, measured series inductance

Cs_neutre = 138.9e-12   # pF, neutral capacitance at 38 MHz (Table 1, Design paper)

Ca_min, Ca_max = 40e-12, 205e-12   # working range (Design paper)
Cg_min, Cg_max = 40e-12, 205e-12


def raw(C, Ls=Ls_serie):
    """Y = 1/(jwLs + 1/jwC), in Siemens: w*C / (1 - w^2*Ls*C)."""
    return w * C / (1 - w ** 2 * Ls * C)


b_self_fixe = -Z0 * raw(Cs_neutre)


def b_total(C):
    return Z0 * raw(C) + b_self_fixe


def ABCD(b_a, b_g, theta):
    c, s = np.cos(theta), np.sin(theta)
    A = c - b_g * s
    B = 1j * Z0 * s
    C_ = 1j * ((b_a + b_g) * c + (1 - b_a * b_g) * s) / Z0
    D = c - b_a * s
    return A, B, C_, D


def rhoA_matched(Ca, Cg, lt):
    A, B, C_, D = ABCD(b_total(Ca), b_total(Cg), beta * lt)
    zA_ohm = (B + A * Z0) / (C_ * Z0 + D)
    return (zA_ohm - Z0) / (zA_ohm + Z0)


def grille_accessible(lt, n=300):
    Ca_v = np.linspace(Ca_min, Ca_max, n)
    Cg_v = np.linspace(Cg_min, Cg_max, n)
    Ca_g, Cg_g = np.meshgrid(Ca_v, Cg_v)
    return rhoA_matched(Ca_g, Cg_g, lt).flatten()


def gamma2min(lt, n=220, n_phase_bins=360):
    pts = grille_accessible(lt, n=n)
    r = np.abs(pts)
    phi = np.mod(np.angle(pts), 2 * np.pi)
    bins = np.floor(phi / (2 * np.pi) * n_phase_bins).astype(int)
    bins = np.clip(bins, 0, n_phase_bins - 1)
    r_max_par_phase = np.full(n_phase_bins, np.nan)
    for k in range(n_phase_bins):
        sel = r[bins == k]
        if sel.size:
            r_max_par_phase[k] = sel.max()
    if np.any(np.isnan(r_max_par_phase)):
        return 0.0, pts
    r_min = r_max_par_phase.min()
    return r_min ** 2 * 100, pts


# lt optimum, taken directly from Mara's own sweep (0.552 m at 38 MHz)
lt_opt = 0.552
g2_final, _ = gamma2min(lt_opt, n=300, n_phase_bins=240)

# ============================================================================
# FIGURE -- Frederic's fixes applied:
#  1) only 5 iso-C curves per family, all SAME thickness
#  2) each curve explicitly labelled with its physical C value
#     (Cmin, (Cmin+C0)/2, C0=neutral/matched, (C0+Cmax)/2, Cmax)
#  3) capacitor variation strictly limited to [Ca_min,Ca_max]/[Cg_min,Cg_max]
#     (already enforced by construction, kept identical here)
#  4) the vertical line at Re(rhoA)=0 is REMOVED (it never represented b=0);
#     only a genuine physical reference (g=1 circle, |rhoA|=1) is kept
# ============================================================================
N_FIG = 220
Ca_v = np.linspace(Ca_min, Ca_max, N_FIG)
Cg_v = np.linspace(Cg_min, Cg_max, N_FIG)
Ca_g, Cg_g = np.meshgrid(Ca_v, Cg_v)
rho_g = rhoA_matched(Ca_g, Cg_g, lt_opt)

fig, ax = plt.subplots(figsize=(7.2, 7.2))

# 5 labelled values per family: min, (min+neutral)/2, neutral, (neutral+max)/2, max
C0 = Cs_neutre
Cvals = [Ca_min, (Ca_min + C0) / 2, C0, (C0 + Ca_max) / 2, Ca_max]
Clabels = [r"$C_{\min}$", r"$(C_{\min}{+}C_0)/2$", r"$C_0$ (neutral)",
           r"$(C_0{+}C_{\max})/2$", r"$C_{\max}$"]

# indices in the N_FIG grid closest to each target capacitance
idx_courbes = [int(np.argmin(np.abs(Ca_v - cv))) for cv in Cvals]

LW = 1.3  # uniform thickness for every curve, as requested
pF = lambda C: f"{C*1e12:.0f} pF"

for k, i in enumerate(idx_courbes):
    # blue curve: Cg fixed at Cvals[k], Ca sweeps -- label with the fixed Cg value
    xb, yb = rho_g[i, :].real, rho_g[i, :].imag
    ax.plot(xb, yb, color="blue", lw=LW)
    # green curve: Ca fixed at Cvals[k], Cg sweeps -- label with the fixed Ca value
    xg, yg = rho_g[:, i].real, rho_g[:, i].imag
    ax.plot(xg, yg, color="green", lw=LW)

    # place an inline label directly on each curve, at the point where the
    # *other* capacitor equals its neutral value C0 -- a fixed, physically
    # meaningful anchor shared by every curve, giving natural spacing
    j0 = int(np.argmin(np.abs(Ca_v - C0)))
    j_b, j_g = j0, j0
    ax.annotate(pF(Cvals[k]), (xb[j_b], yb[j_b]), color="blue", fontsize=7.5,
                ha="center", va="center", xytext=(-18, 10) if k == 2 else (0, 0),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))
    ax.annotate(pF(Cvals[k]), (xg[j_g], yg[j_g]), color="green", fontsize=7.5,
                ha="center", va="center", xytext=(18, -10) if k == 2 else (0, 0),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))

# minimal legend: only genuine physical references (curve families are
# already identified by their inline pF labels, no need to repeat here)
ax.text(0.02, 0.98, "blue: $C_g$ labelled, $C_a$ varies", transform=ax.transAxes,
        color="blue", fontsize=8, va="top", ha="left")
ax.text(0.02, 0.94, "green: $C_a$ labelled, $C_g$ varies", transform=ax.transAxes,
        color="green", fontsize=8, va="top", ha="left")

# Gamma2min disk (largest circle inscribed in the reachable domain for every phase)
r_opt = np.sqrt(g2_final / 100)
theta = np.linspace(0, 2 * np.pi, 300)
ax.fill(r_opt * np.cos(theta), r_opt * np.sin(theta), color="0.75", alpha=0.8, zorder=0,
        label=rf"$\Gamma^2_{{min}}$ = {g2_final:.1f}%  (radius={r_opt:.3f})")

ax.plot(np.cos(theta), np.sin(theta), color="gray", lw=1, ls=":", label=r"$|\rho_A|=1$")

# g=1 circle (real physical reference: unit normalized conductance seen by generator)
theta_g1 = np.linspace(0, 2 * np.pi, 200)
g1_circle = -0.5 + 0.5 * np.exp(1j * theta_g1)
ax.plot(g1_circle.real, g1_circle.imag, color="red", lw=1, ls="--", label="g = 1")

# NOTE: the old axhline(0)/axvline(0) pair (labelled "b=0") has been removed:
# neither Im(rhoA)=0 nor Re(rhoA)=0 is, in general, the true b=0 locus.

ax.set_xlabel(r"Re($\rho_A$)")
ax.set_ylabel(r"Im($\rho_A$)")
ax.set_xlim(-1.05, 1.05)
ax.set_ylim(-1.05, 1.05)
ax.set_aspect("equal")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8.5, framealpha=0.9)
ax.grid(alpha=0.2)

plt.tight_layout()
plt.savefig("domain_fixed.png", dpi=170, bbox_inches="tight")
print("Saved domain_fixed.png in the current working directory")