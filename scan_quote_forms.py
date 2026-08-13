"""
Deep quote discovery across all carrier domains.

3-layer engine (replaces the flat homepage scan):
  L1  Per-type page crawl: bounded crawl of nav/product pages, each assigned
      an insurance type from URL path + page title + headings + body.
  L2  Smart CTA + external quote-portal detection: find "Get Quote"/"Free Quote"
      CTAs by text/class/role (not just URL keywords), and recognize external
      quote-portal domains (Applied Systems WebRater, CSR24, etc.). Webrater
      LOB= params directly reveal the line of business.
  L3  Form-intent classification: tag every <form> as quote / contact / login /
      newsletter / search so genuine quote forms are kept and noise dropped.

Optionally renders JS-heavy SPA candidates with Playwright (Tier 2).

Writes to `form_scan_results` table + JSONL + summary JSON.
"""

import asyncio
import json
import os
import re
import sqlite3
from urllib.parse import urljoin, urlparse

import httpx
import bs4

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(WORKSPACE, "insurance_websites.db")
OUT_JSONL = os.path.join(WORKSPACE, "form_scan_results.jsonl")
REPORT_JSON = os.path.join(WORKSPACE, "form_scan_report.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

FETCH_TIMEOUT = 8.0
API_PROBE_TIMEOUT = 3.0
CONCURRENCY = int(os.environ.get("SCAN_CONCURRENCY", "60"))
MAX_PAGES_PER_SITE = int(os.environ.get("MAX_PAGES", "30"))
API_PROBE_ENABLED = os.environ.get("API_PROBE", "0") == "1"

# ---- keyword sets --------------------------------------------------------
# Each type: (url_path_hints, heading_hints, field_hints)
TYPE_SIGNALS = {
    "auto": (
        ["auto", "car", "vehicle", "motorcycle", "rv-", "boat", "driving", "telematics"],
        ["auto insurance", "car insurance", "vehicle insurance", "get auto quote", "motorcycle"],
        ["vin", "vehicle", "year", "make", "model", "license", "kilometers", "mileage", "driving"],
    ),
    "property": (
        ["home", "property", "house", "condo", "rent", "tenant", "landlord", "realty", "dwelling", "cottage"],
        ["home insurance", "property insurance", "house insurance", "condo", "renters", "tenant insurance", "landlord"],
        ["postal", "street", "address", "property", "built", "roof", "dwelling", "square", "heating"],
    ),
    "business": (
        ["business", "commercial", "contractor", "fleet", "liability", "professional"],
        ["business insurance", "commercial insurance", "liability", "fleet insurance"],
        ["business", "gross", "employees", "liability", "industry", "contractor"],
    ),
    "life": (
        ["life", "critical", "disability", "benefit"],
        ["life insurance", "term life", "critical illness", "disability"],
        ["birth", "smoker", "coverage", "benefit", "age"],
    ),
    "travel": (
        ["travel", "trip", "medical"],
        ["travel insurance", "trip cancellation", "emergency medical"],
        ["destination", "departure", "trip", "duration"],
    ),
}

# CTA phrase detection (text, class, aria-label)
QUOTE_CTA_RE = re.compile(
    r"quote|free ?quote|get a (free )?quote|start (my )?quote|instant ?quote|"
    r"build a (quote|policy)|rate (my|me)|get (my )?(a )?rate|calculate", re.I)

# External quote-portal domains -> canonical portal label
QUOTE_PORTALS = [
    (["webrater.appliedsystems.com"], "applied_systems_webrater"),
    (["appliedsystems.com"], "applied_systems"),
    (["csr24.ca"], "applied_systems_csr24"),
    (["smartquotes.com"], "smart_quotes"),
    (["centralagents.com"], "central_agents_web"),
    (["bgiq.com"], "broker_general"),
    (["eapp2.com"], "eapp2"),
    (["commercialquotes.ca"], "commercial_quotes"),
]
# Webrater LOB param -> insurance type
WEBRATER_LOB = {
    "AUTO": "auto", "HOME": "property", "PROP": "property", "RENT": "property",
    "CONDO": "property", "COMM": "business", "BUSINESS": "business",
    "LIFE": "life", "TRAVEL": "travel",
}

API_DISCOVERY_PATHS = ["/openapi.json", "/swagger.json", "/api-docs", "/api/quote", "/api/v1/quote"]
API_JSON_HINTS = re.compile(r"(\"swagger\"|\"openapi\"|\"paths\"|\"operationId\"|\"info\")")


# ---- helpers -------------------------------------------------------------
def portal_label(url: str):
    host = (urlparse(url).hostname or "").lower()
    for domains, label in QUOTE_PORTALS:
        if any(host == d or host.endswith("." + d) for d in domains):
            return label
    return None


def lob_type(url: str):
    q = urlparse(url).query
    m = re.search(r"[?&]LOB=([A-Z]+)", q)
    if m and m.group(1) in WEBRATER_LOB:
        return WEBRATER_LOB[m.group(1)]
    return None


def classify_page_type(url: str, title: str, headings: str, body: str) -> str:
    """Weight URL path + title + headings heavily; body lightly."""
    url_hay = urlparse(url).path.lower()
    title_hay = (title or "").lower()
    head_hay = (headings or "").lower()
    body_hay = (body or "")[:4000].lower()
    scores = {}
    for t, (path_k, head_k, _field_k) in TYPE_SIGNALS.items():
        s = 0
        s += 4 * sum(1 for k in path_k if k in url_hay)
        s += 3 * sum(1 for k in head_k if k in title_hay)
        s += 2 * sum(1 for k in head_k if k in head_hay)
        s += 1 * sum(1 for k in head_k if k in body_hay)
        scores[t] = s
    top = sorted(scores.items(), key=lambda kv: -kv[1])[0]
    return top[0] if top[1] > 0 else "unknown"


def classify_form_intent(form, action: str) -> str:
    names = []
    for i in form.find_all(["input", "select", "textarea"]):
        n = i.get("name") or i.get("id") or ""
        t = i.get("type") or ""
        names.append((n, t))
    joined = " ".join(n.lower() for n, _ in names if n).strip()
    action_l = action.lower()

    # Login fields always win (e.g. a client portal login form)
    if any(x in joined for x in ["username", "password", "passwd", "signin", "login"]):
        return "login"

    # portal / external quote actions
    if portal_label(action) or "webrater" in action_l or "rater" in action_l:
        return "quote_portal"
    if any(x in action_l for x in ["/quote", "rater", "insurance-quote"]):
        return "quote"
    if any(x in joined for x in ["newsletter", "subscribe"]):
        return "newsletter"
    if "search" in joined or "s=" in joined or any(x in joined for x in ["search", "keywords"]):
        return "search"

    # Quote signal fields
    quote_hits = sum(1 for f in TYPE_SIGNALS.values() for k in f[2] if k in joined)
    if quote_hits >= 2:
        return "quote"
    if any(k in joined for k in ["postal", "postcode", "zip", "vin", "vehicle", "make", "model",
                                 "dob", "birth", "coverage", "deductible", "street-address"]):
        return "quote"

    # Generic name+email+message => contact
    if any(k in joined for k in ["your-message", "your-email", "email", "comment", "message", "phone"]):
        return "contact"
    return "other"


def extract_field_info(form):
    fields = []
    for i in form.find_all(["input", "select", "textarea"]):
        n = i.get("name") or i.get("id") or ""
        if not n:
            continue
        t = i.get("type") or i.name
        opts = [o.get("value") for o in i.find_all("option") if o.get("value")]
        fields.append({"name": n, "type": t, "options": opts[:8]})
    return fields


async def fetch(sem: asyncio.Semaphore, client: httpx.AsyncClient, url: str, timeout: float):
    async with sem:
        try:
            r = await asyncio.wait_for(client.get(url, timeout=timeout), timeout=timeout + 2)
            return r
        except Exception:
            return None


async def deep_scan(sem: asyncio.Semaphore, client: httpx.AsyncClient, root_domain: str,
                    do_api_probe: bool = False) -> dict:
    entry = {
        "domain": root_domain,
        "homepage_status": None,
        "homepage_url": None,
        "spa_detected": False,
        "pages_scanned": 0,
        "quote_links": [],       # internal CTA/page links
        "quote_forms": [],       # intent=quote forms
        "contact_form_count": 0,
        "quote_portals": [],     # external portal quote URLs
        "portal_by_type": {},    # type -> [portal urls]
        "page_types": {},        # url -> type
        "api_endpoints": [],
        "openapi_found": False,
        "insurance_types": [],
        "error": None,
    }

    base = f"https://{root_domain}"
    r = await fetch(sem, client, base, FETCH_TIMEOUT)
    if r is None:
        r = await fetch(sem, client, f"http://{root_domain}", FETCH_TIMEOUT)
    if r is None:
        entry["error"] = "connect_failed"
        return entry
    entry["homepage_status"] = r.status_code
    entry["homepage_url"] = str(r.url)
    host = r.url.host or root_domain
    base_final = str(r.url)
    low = r.text.lower()
    entry["spa_detected"] = any(t in low for t in ["__next_data__", "next/data", "react", "vue", "angular", "_nuxt", "createRoot"])

    # ---- L1: bounded crawl ----
    visited = set()
    queue = [base_final]
    seen_types = set()
    pages_by_type = {}

    while queue and len(visited) < MAX_PAGES_PER_SITE:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        pr = await fetch(sem, client, url, FETCH_TIMEOUT)
        if pr is None or pr.status_code != 200:
            continue
        soup = bs4.BeautifulSoup(pr.text, "lxml")
        final = str(pr.url)
        title = (soup.title.string if soup.title else "") or ""
        headings = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])[:12])
        body = soup.get_text(" ", strip=True)
        ptype = classify_page_type(final, title, headings, body)
        if ptype != "unknown":
            seen_types.add(ptype)
        pages_by_type[final] = ptype

        # collect CTAs + links
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            full = urljoin(final, href)
            text = a.get_text(" ", strip=True)
            cls = " ".join(a.get("class") or [])
            aria = a.get("aria-label") or ""
            is_cta = bool(QUOTE_CTA_RE.search(text)) or bool(QUOTE_CTA_RE.search(cls)) or bool(QUOTE_CTA_RE.search(aria)) or bool(QUOTE_CTA_RE.search(full))

            if not is_cta:
                continue

            portal = portal_label(full)
            lob = lob_type(full)

            if portal:
                cta_type = lob or classify_page_type(full, text, "", "")
                if full not in [p["url"] for p in entry["quote_portals"]]:
                    entry["quote_portals"].append({
                        "url": full, "portal": portal, "insurance_type": cta_type,
                        "found_on": final, "cta_text": text[:60],
                    })
                    entry["portal_by_type"].setdefault(cta_type, []).append(full)
            else:
                # type derives from the link's own URL/text, not the containing page
                cta_type = classify_page_type(full, text, "", "")
                if full not in [l[0] for l in entry["quote_links"]]:
                    entry["quote_links"].append([full, text[:60], cta_type])

            # queue internal links (product pages)
            if host in full and full not in visited and full not in queue:
                queue.append(full)

        # ---- L3: form intent ----
        for f in soup.find_all("form"):
            action = urljoin(final, f.get("action", "")) or "(JS)"
            intent = classify_form_intent(f, action)
            if intent in ("quote", "quote_portal"):
                entry["quote_forms"].append({
                    "page": final, "action": action,
                    "method": f.get("method", "get").upper(),
                    "fields": extract_field_info(f),
                    "intent": intent,
                    "type": ptype,
                })
            elif intent == "contact":
                entry["contact_form_count"] += 1

    entry["pages_scanned"] = len(visited)
    entry["page_types"] = pages_by_type
    entry["insurance_types"] = sorted(seen_types) or ["unknown"]

    # ---- API probes (optional) ----
    if do_api_probe and r.status_code == 200:
        tasks = [fetch(sem, client, urljoin(base_final, p), API_PROBE_TIMEOUT) for p in API_DISCOVERY_PATHS]
        for ar in await asyncio.gather(*tasks):
            if ar is None or ar.status_code != 200:
                continue
            ct = ar.headers.get("content-type", "")
            if "json" in ct or API_JSON_HINTS.search(ar.text[:2000]):
                entry["api_endpoints"].append({"url": str(ar.url), "status": ar.status_code, "content_type": ct})
                if "swagger" in ct or "openapi" in ct:
                    entry["openapi_found"] = True

    return entry


async def scan_site_playwright(root_domain: str, candidate_url: str | None) -> dict:
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        return {"domain": root_domain, "rendered_error": repr(e)}
    target = candidate_url or f"https://{root_domain}"
    result = {"domain": root_domain, "rendered": True, "target": target, "controls": [], "insurance_types": []}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=UA)
            await page.goto(target, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            controls = await page.eval_on_selector_all(
                "input, select, textarea, button[type=submit], form",
                """els => els.map(e => ({
                    tag: e.tagName.toLowerCase(), type: e.type || '',
                    name: e.name || '', id: e.id || '',
                    text: (e.innerText || e.value || '').slice(0, 60),
                    formAction: e.form ? (e.form.action || '') : ''
                }))""",
            )
            result["controls"] = controls[:60]
            text = await page.inner_text("body")
            result["insurance_types"] = ["unknown"]
            await browser.close()
    except Exception as e:
        result["rendered_error"] = repr(e)
    return result


async def _pw_wrap(dc):
    return dc[0], await scan_site_playwright(dc[0], dc[1])


async def with_pw_sem(coro, sem):
    async with sem:
        return await coro


async def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS form_scan_results;
        CREATE TABLE form_scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            homepage_status INTEGER,
            homepage_url TEXT,
            spa_detected INTEGER,
            pages_scanned INTEGER,
            quote_link_count INTEGER,
            quote_form_count INTEGER,
            contact_form_count INTEGER,
            portal_count INTEGER,
            api_endpoint_count INTEGER,
            openapi_found INTEGER,
            insurance_types TEXT,
            quote_links_json TEXT,
            quote_forms_json TEXT,
            quote_portals_json TEXT,
            api_endpoints_json TEXT,
            error TEXT,
            scanned_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()

    rows = cur.execute(
        "SELECT DISTINCT root_domain FROM websites WHERE root_domain IS NOT NULL"
    ).fetchall()
    domains = [r[0] for r in rows]

    limit = int(os.environ.get("SCAN_LIMIT", "0"))
    if limit:
        domains = domains[:limit]
        print(f"[limited to {limit}]", flush=True)

    print(f"Total unique domains to scan: {len(domains)}", flush=True)

    API_PROBE_ALWAYS = set(os.environ.get(
        "API_PROBE_DOMAINS",
        "allstate.ca,cooperators.ca,belairdirect.com,intact.ca,aviva.ca,desjardins.com,"
        "promutuelassurance.ca,brokerlink.ca,westlandinsurance.ca,ia.ca,sunlife.ca,"
        "economicalinsurance.com,caa.ca,tdinsurance.com,sonnet.ca,primerica.com"
    ).split(","))

    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        headers={"User-Agent": UA},
        follow_redirects=True,
        verify=False,
        timeout=httpx.Timeout(12.0, connect=6.0, read=10.0, write=10.0, pool=6.0),
        limits=httpx.Limits(max_connections=CONCURRENCY + 10, max_keepalive_connections=CONCURRENCY),
    ) as client:
        BATCH = 100
        http_results = {}
        for i in range(0, len(domains), BATCH):
            chunk = domains[i:i + BATCH]
            results = await asyncio.gather(*[
                deep_scan(sem, client, d, do_api_probe=API_PROBE_ENABLED or d in API_PROBE_ALWAYS)
                for d in chunk
            ])
            for e in results:
                http_results[e["domain"]] = e
            print(f"  scanned {min(i + BATCH, len(domains))}/{len(domains)}", flush=True)

    # Tier 2: Playwright for SPA sites with no quote forms found
    pw_candidates = []
    for d, e in http_results.items():
        if e.get("spa_detected") and not e.get("quote_forms") and not e.get("quote_portals"):
            cand = None
            if e.get("quote_links"):
                cand = e["quote_links"][0][0]
            pw_candidates.append((d, cand))
    PW_MAX = int(os.environ.get("PW_MAX", "40"))
    pw_candidates = pw_candidates[:PW_MAX]

    pw_results = {}
    if pw_candidates:
        print(f"SPA sites needing render: {len(pw_candidates)}", flush=True)
        pw_sem = asyncio.Semaphore(5)
        for d, e in await asyncio.gather(*[with_pw_sem(_pw_wrap(dc), pw_sem) for dc in pw_candidates]):
            pw_results[d] = e

    # persist JSONL
    with open(OUT_JSONL, "w", encoding="utf-8") as jf:
        for d, e in http_results.items():
            jf.write(json.dumps({"domain": d, "scan": e}, ensure_ascii=False) + "\n")
        for d, e in pw_results.items():
            jf.write(json.dumps({"domain": d, "playwright": e}, ensure_ascii=False) + "\n")

    # persist DB
    for d, e in http_results.items():
        cur.execute(
            """INSERT INTO form_scan_results
               (domain, homepage_status, homepage_url, spa_detected, pages_scanned,
                quote_link_count, quote_form_count, contact_form_count, portal_count,
                api_endpoint_count, openapi_found, insurance_types,
                quote_links_json, quote_forms_json, quote_portals_json,
                api_endpoints_json, error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d,
                e.get("homepage_status"),
                e.get("homepage_url"),
                1 if e.get("spa_detected") else 0,
                e.get("pages_scanned", 0),
                len(e.get("quote_links") or []),
                len(e.get("quote_forms") or []),
                e.get("contact_form_count", 0),
                len(e.get("quote_portals") or []),
                len(e.get("api_endpoints") or []),
                1 if e.get("openapi_found") else 0,
                json.dumps(e.get("insurance_types") or ["unknown"]),
                json.dumps(e.get("quote_links") or []),
                json.dumps(e.get("quote_forms") or []),
                json.dumps(e.get("quote_portals") or []),
                json.dumps(e.get("api_endpoints") or []),
                e.get("error"),
            ),
        )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM form_scan_results")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM form_scan_results WHERE quote_form_count > 0")
    with_forms = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM form_scan_results WHERE portal_count > 0")
    with_portals = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM form_scan_results WHERE api_endpoint_count > 0")
    with_api = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM form_scan_results WHERE error IS NOT NULL")
    errors = cur.fetchone()[0]

    # portal-type distribution
    portal_types = {}
    for e in http_results.values():
        for pt in (e.get("portal_by_type") or {}):
            portal_types[pt] = portal_types.get(pt, 0) + 1

    report = {
        "scanned": total,
        "domains_with_quote_forms": with_forms,
        "domains_with_quote_portals": with_portals,
        "domains_with_api_hits": with_api,
        "errors": errors,
        "playwright_renders": len(pw_results),
        "portal_by_type": portal_types,
    }
    with open(REPORT_JSON, "w") as rf:
        json.dump(report, rf, indent=2)
    conn.close()
    print("DONE", json.dumps(report), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
