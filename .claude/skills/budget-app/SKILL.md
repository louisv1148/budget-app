---
name: budget-app
description: Launch the budget-app Streamlit UI (the Close Month / Analytics / Classifier / Budget & Recurring pages). Use when the user asks to "open the budget app", "start budget", "run the budget UI", or "launch close month".
---

# Budget App Launcher

Start the local Streamlit app and open it in the browser. The app is the primary UI for monthly statement close, expense review, and budget_full_{YYYY-MM}.xlsx generation.

## What to do

1. Check that a Streamlit process isn't already running on the target port:

   ```bash
   lsof -i :8501 | head -2 || true
   ```

   If it's already up, surface the URL `http://localhost:8501` and stop — don't start a second one.

2. Otherwise, launch in the background:

   ```bash
   cd /Users/lvc/budget-app && ./launch_app.command
   ```

   Use the Bash tool with `run_in_background: true`. `launch_app.command` creates/activates the `venv/`, installs `requirements.txt`, and runs `streamlit run src/main_app.py`.

3. Wait briefly for the server to start, then verify:

   ```bash
   curl -sSf http://localhost:8501/_stcore/health
   ```

   Report the URL to the user and the background task ID so they can stop it later.

## Stopping the app

```bash
pkill -f "streamlit run src/main_app.py"
```

## Troubleshooting

- **Port in use, different project**: edit `launch_app.command` to use `--server.port <N>`.
- **Missing `ANTHROPIC_API_KEY`**: the Close Month page will warn but still load. User must fill in `/Users/lvc/budget-app/.env`.
- **`venv/` out of date**: `rm -rf /Users/lvc/budget-app/venv` and rerun the launcher.
