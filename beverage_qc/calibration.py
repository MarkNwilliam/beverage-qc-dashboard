"""Instrument calibration management (ISO/IEC 17025 clause 6.5 traceability).

A pH meter, refractometer and CO2 analyzer on a bottling line are only as good as the
chain of comparisons that ties them back to a national standard. This module models
the bookkeeping a Quality Controller keeps:

    * Instrument — a piece of QC equipment with an ID, type, due date and an
      uncertainty budget.
    * calibrate  — log a calibration event (as-found drift, result, new due date)
      using interval management akin to ILAC-G24.
    * schedule_due / calibration_status — which instruments are due / overdue.

The model is deliberately small and dependency-free; every instrument carries a
traceability note so an auditor can follow the paper trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional


@dataclass
class Instrument:
    """A piece of QC test equipment and its calibration record."""

    instrument_id: str
    name: str
    calibration_type: str  # e.g. "refractometer", "pH meter", "CO2 analyzer"
    traceability: str  # e.g. "NIST-traceable reference standard, CMC-based"
    uncertainty: float  # expanded uncertainty (k=2) of the instrument
    interval_days: int = 365
    last_calibration: Optional[date] = None
    notes: str = ""
    reference: str = ""  # e.g. "DM 9.1", a specific SOP/reference doc

    def next_due(self, today: Optional[date] = None) -> Optional[date]:
        if self.last_calibration is None:
            return None
        today = today or date.today()
        return self.last_calibration + timedelta(days=self.interval_days)

    @property
    def status(self) -> str:
        due = self.next_due()
        if due is None:
            return "never-calibrated"
        today = date.today()
        if due < today:
            return "overdue"
        if (due - today).days <= 7:
            return "due-soon"
        return "in-spec"


def calibrate(
    instrument: Instrument,
    on_date: date,
    as_found_drift: float = 0.0,
    acceptable: bool = True,
    result_note: str = "",
) -> Dict:
    """Record a calibration event and roll the instrument's due date forward.

    Returns a dict describing the event (for an audit log). ILAC-G24 guidance:
    if as-found drift is small, keep the interval; if it is large relative to the
    tolerance, the interval should have been shorter.
    """
    instrument.last_calibration = on_date
    event = {
        "instrument_id": instrument.instrument_id,
        "name": instrument.name,
        "date": on_date.isoformat(),
        "as_found_drift": as_found_drift,
        "acceptable": acceptable,
        "next_due": (on_date + timedelta(days=instrument.interval_days)).isoformat(),
        "result_note": result_note,
    }
    return event


def schedule_due(
    instruments: List[Instrument], today: Optional[date] = None
) -> Dict[str, List[Instrument]]:
    """Bucket instruments by status: in-spec / due-soon / overdue / never-calibrated."""
    today = today or date.today()
    buckets = {"in-spec": [], "due-soon": [], "overdue": [], "never-calibrated": []}
    for inst in instruments:
        status = inst.status
        if inst.last_calibration is None:
            buckets["never-calibrated"].append(inst)
        else:
            buckets[status].append(inst)
    return buckets


def calibration_status(instruments: List[Instrument]) -> Dict[str, int]:
    """Return a status->count tally for a whole register."""
    buckets = schedule_due(instruments)
    return {k: len(v) for k, v in buckets.items()}
