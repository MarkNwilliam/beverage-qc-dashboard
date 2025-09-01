"""Internal audit & CAPA tracking.

A Quality Controller does more than test — they audit. This module models an internal
audit (checklist / finding / severity) and the corrective-and-preventive-action (CAPA)
loop that closes out findings. The same discipline a beverage plant runs before a
certification or customer audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class Finding:
    """A single non-conformance / observation from an audit."""

    id: str
    area: str
    description: str
    severity: str  # "major" | "minor" | "observation"
    corrective_action: str = ""
    due_date: Optional[date] = None
    status: str = "open"  # "open" | "in-progress" | "closed"

    @property
    def is_open(self) -> bool:
        return self.status != "closed"

    @property
    def overdue(self) -> bool:
        if self.due_date is None or self.status == "closed":
            return False
        return date.today() > self.due_date


@dataclass
class Audit:
    """A single internal audit with its findings."""

    id: str
    area: str
    date: date
    auditor: str
    scope: str = ""
    findings: List[Finding] = field(default_factory=list)

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def major_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "major")

    @property
    def minor_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "minor")

    @property
    def open_count(self) -> int:
        return sum(1 for f in self.findings if f.is_open)

    @property
    def closure_rate(self) -> float:
        if not self.findings:
            return 1.0
        return 1.0 - self.open_count / len(self.findings)


def open_capa(findings: List[Finding]) -> List[Finding]:
    """Return the findings still requiring corrective action."""
    return [f for f in findings if f.is_open]


def closing_summary(findings: List[Finding]) -> dict:
    """A dashboard-friendly summary of finding status."""
    return {
        "total": len(findings),
        "open": sum(1 for f in findings if f.is_open),
        "closed": sum(1 for f in findings if not f.is_open),
        "overdue": sum(1 for f in findings if f.overdue),
        "closure_rate": (1.0 - sum(1 for f in findings if f.is_open) / len(findings))
        if findings
        else 1.0,
    }
