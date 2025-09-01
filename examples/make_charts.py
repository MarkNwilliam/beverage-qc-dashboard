"""Generates the README/dashboard figures demonstrating the QC toolkit.

Produces PNG charts into docs/ showing:
  * a Shewhart + CUSUM control-chart pair catching Brix drift,
  * a guard-band conformity diagram,
  * a batch-conformity summary bar chart.

Run:  python examples/make_charts.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beverage_qc.data import generate_batches
from beverage_qc.spc import control_limits, cusum, shewhart
from beverage_qc.qc import DEFAULT_SPECS

DOCS = Path(__file__).resolve().parents[1] / "docs"
DOCS.mkdir(exist_ok=True)


def chart_control_pair() -> None:
    """Shewhart + CUSUM on a Brix series with slow drift."""
    rows = generate_batches(n=60, drift_brix=0.012, fault_step_at=9999)
    series = [r["values"]["Brix (20C)"] for r in rows]
    x = list(range(len(series)))

    limits, flags = shewhart(series)
    s_hi, s_lo, alarms = cusum(series, target=11.0, sigma=limits.sigma, k=0.5, h=5.0)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax = axes[0]
    ax.plot(x, series, color="#1565c0", label="Brix (20C)", linewidth=1.5)
    ax.axhline(limits.ucl, color="red", ls="--", label=f"UCL ({limits.ucl:.2f})")
    ax.axhline(limits.lcl, color="red", ls="--", label=f"LCL ({limits.lcl:.2f})")
    ax.axhline(limits.mean, color="green", ls=":", label=f"mean ({limits.mean:.2f})")
    for xi, f in zip(x, flags):
        if f:
            ax.plot(xi, series[xi], "ro", ms=8)
    ax.set_ylabel("Brix (20C)")
    ax.set_title("Shewhart X-bar chart — slow Brix drift (no point out of limits)")
    ax.legend(fontsize=8, loc="lower right")

    ax = axes[1]
    ax.plot(x, s_hi, color="#c62828", label="CUSUM+ (above target)", linewidth=1.5)
    ax.plot(x, s_lo, color="#4527a0", label="CUSUM- (below target)", linewidth=1.5)
    ax.axhline(5.0, color="black", ls="--", label="decision threshold h=5")
    # shade alarm regions
    hi_arr = np.array(s_hi)
    lo_arr = np.array(s_lo)
    ax.fill_between(x, hi_arr, 5.0, where=hi_arr > 5.0, color="red", alpha=0.25)
    ax.fill_between(x, lo_arr, 5.0, where=lo_arr > 5.0, color="purple", alpha=0.25)
    ax.set_xlabel("Batch number")
    ax.set_ylabel("CUSUM statistic (sigma units)")
    ax.set_title(f"CUSUM — CUSUM catches the drift ({sum(alarms)} alarms)")
    ax.legend(fontsize=8, loc="upper left")

    fig.tight_layout()
    fig.savefig(DOCS / "brix_control_pair.png", dpi=140)
    plt.close(fig)
    print("wrote docs/brix_control_pair.png")


def chart_guard_band() -> None:
    """Diagram of a guarded conformity decision on pH."""
    lower, upper = 2.5, 3.2
    measured = 3.18
    u = 0.05
    g = 1.65 * u

    x = np.linspace(2.2, 3.6, 400)
    # normal density centred on the measured value
    y = (1 / (u * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - measured) / u) ** 2)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(x, y, color="#1565c0", linewidth=2)
    # spec region
    ax.axvspan(lower, upper, color="green", alpha=0.18, label="in-spec region")
    # guard band region (shrunk acceptance)
    ax.axvspan(lower, lower + g, color="orange", alpha=0.35)
    ax.axvspan(upper - g, upper, color="orange", alpha=0.35, label="guard band (ILAC-G8)")
    ax.axvline(measured, color="black", ls="--", label=f"measured={measured}")
    ax.axvline(lower, color="green", ls=":")
    ax.axvline(upper, color="green", ls=":")
    ax.set_xlabel("pH")
    ax.set_ylabel("probability density")
    ax.set_title(
        f"Guarded conformity decision: pH={measured} ±{u} vs [{lower}, {upper}]\n"
        "measured sits in the guard band -> 'inconclusive', not a confident pass"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS / "guard_band.png", dpi=140)
    plt.close(fig)
    print("wrote docs/guard_band.png")


def chart_batch_conformity() -> None:
    """Bar chart of batch conformity across a production window."""
    rows = generate_batches(n=30, fault_step_at=9999)
    from beverage_qc.qc import evaluate_batch, make_batch

    decisions = []
    for r in rows:
        b = make_batch(r["batch_id"], r["values"])
        decisions.append(evaluate_batch(b).overall)

    colors = {"pass": "#2e7d32", "hold": "#f9a825", "reject": "#c62828"}
    fig, ax = plt.subplots(figsize=(10, 3.5))
    bars = ax.bar(range(len(decisions)), [1] * len(decisions), color=[colors[d] for d in decisions])
    ax.bar(range(len(decisions)), [1] * len(decisions),
           color=[colors[d] for d in decisions], edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(decisions)))
    ax.set_xticklabels([r["batch_id"] for r in rows], rotation=90, fontsize=6)
    ax.set_yticks([])
    ax.set_title(f"Batch conformity over {len(rows)} batches "
                 f"({decisions.count('pass')} pass / {decisions.count('hold')} hold / "
                 f"{decisions.count('reject')} reject)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=colors[k], label=k) for k in colors], loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(DOCS / "batch_conformity.png", dpi=140)
    plt.close(fig)
    print("wrote docs/batch_conformity.png")


def main() -> None:
    chart_control_pair()
    chart_guard_band()
    chart_batch_conformity()


if __name__ == "__main__":
    main()
