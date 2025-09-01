"""Synthetic but realistic QC data for a beverage line.

Generates believable time-series of batch-level QC measurements with the drift and
variability a real bottling line shows. Used to populate the dashboard and examples
so the tool is demo-able out of the box. All data is fictional — no real CBL/Pepsi
production data is used.
"""

from __future__ import annotations

import random
from typing import Dict, List

import numpy as np

from .qc import DEFAULT_SPECS


def generate_batches(
    n: int = 120,
    product: str = "Cola CSD",
    line: str = "Line 1",
    seed: int = 42,
    drift_brix: float = 0.0,
    drift_ph: float = 0.0,
    fault_step_at: int = 90,
    step_shift: float = 0.0,
    sigma_factor: float = 1.0,
) -> list:
    """Generate `n` batches of QC measurements for the standard parameters.

    Base targets are the midpoints of the DEFAULT_SPECS ranges. Optional slow drift
    (drift_* per batch) and a step fault (magnitude step_shift from batch index
    fault_step_at onward) let you demonstrate the SPC charts catching trouble.
    """
    rng = np.random.default_rng(seed)

    specs = DEFAULT_SPECS
    def midpoint(name):
        spec = specs[name]
        return (spec.lower + spec.upper) / 2.0

    base = {
        "Brix (20C)": midpoint("Brix (20C)"),
        "pH": midpoint("pH"),
        "Color": midpoint("Color"),
        "CO2 Volume": midpoint("CO2 Volume"),
        "Sensory Score": 9.0,
    }
    # realistic measurement noise (units)
    noise = {
        "Brix (20C)": 0.12,
        "pH": 0.07,
        "Color": 0.03,
        "CO2 Volume": 0.12,
        "Sensory Score": 0.5,
    }

    batches = []
    for i in range(n):
        # cumulative slow drift
        brix_shift = drift_brix * (i - 20)
        ph_shift = drift_ph * (i - 20)

        # step fault
        if i >= fault_step_at:
            brix_shift += step_shift

        values = {}
        for name, target in base.items():
            values[name] = abs(
                target
                + {"Brix (20C)": brix_shift, "pH": ph_shift}.get(name, 0.0)
                + rng.normal(0, noise[name] * sigma_factor)
            )
        batches.append(
            {
                "batch_id": f"{product.replace(' ','')[:2]}{1000+i}",
                "product": product,
                "line": line,
                "operator": random.choice(
                    ["K. Namatovu", "J. Odongo", "S. Nabirye", "M. Kizza"]
                ),
                "timestamp": f"2026-{int(i/30)+1:02d}-{i%28+1:02d}",
                "values": values,
            }
        )
    return batches
