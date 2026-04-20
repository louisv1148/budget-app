"""One-shot migration from v1 (WANT/NEED/SAVINGS/WORK) to v2 (sections).

Run from the repo root:

    python src/tools/migrate_v1_to_v2.py

It reads `data/classified_expenses.json` and `data/budget.json`, writes
`data/transactions.json`, `data/recurring.json` (best-effort), and a new
`data/budget.json` in the section-based shape. The original files are
renamed `*.v1.json.bak` so the old state is recoverable.

Every migrated transaction is marked `reviewed: false` so you can sweep
them in the Classifier/Close-Month UI. The v1 "category" is preserved
under `legacy_category` for audit.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime

# Allow running as a script: `python src/tools/migrate_v1_to_v2.py`
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_SRC)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from schema import SECTIONS, normalize_origin, txn_id  # noqa: E402
from parsers.cycle_resolver import resolve_cycle  # noqa: E402


V1_TXNS = os.path.join(_ROOT, "data", "classified_expenses.json")
V1_BUDGET = os.path.join(_ROOT, "data", "budget.json")
V2_TXNS = os.path.join(_ROOT, "data", "transactions.json")
V2_BUDGET = V1_BUDGET  # written in-place after backup
V2_RECURRING = os.path.join(_ROOT, "data", "recurring.json")


# Best-effort map from v1 category → v2 section. Overrides by subcategory/label
# follow. Anything unmapped falls through to VARIABLE and gets reviewed=false.
CATEGORY_TO_SECTION: dict[str, str] = {
    "NEED": "FIXED_OBLIGATIONS",
    "WANT": "VARIABLE",
    "SAVINGS": "IGNORE",
    "WORK": "OFF_CARD",
    "ALTIS": "BUSINESS_REIMBURSABLE",
    "IGNORE": "IGNORE",
    "UNCATEGORIZED": "VARIABLE",
}

# Subcategory-level overrides. Keys are lowercased.
SUBCATEGORY_TO_SECTION: dict[str, str] = {
    # NEED subcategories that are really recurring subs or off-card
    "izzi": "SUBSCRIPTIONS",
    "cellphone": "SUBSCRIPTIONS",
    "streaming": "SUBSCRIPTIONS",
    "ai": "SUBSCRIPTIONS",
    "insurance": "FIXED_OBLIGATIONS",
    "rent": "FIXED_OBLIGATIONS",
    "pension": "FIXED_OBLIGATIONS",
    "accountant": "FIXED_OBLIGATIONS",
    "student loans": "FIXED_OBLIGATIONS",
    "cowork": "FIXED_OBLIGATIONS",
    # Off-card services
    "housekeeper": "OFF_CARD",
    "psychologist": "OFF_CARD",
    "electricity": "OFF_CARD",
    "gas": "OFF_CARD",
    "water": "OFF_CARD",
    # MSI bucket under WANT maps to MSI
    "msi": "MSI",
}


def _classify(v1_category: str, v1_subcategory: str | None) -> str:
    sub = (v1_subcategory or "").strip().lower()
    if sub and sub in SUBCATEGORY_TO_SECTION:
        return SUBCATEGORY_TO_SECTION[sub]
    return CATEGORY_TO_SECTION.get((v1_category or "").upper(), "VARIABLE")


def _backup(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    backup = path.replace(".json", ".v1.json.bak")
    shutil.copy2(path, backup)
    return backup


def migrate_transactions() -> list[dict]:
    if not os.path.exists(V1_TXNS):
        print(f"(no v1 transactions file at {V1_TXNS} — skipping)")
        return []
    with open(V1_TXNS, "r", encoding="utf-8") as f:
        v1 = json.load(f)

    now = datetime.utcnow().isoformat() + "Z"
    out: list[dict] = []
    # Track per-(origin,date,amount,desc) occurrence index for stable hashing of
    # same-day duplicates (e.g., two Starbucks runs).
    seen_payload: dict[tuple, int] = {}

    for row in v1:
        date = str(row.get("date", ""))[:10]
        desc = row.get("description", "") or ""
        amount = float(row.get("amount", 0) or 0)
        origin = normalize_origin(row.get("origin"))
        v1_cat = row.get("category")
        v1_sub = row.get("subcategory")

        key = (origin, date, round(amount, 2), desc.strip().lower())
        occ = seen_payload.get(key, 0)
        seen_payload[key] = occ + 1

        tid = txn_id(origin, date, amount, desc, occurrence=occ)
        cycle = resolve_cycle(origin, date) if date else None

        section = _classify(v1_cat, v1_sub)
        record = {
            "id": tid,
            "date": date,
            "description": desc,
            "amount_native": amount,
            "currency_native": "MXN",  # v1 data was all MXN
            "amount_mxn": amount,
            "origin": origin,
            "card_cycle_start": cycle.start if cycle else None,
            "card_cycle_end": cycle.end if cycle else None,
            "close_month": cycle.close_month if cycle else None,
            "section": section,
            "subcategory": v1_sub or "",
            "note": row.get("note", "") or "",
            "reviewed": False,
            "legacy_category": v1_cat,
            "imported_from": "v1:classified_expenses.json",
            "imported_at": now,
        }
        out.append(record)

    return out


def migrate_budget() -> dict:
    """Translate WANT/NEED/SAVINGS/WORK budget into sections.

    Totals: each old category's total is added to the section its subcategories
    most naturally map to. Subcategories are carried over under their new section.
    For simplicity the section total becomes the sum of its subcategories
    (lossless given how budget was being used).
    """
    if not os.path.exists(V1_BUDGET):
        print(f"(no v1 budget file at {V1_BUDGET} — writing empty v2 budget)")
        return {s: {"total": 0.0, "subcategories": {}} for s in SECTIONS}

    with open(V1_BUDGET, "r", encoding="utf-8") as f:
        v1 = json.load(f)

    v2: dict = {s: {"total": 0.0, "subcategories": {}} for s in SECTIONS}

    for old_cat, block in v1.items():
        subcats = block.get("subcategories", {}) or {}
        for sub_name, sub_val in subcats.items():
            amount = sub_val["amount"] if isinstance(sub_val, dict) else float(sub_val or 0)
            note = sub_val.get("note", "") if isinstance(sub_val, dict) else ""
            section = _classify(old_cat, sub_name)
            v2[section]["subcategories"][sub_name] = {"amount": amount, "note": note}

    for s in SECTIONS:
        v2[s]["total"] = sum(v["amount"] for v in v2[s]["subcategories"].values())

    return v2


def seed_recurring_from_budget(v2_budget: dict) -> dict:
    """Pre-populate recurring.json with recognizable rows from the migrated budget.

    The user will edit this in the Planner. We only seed — we don't assume we
    got it right.
    """
    recurring = {
        "income": [],
        "fixed_obligations": [],
        "msi": [],
        "subscriptions": [],
        "off_card": [],
    }
    fixed = v2_budget.get("FIXED_OBLIGATIONS", {}).get("subcategories", {})
    for label, row in fixed.items():
        recurring["fixed_obligations"].append({
            "label": label,
            "amount_mxn": float(row.get("amount", 0)),
            "due_day": 1,
        })
    subs = v2_budget.get("SUBSCRIPTIONS", {}).get("subcategories", {})
    for label, row in subs.items():
        recurring["subscriptions"].append({
            "label": label,
            "amount_mxn": float(row.get("amount", 0)),
            "origin": "AMEX",
            "active": True,
        })
    off_card = v2_budget.get("OFF_CARD", {}).get("subcategories", {})
    for label, row in off_card.items():
        recurring["off_card"].append({
            "label": label,
            "amount_mxn": float(row.get("amount", 0)),
            "frequency": "monthly",
        })
    return recurring


def main() -> None:
    print("== budget-app v1 → v2 migration ==")
    print(f"repo root: {_ROOT}")

    if os.path.exists(V2_TXNS) and os.path.getsize(V2_TXNS) > 2:
        print(f"⚠️  {V2_TXNS} already exists and is non-empty.")
        print("    Refusing to overwrite. Delete or rename it, then re-run.")
        sys.exit(1)

    tbak = _backup(V1_TXNS)
    bbak = _backup(V1_BUDGET)
    if tbak: print(f"  backed up transactions → {tbak}")
    if bbak: print(f"  backed up budget       → {bbak}")

    txns = migrate_transactions()
    with open(V2_TXNS, "w", encoding="utf-8") as f:
        json.dump(txns, f, indent=2, ensure_ascii=False)
    print(f"  wrote {len(txns)} transactions → {V2_TXNS}")

    v2_budget = migrate_budget()
    with open(V2_BUDGET, "w", encoding="utf-8") as f:
        json.dump(v2_budget, f, indent=2, ensure_ascii=False)
    budget_total = sum(v["total"] for v in v2_budget.values())
    print(f"  wrote section-based budget (total ${budget_total:,.0f}) → {V2_BUDGET}")

    if not os.path.exists(V2_RECURRING):
        recurring = seed_recurring_from_budget(v2_budget)
        with open(V2_RECURRING, "w", encoding="utf-8") as f:
            json.dump(recurring, f, indent=2, ensure_ascii=False)
        counts = {k: len(v) for k, v in recurring.items()}
        print(f"  seeded recurring.json → {V2_RECURRING}  ({counts})")
    else:
        print(f"  recurring.json exists — leaving it alone")

    print("")
    print("Done. All v1 rows imported with reviewed=false so you can sweep them")
    print("in the Classifier or Close-Month UI.")


if __name__ == "__main__":
    main()
