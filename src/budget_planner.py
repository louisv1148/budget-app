"""Budget planner — section-based (v2).

Two tabs:
  1. Budget — section totals + subcategory allocations (persisted to data/budget.json).
  2. Recurring — income, fixed obligations, MSI with roll-off, subscriptions,
     off-card services (persisted to data/recurring.json). Drives the Excel
     exporter and future classifier heuristics.
"""

from __future__ import annotations

import streamlit as st

from schema import SECTIONS, SECTION_LABELS
from utils.data_loader import (
    load_budget,
    save_budget,
    load_recurring,
    save_recurring,
)


# Sections that have a "budget" (subcategory allocations that roll up to a total).
# INCOME and IGNORE are not budgeted in the allocation sense.
BUDGETED_SECTIONS = [s for s in SECTIONS if s not in ("INCOME", "IGNORE")]


st.title("📋 Budget & Recurring Planner")

tab_budget, tab_recurring = st.tabs(["💰 Budget (by section)", "🔁 Recurring"])


# =============================================================================
# Budget tab
# =============================================================================
with tab_budget:
    if "budget" not in st.session_state:
        st.session_state.budget = load_budget()
    budget = st.session_state.budget

    total_budget = sum(float(budget[s].get("total", 0.0)) for s in BUDGETED_SECTIONS)
    total_allocated = sum(
        sum(v["amount"] for v in budget[s].get("subcategories", {}).values())
        for s in BUDGETED_SECTIONS
    )
    total_unallocated = total_budget - total_allocated

    c1, c2, c3 = st.columns(3)
    c1.info(f"💰 Total Budget: ${total_budget:,.2f}")
    c2.info(f"📊 Total Allocated: ${total_allocated:,.2f}")
    c3.info(f"{'🟢' if total_unallocated >= 0 else '🔴'} Unallocated: ${total_unallocated:,.2f}")

    st.divider()

    for section in BUDGETED_SECTIONS:
        label = SECTION_LABELS[section]
        current_total = float(budget[section].get("total", 0.0))
        subcats = budget[section].get("subcategories", {})
        allocated = sum(v["amount"] for v in subcats.values())
        unallocated = current_total - allocated
        progress_pct = min(allocated / current_total, 1.0) if current_total else 0

        expanded_key = f"expanded_{section}"
        if expanded_key not in st.session_state:
            st.session_state[expanded_key] = False
        add_pressed = st.session_state.get(f"add_{section}", False)
        del_pressed = any(
            st.session_state.get(f"del_{section}_{s}", False) for s in subcats
        )
        should_expand = st.session_state[expanded_key] or add_pressed or del_pressed

        with st.expander(
            f"📂 {label} (Total: ${current_total:,.2f} · Allocated: ${allocated:,.2f})",
            expanded=should_expand,
        ):
            st.progress(
                progress_pct,
                text=f"${allocated:,.2f} of ${current_total:,.2f} ({progress_pct*100:.0f}%)",
            )
            new_total = st.number_input(
                f"Total Budget — {label}",
                min_value=0.0,
                value=current_total,
                step=50.0,
                key=f"total_{section}",
            )
            budget[section]["total"] = new_total

            # existing subcategories
            with st.expander(f"📋 Subcategories ({len(subcats)} items)"):
                to_delete = []
                for sub in list(subcats):
                    row = subcats[sub] if isinstance(subcats[sub], dict) else {
                        "amount": subcats[sub], "note": ""
                    }
                    c1, c2, c3, c4 = st.columns([3, 2, 4, 1])
                    with c1:
                        new_name = st.text_input("Subcategory", value=sub, key=f"name_{section}_{sub}")
                    with c2:
                        new_val = st.number_input(
                            "Amount", min_value=0.0, value=row["amount"], step=10.0,
                            key=f"val_{section}_{sub}",
                        )
                    with c3:
                        note = st.text_input("Note", value=row.get("note", ""), key=f"note_{section}_{sub}")
                    with c4:
                        if st.button("🗑️", key=f"del_{section}_{sub}"):
                            to_delete.append(sub)
                            st.session_state[expanded_key] = True
                    if new_name != sub:
                        del subcats[sub]
                        subcats[new_name] = {"amount": new_val, "note": note}
                    else:
                        subcats[sub] = {"amount": new_val, "note": note}
                for k in to_delete:
                    del subcats[k]

            # add new subcategory
            clear_key = f"clear_fields_{section}"
            should_clear = st.session_state.get(clear_key, False)
            c1, c2, c3 = st.columns([4, 3, 2])
            with c1:
                new_sub = st.text_input(
                    f"New subcategory",
                    value="" if should_clear else st.session_state.get(f"new_sub_{section}", ""),
                    key=f"new_sub_{section}",
                )
            with c2:
                new_amt = st.number_input(
                    "Amount",
                    min_value=0.0,
                    value=0.0 if should_clear else st.session_state.get(f"new_amt_{section}", 0.0),
                    step=10.0,
                    key=f"new_amt_{section}",
                )
            with c3:
                if st.button("Add", key=f"add_{section}") and new_sub:
                    if new_sub not in subcats:
                        subcats[new_sub] = {"amount": new_amt, "note": ""}
                        st.session_state[expanded_key] = True
                        st.session_state[clear_key] = True
                        st.rerun()
                    else:
                        st.warning("Subcategory already exists.")
            if should_clear:
                st.session_state[clear_key] = False

            updated_alloc = sum(v["amount"] for v in subcats.values())
            updated_un = new_total - updated_alloc
            st.info(
                f"{'🟢' if updated_un >= 0 else '🔴'} Unallocated in {label}: ${updated_un:,.2f}"
            )

    if st.button("💾 Save Budget"):
        save_budget(budget)
        st.success("✅ Budget saved to data/budget.json")


# =============================================================================
# Recurring tab
# =============================================================================
with tab_recurring:
    if "recurring" not in st.session_state:
        st.session_state.recurring = load_recurring()
    rec = st.session_state.recurring

    st.caption(
        "These drive the Income, Fixed Obligations, MSI, Subscriptions, and "
        "Off-Card sections of the monthly Excel. MSI rows include an end date "
        "so the roll-off tracker stays accurate."
    )

    def _row_editor(header: str, key: str, fields: list[tuple[str, str, float | str | bool]]):
        """Generic table editor. `fields` is [(field_key, widget_kind, default), ...]."""
        st.subheader(header)
        items = rec.get(key, [])
        to_delete = []
        for i, item in enumerate(items):
            cols = st.columns([3] + [2] * len(fields) + [1])
            for j, (fkey, kind, default) in enumerate(fields):
                with cols[j]:
                    val = item.get(fkey, default)
                    if kind == "text":
                        item[fkey] = st.text_input(fkey, value=val or "", key=f"{key}_{i}_{fkey}")
                    elif kind == "number":
                        item[fkey] = st.number_input(
                            fkey, min_value=0.0, value=float(val or 0), step=10.0,
                            key=f"{key}_{i}_{fkey}",
                        )
                    elif kind == "int":
                        item[fkey] = st.number_input(
                            fkey, min_value=0, value=int(val or 0), step=1,
                            key=f"{key}_{i}_{fkey}",
                        )
                    elif kind == "bool":
                        item[fkey] = st.checkbox(fkey, value=bool(val), key=f"{key}_{i}_{fkey}")
            with cols[-1]:
                if st.button("🗑️", key=f"{key}_del_{i}"):
                    to_delete.append(i)
        for idx in sorted(to_delete, reverse=True):
            del items[idx]
        if st.button(f"➕ Add row — {header}", key=f"{key}_add"):
            blank = {fkey: default for fkey, _, default in fields}
            items.append(blank)
            st.rerun()
        rec[key] = items

    _row_editor(
        "Income",
        "income",
        [("label", "text", ""), ("amount_mxn", "number", 0.0), ("frequency", "text", "monthly")],
    )
    _row_editor(
        "Fixed Obligations",
        "fixed_obligations",
        [("label", "text", ""), ("amount_mxn", "number", 0.0), ("due_day", "int", 1)],
    )
    _row_editor(
        "MSI Installment Plans",
        "msi",
        [
            ("label", "text", ""),
            ("amount_mxn", "number", 0.0),
            ("start", "text", "YYYY-MM"),
            ("months_total", "int", 12),
            ("origin", "text", "AMEX"),
        ],
    )
    _row_editor(
        "Subscriptions",
        "subscriptions",
        [
            ("label", "text", ""),
            ("amount_mxn", "number", 0.0),
            ("origin", "text", "AMEX"),
            ("active", "bool", True),
        ],
    )
    _row_editor(
        "Off-Card",
        "off_card",
        [("label", "text", ""), ("amount_mxn", "number", 0.0), ("frequency", "text", "monthly")],
    )

    if st.button("💾 Save Recurring"):
        save_recurring(rec)
        st.success("✅ Recurring saved to data/recurring.json")
