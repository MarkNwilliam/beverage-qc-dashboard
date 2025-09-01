"""Conformity assessment with guard bands (ILAC-G8 / ISO 17025 clause 7.8.6).

When a batch measurement carries measurement uncertainty u, judging "in spec" by
comparing the raw value to the limit is not enough: a value just inside the limit
could be out of spec once uncertainty is considered. A *guard band* shrinks the
acceptance region so a decision is made with confidence:

    acceptance band = limit +/- g, where g = guard factor * u

Standard guard factors (ILAC-G8) for a 95% confidence decision with approximately
normal uncertainty:
    g = 1.64 * u   (only an upper limit)
    g = 1.65 * u   (only a lower limit)
    g = 1.65 * u   (both limits, one-sided each)

We expose guard_band() (how big is the band) and conformity_decision() (pass/fail
with the guard applied), plus a risk estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt

#: Common ILAC-G8 guard factors (coverage ~95%).
GUARD_FACTORS = {
    "upper_only": 1.64,
    "lower_only": 1.65,
    "both": 1.65,
}


def _normal_cdf(z: float) -> float:
    """Standard normal CDF via erf (no scipy dependency)."""
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def guard_band(uncertainty: float, mode: str = "both") -> float:
    """Return the guard band width for a given expanded uncertainty."""
    return GUARD_FACTORS.get(mode, 1.65) * uncertainty


@dataclass
class ConformityResult:
    """Result of a guarded conformity decision."""

    parameter: str
    measured: float
    uncertainty: float
    lower: float
    upper: float
    guard: float
    decision: str  # "conform" | "nonconform" | "inconclusive"
    risk: float  # probability the true value falls outside spec


def conformity_decision(
    parameter: str,
    measured: float,
    uncertainty: float,
    lower: float,
    upper: float,
    mode: str = "both",
) -> ConformityResult:
    """Decide conformity of a measurement against a spec, applying a guard band.

    The guard band is subtracted from the spec limits to shrink the acceptance
    region; a measured value must fall inside the shrunk band to be judged
    "conform", otherwise we refuse to claim conformity (inconclusive) rather than
    risk a false pass. This is the recommendation of ILAC-G8 for a conservative
    decision rule.
    """
    g = guard_band(uncertainty, mode)

    lo_guard = lower + g if lower is not None else None
    hi_guard = upper - g if upper is not None else None

    if lo_guard is not None and hi_guard is not None:
        if lo_guard < hi_guard:
            in_guard = lo_guard <= measured <= hi_guard
        else:
            # uncertainty so large the guard bands overlap -> never confident
            in_guard = False
    elif lo_guard is not None:
        in_guard = measured >= lo_guard
    elif hi_guard is not None:
        in_guard = measured <= hi_guard
    else:
        in_guard = True

    # naive (no-guard) conformity for the risk estimate
    naive = (measured >= lower and measured <= upper) if (lower is not None and upper is not None) else True

    if in_guard:
        decision = "conform"
    elif naive:
        decision = "inconclusive"
    else:
        decision = "nonconform"

    # Estimate the probability the true value falls outside the spec, assuming the
    # measurement error is normal with the given uncertainty.
    p_out = 0.0
    if lower is not None and upper is not None:
        p_out = _normal_cdf((lower - measured) / uncertainty) + (
            1.0 - _normal_cdf((upper - measured) / uncertainty)
        )
    elif lower is not None:
        p_out = _normal_cdf((lower - measured) / uncertainty)
    elif upper is not None:
        p_out = 1.0 - _normal_cdf((upper - measured) / uncertainty)
    p_out = min(max(p_out, 0.0), 1.0)

    return ConformityResult(
        parameter=parameter,
        measured=measured,
        uncertainty=uncertainty,
        lower=lower,
        upper=upper,
        guard=g,
        decision=decision,
        risk=p_out,
    )
