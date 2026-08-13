"""Insurance Quote Agent - Client Profile schema.

The profile is the single source of truth that the AI caller answers from.
It must never invent a field's value: if a field has no `value`, the honest
answer is "I don't have that" and the field is flagged outstanding.

Fields carry aliases (common ways an agent might phrase a question) so the
Intent Resolver (built next) can match any phrasing. Semantic embedding search
is added later; this module provides the schema + keyword/alias matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field


@dataclass
class ProfileField:
    key: str
    label: str
    aliases: list[str] = dc_field(default_factory=list)
    value: str | None = None
    field_type: str = "text"  # text, date, phone, number, address, bool, list
    sensitive: bool = False
    note: str = ""

    def has_value(self) -> bool:
        return self.value is not None and str(self.value).strip() != ""

    def match_score(self, text: str) -> int:
        """Length of the longest matching alias/label term (0 = no match).

        Longer matches are more specific, so 'vehicle identification number'
        scores higher than 'vehicle' and wins the ranking.
        """
        text = text.lower().strip()
        best = 0
        for term in [self.label, *self.aliases]:
            t = term.lower()
            if t and t in text:
                best = max(best, len(t))
        return best

    def match_alias(self, text: str) -> bool:
        return self.match_score(text) > 0


@dataclass
class ProfileGroup:
    name: str
    fields: list[ProfileField]


class ClientProfile:
    def __init__(self, groups: list[ProfileGroup]):
        self.groups = groups
        self._index = {f.key: f for g in groups for f in g.fields}

    # ---- access ----
    def get(self, key: str) -> ProfileField | None:
        return self._index.get(key)

    def all_fields(self) -> list[ProfileField]:
        return list(self._index.values())

    def group(self, name: str) -> ProfileGroup | None:
        for g in self.groups:
            if g.name == name:
                return g
        return None

    # ---- search / resolution ----
    def search(self, text: str) -> list[ProfileField]:
        """Keyword/alias match ranked by specificity (longest match first).
        Semantic embedding + LLM disambiguation is added in the next step."""
        scored = [(f.match_score(text), f) for f in self.all_fields()]
        scored = [(s, f) for s, f in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored]

    def best_match(self, text: str) -> ProfileField | None:
        """The single most specific matching field, including known-missing
        (no-value) fields, so a question about e.g. 'accidents' targets the
        accidents field (→ honest 'don't know') instead of a weaker 'year' match."""
        scored = [(f.match_score(text), f) for f in self.all_fields()]
        scored = [(s, f) for s, f in scored if s > 0]
        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def missing_fields(self) -> list[ProfileField]:
        return [f for f in self.all_fields() if not f.has_value()]

    # ---- rendering ----
    def to_dict(self) -> dict:
        return {g.name: {f.key: f.value for f in g.fields} for g in self.groups}

    def to_prompt(self) -> str:
        """Render the profile as a compact block for the LLM's context."""
        lines = []
        for g in self.groups:
            lines.append(f"[{g.name}]")
            for f in g.fields:
                val = f.value if f.has_value() else "<unknown>"
                lines.append(f"  {f.key}: {val}")
        return "\n".join(lines)

    def summary(self) -> str:
        total = len(self.all_fields())
        filled = len([f for f in self.all_fields() if f.has_value()])
        return f"Profile: {filled}/{total} fields populated."
