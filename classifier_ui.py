import streamlit as st
import json
import os
from datetime import datetime

# Load data from uploaded file
def load_expenses(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# Save final classifications to a file
def save_expenses(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Load existing classified expenses
def load_existing_expenses(filepath="classified_expenses.json"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Deduplicate expenses based on date, description, and amount
def deduplicate_expenses(existing_expenses, new_expenses):
    existing_keys = set()
    for exp in existing_expenses:
        key = (exp.get("date"), exp.get("description"), exp.get("amount"))
        existing_keys.add(key)
    
    deduplicated = []
    for exp in new_expenses:
        key = (exp.get("date"), exp.get("description"), exp.get("amount"))
        if key not in existing_keys:
            deduplicated.append(exp)
            existing_keys.add(key)
    
    return deduplicated

# Append reviewed entries to classified_expenses.json
def append_to_classified_expenses(reviewed_expenses):
    existing_expenses = load_existing_expenses()
    deduplicated_new = deduplicate_expenses(existing_expenses, reviewed_expenses)
    
    if deduplicated_new:
        all_expenses = existing_expenses + deduplicated_new
        save_expenses(all_expenses, "classified_expenses.json")
        return len(deduplicated_new)
    return 0

CATEGORY_OPTIONS = [
    "WANT", "NEED", "SAVINGS", "ALTIS", "WORK", "IGNORE", "UNCATEGORIZED"
]

# Map of subcategories linked to each category
SUBCATEGORY_MAP = {
    "WANT": ["Restaurant", "Shopping", "Entertainment"],
    "NEED": ["Rent", "Utilities", "Groceries"],
    "SAVINGS": ["Emergency Fund", "Investments"],
    "ALTIS": ["Bus", "Flight"],
    "WORK": ["Office Supplies", "Subscriptions"],
    "IGNORE": ["Transfer", "Internal"],
    "UNCATEGORIZED": []
}

st.set_page_config(page_title="🧾 Expense Classifier", layout="wide")
st.title("🧾 Review and Confirm New Expenses")

uploaded_file = st.file_uploader("Upload new_expenses.json to classify:", type="json")

if uploaded_file is not None:
    expenses = json.load(uploaded_file)
    st.write(f"Loaded {len(expenses)} expenses.")

    # Show summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        total_amount = sum(exp.get("amount", 0) for exp in expenses)
        st.metric("Total Amount", f"${total_amount:,.2f}")
    with col2:
        categorized = len([exp for exp in expenses if exp.get("category", "UNCATEGORIZED") != "UNCATEGORIZED"])
        st.metric("Categorized", f"{categorized}/{len(expenses)}")
    with col3:
        origins = set(exp.get("origin", "Unknown") for exp in expenses)
        st.metric("Origins", len(origins))

    # Filter options
    st.subheader("Filters")
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        selected_origins = st.multiselect(
            "Filter by Origin",
            options=list(origins),
            default=list(origins)
        )
    with filter_col2:
        show_only_uncategorized = st.checkbox("Show only uncategorized expenses")

    # Filter expenses
    filtered_expenses = []
    for idx, expense in enumerate(expenses):
        if expense.get("origin", "Unknown") not in selected_origins:
            continue
        if show_only_uncategorized and expense.get("category", "UNCATEGORIZED") != "UNCATEGORIZED":
            continue
        filtered_expenses.append((idx, expense))

    st.write(f"Showing {len(filtered_expenses)} expenses after filtering.")

    with st.form("classification_form"):
        updated = False
        
        # Header row
        col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 3, 2, 2, 2.5, 2.5, 3])
        with col1:
            st.write("**Date**")
        with col2:
            st.write("**Description**")
        with col3:
            st.write("**Amount**")
        with col4:
            st.write("**Origin**")
        with col5:
            st.write("**Category**")
        with col6:
            st.write("**Subcategory**")
        with col7:
            st.write("**Note**")
        
        st.divider()

        for display_idx, (original_idx, expense) in enumerate(filtered_expenses):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 3, 2, 2, 2.5, 2.5, 3])
            with col1:
                st.text(expense.get("date", ""))
            with col2:
                st.text(expense.get("description", "")[:40] + ("..." if len(expense.get("description", "")) > 40 else ""))
            with col3:
                st.text(f"${expense.get('amount', 0):,.2f}")
            with col4:
                st.text(expense.get("origin", "Unknown")[:10] + ("..." if len(expense.get("origin", "Unknown")) > 10 else ""))
            with col5:
                current_cat = expense.get("category", "UNCATEGORIZED")
                new_cat = st.selectbox(
                    f"Cat",
                    CATEGORY_OPTIONS,
                    index=CATEGORY_OPTIONS.index(current_cat) if current_cat in CATEGORY_OPTIONS else 0,
                    key=f"cat_{original_idx}",
                    label_visibility="collapsed"
                )
                if new_cat != current_cat:
                    expense["category"] = new_cat
                    # Reset subcategory when category changes
                    expense["subcategory"] = ""
                    updated = True
            with col6:
                # Get subcategory options based on current category
                current_category = expense.get("category", "UNCATEGORIZED")
                subcat_options = SUBCATEGORY_MAP.get(current_category, [])
                current_sub = expense.get("subcategory", "")
                
                if subcat_options:
                    new_sub = st.selectbox(
                        "Sub",
                        [""] + subcat_options,
                        index=([""] + subcat_options).index(current_sub) if current_sub in ([""] + subcat_options) else 0,
                        key=f"sub_{original_idx}",
                        label_visibility="collapsed"
                    )
                    if new_sub != current_sub:
                        expense["subcategory"] = new_sub
                        updated = True
                else:
                    st.text("N/A")
                    expense["subcategory"] = ""
            with col7:
                note = st.text_input(
                    "Note", 
                    value=expense.get("note", ""), 
                    key=f"note_{original_idx}",
                    label_visibility="collapsed"
                )
                if note != expense.get("note", ""):
                    expense["note"] = note
                    updated = True

        st.divider()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            save_reviewed = st.form_submit_button("💾 Save to Reviewed File", use_container_width=True)
        with col2:
            append_to_master = st.form_submit_button("📝 Append to Master File", use_container_width=True)
        with col3:
            save_and_append = st.form_submit_button("💾📝 Save & Append", use_container_width=True)

        if save_reviewed or save_and_append:
            save_expenses(expenses, "classified_expenses_reviewed.json")
            st.success("✅ Changes saved to classified_expenses_reviewed.json")
        
        if append_to_master or save_and_append:
            added_count = append_to_classified_expenses(expenses)
            if added_count > 0:
                st.success(f"✅ Added {added_count} new expenses to classified_expenses.json")
            else:
                st.info("ℹ️ No new expenses to add (all were duplicates)")
        
        if updated and not (save_reviewed or append_to_master or save_and_append):
            st.warning("⚠️ You've made changes. Don't forget to save!")

# Sidebar with instructions
with st.sidebar:
    st.header("📖 Instructions")
    st.markdown("""
    1. **Upload** your `new_expenses.json` file
    2. **Filter** expenses if needed
    3. **Review** and update categories & subcategories
    4. **Add notes** for specific expenses
    5. **Save** your work:
       - **Save to Reviewed File**: Creates `classified_expenses_reviewed.json`
       - **Append to Master File**: Adds new expenses to `classified_expenses.json`
       - **Save & Append**: Does both actions
    """)
    
    st.header("📊 Categories & Subcategories")
    for cat in CATEGORY_OPTIONS:
        subcats = SUBCATEGORY_MAP.get(cat, [])
        if subcats:
            st.write(f"• **{cat}**: {', '.join(subcats)}")
        else:
            st.write(f"• **{cat}**")
    
    st.header("🔧 Features")
    st.write("• Subcategory classification")
    st.write("• Automatic deduplication")
    st.write("• Filter by origin")
    st.write("• Show only uncategorized")
    st.write("• Summary statistics")
    st.write("• Auto-reset subcategory on category change")