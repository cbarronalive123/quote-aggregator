"""
market_registry.py
==================
SQLite market registry for the Ontario All-Quote Agent (PPA auto focus).

Seeded from the brief's Appendix A (32 insurer groups / ~60 legal entities,
Ontario PPA rate-approval dataset, Aug 6 2026) plus the aggregator / broker /
gap-fill channels the brief requires. Websites come from the project's
insurance_websites.db where a match was found.

Every row still needs current validation during the hackathon: panels, legal
entities, eligibility and quote flows change. This is the DISCOVERY SEED, not
proof of current new-business availability.

Build:   python market_registry.py          # (re)creates market_registry.db
Read:    SELECT * FROM rate_sources WHERE status != 'seed_done';
"""

import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "market_registry.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_sources (
    registry_id          TEXT PRIMARY KEY,
    insurer_group        TEXT,
    legal_entities       TEXT,          -- from brief Appendix A seed
    brand                TEXT,          -- consumer-facing route
    distribution_type    TEXT,          -- direct|agent|broker|aggregator|affinity|MGA_program|mutual|residual
    product_scope        TEXT,          -- standard_PPA|nonstandard_PPA|high_net_worth|collector|commercial_specialty|unknown
    quote_url            TEXT,
    public_phone_route   TEXT,
    licensed_intermediary TEXT,
    requires_licence     INTEGER, requires_VIN INTEGER,
    requires_membership  INTEGER, requires_human INTEGER,
    terms_or_automation_notes TEXT,
    distinct_rate_source_id TEXT,       -- dedup key (set during validation)
    status               TEXT,          -- brief status enum or 'seed'
    last_verified_at     TEXT,
    source_citation      TEXT,
    notes                TEXT
);
"""

# group -> (legal entities, distribution, product_scope, website, phone, notes)
# Websites from insurance_websites.db; quote routes from brief's route strategy.
SEED = [
    # insurer groups (brief Appendix A)
    ("AIG", "AIG Insurance Company of Canada", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Allstate", "Allstate IC of Canada; Esurance IC of Canada; Pafco Insurance Co; Pembridge Insurance Co",
     "direct+agent+broker", "standard_PPA", "https://www.allstate.ca", "+1 800-255-7828",
     "Direct/agent; Pafco & Pembridge broker; validate Esurance"),
    ("Aviva", "Aviva General IC; Aviva IC of Canada; S&Y IC; Scottish & York IC; Traders General IC",
     "direct+broker", "standard_PPA", "https://www.aviva.ca", "+1 800-387-4518",
     "Aviva Direct rater done (aviva_auto_quote.py); dedup legacy entities"),
    ("Beneva", "Unica Insurance Inc", "broker", "standard_PPA", "https://www.unicainsurance.com",
     "+1 800-361-8335", "Broker route"),
    ("CAA", "CAA Insurance Co; Echelon Insurance", "direct+broker", "standard_PPA",
     "https://www.caasco.com", "+1 800-263-7272", "CAA direct; Echelon non-standard via broker"),
    ("Chubb", "Chubb IC of Canada", "broker", "high_net_worth", "https://www.chubb.com",
     "+1 416-863-0550", "HNW/specialty broker only"),
    ("Co-op", "COSECO Insurance Co; CUMIS General IC; Co-operators General IC; The Sovereign General IC",
     "direct+agent+affinity", "standard_PPA", "https://www.cooperators.ca", "+1 800-363-0444",
     "Co-operators web/agent; affinity + specialty entities need validation"),
    ("Commonwell", "The Commonwell Mutual Insurance Group", "mutual", "standard_PPA",
     "https://www.thecommonwell.ca", "+1 705-324-2146", "Mutual and broker/agent route"),
    ("Continental", "Continental Casualty Company", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Definity", "Definity Insurance Co; Sonnet Insurance Co", "broker+direct", "standard_PPA",
     "https://www.economical.com", "+1 800-267-8318", "Definity/Economical broker; Sonnet direct (sonnet.ca)"),
    ("Desjardins", "Certas Direct IC; Certas Home and Auto IC; The Personal Insurance Co",
     "direct+agent+affinity", "standard_PPA", "https://www.desjardins.com", "+1 866-838-4677",
     "Desjardins web/agent; The Personal affinity (thepersonal.com)"),
    ("Economical", "Economical Mutual Insurance Co", "broker", "standard_PPA",
     "https://www.economical.com", "+1 800-267-8318", "Broker route; map current legal entity"),
    ("FA", "Facility Association", "residual", "standard_PPA",
     "https://www.facilityassociation.com", "", "Residual-market via licensed intermediary only"),
    ("FMRe", "Farm Mutual Reinsurance Plan Inc (on behalf of Ontario Mutuals)", "mutual", "standard_PPA",
     "https://www.farmmutualre.com", "+1 519-740-6415", "Ontario Mutuals locator + per-mutual validation"),
    ("Gore", "Gore Mutual Insurance Co", "broker", "standard_PPA",
     "https://www.goremutual.ca", "+1 519-623-1910", "Broker route"),
    ("Hartford", "Hartford Fire Insurance Co", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Heartland", "Heartland Farm Mutual Inc", "mutual", "standard_PPA",
     "https://www.heartlandmutualinsurance.com", "+1 519-886-4530", "Mutual/local agent or broker"),
    ("Intact", "Belair Insurance Co Inc; The Guarantee Co of NA; Intact Insurance Co; Jevco Insurance Co; Novex Insurance Co; Royal & SunAlliance IC of Canada; Unifund Assurance Co; Western Assurance Co",
     "direct+broker", "standard_PPA", "https://www.intact.ca", "+1 800-387-4458",
     "belairdirect direct; Intact/Jevco broker; validate legacy/affinity"),
    ("Liberty", "Liberty Mutual Insurance Co", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Northbridge", "Federated IC of Canada; Northbridge General IC; Verassure IC; Zenith Insurance Co",
     "broker", "standard_PPA", "https://www.northbridgeinsurance.ca", "+1 416-350-4400",
     "Northbridge + Zenith broker; validate Federated/Verassure scope"),
    ("Optimum", "Optimum Insurance Co Inc", "broker", "standard_PPA",
     "https://www.optimum-general.com", "+1 705-476-4814", "Broker route"),
    ("PURE", "PURE Insurance", "broker", "high_net_worth", "https://www.puregroup.com",
     "", "HNW broker only; avoid counting if inaccessible"),
    ("Peel", "Peel Mutual Insurance Co", "mutual", "standard_PPA",
     "https://www.peelmutual.com", "+1 905-451-2386", "Mutual/local agent or broker"),
    ("Portage", "The Portage la Prairie Mutual Insurance Co", "broker", "standard_PPA",
     "https://www.portagemutual.com", "+1 905-937-0100", "Broker route"),
    ("SGI", "Coachman Insurance Co; SGI CANADA Insurance Services Ltd", "broker", "nonstandard_PPA",
     "https://www.coachmaninsurance.ca", "+1 416-255-3417", "Coachman non-standard (current insurer); broker route"),
    ("Sompo", "Endurance Specialty Insurance Ltd; Sompo Japan Insurance Inc", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("TD", "Primmum Insurance Co; Security National IC; TD General IC", "direct+affinity", "standard_PPA",
     "https://www.tdinsurance.com", "+1 888-336-2627", "TD online/phone and affinity routes"),
    ("Tokio", "Tokio Marine and Nichido Fire IC Ltd", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Travelers", "The Dominion of Canada General IC", "broker", "standard_PPA",
     "https://www.travelerscanada.ca", "+1 800-268-3580", "Broker route"),
    ("Wawanesa", "The Wawanesa Mutual IC", "broker", "standard_PPA",
     "https://www.wawanesa.com", "+1 800-361-2528", "Broker route"),
    ("XL", "XL Specialty Insurance Co", "broker", "commercial_specialty",
     "", "", "Specialty/commercial broker; validate PPA relevance"),
    ("Zurich", "Zurich Insurance Co", "direct+broker", "standard_PPA",
     "https://www.zurichcanada.com", "+1 800-363-9990", "Square One direct for Ontario car (squareone.ca)"),

    # aggregator / digital-broker routes
    ("Agg", "n/a", "aggregator", "standard_PPA", "https://www.rates.ca", "+1 844-726-0907",
     "Broad broker engine A; inspect returned legal underwriters"),
    ("Agg", "n/a", "aggregator", "standard_PPA", "https://www.lowestrates.ca", "+1 855-487-6911",
     "Broad broker engine A alt"),
    ("Agg", "n/a", "broker", "standard_PPA", "https://www.surex.com", "+1 855-242-6612",
     "Broad broker engine B; published insurer/MGA disclosure"),
    ("Agg", "n/a", "broker", "standard_PPA", "https://www.thinkinsure.ca", "+1 855-550-5515",
     "Independent broker verifier"),
    ("Agg", "n/a", "broker", "standard_PPA", "https://www.onlia.ca", "+1 844-472-7905",
     "Digital brokerage; capture returned insurer not the brand"),
    ("Agg", "n/a", "broker", "standard_PPA", "https://scoopinsurance.ca", "+1 416-585-2918",
     "Digital brokerage + callback workflow"),
    ("Agg", "n/a", "aggregator", "standard_PPA", "https://www.insurancehotline.com", "+1 855-821-7312",
     "Lead/broker-network route, not underwriter"),

    # gap-fill / specialty
    ("Special", "Hagerty Insurance Agency", "MGA_program", "collector",
     "https://hagertybroker.ca", "+1 888-349-7834", "Collector vehicles only; underwritten by Aviva"),
    ("Special", "Facility Association", "residual", "standard_PPA",
     "https://www.facilityassociation.com", "", "Residual market; licensed intermediary only"),
]


def create_db(db_path: str | None = None) -> str:
    path = db_path or DEFAULT_DB
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    for i, (group, entities, dist, scope, url, phone, notes) in enumerate(SEED, start=1):
        cur.execute(
            """
            INSERT INTO rate_sources (
                registry_id, insurer_group, legal_entities, brand,
                distribution_type, product_scope, quote_url,
                public_phone_route, requires_licence, requires_VIN,
                requires_membership, requires_human,
                terms_or_automation_notes, distinct_rate_source_id,
                status, last_verified_at, source_citation, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"seed-{i:02d}", group, entities, url,
                dist, scope, url, phone,
                0, 0, 0, 0,
                "", "", "seed", None, "brief Appendix A + insurance_websites.db", notes,
            ),
        )
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    path = create_db()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    n = conn.execute("SELECT COUNT(*) AS c FROM rate_sources").fetchone()["c"]
    print(f"Created {path} with {n} seed rows")
    print("Registries:", ", ".join(r["registry_id"] for r in conn.execute("SELECT registry_id FROM rate_sources")))
    conn.close()
