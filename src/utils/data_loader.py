"""Data loaders for the new (v2) schema.

v2 layout:
    data/transactions.json   — list of transactions (see docstring below)
    data/recurring.json      — income / fixed / MSI / subscriptions / off-card
    data/monthly_close.json  — per-month close ledger
    data/budget.json         — section-based budget (replaces WANT/NEED/SAVINGS/WORK)

Legacy v1 files (classified_expenses.json, classified_expenses_reviewed.json,
new_expenses.json, to_edit.json) are still readable via `load_expenses_raw()`
for the migration tool. Prefer the v2 helpers for everything else.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


DATA_DIR = "data"
TRANSACTIONS_PATH = os.path.join(DATA_DIR, "transactions.json")
RECURRING_PATH = os.path.join(DATA_DIR, "recurring.json")
MONTHLY_CLOSE_PATH = os.path.join(DATA_DIR, "monthly_close.json")
BUDGET_PATH = os.path.join(DATA_DIR, "budget.json")


# ---------- low-level JSON I/O ----------

def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file {path}: {e}")
        return default


def _write_json(path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        print(f"Error saving to {path}: {e}")
        return False


# ---------- v2: transactions ----------

def load_transactions() -> list[dict]:
    return _read_json(TRANSACTIONS_PATH, default=[])


def save_transactions(transactions: list[dict]) -> bool:
    return _write_json(TRANSACTIONS_PATH, transactions)


def upsert_transactions(new_txns: list[dict]) -> int:
    """Merge `new_txns` into transactions.json keyed by `id`. Returns number of rows added.

    Existing rows are preserved — a txn with the same id is a no-op (first-write wins).
    Use `update_transaction()` to mutate a specific row.
    """
    existing = load_transactions()
    seen = {t.get("id") for t in existing if t.get("id")}
    added = [t for t in new_txns if t.get("id") and t["id"] not in seen]
    if added:
        save_transactions(existing + added)
    return len(added)


def update_transaction(txn_id_: str, patch: dict) -> bool:
    txns = load_transactions()
    for t in txns:
        if t.get("id") == txn_id_:
            t.update(patch)
            save_transactions(txns)
            return True
    return False


# ---------- v2: recurring ----------

def _default_recurring() -> dict:
    return {
        "income": [],
        "fixed_obligations": [],
        "msi": [],
        "subscriptions": [],
        "off_card": [],
    }


def load_recurring() -> dict:
    data = _read_json(RECURRING_PATH, default=_default_recurring())
    for key in ("income", "fixed_obligations", "msi", "subscriptions", "off_card"):
        data.setdefault(key, [])
    return data


def save_recurring(data: dict) -> bool:
    return _write_json(RECURRING_PATH, data)


# ---------- v2: monthly close ledger ----------

def load_monthly_close() -> dict:
    return _read_json(MONTHLY_CLOSE_PATH, default={})


def save_monthly_close(data: dict) -> bool:
    return _write_json(MONTHLY_CLOSE_PATH, data)


def get_month_status(close_month: str) -> str:
    entry = load_monthly_close().get(close_month) or {}
    return entry.get("status", "draft")


def set_month_status(close_month: str, status: str, **extras) -> None:
    data = load_monthly_close()
    entry = data.get(close_month, {})
    entry["status"] = status
    if status == "closed":
        entry["closed_at"] = datetime.utcnow().isoformat() + "Z"
    entry.update(extras)
    data[close_month] = entry
    save_monthly_close(data)


# ---------- v2: budget (section-based) ----------

def _default_budget() -> dict:
    from schema import SECTIONS
    return {s: {"total": 0.0, "subcategories": {}} for s in SECTIONS}


def load_budget() -> dict:
    data = _read_json(BUDGET_PATH, default=_default_budget())
    from schema import SECTIONS
    for s in SECTIONS:
        data.setdefault(s, {"total": 0.0, "subcategories": {}})
        data[s].setdefault("total", 0.0)
        data[s].setdefault("subcategories", {})
    return data


def save_budget(data: dict) -> bool:
    return _write_json(BUDGET_PATH, data)


# ---------- legacy helpers (kept for migration + classifier_ui fallback) ----------

def load_expenses_raw(filepath: str) -> list[dict]:
    """Read any v1 expense file. Returns [] on missing/invalid."""
    return _read_json(filepath, default=[])


def save_expenses_raw(data: list[dict], filepath: str) -> bool:
    return _write_json(filepath, data)


def get_data_file_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)
