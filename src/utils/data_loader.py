"""
Data loading and management utilities for the budget application.
"""

import json
import os
from typing import List, Dict, Any
from datetime import datetime

def load_expenses(filepath: str) -> List[Dict[str, Any]]:
    """Load expenses from a JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file {filepath}: {e}")
        return []

def save_expenses(data: List[Dict[str, Any]], filepath: str) -> bool:
    """Save expenses to a JSON file."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving to {filepath}: {e}")
        return False

def load_existing_expenses(filepath: str = "data/classified_expenses.json") -> List[Dict[str, Any]]:
    """Load existing classified expenses."""
    return load_expenses(filepath)

def deduplicate_expenses(existing_expenses: List[Dict[str, Any]], 
                        new_expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate expenses based on date, description, and amount."""
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

def append_to_classified_expenses(reviewed_expenses: List[Dict[str, Any]], 
                                filepath: str = "data/classified_expenses.json") -> int:
    """Append reviewed entries to classified expenses file."""
    existing_expenses = load_existing_expenses(filepath)
    deduplicated_new = deduplicate_expenses(existing_expenses, reviewed_expenses)
    
    if deduplicated_new:
        all_expenses = existing_expenses + deduplicated_new
        save_expenses(all_expenses, filepath)
        return len(deduplicated_new)
    return 0

def get_data_file_path(filename: str) -> str:
    """Get the full path for a data file."""
    return os.path.join("data", filename)

def backup_data(source_file: str, backup_suffix: str = None) -> str:
    """Create a backup of a data file."""
    if backup_suffix is None:
        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    base_name = os.path.splitext(source_file)[0]
    extension = os.path.splitext(source_file)[1]
    backup_file = f"{base_name}_backup_{backup_suffix}{extension}"
    
    try:
        data = load_expenses(source_file)
        save_expenses(data, backup_file)
        return backup_file
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None