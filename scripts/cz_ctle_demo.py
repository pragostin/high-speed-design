#!/usr/bin/env python3
"""
cz_ctle_demo.py — real-zero vs complex-zero CTLE equalization, illustrated.

Companion to the card:  cards/2026-05-27-cz-ctle.md

Scenario (the card's worked example):
  - H_core(s): TIA-core output with ~10 dB rolloff at Nyquist (56 GHz),
    modeled as a 2-pole low-pass (so it also has a realistic GD variation).
  - 5 cascaded equalizer stages recover the rolloff to ~4 dB residual at 56 GHz
    (~6 dB of boost, distributed), two ways:
        Case 1 — REAL-ZERO CTLE    (each stage: real zero + real pole)
        Case 2 — COMPLEX-ZERO CTLE (each stage: conjugate zero pair + pole pair)
    Both are tuned (by root-finding fz) to the SAME -4 dB residual, so the plots
    isolate the *group-delay* behaviour.

HONEST FRAMING — what the figures actually show:
  For identical-stage cascades normalized to DC, a real-zero CTLE does NOT
  automatically have worse group delay than a complex-zero one; a zero-pole pair
  is partly self-compensating. The genuine, teachable advantage of the complex
  zero is the EXTRA KNOB q_z: at fixed magnitude it controls the GD shape, and a
  well-damped (low-q_z) conjugate zero can drop a *localized* GD correction that
  a single real zero cannot. Push q_z too high and the same boost RINGS — the GD
  blows up. Panel 3 (the q_z sweep) is the real lesson.

Outputs three PNGs into site/assets/img/ (so the site can show them):
    cz_ctle_magnitude.png
    cz_ctle_groupdelay.png
    cz_ctle_qz_sweep.png

Run:
    python3 scripts/cz_ctle_demo.py
    python3 scripts/cz_ctle_demo.py --show

Deps: numpy, scipy, matplotlib
    pip install numpy scipy matplotlib --break-system-packages
"""
from __future__ import annotations
import argparse
import os
import numpy as np

try:
    from scipy.optimize import brentq
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

# ----------------------------------------------------------------------------
F_NYQ = 56e9
F = np.linspace(1e8, 1.4 * F_NYQ, 4000)
W = 2 * np.pi * F
JW = 1j * W
IDX_NYQ = int(np.argmin(np.abs(F - F_NYQ)))
N_STAGES = 5

DB = lambda H: 20 * np.log10(np.abs(H))


def group_delay_ps(H):
    phase = np.unwrap(np.angle(H))
    return -np.gradient(phase, W) * 1e12


def gd_pkpk(H):
    g = group_delay_ps(H)
    m = F <= F_NYQ
    return g[m].max() - g[m].min()


def norm_dc(H):
    return H / np.abs(H[0])


# ----------------------------------------------------------------------------
# building blocks
# ----------------------------------------------------------------------------
def two_pole_lowpass(f_p, q):
    wp = 2 * np.pi * f_p
    return 1.0 / (1 + JW / (q * wp) + (JW / wp) ** 2)


def real_zero_stage(f_z, f_p):
    wz, wp = 2 * np.pi * f_z, 2 * np.pi * f_p
    return (1 + JW / wz) / (1 + JW / wp)


def complex_zero_stage(f_z, q_z, f_p, q_p):
    wz, wp = 2 * np.pi * f_z, 2 * np.pi * f_p
    num = 1 + JW / (q_z * wz) + (JW / wz) ** 2
    den = 1 + JW / (q_p * wp) + (JW / wp) ** 2
    return num / den


# ----------------------------------------------------------------------------
# core + solving for -4 dB residual
# ----------------------------------------------------------------------------
H_CORE = two_pole_lowpass(f_p=32e9, q=0.78)   # ~ -9.7 dB @ 56 GHz
TARGET_RESID_DB = -4.0


def residual_db(H_eq):
    return DB(norm_dc(H_CORE * H_eq))[IDX_NYQ]


def solve_fz(stage_builder, lo, hi):
    """Find zero frequency f_z so the cascade lands at TARGET_RESID_DB.
    stage_builder(f_z) -> single-stage H; cascade is **N_STAGES."""
    def err(fz):
        return residual_db(stage_builder(fz) ** N_STAGES) - TARGET_RESID_DB
    if HAVE_SCIPY:
        return brentq(err, lo, hi)
    # bisection fallback
    a, b = lo, hi
    fa = err(a)
    for _ in range(80):
        m = 0.5 * (a + b)
        fm = err(m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
    return 0.5 * (a + b)


# Case 1: real zero, realistic pole at 1.8x the zero
fz_rz = solve_fz(lambda fz: real_zero_stage(fz, 1.8 * fz), 40e9, 220e9)
H_CASE1 = norm_dc(H_CORE * real_zero_stage(fz_rz, 1.8 * fz_rz) ** N_STAGES)

# Case 2: complex zero, well-damped (q_z=0.6), pole pair at 2.2x
QZ_MAIN, PR_MAIN, QP_MAIN = 0.6, 2.2, 0.62
fz_cz = solve_fz(lambda fz: complex_zero_stage(fz, QZ_MAIN, PR_MAIN * fz, QP_MAIN),
                 30e9, 160e9)
H_CASE2 = norm_dc(H_CORE * complex_zero_stage(fz_cz, QZ_MAIN, PR_MAIN * fz_cz, QP_MAIN) ** N_STAGES)

H_CORE_N = norm_dc(H_CORE)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("Real-zero vs complex-zero CTLE  (Nyquist = 56 GHz, 5 stages)")
    print("=" * 66)
    print(f"core              : {DB(H_CORE_N)[IDX_NYQ]:6.2f} dB @ Nyq   "
          f"GD pk-pk {gd_pkpk(H_CORE_N):5.2f} ps")
    print(f"Case 1 real-zero  : {DB(H_CASE1)[IDX_NYQ]:6.2f} dB @ Nyq   "
          f"GD pk-pk {gd_pkpk(H_CASE1):5.2f} ps   (fz={fz_rz/1e9:.1f}, fp={1.8*fz_rz/1e9:.1f} GHz)")
    print(f"Case 2 complex-z  : {DB(H_CASE2)[IDX_NYQ]:6.2f} dB @ Nyq   "
          f"GD pk-pk {gd_pkpk(H_CASE2):5.2f} ps   (fz={fz_cz/1e9:.1f}, qz={QZ_MAIN})")
    print("=" * 66)

    try:
        import matplotlib
        if not args.show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing -> pip install matplotlib --break-system-packages")
        return

    C_CORE, C_RZ, C_CZ = "#8a7f74", "#c4663a", "#3a7ca5"
    fGHz = F / 1e9
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                           "..", "site", "assets", "img"))
    os.makedirs(out_dir, exist_ok=True)

    def nyq_marker(ax):
        ax.axvline(F_NYQ / 1e9, color="0.6", ls=":", lw=1)
        ax.text(F_NYQ / 1e9, ax.get_ylim()[1], " Nyquist", va="top",
                color="0.45", fontsize=9)

    # ---- Fig 1: magnitude ----
    fig, ax = plt.subplots(figsize=(9, 5.0))
    ax.plot(fGHz, DB(H_CORE_N), C_CORE, lw=2, ls="--",
            label=f"core (uncompensated): {DB(H_CORE_N)[IDX_NYQ]:.1f} dB @ Nyq")
    ax.plot(fGHz, DB(H_CASE1), C_RZ, lw=2.2,
            label=f"Case 1 real-zero: {DB(H_CASE1)[IDX_NYQ]:.1f} dB @ Nyq")
    ax.plot(fGHz, DB(H_CASE2), C_CZ, lw=2.2,
            label=f"Case 2 complex-zero: {DB(H_CASE2)[IDX_NYQ]:.1f} dB @ Nyq")
    ax.axhline(-4, color="0.8", ls=":", lw=1)
    ax.text(1, -4, " -4 dB target", va="bottom", color="0.5", fontsize=8)
    ax.set_xlabel("Frequency [GHz]")
    ax.set_ylabel("Magnitude [dB]  (normalized to DC)")
    ax.set_title("Magnitude: both cascades recover 10 dB rolloff to ~4 dB "
                 "residual\n(tuned to the same residual by design)")
    ax.set_ylim(-13, 6)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="lower left")
    nyq_marker(ax)
    fig.tight_layout()
    p = os.path.join(out_dir, "cz_ctle_magnitude.png")
    fig.savefig(p, dpi=130)
    print("wrote", p)

    # ---- Fig 2: group delay (referenced to DC so tilt is visible) ----
    fig, ax = plt.subplots(figsize=(9, 5.0))
    g0 = lambda H: group_delay_ps(H) - group_delay_ps(H)[0]
    ax.plot(fGHz, g0(H_CORE_N), C_CORE, lw=2, ls="--",
            label=f"core  (pk-pk {gd_pkpk(H_CORE_N):.1f} ps)")
    ax.plot(fGHz, g0(H_CASE1), C_RZ, lw=2.2,
            label=f"Case 1 real-zero  (pk-pk {gd_pkpk(H_CASE1):.1f} ps)")
    ax.plot(fGHz, g0(H_CASE2), C_CZ, lw=2.2,
            label=f"Case 2 complex-zero, q_z={QZ_MAIN}  (pk-pk {gd_pkpk(H_CASE2):.1f} ps)")
    ax.set_xlabel("Frequency [GHz]")
    ax.set_ylabel("Group delay rel. to DC [ps]")
    ax.set_title("Group delay at the SAME magnitude: a well-damped complex zero\n"
                 "keeps GD controlled; both are usable — tuning is everything")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="lower left")
    nyq_marker(ax)
    fig.tight_layout()
    p = os.path.join(out_dir, "cz_ctle_groupdelay.png")
    fig.savefig(p, dpi=130)
    print("wrote", p)

    # ---- Fig 3: q_z sweep — the real lesson ----
    fig, (axm, axg) = plt.subplots(1, 2, figsize=(11, 4.6))
    qz_list = [0.5, 0.6, 0.7, 0.85, 1.0, 1.3]
    cmap = plt.cm.viridis(np.linspace(0.1, 0.9, len(qz_list)))
    for qz, col in zip(qz_list, cmap):
        fz = solve_fz(lambda fz: complex_zero_stage(fz, qz, PR_MAIN * fz, QP_MAIN),
                      25e9, 200e9)
        H = norm_dc(H_CORE * complex_zero_stage(fz, qz, PR_MAIN * fz, QP_MAIN) ** N_STAGES)
        axm.plot(fGHz, DB(H), color=col, lw=1.8, label=f"q_z={qz}")
        g = group_delay_ps(H) - group_delay_ps(H)[0]
        axg.plot(fGHz, g, color=col, lw=1.8, label=f"q_z={qz} ({gd_pkpk(H):.0f} ps)")
    for a, ttl, yl in [(axm, "Magnitude (all tuned to -4 dB @ Nyq)", "Mag [dB]"),
                       (axg, "Group delay rel. DC", "GD [ps]")]:
        a.axvline(F_NYQ / 1e9, color="0.6", ls=":", lw=1)
        a.set_xlabel("Frequency [GHz]"); a.set_ylabel(yl); a.set_title(ttl)
        a.grid(True, alpha=0.3); a.legend(fontsize=8, loc="best")
    axm.set_ylim(-13, 8)
    fig.suptitle("The complex-zero knob: at FIXED magnitude, q_z sets the GD shape "
                 "(low q_z = controlled, high q_z = ringing)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    p = os.path.join(out_dir, "cz_ctle_qz_sweep.png")
    fig.savefig(p, dpi=130)
    print("wrote", p)

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
