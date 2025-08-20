import streamlit as st
import pandas as pd
import json
import os
import datetime as dt
import plotly.express as px

st.title("📊 Budget Analytics Dashboard")

# === Load classified expenses ===
def load_expenses():
    try:
        with open("data/classified_expenses.json", "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    except Exception as e:
        st.error(f"Error loading expenses: {e}")
        return pd.DataFrame()

# === Load budget ===
def load_budget():
    try:
        with open("data/budget.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.warning("No budget found. Create one in the Budget Planner.")
        return {}

# === Filters ===
def get_period_filter(df, option, custom_start=None, custom_end=None):
    if option == "Custom Range" and custom_start and custom_end:
        mask = (df["date"] >= pd.to_datetime(custom_start)) & (df["date"] <= pd.to_datetime(custom_end))
        return df.loc[mask], custom_start, custom_end
        
    today = dt.date.today()
    if option == "Current Calendar Month":
        start = today.replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    elif option == "Prior Calendar Month":
        current_month_start = today.replace(day=1)
        end = current_month_start - dt.timedelta(days=1)
        start = end.replace(day=1)
    elif option == "Current Credit Card Month":
        if today.day >= 20:
            start = today.replace(day=20)
            end = (start + dt.timedelta(days=32)).replace(day=19)
        else:
            end = today.replace(day=19)
            start = (end - dt.timedelta(days=32)).replace(day=20)
    elif option == "Prior Credit Card Month":
        if today.day >= 20:
            current_start = today.replace(day=20)
            end = (current_start - dt.timedelta(days=1))
            start = (end - dt.timedelta(days=32)).replace(day=20)
        else:
            current_end = today.replace(day=19)
            end = (current_end - dt.timedelta(days=32)).replace(day=19)
            start = (end - dt.timedelta(days=32)).replace(day=20)
    else:  # All Time
        return df, None, None

    mask = (df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))
    return df.loc[mask], start, end

def calculate_time_progress(start_date, end_date):
    """Calculate how much of the time period has elapsed"""
    if not start_date or not end_date:
        return None
    
    today = dt.date.today()
    start = start_date if isinstance(start_date, dt.date) else start_date.date()
    end = end_date if isinstance(end_date, dt.date) else end_date.date()
    
    if today < start:
        return 0
    elif today > end:
        return 100
    else:
        total_days = (end - start).days + 1
        elapsed_days = (today - start).days + 1
        return min(100, (elapsed_days / total_days) * 100)

# === Main App ===
df = load_expenses()
budget_data = load_budget()

if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    # Period selection with custom range option
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        period = st.selectbox(
            "Select Time Period:",
            ["Current Calendar Month", "Prior Calendar Month", "Current Credit Card Month", "Prior Credit Card Month", "Custom Range", "All Time"]
        )
    
    custom_start = custom_end = None
    if period == "Custom Range":
        with col2:
            custom_start = st.date_input("Start Date", value=dt.date.today().replace(day=1))
        with col3:
            custom_end = st.date_input("End Date", value=dt.date.today())

    df_filtered, start_date, end_date = get_period_filter(df, period, custom_start, custom_end)

    # === Summary Metrics Cards ===
    if budget_data:
        total_budget = sum(budget_data[cat]["total"] for cat in budget_data)
        total_spent = df_filtered["amount"].sum()
        total_remaining = total_budget - total_spent
        time_progress = calculate_time_progress(start_date, end_date)
        
        st.subheader("📊 Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Budget", 
                f"${total_budget:,.0f}",
                help="Total budgeted amount for selected period"
            )
        
        with col2:
            st.metric(
                "Total Spent", 
                f"${total_spent:,.0f}",
                delta=f"${total_spent - total_budget:,.0f}",
                delta_color="inverse",
                help="Total expenses for selected period"
            )
        
        with col3:
            budget_used_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0
            st.metric(
                "Budget Used", 
                f"{budget_used_pct:.1f}%",
                help="Percentage of total budget consumed"
            )
        
        with col4:
            if time_progress is not None:
                st.metric(
                    "Time Elapsed", 
                    f"{time_progress:.1f}%",
                    help="Percentage of time period that has passed"
                )
            else:
                st.metric("Remaining Budget", f"${total_remaining:,.0f}")

    # === Unclassified Expenses Alert ===
    unclassified = df_filtered[df_filtered["category"].isin(["UNCLASSIFIED", "Unknown", ""]) | df_filtered["category"].isna()]
    if not unclassified.empty:
        st.error(f"⚠️ **{len(unclassified)} unclassified expenses** totaling ${unclassified['amount'].sum():,.0f} found! Please classify these in the Expense Classifier.")
        
        with st.expander("View Unclassified Expenses"):
            st.dataframe(unclassified[["date", "description", "amount"]].sort_values("date", ascending=False))

    st.divider()

    st.subheader("💰 Spending vs. Budget Analysis")

    # === Category Analysis ===
    cat_actual = df_filtered.groupby("category")["amount"].sum().reset_index()
    # Exclude unnecessary categories from main analysis
    cat_actual = cat_actual[~cat_actual["category"].isin(["UNCLASSIFIED", "ALTIS", "IGNORE"])]

    if budget_data:
        cat_budget = pd.DataFrame([
            {"category": cat, "budgeted": budget_data[cat]["total"]} for cat in budget_data
        ])
        cat_merged = pd.merge(cat_actual, cat_budget, on="category", how="outer").fillna(0)
        cat_merged["delta"] = cat_merged["budgeted"] - cat_merged["amount"]
        cat_merged["utilization"] = (cat_merged["amount"] / cat_merged["budgeted"] * 100).round(1)
        cat_merged = cat_merged.sort_values("amount", ascending=False)

        # Budget utilization indicators - filter out unwanted categories
        budget_categories = cat_merged[~cat_merged["category"].isin(["ALTIS", "IGNORE"])]
        
        st.subheader("🎯 Budget Utilization by Category")
        
        for _, row in budget_categories.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                utilization = row["utilization"] if row["budgeted"] > 0 else 0
                color = "red" if utilization > 100 else "orange" if utilization > 80 else "green"
                st.progress(
                    min(utilization / 100, 1.0), 
                    text=f"{row['category']}: ${row['amount']:,.0f} / ${row['budgeted']:,.0f} ({utilization:.1f}%)"
                )
            with col2:
                delta_color = "red" if row["delta"] < 0 else "green"
                st.markdown(f"<span style='color: {delta_color}; font-weight: bold;'>${row['delta']:+,.0f}</span>", unsafe_allow_html=True)

        # Category comparison chart - filter out unwanted categories and make side-by-side
        chart_data = budget_categories.melt(id_vars=["category"], value_vars=["amount", "budgeted"])
        fig1 = px.bar(
            chart_data,
            x="category", y="value", color="variable",
            title="Spending vs. Budget by Category",
            labels={"value": "Amount ($)", "variable": "Type"},
            color_discrete_map={"amount": "#ff7f0e", "budgeted": "#1f77b4"},
            barmode="group"  # This makes bars side-by-side instead of stacked
        )
        fig1.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)

        # === Subcategory Analysis ===
        if "subcategory" in df_filtered.columns:
            st.subheader("📋 Budget Utilization by Subcategory")
            # Fill missing subcategories
            df_sub = df_filtered.copy()
            df_sub["subcategory"] = df_sub["subcategory"].fillna("No Subcategory")
            
            sub_actual = df_sub.groupby(["category", "subcategory"])["amount"].sum().reset_index()
            # Exclude unnecessary categories from subcategory analysis
            sub_actual = sub_actual[~sub_actual["category"].isin(["UNCLASSIFIED", "ALTIS", "IGNORE"])]

            budget_rows = []
            for cat in budget_data:
                for sub, detail in budget_data[cat].get("subcategories", {}).items():
                    budget_rows.append({
                        "category": cat,
                        "subcategory": sub,
                        "budgeted": detail["amount"] if isinstance(detail, dict) else detail
                    })

            if budget_rows:
                sub_budget = pd.DataFrame(budget_rows)
                sub_merged = pd.merge(sub_actual, sub_budget, on=["category", "subcategory"], how="outer").fillna(0)
                sub_merged["delta"] = sub_merged["budgeted"] - sub_merged["amount"]
                sub_merged["utilization"] = (sub_merged["amount"] / sub_merged["budgeted"] * 100).round(1)
                
                # Sort by category, then by spending amount within each category
                sub_merged = sub_merged.sort_values(["category", "amount"], ascending=[True, False])
                
                # Display as vertical list organized by category
                current_category = None
                for _, row in sub_merged.iterrows():
                    # Show category header when it changes
                    if row["category"] != current_category:
                        current_category = row["category"]
                        st.write(f"**{current_category}**")
                    
                    # Only show subcategories that have a budget or actual spending
                    if row["budgeted"] > 0 or row["amount"] > 0:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            utilization = row["utilization"] if row["budgeted"] > 0 else 0
                            # Handle cases where there's no budget but there's spending
                            if row["budgeted"] == 0 and row["amount"] > 0:
                                progress_val = 1.0  # Show full bar for over-budget
                                text = f"  {row['subcategory']}: ${row['amount']:,.0f} / $0 (No Budget Set)"
                            else:
                                progress_val = min(utilization / 100, 1.0)
                                text = f"  {row['subcategory']}: ${row['amount']:,.0f} / ${row['budgeted']:,.0f} ({utilization:.1f}%)"
                            
                            st.progress(progress_val, text=text)
                        with col2:
                            delta_color = "red" if row["delta"] < 0 else "green"
                            st.markdown(f"<span style='color: {delta_color}; font-weight: bold;'>${row['delta']:+,.0f}</span>", unsafe_allow_html=True)
        else:
            st.info("📋 Subcategory data not available in expense records. Classify expenses with subcategories to see detailed analysis.")

    else:
        st.info("💡 No budget file found — create one in the Budget Planner to enable comparisons.")
        
        # Show category spending without budget comparison
        fig1_simple = px.bar(
            cat_actual.sort_values("amount", ascending=False),
            x="category", y="amount",
            title="Total Spending by Category",
            labels={"amount": "Amount ($)"}
        )
        fig1_simple.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')
        fig1_simple.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1_simple, use_container_width=True)

    # === Detailed Expenses Table ===
    st.subheader("🧾 Detailed Expenses")
    
    # Filter options for the table
    col1, col2 = st.columns(2)
    with col1:
        selected_categories = st.multiselect(
            "Filter by Categories:",
            options=df_filtered["category"].unique(),
            default=df_filtered["category"].unique()
        )
    with col2:
        min_amount = st.number_input("Minimum Amount ($):", min_value=0.0, value=0.0, step=10.0)
    
    table_filtered = df_filtered[
        (df_filtered["category"].isin(selected_categories)) & 
        (df_filtered["amount"] >= min_amount)
    ].sort_values("date", ascending=False)
    
    # Display as interactive table with edit buttons
    st.write("**Expense Details** (click ✏️ to edit)")
    
    # Create header row
    header_cols = st.columns([2, 4, 2, 2, 2, 1])
    with header_cols[0]:
        st.write("**Date**")
    with header_cols[1]:
        st.write("**Description**")
    with header_cols[2]:
        st.write("**Category**")
    with header_cols[3]:
        if "subcategory" in table_filtered.columns:
            st.write("**Subcategory**")
        else:
            st.write("**Type**")
    with header_cols[4]:
        st.write("**Amount**")
    with header_cols[5]:
        st.write("**Edit**")
    
    st.divider()
    
    # Display each row with edit button
    for idx, row in table_filtered.iterrows():
        cols = st.columns([2, 4, 2, 2, 2, 1])
        
        with cols[0]:
            st.write(row["date"].strftime("%Y-%m-%d"))
        with cols[1]:
            st.write(row["description"])
        with cols[2]:
            st.write(row["category"])
        with cols[3]:
            if "subcategory" in table_filtered.columns:
                st.write(row.get("subcategory", "No Subcategory"))
            else:
                st.write("—")
        with cols[4]:
            st.write(f"${row['amount']:,.0f}")
        with cols[5]:
            if st.button("✏️", key=f"edit_{idx}", help="Edit this expense"):
                # Save to session state for editing
                edit_data = row.to_dict()
                # Convert date to string for JSON serialization
                if 'date' in edit_data:
                    edit_data['date'] = edit_data['date'].strftime('%Y-%m-%d')
                
                # Save to temp file for cross-page communication
                os.makedirs("data", exist_ok=True)
                with open("data/to_edit.json", "w", encoding="utf-8") as f:
                    json.dump(edit_data, f, indent=2, ensure_ascii=False, default=str)
                
                # Redirect to Expense Classifier
                st.switch_page("pages/classifier_ui.py")
    
    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Expenses Shown", f"${table_filtered['amount'].sum():,.0f}")
    with col2:
        st.metric("Number of Transactions", len(table_filtered))
    with col3:
        avg_transaction = table_filtered["amount"].mean() if len(table_filtered) > 0 else 0
        st.metric("Average Transaction", f"${avg_transaction:.0f}")

else:
    st.warning("📋 No classified expense data found. Make sure to:")
    st.markdown("""
    1. Upload and classify expenses using the **Expense Classifier**
    2. Ensure 'classified_expenses.json' exists in the /data folder
    3. Create a budget using the **Budget Planner** for comparison features
    """)