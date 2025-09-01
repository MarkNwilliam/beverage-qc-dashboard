"""HACCP food-safety hazard analysis (Codex Alimentarius principle 1-7).

Hazard Analysis and Critical Control Points is how a beverage plant controls food
safety. The QC role maps every step in the process to the hazards ('physical',
'chemical' or 'biological'), decides which steps are Critical Control Points (CCPs),
sets critical limits (CLs), monitoring, corrective actions and verification.

This module:
    * defines a Hazard and a CriticalControlPoint with a critical limit
    * check_ccp() — judge a CCP monitoring reading against its CL (the decision a
      QC/process operator makes on the floor)
    * run_haccp_table() — a walkable HACCP plan for a generic CSD line
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Hazard:
    """A food-safety hazard identified at a process step."""

    source: str
    category: str  # "physical" | "chemical" | "biological"
    severity: int  # 1-5
    likelihood: int  # 1-5
    prevention: str = ""

    @property
    def risk(self) -> int:
        return self.severity * self.likelihood

    def is_significant(self, threshold: int = 9) -> bool:
        return self.risk >= threshold


@dataclass
class CriticalControlPoint:
    """A CCP with its critical limit (CL), monitoring and corrective action."""

    step: str
    hazard: str
    critical_limit_lower: float
    critical_limit_upper: float
    unit: str = ""
    monitoring: str = ""
    corrective_action: str = ""


def check_ccp(
    ccp: CriticalControlPoint, reading: float
) -> Dict:
    """Judge a CCP monitoring reading against its critical limit."""
    within = ccp.critical_limit_lower <= reading <= ccp.critical_limit_upper
    return {
        "step": ccp.step,
        "hazard": ccp.hazard,
        "reading": reading,
        "unit": ccp.unit,
        "critical_limit": (ccp.critical_limit_lower, ccp.critical_limit_upper),
        "within_limit": within,
        "action": "release" if within else ccp.corrective_action,
    }


def run_haccp_table() -> List[Dict]:
    """A generic HACCP plan for a carbonated soft-drink line.

    Not a real CBL/Pepsi plan — a representative model of the steps a Quality
    Controller owns, useful as a reference and for the dashboard.
    """
    steps = [
        {"step": "Syrup batching", "hazard": "Microbial growth / wrong concentration",
         "CCP": True, "CL": (min, max), "unit": "brix"},
        {"step": "Carbonation", "hazard": "Gas blend / CO2 overrun", "CCP": True,
         "unit": "vol"},
        {"step": "Filling", "hazard": "Gross fill, foreign bodies", "CCP": True,
         "unit": "ml"},
        {"step": "Capping/sealing", "hazard": "Torque / leak / ingress", "CCP": True,
         "unit": "in-lb"},
        {"step": "Pasteurization", "hazard": "Under-process (biological)", "CCP": True,
         "unit": "degC"},
        {"step": "Post-fill inspection", "hazard": "Damaged bottles / labels", "CCP": False},
    ]
    # Reassign CL placeholders to real floats for the CCPs
    cls = {
        "Syrup batching": (10.5, 11.5),
        "Carbonation": (3.0, 4.2),
        "Filling": (480.0, 510.0),
        "Capping/sealing": (12.0, 18.0),
        "Pasteurization": (72.0, 75.0),
    }
    for s in steps:
        if s["CCP"]:
            s["CL"] = {"lower": cls[s["step"]][0], "upper": cls[s["step"]][1]}
    return steps
