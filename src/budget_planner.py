import streamlit as st
import json
import os

st.title("💰 Budget Setup and Allocation")

CATEGORY_OPTIONS = ["WANT", "NEED", "SAVINGS", "WORK"]

# === Data functions ===
def load_budget():
    if os.path.exists("data/budget.json"):
        with open("data/budget.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {cat: {"total": 0.0, "subcategories": {}} for cat in CATEGORY_OPTIONS}

def save_budget(data):
    os.makedirs("data", exist_ok=True)
    with open("data/budget.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# === Load or initialize in session ===
if "budget" not in st.session_state:
    st.session_state.budget = load_budget()

budget = st.session_state.budget

st.write("### Edit your budget for each category and subcategory")

# Calculate totals across all categories
total_budget = sum(float(budget[cat].get("total", 0.0)) for cat in CATEGORY_OPTIONS)
total_allocated = sum([
    sum([v["amount"] if isinstance(v, dict) else v for v in budget[cat].get("subcategories", {}).values()])
    for cat in CATEGORY_OPTIONS
])
total_unallocated = total_budget - total_allocated

col1, col2, col3 = st.columns(3)
with col1:
    st.info(f"💰 Total Budget: ${total_budget:,.2f}")
with col2:
    st.info(f"📊 Total Allocated: ${total_allocated:,.2f}")
with col3:
    unallocated_color = "🟢" if total_unallocated >= 0 else "🔴"
    st.info(f"{unallocated_color} Total Unallocated: ${total_unallocated:,.2f}")

st.divider()

for category in CATEGORY_OPTIONS:
    # Get stored values
    current_total = float(budget[category].get("total", 0.0))
    subcat_dict = budget[category].get("subcategories", {})
    allocated = sum([v["amount"] if isinstance(v, dict) else v for v in subcat_dict.values()])
    unallocated = current_total - allocated
    
    # Calculate progress for display
    progress_pct = min(allocated / current_total, 1.0) if current_total else 0

    # Check if this category was just interacted with
    category_key = f"expanded_{category}"
    if category_key not in st.session_state:
        st.session_state[category_key] = False
    
    # Check for button presses that should keep the category expanded
    add_pressed = f"add_{category}" in st.session_state and st.session_state[f"add_{category}"]
    delete_buttons = [f"del_{category}_{subcat}" in st.session_state and st.session_state[f"del_{category}_{subcat}"] 
                     for subcat in subcat_dict.keys()]
    any_delete_pressed = any(delete_buttons) if delete_buttons else False
    
    # Keep expanded if user just interacted with this category
    should_expand = st.session_state[category_key] or add_pressed or any_delete_pressed

    with st.expander(f"📂 {category} (Total: ${current_total:,.2f} | Allocated: ${allocated:,.2f} | Unallocated: ${unallocated:,.2f})", expanded=should_expand):
        # Show progress bar right after category header
        st.progress(progress_pct, text=f"${allocated:,.2f} of ${current_total:,.2f} allocated ({progress_pct*100:.0f}%)")
        # Edit total
        total_key = f"total_{category}"
        new_total = st.number_input(
            f"Total Budget for {category}",
            min_value=0.0,
            value=current_total,
            step=50.0,
            key=total_key
        )
        budget[category]["total"] = new_total

        # === Existing subcategories ===
        with st.expander(f"📋 Subcategories ({len(subcat_dict)} items, ${allocated:,.2f} total)"):
            to_delete = []
            for subcat in list(subcat_dict):
                data = subcat_dict[subcat] if isinstance(subcat_dict[subcat], dict) else {"amount": subcat_dict[subcat], "note": ""}

                col1, col2, col3, col4 = st.columns([3, 2, 4, 1])
                with col1:
                    new_name = st.text_input("Subcategory", value=subcat, key=f"name_{category}_{subcat}")
                with col2:
                    new_val = st.number_input("Amount", min_value=0.0, value=data["amount"], step=10.0, key=f"val_{category}_{subcat}")
                with col3:
                    note = st.text_input("Note", value=data.get("note", ""), key=f"note_{category}_{subcat}")
                with col4:
                    if st.button("🗑️ Remove", key=f"del_{category}_{subcat}"):
                        to_delete.append(subcat)
                        # Keep this category expanded after deleting
                        st.session_state[category_key] = True

                # Update
                if new_name != subcat:
                    del subcat_dict[subcat]
                    subcat_dict[new_name] = {"amount": new_val, "note": note}
                else:
                    subcat_dict[subcat] = {"amount": new_val, "note": note}

            for key in to_delete:
                del subcat_dict[key]

        # === Add new subcategory ===
        # Check if we should clear fields (after successful add)
        clear_key = f"clear_fields_{category}"
        should_clear = st.session_state.get(clear_key, False)
        
        col1, col2, col3 = st.columns([4, 3, 2])
        with col1:
            new_subcat = st.text_input(
                f"New subcategory for {category}", 
                value="" if should_clear else st.session_state.get(f"new_subcat_{category}", ""),
                key=f"new_subcat_{category}"
            )
        with col2:
            new_value = st.number_input(
                "Amount", 
                min_value=0.0, 
                value=0.0 if should_clear else st.session_state.get(f"new_val_{category}", 0.0),
                step=10.0, 
                key=f"new_val_{category}"
            )
        with col3:
            if st.button("Add", key=f"add_{category}") and new_subcat:
                if new_subcat not in subcat_dict:
                    subcat_dict[new_subcat] = {"amount": new_value, "note": ""}
                    # Keep this category expanded after adding
                    st.session_state[category_key] = True
                    # Mark fields to be cleared on next run
                    st.session_state[clear_key] = True
                    st.rerun()
                else:
                    st.warning("Subcategory already exists.")
        
        # Reset clear flag after widgets are rendered
        if should_clear:
            st.session_state[clear_key] = False

        # Display updated unallocated
        updated_allocated = sum([v["amount"] for v in subcat_dict.values()])
        updated_unallocated = new_total - updated_allocated
        unallocated_color = "🟢" if updated_unallocated >= 0 else "🔴"
        st.info(f"{unallocated_color} Unallocated in {category}: ${updated_unallocated:,.2f}")

# === Save Budget ===
if st.button("💾 Save Budget"):
    save_budget(budget)
    st.success("✅ Budget saved successfully to /data/budget.json")