"""Statistical process control (SPC) for batch quality data.

A bottling line drifts. A slightly warmer syrup, a worn pH probe, a fouled carbonator
— each creeps into the product one batch at a time. Control charts are how a Quality
Controller sees a process move before a batch is ever out of spec.

We implement two workhorse charts, both from first principles (no sklearn):

* Shewhart X-bar chart — mean +/- 3 sigma control limits. Good at catching a single
  point that strays far from the mean (a step fault, a bad reading).
* CUSUM chart — accumulates every small deviation from a target; a persistent bias of
  a fraction of a sigma grows the cumulative sum until it crosses a decision
  threshold h. Blind to a single wild point but razor-sharp on slow drift.

Both are standard ASQC/ISO 7870-1 techniques straight out of the metrology /
quality-control handbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class ControlLimits:
    """Control-limit object for a Shewhart chart."""

    mean: float
    ucl: float
    lcl: float
    sigma: float
    n: int
    limits_width: float = 3.0  # multiples of sigma

    def is_out(self, value: float) -> bool:
        return value > self.ucl or value < self.lcl


def control_limits(values: List[float], width: float = 3.0) -> ControlLimits:
    """Compute Shewhart X-bar control limits from a process-history series.

    Uses the sample mean and the standard deviation of the series:
        UCL = mean + width * sigma
        LCL = mean - width * sigma
    """
    arr = np.asarray(values, dtype=float)
    mean = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    return ControlLimits(mean, mean + width * sigma, mean - width * sigma, sigma, len(arr), width)


def shewhart(
    values: List[float], limits: Optional[ControlLimits] = None, width: float = 3.0
) -> tuple:
    """Run a Shewhart chart over values; return (limits, out_flags).

    out_flags is a boolean mask marking points that violate the control limits.
    """
    limits = limits or control_limits(values, width)
    out_flags = [limits.is_out(v) for v in values]
    return limits, out_flags


def cusum(
    values: List[float],
    target: float,
    sigma: float,
    k: float = 0.5,
    h: float = 5.0,
) -> tuple:
    """Tabular CUSUM (ISO 7870-1 / Montgomery).

    * k  = the reference value (allowable slack), in units of sigma
    * h  = the decision interval / threshold, in units of sigma

    Two accumulators, one for a positive shift above target (S_hi) and one for a
    negative shift below target (S_lo). A point crosses h when drift has built up
    beyond tolerance. Returns (S_hi, S_lo, alarm_flags).
    """
    S_hi: List[float] = []
    S_lo: List[float] = []
    alarms: List[bool] = []

    prev_hi = 0.0
    prev_lo = 0.0
    for v in values:
        std = (v - target) / sigma if sigma > 0 else 0.0
        prev_hi = max(0.0, prev_hi + std - k)
        prev_lo = max(0.0, prev_lo - std - k)
        S_hi.append(prev_hi)
        S_lo.append(prev_lo)
        alarms.append(prev_hi > h or prev_lo > h)

    return S_hi, S_lo, alarms


@dataclass
class DriftSummary:
    """Concise summary of what SPC found in a quality series."""

    series_name: str
    n: int
    mean: float
    std: float
    shewhart_violations: int
    cusum_alarms: int
    verdict: str  # "in control" | "review" | "out of control"

    def as_dict(self) -> dict:
        return {
            "series": self.series_name,
            "n": self.n,
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "shewhart_violations": self.shewhart_violations,
            "cusum_alarms": self.cusum_alarms,
            "verdict": self.verdict,
        }


def detect_drift_summary(
    series_name: str,
    values: List[float],
    target: Optional[float] = None,
    k: float = 0.5,
    h: float = 5.0,
    width: float = 3.0,
) -> DriftSummary:
    """Run both charts over a QC series and summarize.

    Verdict:
        out of control  -> CUSUM alarmed (persistent drift) or >=2 Shewhart violations
        review          -> exactly 1 Shewhart violation (possible step)
        in control      -> nothing fired
    """
    arr = np.asarray(values, dtype=float)
    limits, out_flags = shewhart(list(arr), width=width)
    tgt = float(np.mean(arr)) if target is None else float(target)
    _, _, cusum_alarms = cusum(list(arr), target=tgt, sigma=limits.sigma, k=k, h=h)

    n_shep = int(sum(out_flags))
    n_cusum = int(sum(cusum_alarms))

    if n_cusum > 0 or n_shep >= 2:
        verdict = "out of control"
    elif n_shep == 1:
        verdict = "review"
    else:
        verdict = "in control"

    return DriftSummary(
        series_name=series_name,
        n=len(arr),
        mean=float(np.mean(arr)),
        std=limits.sigma,
        shewhart_violations=n_shep,
        cusum_alarms=n_cusum,
        verdict=verdict,
    )
