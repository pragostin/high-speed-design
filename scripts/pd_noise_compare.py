#!/usr/bin/env python3
"""
pd_noise_compare.py — quantify why a higher-C_J photodiode can lower input-referred
noise, by computing the optical-referred IRN_avg metric for two photodiodes.

Companion to the card:
    cards/2026-05-26-tia-noise-transfer-function.md  (§6)

Metric (as used in lab):
    IRN_avg = sqrt( ∫_0^fN  i_n,in^2(f) / |H_PD(f)/R|^2  df )  /  sqrt(fN)
    fN = Nyquist = 56 GHz for 100 GBaud PAM4 (112 Gb/s class, 56 GBd symbol-rate
    Nyquist; adjust fN below if your convention differs).

  - numerator integrand  = TIA-referred input noise PSD divided by the *normalized*
    PD response |H_PD/R|^2 .  The PD S21 is in the SIGNAL path, not the NOISE path,
    so referring noise to the optical input divides by it.
  - sqrt(integral)       -> rms input-referred noise current  [A]
  - / sqrt(fN)           -> band-averaged spectral density     [A/sqrt(Hz)]

The point: C_J enters the NUMERATOR (via the f^2 term), PD bandwidth enters the
DENOMINATOR (via |H_PD|^2). A wider, higher-C_J diode can still win.

This is a first-order teaching model (lumped C_in, single-pole amp, simple PD
poles). It reproduces the *direction and rough magnitude* of the measured
20–30 % improvement; it is NOT a substitute for the extracted/EM netlist.

Run:
    python3 scripts/pd_noise_compare.py
    python3 scripts/pd_noise_compare.py --no-plot      # numbers only
    python3 scripts/pd_noise_compare.py --fN 56e9
Output:
    prints IRN_avg for each PD + the ratio, and (unless --no-plot) writes
    scripts/pd_noise_compare.png with the two optical-referred spectra + crossover.

Deps: numpy (required), matplotlib (only if plotting).
"""
from __future__ import annotations
import argparse
import math
from dataclasses import dataclass

import numpy as np

# ----------------------------------------------------------------------------
# Physical constants
# ----------------------------------------------------------------------------
K_B = 1.380649e-23   # Boltzmann [J/K]
Q_E = 1.602176634e-19  # electron charge [C]


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
@dataclass
class TIA:
    """First-order shunt-feedback TIA noise model (see §2 of the card)."""
    R_F: float = 250.0      # feedback resistor [ohm]
    gm: float = 60e-3       # front-end transconductance [S]
    gamma: float = 1.5      # channel-noise factor (tech-dependent)
    T: float = 300.0        # temperature [K]
    C_fixed: float = 60e-15  # pad + ESD + C_gs, i.e. C_in WITHOUT the diode [F]

    def psd_referred_to_tia_input(self, f, C_pd, I_pd=0.0):
        """
        Input-referred noise current PSD [A^2/Hz] at the TIA input node.
        i_n,in^2(f) = 4kT/R_F  +  4kT*gamma/gm * (1/R_F^2 + (2*pi*f*C_in)^2) + 2qI
        C_in = C_fixed + C_pd
        """
        C_in = self.C_fixed + C_pd
        vn2 = 4 * K_B * self.T * self.gamma / self.gm           # amp input voltage noise PSD [V^2/Hz]
        i_res = 4 * K_B * self.T / self.R_F                      # feedback-R thermal (flat)
        i_vn = vn2 * (1.0 / self.R_F**2 + (2 * np.pi * f * C_in) ** 2)  # shaped f^2 term
        i_shot = 2 * Q_E * I_pd                                  # PD shot (flat); 0 if dark
        return i_res + i_vn + i_shot


@dataclass
class Photodiode:
    """
    PD signal-path response.  H_PD(s) = R_resp * H_opt(s) * H_elec(s).
    We work with the NORMALIZED magnitude-squared |H_PD/R_resp|^2, a low-pass
    that rolls off and inflates the optical-referred noise when divided out.

    Optical pole:  user-specified f_opt (transit/absorption limited).
    Electrical pole: from C_J ->  f_elec = 1/(2*pi*(R_load+R_s)*C_J).
    The measured total BW combines as 1/fPD^2 = 1/fopt^2 + 1/felec^2.
    Optical pole order `n_opt` lets you make the optical roll-off steeper than RC.
    """
    name: str
    C_J: float            # junction capacitance [F]
    f_opt: float          # optical/transit -3dB [Hz]
    n_opt: int = 1        # optical pole order (1 = single-pole; >1 = steeper)
    R_load: float = 50.0  # effective load seen by the diode pole [ohm]
    R_s: float = 10.0     # series resistance [ohm]

    @property
    def f_elec(self) -> float:
        return 1.0 / (2 * np.pi * (self.R_load + self.R_s) * self.C_J)

    @property
    def f_pd(self) -> float:
        """Combined -3dB (series of optical and electrical), reported in GHz elsewhere."""
        return 1.0 / math.sqrt(1.0 / self.f_opt**2 + 1.0 / self.f_elec**2)

    def H2_norm(self, f):
        """|H_PD(f)/R_resp|^2  — normalized, DC = 1."""
        h_opt2 = 1.0 / (1.0 + (f / self.f_opt) ** 2) ** self.n_opt
        h_elec2 = 1.0 / (1.0 + (f / self.f_elec) ** 2)
        return h_opt2 * h_elec2


# ----------------------------------------------------------------------------
# Metric
# ----------------------------------------------------------------------------
def irn_avg(tia: TIA, pd: Photodiode, fN: float, n_pts: int = 200_001,
            floor: float = 1e-3):
    """
    IRN_avg = sqrt(∫_0^fN  i_n,in^2 / |H_PD/R|^2  df) / sqrt(fN)   [A/sqrt(Hz)]

    `floor` clamps the PD response from below so the 1/|H|^2 division can't blow
    up to a non-physical infinity past the roll-off (a real RX has finite EQ).
    Returns (irn_avg, f_grid, optical_referred_psd).
    """
    f = np.linspace(0.0, fN, n_pts)
    psd_tia = tia.psd_referred_to_tia_input(f, pd.C_J)
    h2 = np.maximum(pd.H2_norm(f), floor)
    psd_opt = psd_tia / h2
    total = np.trapz(psd_opt, f)          # [A^2]   (rms^2)
    irn = math.sqrt(total) / math.sqrt(fN)  # [A/sqrt(Hz)]
    return irn, f, psd_opt


def find_crossover(f, psd_a, psd_b):
    """First frequency where psd_b drops below psd_a (PD_2 overtakes PD_1)."""
    diff = psd_b - psd_a
    sign = np.sign(diff)
    idx = np.where(np.diff(sign) != 0)[0]
    return f[idx[0]] if len(idx) else None


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fN", type=float, default=56e9,
                    help="Nyquist / integration upper limit [Hz] (default 56e9)")
    ap.add_argument("--no-plot", action="store_true", help="skip the PNG plot")
    args = ap.parse_args()

    tia = TIA()

    # --- the two diodes from the discussion ---------------------------------
    # PD_1: low C_J, but OPTICALLY limited -> early, somewhat steep optical pole.
    #       electrical BW >60 GHz (set by the small C_J). Combined ~31 GHz.
    pd1 = Photodiode(name="PD_1 (25 fF, opt-limited)", C_J=25e-15,
                     f_opt=31.5e9, n_opt=2)   # n_opt=2 -> steeper-than-RC optical roll-off
    # PD_2: higher C_J, balanced optical/electrical -> combined ~45 GHz.
    pd2 = Photodiode(name="PD_2 (50 fF, balanced)", C_J=50e-15,
                     f_opt=63e9, n_opt=1)     # opt and elec poles land close together

    print("=" * 70)
    print(f"IRN_avg comparison   (integration to Nyquist fN = {args.fN/1e9:.0f} GHz)")
    print("=" * 70)
    print(f"TIA: R_F={tia.R_F:.0f} ohm, gm={tia.gm*1e3:.0f} mS, "
          f"gamma={tia.gamma}, C_fixed(pad+ESD+Cgs)={tia.C_fixed*1e15:.0f} fF")
    print("-" * 70)

    results = {}
    for pd in (pd1, pd2):
        irn, f, psd = irn_avg(tia, pd, args.fN)
        results[pd.name] = (irn, f, psd, pd)
        print(f"{pd.name}")
        print(f"    C_J            = {pd.C_J*1e15:5.1f} fF")
        print(f"    f_opt          = {pd.f_opt/1e9:5.1f} GHz (pole order {pd.n_opt})")
        print(f"    f_elec(C_J)    = {pd.f_elec/1e9:5.1f} GHz")
        print(f"    f_PD combined  = {pd.f_pd/1e9:5.1f} GHz")
        print(f"    C_in total     = {(tia.C_fixed+pd.C_J)*1e15:5.1f} fF")
        print(f"    >>> IRN_avg    = {irn*1e12:6.3f} pA/sqrt(Hz)")
        print("-" * 70)

    irn1 = results[pd1.name][0]
    irn2 = results[pd2.name][0]
    improvement = (irn1 - irn2) / irn1 * 100.0
    print(f"PD_2 vs PD_1:  IRN_avg change = {improvement:+.1f} %  "
          f"({'improvement' if improvement > 0 else 'worse'})")
    print("Expected from the discussion: 20–30% improvement with PD_2.")
    print("=" * 70)

    if args.no_plot:
        return

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib not installed -> skipping plot; "
              "pip install matplotlib --break-system-packages)")
        return

    f1 = results[pd1.name][1]
    psd1 = results[pd1.name][2]
    psd2 = results[pd2.name][2]
    xover = find_crossover(f1, psd1, psd2)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    # sqrt(PSD) in pA/sqrt(Hz) is the readable y-axis
    ax.semilogy(f1/1e9, np.sqrt(psd1)*1e12, label=pd1.name, lw=2)
    ax.semilogy(f1/1e9, np.sqrt(psd2)*1e12, label=pd2.name, lw=2)
    ax.axvline(args.fN/1e9, ls="--", color="0.5", lw=1)
    ax.text(args.fN/1e9, ax.get_ylim()[1], "  Nyquist", va="top", color="0.4", fontsize=9)
    if xover is not None:
        ax.axvline(xover/1e9, ls=":", color="crimson", lw=1)
        ax.text(xover/1e9, ax.get_ylim()[0]*1.3,
                f"  crossover {xover/1e9:.0f} GHz", color="crimson", fontsize=9)
    ax.set_xlabel("Frequency [GHz]")
    ax.set_ylabel(r"Optical-referred noise  $\sqrt{i_{n,opt}^2}$  [pA/$\sqrt{\mathrm{Hz}}$]")
    ax.set_title("Optical-referred input noise: PD bandwidth vs. capacitance\n"
                 f"IRN_avg(PD_1)={irn1*1e12:.2f}, IRN_avg(PD_2)={irn2*1e12:.2f} pA/√Hz "
                 f"({improvement:+.0f}%)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = __file__.rsplit("/", 1)[0] + "/pd_noise_compare.png"
    fig.savefig(out, dpi=130)
    print(f"\nPlot written -> {out}")


if __name__ == "__main__":
    main()
