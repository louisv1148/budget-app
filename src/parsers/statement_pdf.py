"""Parse bank/credit-card statement PDFs via the Claude API.

One entry point: `parse_statement(pdf_path, issuer)` → list of raw transaction
dicts with keys: date, description, amount_native, currency_native, foreign.
`issuer` is one of AMEX | BBVA | NU | GBM and tunes the prompt.

Cost: roughly a few cents per statement. Keep the `anthropic` client lazy so
the page loads even without the key configured; callers should surface a
friendly message when `ANTHROPIC_API_KEY` is missing.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

from schema import ORIGINS


# Per-issuer hints injected into the user prompt. Keep these declarative — the
# model handles the heavy lifting.
ISSUER_HINTS: dict[str, str] = {
    "AMEX": (
        "This is a Spanish-language American Express (Mexico) statement. "
        "Extract each cargo/compra. Skip 'PAGO RECIBIDO', 'INTERES', unless "
        "explicitly a fee. Amounts that are negative (shown with parentheses "
        "or a minus sign) should be treated as refunds — preserve sign. "
        "Charges marked 'USD' or with 'Dolar' commentary are USD-denominated; "
        "put the USD amount in amount_native and set currency_native='USD'. "
        "Otherwise MXN. Include MSI (meses sin intereses) installments as "
        "separate rows at the per-month amount."
    ),
    "BBVA": (
        "This is a BBVA (Mexico) account statement in English. Extract debit "
        "card charges and direct debits. Skip internal transfers between own "
        "accounts unless they're clearly payments to a third party. Amounts "
        "are MXN."
    ),
    "NU": (
        "This is a Nu (Nubank Mexico) credit card statement. Extract purchases "
        "from the 'compras del periodo' section. Skip 'Pago recibido' and "
        "'Intereses' rows. Amounts are MXN."
    ),
    "GBM": (
        "This is a GBM (Grupo Bursátil Mexicano) brokerage statement. Extract "
        "trades, fees, and dividends. Mark trades with section='IGNORE' in "
        "extra_hint because they're movements, not expenses. Extract only fees "
        "and maintenance charges as transactions. Amounts are MXN."
    ),
}


def _strict_system_prompt() -> str:
    return (
        "You extract financial transactions from bank and credit card statement PDFs. "
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "statement_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or null,\n'
        '  "transactions": [\n'
        "    {\n"
        '      "date": "YYYY-MM-DD",\n'
        '      "description": "merchant / description as-printed",\n'
        '      "amount_native": number (positive for charges, negative for refunds),\n'
        '      "currency_native": "MXN" | "USD",\n'
        '      "foreign": boolean (true if currency_native != MXN)\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "No prose. No markdown fences. If a field is unknown, omit it. Dates must "
        "be ISO. Use the current year from the statement period when the txn only "
        "shows month/day."
    )


def _extract_json(text: str) -> dict:
    """Strip code fences if present, then json.loads."""
    if not text:
        raise ValueError("empty model response")
    text = text.strip()
    # remove ```json ... ``` fencing if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def parse_statement(pdf_path: str, issuer: str, *, model: str | None = None) -> dict[str, Any]:
    """Parse `pdf_path` using Claude. Returns the model's full JSON payload.

    Raises FileNotFoundError, RuntimeError, ValueError.
    """
    issuer = issuer.upper()
    if issuer not in ISSUER_HINTS:
        raise ValueError(f"Unknown issuer: {issuer!r}. Expected one of {list(ISSUER_HINTS)}.")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env or shell before parsing."
        )

    # Lazy import so the page loads even without anthropic installed yet.
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(
            "The `anthropic` package is not installed. Run: pip install anthropic"
        ) from e

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    client = Anthropic(api_key=api_key)

    resp = client.messages.create(
        model=model or "claude-sonnet-4-6",
        max_tokens=16000,
        temperature=0,
        system=_strict_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Issuer: {issuer}\n"
                            f"Hint: {ISSUER_HINTS[issuer]}\n\n"
                            "Extract every transaction. Return the JSON per the schema."
                        ),
                    },
                ],
            }
        ],
    )

    # Concatenate any text content blocks.
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    return _extract_json(text)


def raw_txns_to_records(
    raw: list[dict],
    origin: str,
    source_file: str,
) -> list[dict]:
    """Convert Claude's raw txns into v2 transaction records (without 'id' yet).

    The caller is responsible for calling `txn_id()` with an occurrence index
    and upserting via `data_loader.upsert_transactions`.
    """
    from datetime import datetime
    from parsers.cycle_resolver import resolve_cycle
    from schema import normalize_origin

    origin = normalize_origin(origin)
    if origin not in ORIGINS:
        origin = "MANUAL"
    now = datetime.utcnow().isoformat() + "Z"

    out: list[dict] = []
    for r in raw:
        date = str(r.get("date", ""))[:10]
        desc = (r.get("description") or "").strip()
        amt = float(r.get("amount_native", 0) or 0)
        currency = (r.get("currency_native") or "MXN").upper()
        if not date or not desc:
            continue
        cycle = resolve_cycle(origin, date)

        # amount_mxn: for MXN it's identity; for USD we leave None so the
        # Excel exporter / FX module can backfill (plan: reuse Altis fetch_fx).
        amount_mxn = amt if currency == "MXN" else None

        out.append({
            "date": date,
            "description": desc,
            "amount_native": amt,
            "currency_native": currency,
            "amount_mxn": amount_mxn,
            "origin": origin,
            "card_cycle_start": cycle.start,
            "card_cycle_end": cycle.end,
            "close_month": cycle.close_month,
            "section": "VARIABLE",  # default until classified
            "subcategory": "",
            "note": "",
            "reviewed": False,
            "imported_from": os.path.basename(source_file),
            "imported_at": now,
        })
    return out
