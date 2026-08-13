"""Test run for the auto quote agent (phone-agent spec).

Simulates a live call with a carrier rep using the applicant's real profile
(auto_quote_agent/profile.json). Exercises the core loop:
  1. Opening disclosure (automation + purpose + recording consent)
  2. Answer the rep's questions (in shuffled order) from the profile
  3. Honestly say "don't know" when a field is missing
  4. Capture a quote if the rep gives one
  5. Produce the terminal status + structured notes per the spec's enum

Run from the project root:  .venv\\Scripts\\python.exe auto_quote_agent\\test_run.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.quote.load_profile import load_profile

# Benchmark coverage requested (apples-to-apples) - from phone_agent_ai.md sec 5.
# Each item includes the natural question the broker would ask and the answer.
BENCHMARK = {
    "effective_date": {
        "question": "When would you like your coverage to take effect?",
        "answer": "2026/09/01",
    },
    "third_party_liability": {
        "question": "What third-party liability limits are you looking for?",
        "answer": "$2,000,000",
    },
    "dcpd": {
        "question": "Do you want DCPD (Direct Compensation - Property Damage) included?",
        "answer": "Included",
    },
    "accident_benefits": {
        "question": "What accident benefits coverage do you need?",
        "answer": "Standard mandatory medical, rehabilitation and attendant care",
    },
    "own_damage": {
        "question": "What own-damage coverage do you want (collision and comprehensive)?",
        "answer": "Collision + comprehensive, $1,000 deductible",
    },
    "endorsements": {
        "question": "Are you interested in any optional endorsements?",
        "answer": "Track OPCF 44R family protection; OPCF 20/27/43 if offered",
    },
    "telematics": {
        "question": "Would you like to opt into telematics / usage-based insurance?",
        "answer": "No",
    },
    "term": {
        "question": "How long a term are you looking for?",
        "answer": "12 months",
    },
}

# Terminal status enum from the brief (sec 10).
STATUSES = ["quoted_comparable", "quoted_non_comparable", "callback_required",
            "manual_handoff", "blocked", "unreachable", "ineligible", "unresolved"]

# A representative (shuffled) call, including one where the rep gives a quote.
REP_QUESTIONS = [
    "Thank you for calling. May I have your full name?",
    "And what is your date of birth?",
    "Can I get your driver's licence number please?",
    "What is your current address?",
    "And do you own your home or do you rent?",
    "Tell me about the vehicle you'd like to insure.",
    "What is the vehicle identification number, the VIN?",
    "How many kilometres do you drive in a year?",
    "Do you have winter tires on the vehicle?",
    "Who are you currently insured with?",
    "What coverage limits are you looking for?",
    "Are you interested in roadside assistance or any add-ons?",
]


def resolve_answer(profile, question: str) -> str:
    """Answer a rep question from the profile, or honestly say we don't know."""
    matches = [f for f in profile.search(question) if f.has_value()]
    if not matches:
        return "I don't have that information available, I'm sorry."
    # Prefer the most specific / first confident match.
    f = matches[0]
    return f"{f.label}: {f.value}"


def opening_disclosure() -> str:
    return (
        "Hello, I am an automated assistant calling on behalf of Test Driver to "
        "request an Ontario private-passenger auto insurance quote. This call may be "
        "recorded. Is it okay to continue with an automated assistant? The applicant is "
        "available if you need verification or consent."
    )


def main():
    profile = load_profile()
    print("=" * 70)
    print("AUTO QUOTE AGENT - SIMULATED TEST RUN")
    print("Applicant: Test Driver | Ontario PPA auto quote | Allstate 1-800 route")
    print(profile.summary())
    print("=" * 70)

    consent_to_record = "yes"
    print("\n[AGENT ->] " + opening_disclosure())
    print(f"[REP ->]   Yes, go ahead. (consent to record: {consent_to_record})")

    transcript = [{"role": "rep", "text": "Yes, go ahead (recording consented)"}]
    answered = []
    unknown = []

    for q in REP_QUESTIONS:
        answer = resolve_answer(profile, q)
        print(f"\n[REP ->]   {q}")
        print(f"[AGENT ->] {answer}")
        transcript.append({"role": "rep", "text": q})
        transcript.append({"role": "agent", "text": answer})
        if "I don't have that information" in answer:
            unknown.append(q)
        else:
            answered.append(q)

    # Simulate the rep giving a quote (quote capture).
    quote = {
        "premium_annual": 2388,
        "premium_monthly": 199,
        "reference_number": "ALLS-2026-88412",
        "carrier": "Allstate",
        "valid_until": "2026/09/01",
        "phone_number": "1-800-255-7828",
        "coverage_matches_benchmark": True,
    }
    print("\n[REP ->]   Alright, I can offer you a full-coverage quote. That's "
          "$199 per month, which works out to $2,388 per year for a 12-month term. "
          "Your quote reference ID is ALLS-2026-88412, and it's valid until "
          "September 1st. You can reach us at 1-800-255-7828 if you have questions.")
    print("[AGENT ->] Thank you. Could you confirm the reference number is "
          "ALLS-2026-88412 and that this matches the $2,000,000 liability and "
          "$1,000 deductible package I requested?")
    transcript.append({"role": "rep", "text": "quote offered"})

    # End-of-call notes.
    status = "quoted_comparable" if quote["coverage_matches_benchmark"] else "quoted_non_comparable"
    notes = {
        "applicant": "Test Driver",
        "purpose": "Ontario private-passenger auto insurance quote",
        "route": "outbound to Allstate 1-800-255-7828",
        "recorded": consent_to_record == "yes",
        "benchmark_coverage": BENCHMARK,
        "questions_answered": len(answered),
        "questions_unknown": unknown,
        "outstanding_fields": [f.key for f in profile.missing_fields()],
        "blockers": "none",
        "whats_needed": [] if quote["coverage_matches_benchmark"] else "confirm coverage differences",
        "transcript": transcript,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "terminal_status": status,
        "quote_obtained": True,
        "quote": quote,
    }

    print("\n" + "=" * 70)
    print("TERMINAL STATUS:", status)
    print("=" * 70)
    print(json.dumps(notes, indent=2, default=str))

    out = Path(__file__).resolve().parent / "test_run_notes.json"
    out.write_text(json.dumps(notes, indent=2, default=str), encoding="utf-8")
    print(f"\nNotes written to: {out}")


if __name__ == "__main__":
    main()
