"""Close Month — the monthly reconciliation page.

v1 scope (this page, today):
  - Select the close month.
  - Ingest PDFs for Amex / BBVA / Nu / GBM via Claude API.
  - Dedupe against existing transactions.json.
  - Review grid: all new txns for the month, edit section/subcategory/note
    inline, bulk-approve.
  - Generate the budget_full Excel for the month.

Deferred (later subphases):
  - AI section suggestions with Notion + Calendar evidence.
  - Receipt drop-zone and Altis skill invocation.
  - Per-month close/freeze lifecycle.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from schema import (
    SECTIONS,
    SECTION_LABELS,
    ORIGINS,
    normalize_origin,
    txn_id,
)
from utils.data_loader import (
    load_transactions,
    save_transactions,
    upsert_transactions,
    set_month_status,
    load_monthly_close,
    load_budget,
)
from parsers.statement_pdf import parse_statement, raw_txns_to_records


st.title("🗓️ Close Month")

# =============================================================================
# Month picker
# =============================================================================
today = dt.date.today()
# default to last full calendar month
default_year = today.year if today.month > 1 else today.year - 1
default_month = today.month - 1 if today.month > 1 else 12
default_close = f"{default_year:04d}-{default_month:02d}"

c1, c2 = st.columns([1, 2])
with c1:
    month_str = st.text_input("Close Month (YYYY-MM)", value=default_close, max_chars=7)
with c2:
    status = load_monthly_close().get(month_str, {}).get("status", "draft")
    color = {"closed": "🟢", "in-review": "🟡", "draft": "⚪"}.get(status, "⚪")
    st.info(f"{color} Status: **{status}**")

try:
    close_year, close_month_num = month_str.split("-")
    close_year, close_month_num = int(close_year), int(close_month_num)
except Exception:
    st.error("Close month must be in the form YYYY-MM")
    st.stop()


# =============================================================================
# Step 1: Ingest statements
# =============================================================================
st.subheader("1. Ingest statements")
st.caption(
    "Drop one PDF per issuer. The app parses with Claude, dedupes by "
    "`(origin, date, amount, description)`, and appends new rows to "
    "`data/transactions.json`."
)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.warning(
        "ANTHROPIC_API_KEY is not set. The PDF parser won't run. "
        "Add it to `.env` in the repo root or export it in your shell, then reload."
    )


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _process_uploaded_pdf(uploaded_file, issuer: str) -> dict:
    """Save upload to a temp file, parse, upsert into transactions.json."""
    tmpdir = Path(tempfile.mkdtemp(prefix="budget-close-"))
    tmp_path = tmpdir / uploaded_file.name
    tmp_path.write_bytes(uploaded_file.getbuffer())

    payload = parse_statement(str(tmp_path), issuer)
    raw = payload.get("transactions", [])
    records = raw_txns_to_records(raw, origin=issuer, source_file=uploaded_file.name)

    # Assign ids with occurrence index for same-day duplicates
    existing = load_transactions()
    seen = {t.get("id") for t in existing if t.get("id")}
    occ_counter: dict[tuple, int] = {}
    for rec in records:
        key = (rec["origin"], rec["date"], round(rec["amount_native"], 2), rec["description"].strip().lower())
        occ = occ_counter.get(key, 0)
        occ_counter[key] = occ + 1
        rec["id"] = txn_id(rec["origin"], rec["date"], rec["amount_native"], rec["description"], occurrence=occ)

    # Keep only rows that belong to this close month (guard against stray
    # cross-month rows — statements usually only contain one cycle but Amex
    # can include the grace-period overlap).
    in_scope = [r for r in records if r["close_month"] == month_str]
    out_of_scope = [r for r in records if r["close_month"] != month_str]

    added = upsert_transactions(in_scope)

    return {
        "parsed": len(raw),
        "in_scope": len(in_scope),
        "out_of_scope": len(out_of_scope),
        "added": added,
        "duplicates_skipped": len(in_scope) - added,
        "sha256": _sha256(str(tmp_path)),
        "statement_period": payload.get("statement_period"),
    }


uploader_cols = st.columns(4)
issuer_labels = {"AMEX": "Amex (Spanish)", "BBVA": "BBVA", "NU": "Nu", "GBM": "GBM"}
for (issuer, label), col in zip(issuer_labels.items(), uploader_cols):
    with col:
        up = st.file_uploader(label, type=["pdf"], key=f"upload_{issuer}")
        if up is not None:
            btn = st.button(f"Parse {issuer}", key=f"parse_{issuer}")
            if btn:
                with st.status(f"Parsing {issuer} via Claude…", expanded=True) as s:
                    try:
                        result = _process_uploaded_pdf(up, issuer)
                        s.update(label=f"{issuer} parsed", state="complete")
                        st.write(result)

                        # record in monthly_close.json
                        mc = load_monthly_close()
                        entry = mc.get(month_str, {"status": "in-review", "statements": {}})
                        entry.setdefault("statements", {})[issuer] = {
                            "file": up.name,
                            "sha256": result["sha256"],
                            "statement_period": result.get("statement_period"),
                            "added": result["added"],
                        }
                        entry["status"] = "in-review"
                        mc[month_str] = entry
                        from utils.data_loader import save_monthly_close
                        save_monthly_close(mc)
                    except Exception as e:
                        s.update(label=f"{issuer} failed", state="error")
                        st.exception(e)


# =============================================================================
# Step 2: Review grid
# =============================================================================
st.divider()
st.subheader("2. Review")

all_txns = load_transactions()
month_txns = [t for t in all_txns if t.get("close_month") == month_str]

if not month_txns:
    st.info("No transactions ingested yet for this close month.")
    st.stop()

st.caption(f"{len(month_txns)} transactions in this close month.")
unreviewed_count = sum(1 for t in month_txns if not t.get("reviewed"))
if unreviewed_count:
    st.warning(f"{unreviewed_count} not yet reviewed.")

# Load budget subcategories for quick section→subcategory lookup
budget = load_budget()

df = pd.DataFrame(month_txns)
# Ensure expected columns exist
for col in ("section", "subcategory", "note", "reviewed", "amount_mxn"):
    if col not in df.columns:
        df[col] = None
df["reviewed"] = df["reviewed"].fillna(False).astype(bool)
df["section"] = df["section"].fillna("VARIABLE")
df["subcategory"] = df["subcategory"].fillna("")
df["note"] = df["note"].fillna("")
df["amount_mxn"] = pd.to_numeric(df["amount_mxn"], errors="coerce").fillna(df["amount_native"])

# Filters
fc1, fc2, fc3 = st.columns(3)
with fc1:
    only_unreviewed = st.checkbox("Show only unreviewed", value=True)
with fc2:
    origins = sorted(df["origin"].dropna().unique())
    origin_filter = st.multiselect("Origins", options=origins, default=origins)
with fc3:
    sections_filter = st.multiselect(
        "Sections",
        options=SECTIONS,
        default=SECTIONS,
        format_func=lambda s: SECTION_LABELS.get(s, s),
    )

view = df[df["origin"].isin(origin_filter) & df["section"].isin(sections_filter)]
if only_unreviewed:
    view = view[~view["reviewed"]]
view = view.sort_values("date")

st.caption(f"{len(view)} rows shown.")

# Editable data editor. Only the editable columns are writable.
editable_cols = ["section", "subcategory", "note", "reviewed"]
display = view[[
    "id", "date", "origin", "description", "amount_mxn",
    "section", "subcategory", "note", "reviewed",
]].copy()

edited = st.data_editor(
    display,
    column_config={
        "id": st.column_config.TextColumn("id", disabled=True, width="small"),
        "date": st.column_config.TextColumn("Date", disabled=True, width="small"),
        "origin": st.column_config.TextColumn("Origin", disabled=True, width="small"),
        "description": st.column_config.TextColumn("Description", disabled=True, width="large"),
        "amount_mxn": st.column_config.NumberColumn("MXN", disabled=True, format="$%.0f"),
        "section": st.column_config.SelectboxColumn("Section", options=SECTIONS, required=True),
        "subcategory": st.column_config.TextColumn("Subcategory"),
        "note": st.column_config.TextColumn("Note"),
        "reviewed": st.column_config.CheckboxColumn("✓"),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key="review_editor",
)

b1, b2, b3 = st.columns([1, 1, 2])
if b1.button("💾 Save edits", type="primary"):
    # Merge edits back into all_txns by id.
    edits_by_id = {r["id"]: r for r in edited.to_dict(orient="records")}
    updated = 0
    for t in all_txns:
        tid = t.get("id")
        if tid in edits_by_id:
            e = edits_by_id[tid]
            for c in editable_cols:
                t[c] = e.get(c, t.get(c))
            updated += 1
    save_transactions(all_txns)
    st.success(f"Saved {updated} rows.")
    st.rerun()

if b2.button("✅ Approve all shown"):
    edits_by_id = {r["id"]: r for r in edited.to_dict(orient="records")}
    updated = 0
    for t in all_txns:
        tid = t.get("id")
        if tid in edits_by_id:
            e = edits_by_id[tid]
            for c in editable_cols:
                t[c] = e.get(c, t.get(c))
            t["reviewed"] = True
            updated += 1
    save_transactions(all_txns)
    st.success(f"Approved {updated} rows.")
    st.rerun()


# =============================================================================
# Step 3: Outputs
# =============================================================================
st.divider()
st.subheader("3. Outputs")

o1, o2 = st.columns(2)

with o1:
    st.markdown("**Altis reimbursement workbook**")
    biz = [t for t in month_txns if t.get("section") == "BUSINESS_REIMBURSABLE"]
    st.caption(f"{len(biz)} business-reimbursable rows in scope.")
    st.button(
        "🧾 Run Altis reimbursement (coming in next subphase)",
        disabled=True,
    )

with o2:
    st.markdown("**Monthly Excel**")
    try:
        from export.budget_full_excel import build as build_excel  # lazy
        have_exporter = True
    except Exception:
        have_exporter = False

    if have_exporter:
        if st.button("📊 Generate budget_full_{YYYY-MM}.xlsx".replace("{YYYY-MM}", month_str)):
            out_path = os.path.join("data", "exports", f"budget_full_{month_str}.xlsx")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            try:
                build_excel(month_str, out_path)
                st.success(f"Wrote {out_path}")
                with open(out_path, "rb") as f:
                    st.download_button(
                        "⬇️ Download",
                        data=f.read(),
                        file_name=os.path.basename(out_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as e:
                st.exception(e)
    else:
        st.button("📊 Generate Excel (exporter missing)", disabled=True)

st.divider()
st.caption(
    "After you've swept all rows in this month, click **Approve all shown** "
    "with the 'only unreviewed' filter off to mark the month reviewed. "
    "Closing/freezing the month lands in the next subphase."
)
