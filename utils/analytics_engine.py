"""
Analytics and calculation engine for budget insights.
"""

import pandas as pd
import json
import datetime as dt
from typing import List, Dict, Any

def load_data(filepath: str = "data/classified_expenses.json") -> pd.DataFrame:
    """Load classified expenses data into a DataFrame."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def get_period_filter(df: pd.DataFrame, option: str) -> pd.DataFrame:
    """Filter DataFrame by time period."""
    today = dt.date.today()
    
    if option == "Current Calendar Month":
        start = today.replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    elif option == "Current Credit Card Month":
        if today.day >= 20:
            start = today.replace(day=20)
            end = (start + dt.timedelta(days=32)).replace(day=19)
        else:
            end = today.replace(day=19)
            start = (end - dt.timedelta(days=32)).replace(day=20)
    else:
        return df  # all time

    mask = (df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))
    return df.loc[mask]

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and prepare data for analysis."""
    if df.empty:
        return df
    
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    
    return df