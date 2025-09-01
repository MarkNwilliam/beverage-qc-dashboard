"""beverage_qc — a quality-control toolkit for carbonated soft-drink / beverage production.

Mirrors the day-to-day discipline a Quality Controller in a bottling plant keeps:
    * batch testing (brix, pH, color, CO2, sensory)
    * statistical process control (Shewhart / CUSUM control charts)
    * conformity decisions with guard bands (ILAC-G8 style, ISO 17025 clause 7.8.6)
    * calibration scheduling / traceability (ISO/IEC 17025 clause 6.5)
    * HACCP food-safety hazard control
    * internal audits and CAPA tracking

Everything is built from first principles (ISO 4126 / ICUMSA / GUM / ILAC-G8) so
every number is traceable to a published standard or formula — the same discipline
regulated food & beverage environments demand.
"""

from .qc import BatchResult, ParameterSpec, make_batch, evaluate_batch
from .spc import control_limits, shewhart, cusum, detect_drift_summary
from .conformity import conformity_decision, guard_band
from .calibration import Instrument, calibrate, schedule_due, calibration_status

__all__ = [
    "BatchResult",
    "ParameterSpec",
    "make_batch",
    "evaluate_batch",
    "control_limits",
    "shewhart",
    "cusum",
    "detect_drift_summary",
    "conformity_decision",
    "guard_band",
    "Instrument",
    "calibrate",
    "schedule_due",
    "calibration_status",
]
__version__ = "0.1.0"
