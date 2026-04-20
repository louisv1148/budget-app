# Budget App

A personal budget reconciliation tool for closing monthly credit-card / bank statements against a structured monthly budget. Built for one person, one workflow.

## What it does

- Ingest Amex (ES), BBVA, Nu, and GBM statement PDFs; Claude extracts transactions into structured JSON.
- Resolve each transaction to its statement cycle (Amex 20→19; others calendar) and close month.
- Review and classify transactions by section: `FIXED_OBLIGATIONS`, `MSI`, `SUBSCRIPTIONS`, `OFF_CARD`, `VARIABLE`, `BUSINESS_REIMBURSABLE`, `FEES`, `INCOME`, `IGNORE`.
- Generate `budget_full_{YYYY-MM}.xlsx` — a single-sheet monthly close workbook with subtotals, formula-driven summary, and an MSI roll-off tracker.

## Pages

- **Close Month** — upload statements for a month, review the combined grid, generate the Excel.
- **Analytics Dashboard** — spending vs. budget by section and subcategory, with credit-card-cycle-aware filters.
- **Expense Classifier** — edit a single transaction (invoked from the Dashboard's ✏️ button).
- **Budget & Recurring** — edit section budgets and the `recurring.json` that drives Income / Fixed / MSI / Subscriptions / Off-Card.

## Getting started

```bash
# one-time: copy .env.template to .env and fill in ANTHROPIC_API_KEY
cp .env.template .env

# launch
./launch_app.command
```

## Layout

```
src/
  main_app.py                  Streamlit entry point + page nav
  schema.py                    SECTIONS, ORIGINS, txn_id, normalize_origin
  analytics_dashboard.py       Spending vs. budget visualization
  budget_planner.py            Budget + Recurring editors
  pages/
    close_month.py             Monthly ingest + review + Excel export
    classifier_ui.py           Single-transaction edit
  parsers/
    statement_pdf.py           Claude-driven PDF extraction
    cycle_resolver.py          (origin, date) → statement cycle
  export/
    budget_full_excel.py       openpyxl builder for the monthly Excel
  utils/
    data_loader.py             JSON I/O for transactions / recurring / budget / monthly_close
  tools/
    migrate_v1_to_v2.py        One-shot WANT/NEED → sections migration

data/                          All data (gitignored)
  transactions.json
  recurring.json
  budget.json
  monthly_close.json
  exports/                     Generated Excels
```

## Data model

See [.claude/plans/](../../.claude/plans/) for the plan file and full schema spec. Transactions look like:

```jsonc
{
  "id": "amex-2026-03-f4a2b1",           // sha1(origin|date|amount|desc)[:12]
  "date": "2026-03-12",
  "description": "JW MARRIOTT HOTELS",
  "amount_native": 8420.00,
  "currency_native": "MXN",
  "amount_mxn": 8420.00,
  "origin": "AMEX",
  "card_cycle_start": "2026-02-20",
  "card_cycle_end":   "2026-03-19",
  "close_month":      "2026-03",
  "section": "BUSINESS_REIMBURSABLE",
  "subcategory": "Hotels",
  "note": "...",
  "reimbursement": { "reembolso": "Clipway", ... },
  "reviewed": true
}
```

## Security

- `data/*.json`, `.env`, `venv/`, and statement PDFs are gitignored.
- Statement PDFs stay in OneDrive — the app reads them in place and uploads only to the Anthropic API for parsing.
- No credentials or transaction contents are logged.

## Roadmap

Subphases 1–4 are shipped (schema, section-based UI, PDF parser + Close Month MVP, Excel exporter). Not yet built: Notion roadshow cross-reference, EventKit calendar hints, AI section classifier, Altis reimbursement-skill bridge, month-close lifecycle. See [.claude/plans/](../../.claude/plans/) for the full plan.
