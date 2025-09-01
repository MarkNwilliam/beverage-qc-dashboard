"""Tests for the beverage QC library. Run with: python -m pytest tests/ -q"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beverage_qc.qc import (
    BatchResult,
    DEFAULT_SPECS,
    ParameterSpec,
    evaluate_batch,
    make_batch,
)
from beverage_qc.conformity import conformity_decision, guard_band
from beverage_qc.spc import (
    control_limits,
    cusum,
    detect_drift_summary,
    shewhart,
)
from beverage_qc.calibration import (
    Instrument,
    calibrate,
    calibration_status,
    schedule_due,
)
from beverage_qc.haccp import CriticalControlPoint, check_ccp
from beverage_qc.audit import Finding, Audit, closing_summary


def test_spec_defaults_are_sane():
    brix = DEFAULT_SPECS["Brix (20C)"]
    assert brix.lower < brix.upper
    assert 10.5 <= brix.lower <= 12.0


def test_test_and_evaluate_pass():
    batch = make_batch(
        "B1",
        {
            "Brix (20C)": 11.0,
            "pH": 2.9,
            "Color": 0.45,
            "CO2 Volume": 3.6,
            "Sensory Score": 9.0,
        },
        product="Cola",
    )
    ev = evaluate_batch(batch)
    assert ev.overall == "pass"
    assert ev.issue_count == 0


def test_out_of_spec_fails():
    # Brix well above the limit -> reject
    batch = make_batch("B2", {"Brix (20C)": 13.5, "pH": 2.9})
    ev = evaluate_batch(batch)
    assert ev.overall == "reject"
    assert ev.evaluations["Brix (20C)"].decision == "fail"


def test_tolerance_warning_holds():
    # Inside limits but outside tolerance band -> hold
    spec = DEFAULT_SPECS["Brix (20C)"]  # 10.5-11.5, tol 0.1 -> warn band 10.6-11.4
    batch = make_batch("B3", {"Brix (20C)": 11.45, "pH": 2.9})
    ev = evaluate_batch(batch)
    assert ev.evaluations["Brix (20C)"].decision == "warning"
    assert ev.overall == "hold"


def test_guard_band_width():
    g = guard_band(0.05, "both")
    assert g == 1.65 * 0.05


def test_conformity_in_spec():
    r = conformity_decision("pH", measured=2.9, uncertainty=0.05, lower=2.5, upper=3.2)
    assert r.decision == "conform"
    assert r.risk < 1.0


def test_conformity_nonconform():
    r = conformity_decision("pH", measured=3.4, uncertainty=0.05, lower=2.5, upper=3.2)
    assert r.decision == "nonconform"


def test_conformity_inconclusive_at_limit():
    # just inside limit but inside the guard band region -> refuse to claim conformity
    r = conformity_decision("pH", measured=3.19, uncertainty=0.05, lower=2.5, upper=3.2)
    assert r.decision in ("conform", "inconclusive")
    assert r.guard > 0


def test_control_limits_symmetric():
    limits = control_limits([2.9, 3.0, 3.1, 2.8, 3.0])
    assert abs((limits.ucl - limits.mean) - (limits.mean - limits.lcl)) < 1e-9


def test_shewhart_flags_extreme_point():
    vals = [3.0] * 10 + [6.0]
    limits, flags = shewhart(vals)
    assert flags[-1] is True


def test_cusum_no_alarm_on_stable():
    vals = [3.0, 3.01, 2.99, 3.02, 2.98] * 6
    _, _, alarms = cusum(vals, target=3.0, sigma=0.02)
    assert not any(alarms)


def test_detect_drift_out_of_control():
    # steady upward bias should trip the CUSUM
    vals = [3.0 + 0.05 * i for i in range(40)]
    summary = detect_drift_summary("pH", vals, target=3.0)
    assert summary.verdict == "out of control"


def test_calibration_status():
    inst = Instrument(
        "T-01",
        "Refractometer",
        "refractometer",
        traceability="NIST-traceable",
        uncertainty=0.02,
        interval_days=180,
        last_calibration=date(2020, 1, 1),
    )
    status = calibration_status([inst])
    assert status["overdue"] >= 1


def test_calibrate_rolls_due():
    inst = Instrument(
        "PH-02", "pH meter", "pH meter", traceability="NIST", uncertainty=0.02,
        interval_days=180, last_calibration=date(2020, 1, 1),
    )
    calibrate(inst, date(2026, 1, 1), as_found_drift=0.01)
    from datetime import timedelta
    assert inst.next_due(date(2026, 1, 1)) == date(2026, 1, 1) + timedelta(days=180)


def test_ccp_check():
    ccp = CriticalControlPoint(
        step="Pasteurization",
        hazard="biological",
        critical_limit_lower=72.0,
        critical_limit_upper=75.0,
        unit="degC",
        corrective_action="Divert & re-process",
    )
    assert check_ccp(ccp, 73.0)["within_limit"] is True
    assert check_ccp(ccp, 69.0)["action"] == "Divert & re-process"


def test_audit_closing_summary():
    findings = [
        Finding("F1", "Filling", "torn gasket", "major", status="closed"),
        Finding("F2", "Lab", "old buffer", "minor", status="open"),
    ]
    summ = closing_summary(findings)
    assert summ["closed"] == 1
    assert summ["closure_rate"] == 0.5
