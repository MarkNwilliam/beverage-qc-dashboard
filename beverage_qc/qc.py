"""Batch quality-control testing for carbonated soft drinks.

A Quality Controller pulls a finished-goods sample from a line and measures the
parameters that define "in-spec": brix (dissolved solids via refractometer, ICUMSA
Brix-20), titratable pH, color (Absorbance Units, EBC/ICUMSA-style), CO2 volume
(carbonation at 20 degC), and sensory. Each measurement is compared to a spec
(lower/upper limit) with a tolerance band.

This module supplies:
    * ParameterSpec  — a named spec with lower/upper limits and units
    * BatchResult    — one sampled batch with measured values per parameter
    * make_batch     — produce a BatchResult from raw measurements
    * evaluate_batch — judge each parameter against its spec and return a decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

@dataclass
class ParameterSpec:
    """A single quality parameter's specification (lower/upper limit)."""

    lower: float
    upper: float
    units: str = ""
    tolerance: float = 0.0
    critical: bool = False
    description: str = ""


#: Standard QC parameters for a carbonated soft drink, with typical bottler limits.
#: Units and limits are representative of a generic CSD and configurable per plant.
DEFAULT_SPECS: Dict[str, "ParameterSpec"] = {
    "Brix (20C)": ParameterSpec(10.5, 11.5, "deg Brix", tolerance=0.1),
    "pH": ParameterSpec(2.5, 3.2, "pH", tolerance=0.05),
    "Color": ParameterSpec(0.30, 0.60, "AU", tolerance=0.02),
    "CO2 Volume": ParameterSpec(3.0, 4.2, "vol", tolerance=0.1),
    "Sensory Score": ParameterSpec(0.0, 10.0, "score", tolerance=0.0),
}


@dataclass
class BatchResult:
    """The measured quality results for one production batch / sample."""

    batch_id: str
    product: str = ""
    line: str = ""
    operator: str = ""
    timestamp: str = ""
    values: Dict[str, float] = field(default_factory=dict)

    def get(self, name: str) -> Optional[float]:
        return self.values.get(name)


def make_batch(
    batch_id: str,
    measurements: Dict[str, float],
    product: str = "",
    line: str = "",
    operator: str = "",
    timestamp: str = "",
) -> BatchResult:
    """Wrap a set of measured values into a BatchResult.

    measurements maps a parameter name (must exist in DEFAULT_SPECS or the specs you
    pass to evaluation) to its measured value, e.g.
        {"Brix (20C)": 11.0, "pH": 2.9, "Color": 0.45, "CO2 Volume": 3.6, ...}
    """
    return BatchResult(
        batch_id=batch_id,
        product=product,
        line=line,
        operator=operator,
        timestamp=timestamp,
        values=dict(measurements),
    )


@dataclass
class ParameterEvaluation:
    """Outcome of judging one parameter of a batch against its spec."""

    name: str
    measured: float
    lower: float
    upper: float
    within_tolerance: bool
    decision: str  # "pass" | "warning" | "fail"


@dataclass
class BatchEvaluation:
    """Aggregate outcome for a whole batch."""

    batch_id: str
    evaluations: Dict[str, ParameterEvaluation]
    overall: str  # "pass" | "hold" | "reject"
    issue_count: int = 0

    @property
    def issues(self) -> Dict[str, str]:
        return {
            name: ev.decision
            for name, ev in self.evaluations.items()
            if ev.decision != "pass"
        }


def _evaluate_one(
    name: str, measured: float, spec: ParameterSpec
) -> ParameterEvaluation:
    """Decide pass / warning / fail for a single parameter.

    Decision logic:
        fail      -> outside limits
        warning   -> inside limits but outside the tolerance band (a drift risk,
                     guards the spec so a batch is pulled before it goes out)
        pass      -> comfortably inside limits and tolerance
    """
    outside = measured < spec.lower or measured > spec.upper
    # tolerance is a margin from the limit; if exceeded the value is drifting off-spec
    within_tol = True
    if spec.tolerance > 0:
        within_tol = (
            (spec.lower + spec.tolerance) <= measured <= (spec.upper - spec.tolerance)
        )

    if outside:
        decision = "fail"
    elif not within_tol:
        decision = "warning"
    else:
        decision = "pass"

    return ParameterEvaluation(
        name=name,
        measured=measured,
        lower=spec.lower,
        upper=spec.upper,
        within_tolerance=within_tol,
        decision=decision,
    )


def evaluate_batch(
    batch: BatchResult, specs: Optional[Dict[str, ParameterSpec]] = None
) -> BatchEvaluation:
    """Judge a whole batch against its specs.

    Overall decision:
        reject -> any parameter fails
        hold   -> no fails but at least one warning (needs review, hold stock)
        pass   -> every parameter passes
    """
    specs = specs or DEFAULT_SPECS
    evals = {}
    for name, measured in batch.values.items():
        spec = specs.get(name)
        if spec is None:
            continue
        evals[name] = _evaluate_one(name, measured, spec)

    decisions = {e.decision for e in evals.values()}
    if "fail" in decisions:
        overall = "reject"
    elif "warning" in decisions:
        overall = "hold"
    else:
        overall = "pass"

    issue_count = sum(1 for e in evals.values() if e.decision != "pass")
    return BatchEvaluation(batch_id=batch.batch_id, evaluations=evals, overall=overall, issue_count=issue_count)
