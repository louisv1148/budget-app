import os
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

st.set_page_config(
    page_title="💰 Personal Budget Suite",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

page = st.navigation([
    st.Page("pages/close_month.py", title="🗓️ Close Month"),
    st.Page("analytics_dashboard.py", title="📊 Analytics Dashboard"),
    st.Page("pages/classifier_ui.py", title="🏷️ Expense Classifier"),
    st.Page("budget_planner.py", title="📋 Budget & Recurring"),
])

page.run()
