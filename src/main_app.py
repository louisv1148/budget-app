import streamlit as st

# Configure the main app
st.set_page_config(
    page_title="💰 Personal Budget Suite",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navigation
page = st.navigation([
    st.Page("analytics_dashboard.py", title="📊 Analytics Dashboard"),
    st.Page("pages/classifier_ui.py", title="🏷️ Expense Classifier"),
    st.Page("budget_planner.py", title="📋 Budget Planner"),
])

# Run the selected page
page.run()