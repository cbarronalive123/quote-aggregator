"""Extract a quote from the broker's spoken/text utterance.

Only amounts that are `$NNN` or `NNN dollars/per month/per year/...` count as
prices, so digits inside a reference number (e.g. ALLS 202688412) are ignored.

Handles:
  "...annual $2,388 ... monthly premium. It's $199. Reference number is ALLS 202688412"
  -> monthly=199, annual=2388, ref=ALLS 202688412
  "...price per month will be $75 ... times 12 months ... reference ID ABC 1 2 3"
  -> monthly=75, annual=900, ref=ABC 1 2 3
"""

from __future__ import annotations

import re

from app.quote.quote_notes import QuoteRecord

_PRICE = re.compile(
    r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b"
    r"|([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:dollars?|per month|/month|a month|monthly|per year|/yr|a year|annually|annual|premium)\b",
    re.IGNORECASE,
)
_REF = re.compile(
    r"(?:quote reference(?:\s*id)?|reference(?:\s*(?:id|number))?)\s*"
    r"(?:will be|is|:)?\s*([A-Za-z0-9][A-Za-z0-9\s\-]{1,24})",
    re.IGNORECASE,
)
_FILLER = {"and", "it", "is", "valid", "until", "which", "the", "are", "you", "that"}


def _num(s: str) -> float:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def _prices(text: str) -> list[tuple[int, float]]:
    out = []
    for m in _PRICE.finditer(text):
        v = (m.group(1) or m.group(2) or "").strip()
        if v and v.replace(",", "").replace(".", "").isdigit():
            out.append((m.start(), _num(v)))
    return out


def _closest(prices: list[tuple[int, float]], idx: int, window: int = 60) -> float | None:
    best = None
    for pos, val in prices:
        if abs(pos - idx) <= window and (best is None or abs(pos - idx) < abs(best[0] - idx)):
            best = (pos, val)
    return best[1] if best else None


def extract_quote(text: str) -> QuoteRecord | None:
    t = text.strip()
    if not t:
        return None
    low = t.lower()
    prices = _prices(t)

    def near(word: str) -> float | None:
        idx = low.find(word)
        return _closest(prices, idx) if idx >= 0 else None

    monthly = near("per month") or near("/month") or near("monthly")
    annual = near("per year") or near("annually") or near("/yr") or near("a year") or near("annual")

    # If 'monthly' landed on the annual price (e.g. "annual $2,388 ... monthly premium"),
    # pick the other amount for monthly.
    if annual is not None and monthly is not None and monthly == annual and len(prices) >= 2:
        idx = max(low.find("per month"), low.find("monthly"))
        _prices_sorted = sorted(prices, key=lambda x: abs(x[0] - idx))
        if len(_prices_sorted) >= 2:
            monthly = _prices_sorted[1][1]

    if annual is None and monthly is not None and ("12" in low or "12 month" in low or "times 12" in low):
        annual = monthly * 12

    ref = ""
    m = _REF.search(t)
    if m:
        tokens = []
        for tok in re.findall(r"[A-Za-z0-9]+", m.group(1)):
            if tok.lower() in _FILLER:
                break
            tokens.append(tok)
        ref = " ".join(tokens).upper()
        # Collapse a spelled-out ID like "A-L-L-S-2-0-2-6-8-8-4-1-2" -> "ALLS202688412"
        if "-" in m.group(1) and " " not in m.group(1):
            ref = ref.replace(" ", "")

    if monthly is None and annual is None and not ref:
        return None
    return QuoteRecord(annual=annual, monthly=monthly, reference_number=ref)
