"""Analytics Dashboard (v2 — section-based)."""

from __future__ import annotations

import datetime as dt
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from schema import SECTIONS, SECTION_LABELS, sections_in_order
from utils.data_loader import load_transactions, load_budget


st.title("📊 Budget Analytics Dashboard")


# ---------- data ----------

def _to_df() -> pd.DataFrame:
    rows = load_transactions()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount_mxn"] = pd.to_numeric(df.get("amount_mxn", df.get("amount_native")), errors="coerce")
    df = df.dropna(subset=["amount_mxn", "date"])
    if "section" not in df.columns:
        df["section"] = "VARIABLE"
    if "subcategory" not in df.columns:
        df["subcategory"] = ""
    return df


df = _to_df()
budget = load_budget()


# ---------- period filter ----------

def _period_range(opt: str, custom_start=None, custom_end=None):
    today = dt.date.today()
    if opt == "Custom Range" and custom_start and custom_end:
        return custom_start, custom_end
    if opt == "Current Calendar Month":
        s = today.replace(day=1)
        e = (s + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
        return s, e
    if opt == "Prior Calendar Month":
        s = today.replace(day=1)
        e = s - dt.timedelta(days=1)
        s = e.replace(day=1)
        return s, e
    if opt == "Current Close Month (Amex-cycle aware)":
        # Use today's calendar month as the close_month we're rolling up
        return today.replace(day=1), today
    if opt == "All Time":
        return None, None
    return None, None


def _apply_filter(df: pd.DataFrame, opt: str, start, end) -> pd.DataFrame:
    if df.empty:
        return df
    if opt == "Current Close Month (Amex-cycle aware)":
        close_month = f"{start.year:04d}-{start.month:02d}"
        return df[df["close_month"] == close_month]
    if start is None or end is None:
        return df
    mask = (df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))
    return df.loc[mask]


def _time_progress(start, end):
    if not start or not end:
        return None
    today = dt.date.today()
    s = start if isinstance(start, dt.date) else start.date()
    e = end if isinstance(end, dt.date) else end.date()
    if today < s:
        return 0
    if today > e:
        return 100
    total = (e - s).days + 1
    elapsed = (today - s).days + 1
    return min(100, (elapsed / total) * 100)


# ---------- UI ----------

if df.empty:
    st.warning("No transactions yet. Import statements in the Close Month page.")
    st.stop()

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    period = st.selectbox(
        "Time Period",
        [
            "Current Close Month (Amex-cycle aware)",
            "Current Calendar Month",
            "Prior Calendar Month",
            "Custom Range",
            "All Time",
        ],
    )

custom_start = custom_end = None
if period == "Custom Range":
    with c2:
        custom_start = st.date_input("Start", value=dt.date.today().replace(day=1))
    with c3:
        custom_end = st.date_input("End", value=dt.date.today())

start, end = _period_range(period, custom_start, custom_end)
df_f = _apply_filter(df, period, start, end)


# ---------- overview cards ----------

spendable = df_f[~df_f["section"].isin(["IGNORE", "INCOME"])]
total_spent = spendable["amount_mxn"].sum()

budget_total = sum(
    v.get("total", 0.0)
    for k, v in budget.items()
    if k not in ("INCOME", "IGNORE")
)

st.subheader("Overview")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Budget", f"${budget_total:,.0f}")
k2.metric(
    "Total Spent",
    f"${total_spent:,.0f}",
    delta=f"${total_spent - budget_total:,.0f}",
    delta_color="inverse",
)
pct = (total_spent / budget_total * 100) if budget_total > 0 else 0
k3.metric("Budget Used", f"{pct:.1f}%")
tp = _time_progress(start, end)
if tp is not None:
    k4.metric("Time Elapsed", f"{tp:.1f}%")
else:
    k4.metric("Remaining", f"${budget_total - total_spent:,.0f}")


# ---------- unreviewed alert ----------

unreviewed = df_f[df_f.get("reviewed", False) == False]  # noqa: E712
if not unreviewed.empty:
    st.warning(
        f"⚠️ {len(unreviewed)} unreviewed transactions in this period totaling "
        f"${unreviewed['amount_mxn'].sum():,.0f}. Sweep them in the Classifier or Close Month page."
    )


st.divider()


# ---------- section utilization ----------

st.subheader("Spending by Section")
by_section = (
    spendable.groupby("section")["amount_mxn"].sum().reset_index()
)
by_section["budgeted"] = by_section["section"].map(
    lambda s: budget.get(s, {}).get("total", 0.0)
)
by_section["delta"] = by_section["budgeted"] - by_section["amount_mxn"]
by_section["utilization"] = (
    by_section["amount_mxn"] / by_section["budgeted"] * 100
).where(by_section["budgeted"] > 0, 0).round(1)
by_section["section_order"] = by_section["section"].apply(lambda s: SECTIONS.index(s) if s in SECTIONS else 999)
by_section = by_section.sort_values("section_order")
by_section["label"] = by_section["section"].map(SECTION_LABELS)

for _, row in by_section.iterrows():
    c1, c2 = st.columns([3, 1])
    with c1:
        util = row["utilization"]
        st.progress(
            min(util / 100, 1.0) if row["budgeted"] > 0 else 0.0,
            text=(
                f"{row['label']}: ${row['amount_mxn']:,.0f} / ${row['budgeted']:,.0f} ({util:.1f}%)"
                if row["budgeted"] > 0
                else f"{row['label']}: ${row['amount_mxn']:,.0f} (no budget set)"
            ),
        )
    with c2:
        delta_color = "red" if row["delta"] < 0 else "green"
        st.markdown(
            f"<span style='color:{delta_color};font-weight:bold;'>${row['delta']:+,.0f}</span>",
            unsafe_allow_html=True,
        )


# ---------- chart ----------

chart_df = by_section[by_section["budgeted"] > 0].melt(
    id_vars=["label"], value_vars=["amount_mxn", "budgeted"]
)
if not chart_df.empty:
    fig = px.bar(
        chart_df,
        x="label", y="value", color="variable",
        labels={"value": "MXN", "variable": "", "label": ""},
        color_discrete_map={"amount_mxn": "#ff7f0e", "budgeted": "#1f77b4"},
        barmode="group",
    )
    fig.update_traces(texttemplate="$%{y:,.0f}", textposition="outside")
    fig.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)


# ---------- subcategory drill-down ----------

st.subheader("Subcategories")
sub_actual = (
    spendable.assign(subcategory=spendable["subcategory"].replace("", "—").fillna("—"))
    .groupby(["section", "subcategory"])["amount_mxn"].sum().reset_index()
)
sub_budget_rows = []
for s, block in budget.items():
    for sub, detail in block.get("subcategories", {}).items():
        amt = detail["amount"] if isinstance(detail, dict) else detail
        sub_budget_rows.append({"section": s, "subcategory": sub, "budgeted": amt})
sub_budget = pd.DataFrame(sub_budget_rows) if sub_budget_rows else pd.DataFrame(
    columns=["section", "subcategory", "budgeted"]
)
sub_merged = pd.merge(sub_actual, sub_budget, on=["section", "subcategory"], how="outer").fillna(0)
sub_merged["delta"] = sub_merged["budgeted"] - sub_merged["amount_mxn"]
sub_merged["utilization"] = (
    sub_merged["amount_mxn"] / sub_merged["budgeted"] * 100
).where(sub_merged["budgeted"] > 0, 0).round(1)
sub_merged["section_order"] = sub_merged["section"].apply(lambda s: SECTIONS.index(s) if s in SECTIONS else 999)
sub_merged = sub_merged.sort_values(["section_order", "amount_mxn"], ascending=[True, False])

current_section = None
for _, row in sub_merged.iterrows():
    if row["section"] != current_section:
        current_section = row["section"]
        st.write(f"**{SECTION_LABELS.get(current_section, current_section)}**")
    if row["budgeted"] <= 0 and row["amount_mxn"] <= 0:
        continue
    c1, c2 = st.columns([3, 1])
    with c1:
        util = row["utilization"]
        if row["budgeted"] == 0 and row["amount_mxn"] > 0:
            text = f"  {row['subcategory']}: ${row['amount_mxn']:,.0f} (no budget)"
            st.progress(1.0, text=text)
        else:
            st.progress(
                min(util / 100, 1.0),
                text=f"  {row['subcategory']}: ${row['amount_mxn']:,.0f} / ${row['budgeted']:,.0f} ({util:.1f}%)",
            )
    with c2:
        color = "red" if row["delta"] < 0 else "green"
        st.markdown(
            f"<span style='color:{color};font-weight:bold;'>${row['delta']:+,.0f}</span>",
            unsafe_allow_html=True,
        )


st.divider()


# ---------- detailed table ----------

st.subheader("Transactions")
f1, f2, f3 = st.columns(3)
with f1:
    section_filter = st.multiselect(
        "Sections",
        options=sections_in_order(df_f["section"].unique()),
        default=sections_in_order(df_f["section"].unique()),
        format_func=lambda s: SECTION_LABELS.get(s, s),
    )
with f2:
    origin_filter = st.multiselect(
        "Origins",
        options=sorted(df_f["origin"].dropna().unique()),
        default=sorted(df_f["origin"].dropna().unique()),
    )
with f3:
    min_amt = st.number_input("Min amount MXN", min_value=0.0, value=0.0, step=50.0)

view = df_f[
    df_f["section"].isin(section_filter)
    & df_f["origin"].isin(origin_filter)
    & (df_f["amount_mxn"] >= min_amt)
].sort_values("date", ascending=False)

st.write("**Transactions** (click ✏️ to edit in the Classifier)")
header = st.columns([2, 4, 1.5, 1.5, 2, 2, 0.7])
for col, title in zip(header, ["Date", "Description", "Origin", "Amount", "Section", "Subcategory", "Edit"]):
    col.write(f"**{title}**")
st.divider()

for _, row in view.iterrows():
    cols = st.columns([2, 4, 1.5, 1.5, 2, 2, 0.7])
    cols[0].write(row["date"].strftime("%Y-%m-%d"))
    cols[1].write(row["description"])
    cols[2].write(row.get("origin", "—"))
    cols[3].write(f"${row['amount_mxn']:,.0f}")
    cols[4].write(SECTION_LABELS.get(row["section"], row["section"]))
    cols[5].write(row.get("subcategory", "") or "—")
    with cols[6]:
        if st.button("✏️", key=f"edit_{row['id']}"):
            os.makedirs("data", exist_ok=True)
            edit_data = dict(row)
            edit_data["date"] = row["date"].strftime("%Y-%m-%d")
            # dates/ints → json-safe
            with open("data/to_edit.json", "w", encoding="utf-8") as f:
                json.dump(edit_data, f, indent=2, ensure_ascii=False, default=str)
            st.switch_page("pages/classifier_ui.py")

c1, c2, c3 = st.columns(3)
c1.metric("Shown total", f"${view['amount_mxn'].sum():,.0f}")
c2.metric("Transactions", len(view))
c3.metric("Average", f"${view['amount_mxn'].mean():,.0f}" if len(view) else "$0")
