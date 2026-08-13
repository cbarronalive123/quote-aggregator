# Insurance Websites — SQLite Extraction Report

> Generated from the three CSV files in the workspace:
> - `Insurance_broker_CA.csv` (8,264 data rows)
> - `Insurance_CA.csv` (11,772 data rows)
> - `Insurance_company_CA.csv` (9,857 data rows)

## Summary

| Metric | Value |
|---|---|
| Total CSV rows scanned | 29,893 |
| Rows with a usable website value | 26,363 |
| **Unique root domains** | **4,965** |
| SQLite database file | `insurance_websites.db` |
| Script that produced it | `extract_websites.py` |

## Extraction Methodology

1. **Read all three CSVs** with Python (`csv` module, `utf-8-sig` encoding to strip BOM).
2. **Pulled the `website` column** from every row. Many cells contained comma-separated URLs or extra whitespace — only the first token in each cell was kept.
3. **Normalized each URL** to a bare hostname (lowercased, `www.` kept in the normalized host but stripped for grouping purposes via root-domain extraction). Rows that were empty, contained only an email address (`@` with no scheme), or had no dot in the host were dropped.
4. **Derived a root domain** for grouping. Common two-part Canadian TLDs (e.g. `co.ca`, `on.ca`, `qc.ca`, `gc.ca`) are treated as a single suffix, so `foo.on.ca` collapses to `foo.on.ca` rather than `on.ca`.
5. **Cleaned address metadata** out of the `complete_address` JSON-ish blob column (city, province, postal code) using lightweight regex so the DB can be sliced by region.
6. **Wrote two tables** into `insurance_websites.db`:
   - `websites` — every kept row (company name, raw + normalized URL, root domain, category, city, province, postal, phone, lat/lon, source file).
   - `unique_domains` — one row per unique root domain, with a count of how many source rows it appeared in and which file it was first seen in.

## Per-source-file Breakdown (kept rows)

| Source file | Kept rows |
|---|---|
| `Insurance_CA.csv` | 10,221 |
| `Insurance_company_CA.csv` | 8,565 |
| `Insurance_broker_CA.csv` | 7,577 |

## Geographic Distribution (by province parsed from address)

| Province | Rows |
|---|---|
| Ontario | 11,075 |
| Quebec | 5,769 |
| British Columbia | 4,557 |
| Alberta | 1,709 |
| Saskatchewan | 568 |
| New Brunswick | 550 |
| Nova Scotia | 465 |
| Manitoba | 391 |
| (unknown) | 385 |
| Prince Edward Island | 243 |
| Newfoundland and Labrador | 231 |
| Yukon | 39 |
| Northwest Territories | 31 |
| + a small number of cross-border rows (Michigan, New York, Maine) | ~44 |

## Top 10 Most Common Domains

These are the carriers/brokers with the largest footprint in the dataset (domain → number of rows it appeared in):

| Domain | Row count |
|---|---|
| cooperators.ca | 1,169 |
| allstate.ca | 955 |
| westlandinsurance.ca | 635 |
| brokerlink.ca | 495 |
| primerica.com | 425 |
| thebig.ca | 419 |
| sunlife.ca | 415 |
| hubinternational.com | 372 |
| desjardins.com | 342 |
| ia.ca | 247 |

## Domain-frequency Distribution

- **1,818 domains** appear in exactly one row (single-location brokers).
- **1,010 domains** appear in two rows.
- The long tail shows a small set of national carriers appearing in hundreds of rows each (e.g. `cooperators.ca` in 1,169 rows, `allstate.ca` in 955).
- Only ~6 domains appear in more than 400 rows — these are the large national carriers and are the highest-value targets for direct API integration vs. headless-browser automation.

## Re-running the extraction

```bash
python extract_websites.py
```

The script is idempotent: it `DROP`s and recreates the `websites` and `unique_domains` tables every run, so it can be re-run after the CSVs are updated.
