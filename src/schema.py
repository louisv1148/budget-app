"""Canonical section/origin constants and small helpers.

The app used to store WANT/NEED/SAVINGS/WORK as the primary category. The new
data model uses the sections that appear in budget_full_YYYY-MM.xlsx. Every
transaction belongs to exactly one section.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


SECTIONS: list[str] = [
    "INCOME",
    "FIXED_OBLIGATIONS",
    "MSI",
    "SUBSCRIPTIONS",
    "OFF_CARD",
    "VARIABLE",
    "BUSINESS_REIMBURSABLE",
    "FEES",
    "IGNORE",
]

SECTION_LABELS: dict[str, str] = {
    "INCOME": "Income",
    "FIXED_OBLIGATIONS": "Fixed Obligations",
    "MSI": "MSI Installment Plans",
    "SUBSCRIPTIONS": "Subscriptions & Recurring",
    "OFF_CARD": "Off-Card Expenses",
    "VARIABLE": "Variable Spending",
    "BUSINESS_REIMBURSABLE": "Business Expenses — Reimbursable",
    "FEES": "Fees & Penalties",
    "IGNORE": "Ignore",
}

ORIGINS: list[str] = ["AMEX", "BBVA", "NU", "GBM", "CASH", "MANUAL"]

REEMBOLSO_OPTIONS: list[str] = [
    "Clipway",
    "Reverence",
    "Odyssey",
    "SIPE",
    "SI",
    "Altis_GP",
]

CUENTA_CONTABLE_OPTIONS: list[str] = [
    "Hoteles",
    "Vuelos",
    "Comidas con Clientes",
    "Transporte",
    "Otros",
]

CC_OPTIONS: list[str] = ["Alternativos", "Primarios", "Administrativos"]


def txn_id(origin: str, date: str, amount: float, description: str, occurrence: int = 0) -> str:
    """Stable content hash used for dedup. `occurrence` disambiguates same-day duplicates."""
    payload = f"{origin}|{date}|{amount:.2f}|{description.strip().lower()}|{occurrence}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Cycle:
    start: str  # ISO date
    end: str    # ISO date
    close_month: str  # YYYY-MM


def section_display(section: str) -> str:
    return SECTION_LABELS.get(section, section)


def is_business(section: str) -> bool:
    return section == "BUSINESS_REIMBURSABLE"


def normalize_origin(raw: str | None) -> str:
    """Map historical origin labels (e.g. 'Nu Bank', 'BBVA Credit') to the canonical set."""
    if not raw:
        return "MANUAL"
    r = raw.strip().upper()
    if "AMEX" in r or "AMERICAN EXPRESS" in r:
        return "AMEX"
    if "BBVA" in r:
        return "BBVA"
    if "NU" in r:
        return "NU"
    if "GBM" in r:
        return "GBM"
    if "CASH" in r:
        return "CASH"
    return "MANUAL"


def validate_section(section: str | None) -> str:
    if section in SECTIONS:
        return section
    return "VARIABLE"


def sections_in_order(sections: Iterable[str]) -> list[str]:
    order = {s: i for i, s in enumerate(SECTIONS)}
    return sorted(sections, key=lambda s: order.get(s, 999))
