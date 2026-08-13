"""
register_form_script.py
=======================
Create the `form_scripts` table (if missing) and register a quote-form -> script
mapping in insurance_websites.db.

This is the DB side of the methodology: every quote form that gets a Playwright
automation script is recorded here so the registry knows which file drives it.

Examples
--------
Create table + register the Verge auto quote script (a lead-gen form):
    python register_form_script.py --form "https://www.vergeinsurance.com/auto-insurance-quote/" \
        --domain vergeinsurance.com --type auto --script vergeinsurance_auto_quote.py \
        --kind lead_gen

Update an existing record's status / note / kind:
    python register_form_script.py --form "..." \
        --status submitted --kind lead_gen --note "Filled, submitted, followed to thank-you page."
"""
import argparse
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "insurance_websites.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS form_scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_url TEXT NOT NULL,
            domain TEXT,
            insurance_type TEXT,
            script_file TEXT,
            status TEXT DEFAULT 'registered',
            result_note TEXT,
            form_kind TEXT DEFAULT 'unknown',   -- lead_gen | quote | unknown
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT,
            UNIQUE(form_url)
        )
    """)
    return conn


def main():
    ap = argparse.ArgumentParser(description="Register a quote form -> script in the DB.")
    ap.add_argument("--form", required=True, help="Quote form URL (the form's page).")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--type", default=None, help="insurance_type: auto/property/business/life/travel/unknown")
    ap.add_argument("--script", default=None, help="script file name, e.g. vergeinsurance_auto_quote.py")
    ap.add_argument("--kind", default=None, choices=["lead_gen", "quote", "unknown"],
                    help="form_kind: lead_gen (collects info, no live $ value) vs quote (returns a dollar value)")
    ap.add_argument("--status", default=None)
    ap.add_argument("--note", default=None)
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    exists = cur.execute("SELECT id FROM form_scripts WHERE form_url=?", (args.form,)).fetchone()
    if exists:
        sets, params = ["updated_at=datetime('now')"], []
        if args.domain:
            sets.append("domain=?"); params.append(args.domain)
        if args.type:
            sets.append("insurance_type=?"); params.append(args.type)
        if args.script:
            sets.append("script_file=?"); params.append(args.script)
        if args.kind:
            sets.append("form_kind=?"); params.append(args.kind)
        if args.status:
            sets.append("status=?"); params.append(args.status)
        if args.note:
            sets.append("result_note=?"); params.append(args.note)
        params.append(args.form)
        cur.execute(f"UPDATE form_scripts SET {', '.join(sets)} WHERE form_url=?", params)
        print(f"Updated existing record for {args.form}")
    else:
        cur.execute(
            """INSERT INTO form_scripts (form_url, domain, insurance_type, script_file, status, result_note, form_kind)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (args.form, args.domain, args.type, args.script, args.status or "registered",
             args.note, args.kind or "unknown"),
        )
        print(f"Inserted new record for {args.form}")

    conn.commit()
    print("\nform_scripts rows:")
    for r in cur.execute("SELECT id, form_url, domain, insurance_type, script_file, form_kind, status FROM form_scripts"):
        print(" ", r)
    conn.close()


if __name__ == "__main__":
    main()
