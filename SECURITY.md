# 🔒 Security & Privacy

## Protected Files

This application handles sensitive financial data. The following files are **NEVER** committed to git:

### Financial Data (Completely Private)
- `data/budget.json` - Your personal budget allocations
- `data/classified_expenses.json` - Your categorized expenses
- `data/classified_expenses_reviewed.json` - Reviewed expense classifications
- `data/to_edit.json` - Temporary editing files
- Any `*.json` files in the `data/` directory

### API Keys & Secrets
- `.env` files - Environment variables and API keys
- `*.key` files - Any key files
- `*.secret` files - Secret configuration files
- `api_keys.txt`, `secrets.txt`, `credentials.json`

## Setting Up Securely

1. **Copy Environment Template**: `cp .env.template .env`
2. **Add Your API Keys**: Edit `.env` with your actual API keys
3. **Never Share**: Your `.env` file and `data/` directory are private

## Git Safety

The `.gitignore` file is configured to protect all sensitive data. Before committing:

```bash
# Verify no sensitive data will be committed
git status
git diff --cached

# Only commit application code, never data files
git add src/ requirements.txt README.md
```

## Data Location

All your sensitive financial data stays in the `data/` directory on your local machine only. This ensures:

- ✅ Your expenses remain completely private
- ✅ Budget information never leaves your computer
- ✅ API keys are never exposed publicly
- ✅ Bank/financial data stays secure

## Sharing This Project

If you want to share this code:
1. Fork/clone contains only application code
2. No financial data or API keys included
3. Other users create their own `data/` directory
4. Other users add their own `.env` file