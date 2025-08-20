import streamlit as st
import pandas as pd
import json
import os
import datetime as dt
import plotly.express as px

st.set_page_config(page_title="📊 Budget Analytics", layout="wide")
st.title("📊 Budget Analytics Dashboard")

# === Load classified data ===
def load_data():
    try:
        with open("data/classified_expenses.json", "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# === Filters ===
def get_period_filter(df, option):
    today = dt.date.today()
    start = None
    end = None
    
    if option == "Current Calendar Month":
        start = today.replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    elif option == "Prior Calendar Month":
        # Get first day of current month, then go back one day to get last day of prior month
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
            # Current period started on 20th, so prior period ended on 19th
            current_start = today.replace(day=20)
            end = (current_start - dt.timedelta(days=1))
            start = (end - dt.timedelta(days=32)).replace(day=20)
        else:
            # Current period ends on 19th, so prior period ended on previous month's 19th
            current_end = today.replace(day=19)
            end = (current_end - dt.timedelta(days=32)).replace(day=19)
            start = (end - dt.timedelta(days=32)).replace(day=20)
    else:
        return df, None, None  # all time

    mask = (df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))
    return df.loc[mask], start, end

# === Main App ===
df = load_data()

if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    period = st.selectbox(
        "Select Time Period:",
        ["Current Calendar Month", "Prior Calendar Month", "Current Credit Card Month", "Prior Credit Card Month", "All Time"]
    )

    filtered, start_date, end_date = get_period_filter(df, period)
    
    # Display date range
    if start_date and end_date:
        st.info(f"📅 **Date Range:** {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}")
    elif period == "All Time":
        if not filtered.empty:
            min_date = filtered["date"].min().strftime('%B %d, %Y')
            max_date = filtered["date"].max().strftime('%B %d, %Y')
            st.info(f"📅 **Date Range:** {min_date} - {max_date}")
        else:
            st.info("📅 **Date Range:** No data available")

    # Calculate summary metrics
    total_spending = filtered[filtered["category"] != "IGNORE"]["amount"].sum()
    effective_spending = filtered[filtered["category"].isin(["WORK", "WANT", "NEED"])]["amount"].sum()
    
    # Display summary metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 Total Spending", f"${total_spending:,.0f}")
    with col2:
        st.metric("🎯 Effective Spending", f"${effective_spending:,.0f}")
    
    st.divider()
    
    st.subheader("📌 Total Spent by Category")
    cat_sum = filtered[filtered["category"] != "IGNORE"].groupby("category")["amount"].sum().reset_index()
    fig1 = px.bar(cat_sum, x="category", y="amount", title="Spending by Category")
    fig1.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("📌 Total Spent by Subcategory")
    # Check if subcategory column exists and handle missing values
    if "subcategory" in filtered.columns:
        # Fill missing subcategories with "No Subcategory"
        filtered_copy = filtered.copy()
        filtered_copy["subcategory"] = filtered_copy["subcategory"].fillna("No Subcategory")
        filtered_copy["subcategory"] = filtered_copy["subcategory"].replace("", "No Subcategory")
        
        subcat_sum = filtered_copy.groupby(["category", "subcategory"])["amount"].sum().reset_index()
        fig2 = px.bar(subcat_sum, x="subcategory", y="amount", color="category", title="Spending by Subcategory")
        fig2.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Subcategory data not available. Please ensure your expense data includes subcategory information.")

    st.subheader("🧾 Detailed Expenses")
    st.dataframe(filtered.sort_values("date", ascending=False))
else:
    st.warning("No classified expense data found. Make sure 'classified_expenses.json' exists in /data.")