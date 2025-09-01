"""End-to-end demo of the beverage QC toolkit.

Simulates a shift's QC activity on a carbonated soft-drink line and prints a
readable report: batch conformity, SPC verdict per parameter, a conformity
decision with a guard band, and calibration status. This is the same workflow a
Quality Controller walks on the floor.

Run:  python examples/demo.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beverage_qc.audit import Audit, Finding, closing_summary
from beverage_qc.calibration import Instrument, calibration_status
from beverage_qc.conformity import conformity_decision
from beverage_qc.data import generate_batches
from beverage_qc.qc import evaluate_batch, make_batch
from beverage_qc.spc import detect_drift_summary


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def main() -> None:
    # 1) A clean run: everything in spec
    section("1) Clean production run — batch conformity")
    clean = generate_batches(n=12, fault_step_at=9999)
    for row in clean:
        batch = make_batch(
            row["batch_id"],
            row["values"],
            product=row["product"],
            line=row["line"],
            operator=row["operator"],
            timestamp=row["timestamp"],
        )
        result = evaluate_batch(batch)
        print(f"  {row['batch_id']}: {result.overall.upper()}  (issues={result.issue_count})")

    # 2) A drifting run, caught by SPC
    section("2) Drifting Brix — does SPC catch it?")
    drifty = generate_batches(n=60, drift_brix=0.01, fault_step_at=9999)
    brix_series = [r["values"]["Brix (20C)"] for r in drifty]
    summary = detect_drift_summary("Brix (20C)", brix_series, target=11.0)
    print(f"  series n={summary.n}  mean={summary.mean:.3f}  std={summary.std:.3f}")
    print(f"  shewhart_violations={summary.shewhart_violations}  cusum_alarms={summary.cusum_alarms}")
    print(f"  verdict: {summary.verdict.upper()}")

    # 3) Conformity decision with a guard band
    section("3) Guard-band conformity decision (ILAC-G8, k=2 uncertainty)")
    dec = conformity_decision("pH", measured=3.18, uncertainty=0.05, lower=2.5, upper=3.2)
    print(f"  pH=3.18 ±0.05 vs [2.5, 3.2]: guard={dec.guard:.3f} decision={dec.decision.upper()}")
    print(f"  estimated risk of being out-of-spec: {dec.risk*100:.2f}%")

    # 4) Calibration status
    section("4) Calibration register status")
    instruments = [
        Instrument("RF-01", "Refractometer", "refractometer",
                   "NIST-traceable, CMC-based", 0.02, 180, date(2024, 1, 1)),
        Instrument("PH-02", "pH meter", "pH meter",
                   "NIST-traceable buffer set", 0.03, 90, date(2026, 7, 15)),
        Instrument("CO2-03", "CO2 analyzer", "CO2 analyzer",
                   "Cal-gas traceable", 0.05, 120, date(2026, 8, 20)),
        Instrument("TB-04", "Torque tester", "torque tester",
                   "Manufacturer reference", 0.1, 365, date(2026, 9, 1)),
    ]
    for s, n in calibration_status(instruments).items():
        print(f"  {s:>16}: {n}")

    # 5) Audit close-out
    section("5) Internal audit close-out")
    audit = Audit("AUD-2026-01", "Packaging & Filling", date(2026, 8, 10), "M. Nkugwa")
    audit.add_finding(Finding("F-01", "Filling", "torn filler gasket", "major",
                              "replace gasket, re-qualify", date(2026, 8, 25), "closed"))
    audit.add_finding(Finding("F-02", "Lab", "buffer past expiry", "minor",
                              "inventory buffer rotation", date(2026, 9, 10), "open"))
    summ = closing_summary(audit.findings)
    print(f"  total={summ['total']} closed={summ['closed']} open={summ['open']} "
          f"overdue={summ['overdue']} closure_rate={summ['closure_rate']:.0%}")
    print(f"  majors={audit.major_count} minors={audit.minor_count}")


if __name__ == "__main__":
    main()
