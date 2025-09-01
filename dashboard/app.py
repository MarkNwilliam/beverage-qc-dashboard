"""Streamlit dashboard for the beverage QC toolkit.

This is a self-contained multi-page-ish single-file dashboard. Run with:

    streamlit run dashboard/app.py

It demonstrates everything a Quality Controller owns on a beverage line, rendered
from the underlying `beverage_qc` library:

    * Batch QC testing & conformity (brix, pH, color, CO2, sensory)
    * Statistical process control (Shewhart + CUSUM control charts)
    * Guard-band conformity decisions (ILAC-G8 / ISO 17025 cl. 7.8.6)
    * Calibration register & scheduling (ISO/IEC 17025 cl. 6.5)
    * HACCP food-safety critical-control-point checks
    * Internal audit & CAPA close-out
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beverage_qc.audit import Audit, Finding, closing_summary
from beverage_qc.calibration import Instrument, calibrate, calibration_status
from beverage_qc.conformity import conformity_decision
from beverage_qc.data import generate_batches
from beverage_qc.qc import DEFAULT_SPECS, evaluate_batch, make_batch
from beverage_qc.spc import control_limits, cusum, shewhart

st.set_page_config(page_title="Beverage QC Dashboard", layout="wide")


def color_of(decision: str) -> str:
    return {"pass": "#2e7d32", "hold": "#f9a825", "reject": "#c62828",
            "conform": "#2e7d32", "inconclusive": "#f9a825", "nonconform": "#c62828",
            "in control": "#2e7d32", "review": "#f9a825", "out of control": "#c62828",
            "in-spec": "#2e7d32", "due-soon": "#f9a825", "overdue": "#c62828",
            "never-calibrated": "#607d8b"}.get(decision, "#616161")


@st.cache(suppress_st_warning=True, allow_output_mutation=True, show_spinner=False)
def load_data(n=140, drift=0.012, fault_at=9999):
    rows = generate_batches(n=n, drift_brix=drift, fault_step_at=fault_at)
    return rows


# ----------------------------------------------------------------------------- sidebar
st.sidebar.title("Beverage QC")
st.sidebar.caption("Carbonated Soft-Drink Quality Control Toolkit")
page = st.sidebar.radio(
    "Go to",
    ["Overview", "Batch Testing", "SPC Control Charts", "Conformity (Guard Bands)",
     "Calibration", "HACCP", "Audit & CAPA"],
)
n_batches = st.sidebar.slider("Batches (simulated)", 40, 200, 140)
drift = st.sidebar.slider("Brix drift /batch", 0.0, 0.03, 0.012, 0.001)
st.sidebar.info("Example data is simulated for demo purposes. "
                "All analysis is the author's own independent QMS tooling, "
                "not affiliated with any beverage company.")

rows = load_data(n_batches, drift)

# ----------------------------------------------------------------------------- overview
if page == "Overview":
    st.title("Beverage Line Quality Control Dashboard")
    st.markdown(
        "A quality-control toolkit for a carbonated soft-drink bottling line, "
        "mirroring the day-to-day discipline of a Quality Controller: process "
        "monitoring, food safety, plant quality, calibration and auditing."
    )

    # KPI cards
    results = [evaluate_batch(make_batch(r["batch_id"], r["values"])) for r in rows]
    na = st.columns(5)
    na[0].metric("Batches reviewed", len(results))
    na[1].metric("Pass", sum(1 for r in results if r.overall == "pass"))
    na[2].metric("Hold", sum(1 for r in results if r.overall == "hold"))
    na[3].metric("Reject", sum(1 for r in results if r.overall == "reject"))
    na[4].metric("Yield (pass %)", f"{sum(1 for r in results if r.overall=='pass')/len(results)*100:.0f}%")

    st.markdown("### The QC workflow this dashboard exercises")
    st.markdown(
        "1. **Batch testing** — brix, pH, color, CO2, sensory vs. spec limits\n"
        "2. **SPC** — Shewhart + CUSUM control charts catch drift before batches go out\n"
        "3. **Conformity** — guard-band decisions (ILAC-G8) that refuse a false claim of conform\n"
        "4. **Calibration** — ISO/IEC 17025 traceability and scheduling\n"
        "5. **HACCP** — critical-control-point checks with corrective actions\n"
        "6. **Audit & CAPA** — findings and close-out"
    )

    st.image(str(Path(__file__).resolve().parents[1] / "docs" / "brix_control_pair.png"),
             caption="Shewhart (top) fails to see slow drift; CUSUM (bottom) catches it")

# ----------------------------------------------------------------------------- batch testing
elif page == "Batch Testing":
    st.title("Batch Testing & Conformity")
    st.markdown(
        "Each batch is pulled, measured against the five QC parameters and judged "
        "pass / hold / reject. A **hold** is inside limits but drifting toward the "
        "tolerance edge — stock is held for review so a batch never ships marginal."
    )

    spec_rows = []
    for name, spec in DEFAULT_SPECS.items():
        spec_rows.append({"parameter": name, "lower": spec.lower, "upper": spec.upper,
                          "units": spec.units, "tolerance": spec.tolerance})
    st.dataframe(pd.DataFrame(spec_rows), use_container_width=True)

    # conformity table
    table = []
    for r in rows:
        b = make_batch(r["batch_id"], r["values"], product=r["product"], line=r["line"])
        ev = evaluate_batch(b)
        row = {"batch": r["batch_id"], "operator": r["operator"], "timestamp": r["timestamp"]}
        for pname in ["Brix (20C)", "pH", "Color", "CO2 Volume", "Sensory Score"]:
            row[pname] = round(r["values"].get(pname, 0.0), 3)
        row["verdict"] = ev.overall
        table.append(row)
    df = pd.DataFrame(table)
    st.dataframe(df.style.map(lambda v: f"color: {color_of(v)}; font-weight:bold",
                              subset=["verdict"]), use_container_width=True)

    col = st.selectbox("Parameter distribution", list(DEFAULT_SPECS.keys()))
    vals = [r["values"][col] for r in rows]
    spec = DEFAULT_SPECS[col]
    st.line_chart(pd.Series(vals, name=col))

# ----------------------------------------------------------------------------- SPC
elif page == "SPC Control Charts":
    st.title("Statistical Process Control")
    st.markdown(
        "A Shewhart X-bar chart uses ±3 sigma control limits — good at catching a "
        "single stray point. A **CUSUM** accumulates every small deviation, so it "
        "catches slow drift that no single point reveals. Both sit on the same "
        "series here."
    )
    param = st.selectbox("Parameter", list(DEFAULT_SPECS.keys()))
    series = [r["values"][param] for r in rows]
    x = list(range(len(series)))

    limits, flags = shewhart(series)
    s_hi, s_lo, alarms = cusum(series, target=float(np.mean(series)),
                               sigma=limits.sigma, k=0.5, h=5.0)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Shewhart X-bar")
        out_count = int(sum(flags))
        st.metric("Out-of-limit points", out_count)
        df_s = pd.DataFrame({"batch": x, param: series,
                             "UCL": [limits.ucl] * len(x), "LCL": [limits.lcl] * len(x),
                             "mean": [limits.mean] * len(x)})
        st.line_chart(df_s.set_index("batch"))
    with c2:
        st.subheader("CUSUM")
        st.metric("CUSUM alarms", int(sum(alarms)))
        df_c = pd.DataFrame({"x": x, "CUSUM+": s_hi, "CUSUM-": s_lo,
                             "h": [5.0] * len(x)})
        st.line_chart(df_c.set_index("x"))

    verdict = "out of control" if (sum(alarms) or out_count >= 2) else ("review" if out_count == 1 else "in control")
    st.success(f"Process verdict: **{verdict.upper()}**")

# ----------------------------------------------------------------------------- conformity
elif page == "Conformity (Guard Bands)":
    st.title("Conformity Decisions with Guard Bands")
    st.markdown(
        "A measurement carries uncertainty `u`. Simply comparing the raw value to a "
        "limit can pass a measurement that is really out of spec. A **guard band** "
        "(ILAC-G8) shrinks the acceptance region by `g = guard * u`, so the QC "
        "function either confirms conformance or refuses to claim it."
    )
    col, lo, hi, unc = st.columns(4)
    param = col.selectbox("Parameter", list(DEFAULT_SPECS.keys()))
    spec = DEFAULT_SPECS[param]
    lo = lo.number_input("Lower limit", value=float(spec.lower))
    hi = hi.number_input("Upper limit", value=float(spec.upper))
    unc = unc.number_input("Uncertainty (k=2)", value=0.05, step=0.01)

    measured = st.slider("Measured value", float(spec.lower - 0.5),
                         float(spec.upper + 0.5), float((spec.lower + spec.upper) / 2), 0.01)
    dec = conformity_decision(param, measured, unc, lo, hi)
    st.metric("Guard band width", f"{dec.guard:.3f}", f"g = 1.65*u")
    st.markdown(f"Decision: **{dec.decision.upper()}** "
                f"&nbsp;(risk the true value is out-of-spec: {dec.risk*100:.1f}%)")
    st.image(str(Path(__file__).resolve().parents[1] / "docs" / "guard_band.png"),
             caption="Guarded conformity on pH — a value near the limit in the guard band is 'inconclusive'")

# ----------------------------------------------------------------------------- calibration
elif page == "Calibration":
    st.title("Calibration Register & Scheduling")
    st.markdown("Every QC instrument on the line is traceable to a reference and "
                "scheduled for calibration (ISO/IEC 17025 clause 6.5).")
    instruments = [
        Instrument("RF-01", "Refractometer", "refractometer",
                   "NIST-traceable, CMC-based", 0.02, 180, date(2026, 2, 10)),
        Instrument("PH-02", "pH meter", "pH meter",
                   "NIST-traceable buffer set", 0.03, 90, date(2026, 8, 1)),
        Instrument("CO2-03", "CO2 analyzer", "CO2 analyzer",
                   "Cal-gas traceable", 0.05, 120, date(2026, 8, 20)),
        Instrument("TB-04", "Torque tester", "torque tester",
                   "Manufacturer reference", 0.1, 365, date(2025, 12, 1)),
        Instrument("BW-05", "Bottle-weight scale", "mass", 
                   "Class M weights", 0.02, 180, date(2026, 9, 1)),
    ]
    tally = calibration_status(instruments)
    cols = st.columns(len(tally))
    for c, (k, v) in zip(cols, tally.items()):
        c.metric(k, v)

    data = []
    for inst in instruments:
        data.append({"ID": inst.instrument_id, "Name": inst.name, "Type": inst.calibration_type,
                     "Uncertainty": inst.uncertainty, "Interval (days)": inst.interval_days,
                     "Last": inst.last_calibration, "Next due": inst.next_due(),
                     "Status": inst.status})
    df = pd.DataFrame(data)
    st.dataframe(df.style.map(lambda v: f"color: {color_of(v)}", subset=["Status"]),
                 use_container_width=True)

# ----------------------------------------------------------------------------- HACCP
elif page == "HACCP":
    st.title("HACCP Critical Control Points")
    st.markdown("Each CCP has a critical limit (CL), a monitored reading is judged "
                "against it, and a corrective action fires when the limit is violated.")
    from beverage_qc.haccp import CriticalControlPoint, check_ccp, run_haccp_table

    ccp_table = run_haccp_table()
    for step in ccp_table:
        if step["CCP"]:
            ccp = CriticalControlPoint(
                step=step["step"], hazard=step["hazard"],
                critical_limit_lower=step["CL"]["lower"],
                critical_limit_upper=step["CL"]["upper"], unit=step["unit"],
                corrective_action=f"Divert {step['step'].lower()} & re-process")
            st.markdown(f"**{step['step']}** — {step['hazard']} "
                        f"(CL {step['CL']['lower']}–{step['CL']['upper']} {step['unit']})")

    step_name = st.selectbox("CCP step", [s["step"] for s in ccp_table if s["CCP"]])
    s = next(x for x in ccp_table if x["step"] == step_name)
    reading = st.slider("Monitored reading", float(s["CL"]["lower"] - 5),
                        float(s["CL"]["upper"] + 5), float((s["CL"]["lower"] + s["CL"]["upper"]) / 2))
    ccp = CriticalControlPoint(step=s["step"], hazard=s["hazard"],
                               critical_limit_lower=s["CL"]["lower"],
                               critical_limit_upper=s["CL"]["upper"], unit=s["unit"],
                               corrective_action=f"Divert {s['step'].lower()} & re-process")
    res = check_ccp(ccp, reading)
    st.metric("Within critical limit", "YES" if res["within_limit"] else "NO",
              res["action"] if not res["within_limit"] else "release")
    st.markdown(
        f"**CCP check:** {s['step']} reading = **{reading} {s['unit']}** "
        f"(CL {s['CL']['lower']}–{s['CL']['upper']} {s['unit']}) → "
        f"**{'RELEASE' if res['within_limit'] else res['action']}**")

# ----------------------------------------------------------------------------- audit
else:
    st.title("Internal Audit & CAPA")
    st.markdown("Findings from internal audits, their severity, and the corrective / "
                "preventive-action close-out the Quality Controller drives.")
    audit = Audit("AUD-2026-001", "Line 1 Packaging & Filling", date(2026, 8, 10), "M. Nkugwa")
    audit.add_finding(Finding("F-001", "Filling", "torn filler gasket", "major",
                              "replace gasket & re-qualify", date(2026, 8, 25), "closed"))
    audit.add_finding(Finding("F-002", "Lab", "buffer past expiry", "minor",
                              "inventory rotation", date(2026, 9, 10), "open"))
    audit.add_finding(Finding("F-003", "Carbonation", "CO2 permeate leak", "major",
                              "replace seal and recalibrate", date(2026, 9, 5), "in-progress"))
    audit.add_finding(Finding("F-004", "Warehouse", "label stock order", "observation",
                              "reorder label stock", date(2026, 8, 30), "open"))

    summ = closing_summary(audit.findings)
    cols = st.columns(5)
    cols[0].metric("Total findings", summ["total"])
    cols[1].metric("Open", summ["open"])
    cols[2].metric("Closed", summ["closed"])
    cols[3].metric("Overdue", summ["overdue"])
    cols[4].metric("Closure rate", f"{summ['closure_rate']*100:.0f}%")

    fdata = []
    for f in audit.findings:
        fdata.append({"ID": f.id, "Area": f.area, "Description": f.description,
                      "Severity": f.severity, "Action": f.corrective_action,
                      "Due": f.due_date, "Status": f.status})
    st.dataframe(pd.DataFrame(fdata), use_container_width=True)
