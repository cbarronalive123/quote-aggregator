"""Quote record + notes for the auto quote agent.

At the end of the call the broker supplies the quote (annual price, monthly
price, quote/reference number, company, valid-until, call-back phone). These are
captured and written to a JSON notes file so they can be referenced later.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_COMPANY = "Allstate"


@dataclass
class QuoteRecord:
    annual: float | None = None
    monthly: float | None = None
    reference_number: str = ""
    company: str = DEFAULT_COMPANY
    valid_until: str = ""
    phone_number: str = ""
    coverage_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CallNotes:
    applicant: str = "Test Driver"
    purpose: str = "Ontario private-passenger auto insurance quote"
    recorded: bool = True
    terminal_status: str = "unresolved"
    quote: QuoteRecord = field(default_factory=QuoteRecord)
    questions_asked: int = 0
    unknowns: list[str] = field(default_factory=list)
    outstanding_fields: list[str] = field(default_factory=list)
    blockers: str = ""
    whats_needed: list[str] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["quote"] = self.quote.to_dict()
        return d


def write_notes(notes: CallNotes, path: Path | None = None) -> Path:
    """Persist call notes as JSON for future reference."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "auto_quote_agent" / "call_notes.json"
    notes.timestamp = notes.timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes.to_dict(), indent=2, default=str), encoding="utf-8")
    return path
