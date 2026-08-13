"""QuoteAnswerEngine - resolves a broker question against the applicant profile
and produces a spoken/text answer. Also provides the opening disclosure and
end-of-call helpers.

Used by both the CLI test run and the quote-agent GUI.
"""

from __future__ import annotations

from app.llm import OllamaClient
from app.quote.profile import ClientProfile
from app.quote.spoken import spoken_answer

DONT_KNOW = "I don't have that information available, I'm sorry."


class QuoteAnswerEngine:
    def __init__(self, profile: ClientProfile):
        self.profile = profile

    def answer(self, question: str) -> str:
        """Structured answer (label: value), or an honest pass."""
        field = self.profile.best_match(question)
        if field is None or not field.has_value():
            return DONT_KNOW
        return f"{field.label}: {field.value}"

    def spoken_answer(self, question: str) -> str:
        """Natural, spoken-style answer, or an honest pass."""
        field = self.profile.best_match(question)
        if field is None or not field.has_value():
            return DONT_KNOW
        return spoken_answer(field)

    def has_answer(self, question: str) -> bool:
        field = self.profile.best_match(question)
        return field is not None and field.has_value()

    def opening(self, applicant: str, purpose: str) -> str:
        return (
            f"Hello, I am an automated assistant calling on behalf of {applicant} "
            f"to request {purpose}. This call may be recorded. Is it okay to continue "
            f"with an automated assistant? {applicant} is available if you need "
            f"verification or consent."
        )

    def end_of_call(self) -> str:
        return (
            "Thank you. I have everything I need for now. We'll review this and "
            "be in touch if anything else is required."
        )


class LLMAnswerEngine(QuoteAnswerEngine):
    """Semantic resolver: maps each broker question to a real profile field with
    the LLM, and honestly returns "don't know" when no field matches (so it never
    guesses a fact the profile doesn't have). Falls back to keyword matching if
    the LLM is unavailable or returns nothing usable."""

    def __init__(self, profile: ClientProfile, llm: OllamaClient | None = None):
        super().__init__(profile)
        self.llm = llm or OllamaClient()

    def answer(self, question: str) -> str:
        # Deterministic: the most specific match wins (including known-missing
        # fields, so we honestly say "don't know" for e.g. accidents/budget).
        field = self.profile.best_match(question)
        if field is not None:
            if field.has_value():
                return f"{field.label}: {field.value}"
            return DONT_KNOW
        # Keyword found nothing - let the LLM map paraphrases the keyword missed.
        key = self._resolve_field_llm(question)
        if key is None:
            return DONT_KNOW
        f = self.profile.get(key)
        if f is not None and f.has_value():
            return f"{f.label}: {f.value}"
        return DONT_KNOW

    def _resolve_field_llm(self, question: str) -> str | None:
        catalog = "\n".join(
            f"- {f.key}: {f.label}" for f in self.profile.all_fields()
        )
        prompt = (
            "You map an insurance broker's question to the correct field key from "
            "the list below. If no field matches, reply exactly: none\n\n"
            f"Fields:\n{catalog}\n\n"
            f"Question: {question}\n\n"
            "Reply with only the field key, or the single word 'none'."
        )
        try:
            resp = self.llm.generate(prompt).strip().lower()
        except Exception:
            return None
        if resp in ("none", "", "no match", "don't know", "unknown"):
            return None
        for f in self.profile.all_fields():
            if f.key in resp:
                return f.key
        return None
