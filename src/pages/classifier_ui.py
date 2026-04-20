"""Classifier UI (v2).

Primary role: edit a single transaction sent from the Dashboard via
`data/to_edit.json`. Full month-close review happens on the new Close Month
page, not here.
"""

from __future__ import annotations

import json
import os

import streamlit as st

from schema import (
    SECTIONS,
    SECTION_LABELS,
    REEMBOLSO_OPTIONS,
    CUENTA_CONTABLE_OPTIONS,
    CC_OPTIONS,
    is_business,
)
from utils.data_loader import load_transactions, save_transactions, update_transaction


st.title("🏷️ Expense Classifier")

EDIT_FILE = "data/to_edit.json"


def _all_subcats_for_section(section: str, budget: dict) -> list[str]:
    return list(budget.get(section, {}).get("subcategories", {}).keys())


def _load_budget_subcats() -> dict[str, list[str]]:
    try:
        with open("data/budget.json", "r", encoding="utf-8") as f:
            budget = json.load(f)
    except Exception:
        budget = {}
    return {s: _all_subcats_for_section(s, budget) for s in SECTIONS}


# ---------- edit-from-dashboard mode ----------

if os.path.exists(EDIT_FILE):
    with open(EDIT_FILE, "r", encoding="utf-8") as f:
        edit = json.load(f)

    st.info("✏️ Edit mode — a transaction from the Dashboard is ready.")
    st.subheader("Transaction")

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Date:** {edit.get('date', '')}")
        st.write(f"**Description:** {edit.get('description', '')}")
        amt = edit.get("amount_mxn", edit.get("amount", 0))
        st.write(f"**Amount:** ${float(amt):,.2f} MXN")
        st.write(f"**Origin:** {edit.get('origin', '—')}")
        st.write(f"**Cycle:** {edit.get('card_cycle_start','?')} → {edit.get('card_cycle_end','?')}")

    subcats_map = _load_budget_subcats()

    with st.form("edit_form"):
        with c2:
            current_section = edit.get("section", "VARIABLE")
            if current_section not in SECTIONS:
                current_section = "VARIABLE"
            new_section = st.selectbox(
                "Section",
                SECTIONS,
                index=SECTIONS.index(current_section),
                format_func=lambda s: SECTION_LABELS.get(s, s),
            )

            sub_opts = subcats_map.get(new_section, [])
            current_sub = edit.get("subcategory", "")
            sub_choice = st.selectbox(
                "Subcategory",
                [""] + sub_opts,
                index=([""] + sub_opts).index(current_sub) if current_sub in ([""] + sub_opts) else 0,
            )

            new_note = st.text_input("Note", value=edit.get("note", ""))

            # reimbursement fields only when business
            reimb = edit.get("reimbursement") or {}
            if is_business(new_section):
                st.markdown("**Reimbursement**")
                r1, r2, r3 = st.columns(3)
                with r1:
                    reembolso = st.selectbox(
                        "Reembolso",
                        [""] + REEMBOLSO_OPTIONS,
                        index=([""] + REEMBOLSO_OPTIONS).index(reimb.get("reembolso", ""))
                        if reimb.get("reembolso", "") in ([""] + REEMBOLSO_OPTIONS)
                        else 0,
                    )
                with r2:
                    cuenta = st.selectbox(
                        "Cuenta contable",
                        [""] + CUENTA_CONTABLE_OPTIONS,
                        index=([""] + CUENTA_CONTABLE_OPTIONS).index(reimb.get("cuenta_contable", ""))
                        if reimb.get("cuenta_contable", "") in ([""] + CUENTA_CONTABLE_OPTIONS)
                        else 0,
                    )
                with r3:
                    cc = st.selectbox(
                        "CC",
                        [""] + CC_OPTIONS,
                        index=([""] + CC_OPTIONS).index(reimb.get("cc", ""))
                        if reimb.get("cc", "") in ([""] + CC_OPTIONS)
                        else 0,
                    )
            else:
                reembolso = cuenta = cc = None

        save_btn, cancel_btn = st.columns(2)
        save_edit = save_btn.form_submit_button("💾 Save", use_container_width=True)
        cancel_edit = cancel_btn.form_submit_button("❌ Cancel", use_container_width=True)

        if save_edit:
            patch = {
                "section": new_section,
                "subcategory": sub_choice,
                "note": new_note,
                "reviewed": True,
            }
            if is_business(new_section):
                patch["reimbursement"] = {
                    **(reimb or {}),
                    "reembolso": reembolso,
                    "cuenta_contable": cuenta,
                    "cc": cc,
                }
            elif "reimbursement" in edit:
                patch["reimbursement"] = None
            if update_transaction(edit["id"], patch):
                os.remove(EDIT_FILE)
                st.success("✅ Saved. Return to the Dashboard.")
            else:
                st.error("Could not find that transaction.")

        if cancel_edit:
            os.remove(EDIT_FILE)
            st.info("Cancelled.")

    st.divider()

else:
    st.info(
        "No transaction queued for edit. Use the **Close Month** page to ingest "
        "statements, or the Dashboard's ✏️ button to edit a single row."
    )

# ---------- quick stats ----------

txns = load_transactions()
if txns:
    from collections import Counter
    total = len(txns)
    unreviewed = sum(1 for t in txns if not t.get("reviewed"))
    biz = sum(1 for t in txns if t.get("section") == "BUSINESS_REIMBURSABLE")
    by_section = Counter(t.get("section") for t in txns)

    st.subheader("Library")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", total)
    c2.metric("Unreviewed", unreviewed)
    c3.metric("Business reimbursable", biz)
    st.caption("By section: " + ", ".join(f"{SECTION_LABELS.get(s,s)} {n}" for s, n in by_section.most_common()))
