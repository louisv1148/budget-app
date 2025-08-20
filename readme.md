# 🧾 Budget Classifier UI

This Streamlit app allows the user to review and confirm AI-suggested classifications for personal expenses.

## ✅ Features

- Uploads `new_expenses.json` (AI-generated predictions)
- Shows each expense with editable:
  - Category dropdown
  - Optional note field
- Saves reviewed items to `classified_expenses_reviewed.json`

## 🚀 How to Run

1. Install Streamlit if needed:pip install streamlit
2. Launch the UI:streamlit run classifier_ui.py
3. Upload your `new_expenses.json` file

4. Confirm or update classifications

5. Click **Save Reviewed Expenses** to generate `classified_expenses_reviewed.json`

## 🧠 What Claude Should Do

- Add a function to **append reviewed entries** into `classified_expenses.json`
- Optionally: deduplicate entries before saving
- Help integrate GPT classification if local version is needed
- Suggest UX improvements (filter by origin, collapse grouped rows, etc.)
