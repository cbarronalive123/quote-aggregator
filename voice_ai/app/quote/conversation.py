"""Quote conversation controller.

Holds the call state machine and turns each broker utterance into the agent's
response:
  greeting -> (first response) -> intro as AI agent
  waiting consent -> (yes/go ahead [+ a question]) -> acknowledge + restate purpose
  -> (broker gives a quote) -> record quote + confirm
  -> (broker asks to spell) -> spell the last value slowly, char by char
  -> otherwise -> answer from profile (natural spoken), or honest "don't know"
"""

from __future__ import annotations

import re

from app.quote.profile import ClientProfile
from app.quote.quote_extract import extract_quote
from app.quote.quote_notes import QuoteRecord
from app.quote.spoken import spell_letters

CONSENT_WORDS = {
    "yes", "yeah", "sure", "okay", "ok", "go ahead", "yes go ahead",
    "yes please", "continue", "please do", "that's fine", "that is fine",
    "yes you may", "you can continue",
}

_QUERY_MARKERS = ("when ", "what ", "how ", "which ", "who ", "where ",
                  "is it", "do you", "can i", "can you", "would you",
                  "could you", "are you", "please tell", "spell")


def _is_consent(text: str) -> bool:
    t = re.sub(r"[^a-z0-9 ]", " ", text.strip().lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t in CONSENT_WORDS or t.startswith("yes") or t.startswith("yeah")


def _has_question(low: str) -> bool:
    if "?" in low:
        return True
    return any(m in low for m in _QUERY_MARKERS)


def _is_spell(low: str) -> bool:
    return "spell" in low


class QuoteConversation:
    def __init__(self, engine, applicant: str = "Test Driver",
                 purpose: str = "an Ontario private-passenger auto insurance quote"):
        self.engine = engine
        self.applicant = applicant
        self.purpose = purpose
        self.greeted = False
        self.waiting_consent = False
        self.quote: QuoteRecord | None = None
        self.unknowns: list[str] = []
        self.last_value: str | None = None  # last answered value, for spelling

    # ---- text blocks ----
    def intro_text(self) -> str:
        return (
            "Glad to hear it. Just so you know, I'm an automated assistant calling on "
            f"behalf of {self.applicant} to request {self.purpose}. This call may be "
            "recorded. Is it okay to continue with an automated assistant? The applicant is "
            "available if you need verification or consent."
        )

    def consent_text(self) -> str:
        return (
            f"Great, thank you. To confirm, I'm here to get {self.purpose} for "
            f"{self.applicant}. Let's get started."
        )

    def quote_text(self, q: QuoteRecord) -> str:
        parts = [f"Thank you, I've recorded that quote."]
        if q.monthly:
            parts.append(f"{q.monthly:g} dollars per month")
        if q.annual:
            parts.append(f"which comes to about {q.annual:g} dollars per year")
        if q.reference_number:
            parts.append(f"with reference number {spell_chars(q.reference_number)}")
        return " ".join(parts) + "."

    # ---- turn handler ----
    def respond(self, broker_text: str) -> dict:
        t = (broker_text or "").strip()
        low = t.lower()

        if not self.greeted:
            self.greeted = True
            self.waiting_consent = True
            return {"type": "intro", "text": self.intro_text(), "quote": None}

        consent = _is_consent(t)
        if self.waiting_consent and consent:
            self.waiting_consent = False
            # Combined "yes go ahead" + an actual question in the same utterance.
            if _has_question(low) and len(t) > 20:
                ans = self.engine.spoken_answer(t)
                if ans and "I don't have that information" not in ans:
                    return {"type": "consent", "text": self.consent_text() + " " + ans,
                            "quote": None}
            return {"type": "consent", "text": self.consent_text(), "quote": None}

        # Quote extraction.
        qr = extract_quote(t)
        if qr:
            if (self.quote is not None
                    and qr.monthly is None and qr.annual is None and qr.reference_number):
                # Broker is restating/correcting only the reference -> keep prices.
                self.quote.reference_number = qr.reference_number
            else:
                self.quote = qr
            return {"type": "quote", "text": self.quote_text(self.quote), "quote": self.quote}

        # Spelling request.
        if _is_spell(low):
            if self.last_value:
                spelled = spell_letters(self.last_value)
                return {"type": "spell", "text": f"Of course, that's spelled {spelled}.",
                        "spell": self.last_value, "quote": None}
            return {"type": "answer",
                    "text": "I'm not sure which item you'd like me to spell.",
                    "quote": None}

        # Normal answer.
        ans = self.engine.spoken_answer(t)
        if "I don't have that information" in ans:
            self.unknowns.append(t)
            return {"type": "unknown", "text": ans, "quote": None}
        field = self.engine.profile.best_match(t)
        if field is not None:
            self.last_value = field.value
        return {"type": "answer", "text": ans, "quote": None}


def spell_chars(value: str) -> str:
    from app.quote.spoken import spell_chars as _sc
    return _sc(value)
