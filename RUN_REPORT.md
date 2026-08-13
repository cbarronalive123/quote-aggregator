# QuoteDrive — Redacted Run Report

> **Applicant:** saved personal profile (Ontario resident). PII redacted per hackathon rules — no
> full name, licence number, address, phone, email, or VIN in this document.
>
> **Vehicle (redacted):** 2012 RAM 1500 Quad Cab 4WD · Ontario PPA · Kitchener-area postal code
>
> **Benchmark coverage package (apples-to-apples target):**
> $2M third-party liability · DCPD included · $1,000 collision/comprehensive deductibles ·
> OPCF 44R family protection · standard accident benefits · no telematics · 12-month term

---

## 1. Coverage ledger (benchmark)

| Coverage element | Target for comparison |
|------------------|----------------------|
| Third-party liability | $2,000,000 |
| DCPD | Included |
| Collision / comprehensive | $1,000 deductible each |
| Endorsements | OPCF 44R (family protection) |
| Accident benefits | Standard mandatory Ontario AB |
| Telematics | Declined (benchmark) |
| Term | 12 months |

---

## 2. Best full 3-carrier automated run (saved profile)

**Run ID:** local `quote_runner` orchestrator · **Timestamp:** 2026-08-11T21:48:53Z (UTC)  
**Environment:** local headed/minimized Playwright · **Profile:** saved applicant (real)  
**Source:** `quote_results.jsonl` / parent orchestrator log

| Carrier | Registry ID | Status | Monthly | Annual | Quote ref | Source |
|---------|---------------|--------|---------|--------|-----------|--------|
| belairdirect | intact-belair-001 | quoted_comparable | $75.58 | $906.96 | BA13967229 | automated |
| Aviva Direct | aviva-001 | quoted_comparable | $263.63 | $3,163.56 | Q 022765563 | automated |
| Allstate | allstate-001 | quoted_comparable | $148.06 | $1,776.72 | 083198576 | automated |

**Comparison (monthly, same profile):** belairdirect **$75.58** · Aviva **$263.63** · Allstate **$148.06**

**Coverage notes:** all three runs used the benchmark intake ($2M TPL, $1k deductibles, OPCF 44R).
Aviva premium reflects RAM 1500 rating; belairdirect and Allstate completed full online raters.

---

## 3. Latest deployed-server run (saved profile)

**Run ID:** server history #23 · **Timestamp:** 2026-08-12T22:56:55Z  
**Environment:** deployed QuoteDrive website + Docker Playwright container on VPS  
**API:** `GET /api/history` on deployed instance

| Carrier | Status | Monthly | Annual | Quote ref | Notes |
|---------|--------|---------|--------|-----------|-------|
| belairdirect | quoted_comparable | $68.50 | $822.00 | BA13978515 | automated · evidence screenshot on server |
| Aviva Direct | **blocked** | — | — | — | `vehicleMake` select timeout (RAM trim mismatch in container session) |
| Allstate | **blocked** | — | — | — | online quote blocked; phone fallback failed (no physical phone connected) |

**Server pattern (Aug 12, multiple Corey runs):** belairdirect consistently returns **~$68.50/mo**
(BA13969998–BA13978515). Aviva fails on server due to vehicle-make selector. Allstate online
blocked from datacenter IP; phone agent dial attempted when device connected.

---

## 4. Evidence-backed handoff / no-quote outcomes

| Carrier | Route | Status | Timestamp | Outcome |
|---------|-------|--------|-----------|---------|
| Allstate | Phone (1-800-255-7828 via ADB) | callback_required | 2026-08-12T13:39:18Z | Outbound call placed on connected cell phone; premium not yet parsed back |
| Allstate | Phone fallback | blocked | 2026-08-12T22:56:55Z | `Phone fallback failed: no physical (cell) phone connected` |
| Coachman (via NFP) | Licensed broker phone | quoted_non_comparable | 2026-08-09T16:20:10Z | $110.00/mo · ref NFP-4492 · non-standard rating · binder expired |

---

## 5. Coverage normalization gap (belairdirect early run)

**Run date:** 2026-08-09 · **Route:** belairdirect direct online rater  
**Result:** $71.92/mo · ref **BA13933019** · status `quoted_comparable_candidate`

| Cover (as returned by rater) | Detail |
|------------------------------|--------|
| Liability | **$1,000,000** (below $2M benchmark) |
| DCPD | Included · $0 deductible |
| Family protection | Included |
| Accident benefits | Non-cat $65,000 / cat $1,000,000 |
| Own-damage | Default offer (limits not fully disclosed on summary page) |

**Gap:** rater defaulted to $1M TPL vs $2M benchmark → marked `quoted_comparable_candidate`, not
ranked against Aviva/Allstate until normalized.

---

## 6. Errors and retries (saved profile timeline)

| Timestamp (UTC) | Carrier | Error (abbreviated) | Resolution |
|-----------------|---------|---------------------|------------|
| 2026-08-11T21:13:26 | Aviva | Confirm-button timeout | Fixed in later run |
| 2026-08-11T21:13:26 | Allstate | Continue button disabled | Fixed in later run |
| 2026-08-11T21:38:16 | Allstate | Marital-status select mismatch | Fixed in later run |
| 2026-08-11T21:48:53 | All three | — | **Full success** (Section 2) |
| 2026-08-12 (server) | Aviva | `vehicleMake` select timeout | Open — RAM/HONDA per-rater vehicle override needed |
| 2026-08-12 (server) | Allstate | Datacenter IP gate + phone agent unavailable | Phone handoff when ADB device connected |

---

## 7. Summary

- **Real quotes obtained** for all three primary carriers on the saved applicant profile (Section 2).
- **Deployed server** reproduces belairdirect reliably; Aviva/Allstate show terminal blockers
  documented above (Section 3–4).
- **No PII** included in this report. Full run history with timestamps available on the deployed
  QuoteDrive instance at `/history` (requires server access; DB not committed to GitHub).

---

*Generated for Ontario All-Quote Agent Challenge submission · QuoteDrive · August 2026*
