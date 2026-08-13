"""Text helpers for cleaning LLM output before it is shown or spoken."""

from __future__ import annotations

import re

# Broad set of emoji / symbol ranges (incl. variation selectors, ZWJ joins,
# and skin-tone modifiers) so replies stay clean for the chat log and TTS.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # many emoji blocks
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U0001F300-\U0001F64F"  # pictographs / emotion
    "\U0001F680-\U0001F6FF"  # transport
    "\U00002600-\U000027BF"  # misc symbols & dingbats
    "\U00002190-\U000021FF"  # arrows
    "\U00002100-\U0000214F"  # letterlike symbols
    "\U00002300-\U000023FF"  # misc technical
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero-width joiner
    "\U0001F3FB-\U0001F3FF"  # skin-tone modifiers
    "]+"
)


def strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def clean_reply(text: str) -> str:
    """Normalize an LLM reply for display + speech: no emojis, tidy spacing."""
    text = strip_emojis(text)
    # Collapse stray whitespace/newlines into single spaces, drop blank lines.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    text = " ".join(ln for ln in lines if ln)
    return text.strip()
