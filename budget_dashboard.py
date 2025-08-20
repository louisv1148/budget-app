import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="💰 Budget Planner", layout="wide")
st.title("💰 Budget Setup and Allocation")

# === Constants ===
CATEGORY_OPTIONS = ["WANT", "NEED", "SAVINGS", "WORK"]

def load_budget():
    if os.path.exists("data/budget.json"):
        with open("data/budget.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {cat: {"total": 0, "subcategories": {}} for cat in CATEGORY_OPTIONS}

def save_budget(data):
    os.makedirs("data", exist_ok=True)
    with open("data/budget.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

budget = load_budget()

# === Budget Summary Table ===
st.subheader("📊 Budget Summary")

# Calculate totals for summary table
summary_data = []
total_budget = 0

for category in CATEGORY_OPTIONS:
    category_total = budget[category]["total"]
    total_budget += category_total
    summary_data.append({
        "Category": category,
        "Budget Amount": f"${category_total:,.2f}"
    })

# Add total row
summary_data.append({
    "Category": "**TOTAL BUDGET**",
    "Budget Amount": f"**${total_budget:,.2f}**"
})

# Display as table
summary_df = pd.DataFrame(summary_data)
st.table(summary_df)

st.divider()

st.write("### Edit your budget for each category and subcategory")

for category in CATEGORY_OPTIONS:
    st.subheader(f"📂 {category}")

    total = st.number_input(f"Total Budget for {category}", min_value=0.0, value=float(budget[category]["total"]), step=50.0, key=f"total_{category}")
    budget[category]["total"] = total

    subcats = budget[category].get("subcategories", {})
    keys_to_remove = []

    # Display and edit existing subcategories
    if subcats:
        for subcat, value in subcats.items():
            col1, col2, col3 = st.columns([4, 3, 1])
            with col1:
                new_name = st.text_input("Subcategory Name", value=subcat, key=f"name_{category}_{subcat}")
            with col2:
                new_value = st.number_input("Allocated Budget", value=float(value), step=10.0, key=f"val_{category}_{subcat}")
            with col3:
                if st.button("🗑️ Remove", key=f"del_{category}_{subcat}"):
                    keys_to_remove.append(subcat)
                    continue

            # Apply changes
            if new_name != subcat:
                budget[category]["subcategories"].pop(subcat)
                budget[category]["subcategories"][new_name] = new_value
            else:
                budget[category]["subcategories"][subcat] = new_value

    # Remove marked subcategories
    for key in keys_to_remove:
        budget[category]["subcategories"].pop(key)

    # Add new subcategory
    col_add1, col_add2 = st.columns([6, 2])
    with col_add1:
        new_subcat = st.text_input(f"New subcategory for {category}", key=f"new_subcat_{category}")
    with col_add2:
        new_value = st.number_input(f"Value", min_value=0.0, step=10.0, key=f"new_val_{category}")

    if new_subcat:
        if st.button(f"➕ Add {new_subcat} to {category}", key=f"add_{category}"):
            if new_subcat not in budget[category]["subcategories"]:
                budget[category]["subcategories"][new_subcat] = new_value
                st.rerun()

    # Display unallocated budget
    allocated = sum(budget[category]["subcategories"].values())
    unallocated = total - allocated
    st.info(f"💡 Unallocated: ${unallocated:,.2f}")

# === Save button ===
if st.button("💾 Save Budget"):
    save_budget(budget)
    st.success("✅ Budget saved successfully to data/budget.json")