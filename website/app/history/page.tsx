import Link from "next/link";
import { getQuoteHistory } from "@/lib/repo";
import type { QuoteRun, QuoteOutcome } from "@/lib/types";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

const STATUS_ORDER = [
  "quoted_comparable",
  "quoted_non_comparable",
  "estimate_only",
  "callback_required",
  "manual_handoff",
  "ineligible",
  "blocked",
  "unresolved",
];

// The site is displayed in Eastern Time (America/Toronto), regardless of the server
// or browser timezone.
const TZ = "America/Toronto";

// Parse an ISO timestamp into a Date. Naive timestamps (no "Z" or offset) were stored
// as UTC, so treat them as UTC rather than letting the runtime guess the server TZ.
function parseTs(iso?: string): Date {
  if (!iso) return new Date(NaN);
  const hasOffset = /(?:Z|[+-]\d{2}:\d{2})$/.test(iso.trim());
  return new Date(hasOffset ? iso : `${iso}Z`);
}

function fmtWhen(iso?: string): string {
  const d = parseTs(iso);
  if (Number.isNaN(d.getTime())) return iso || "—";
  return d.toLocaleString(undefined, {
    timeZone: TZ,
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtDate(iso?: string): string {
  const d = parseTs(iso);
  if (Number.isNaN(d.getTime())) return iso || "—";
  return d.toLocaleDateString(undefined, { timeZone: TZ, year: "numeric", month: "short", day: "numeric" });
}

function fmtTime(iso?: string): string {
  const d = parseTs(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
}

function sortOutcomes(rows: QuoteOutcome[]): QuoteOutcome[] {
  const rank = (q: QuoteOutcome) => {
    const i = STATUS_ORDER.indexOf(q.status);
    return i >= 0 ? i : 99;
  };
  return [...rows].sort((a, b) => rank(a) - rank(b) || (a.annual_premium ?? 0) - (b.annual_premium ?? 0));
}

function statusBadge(status?: string) {
  const ok = status === "quoted_comparable";
  const partial = status === "quoted_non_comparable";
  const blocked = status === "blocked" || status === "unresolved" || status === "ineligible";
  const cls = ok ? "text-accent" : partial ? "text-secondary" : "text-muted";
  const label = (status || "unknown").replace(/_/g, " ");
  return <span className={`badge ${cls}`}>{label}</span>;
}

function RunTable({ run }: { run: QuoteRun }) {
  const rows = sortOutcomes(run.outcomes);
  const quotedCount = rows.filter((o) => o.status === "quoted_comparable").length;
  return (
    <div>
      <div
        className="panel"
        style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          gap: 16, flexWrap: "wrap", marginBottom: 16,
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>
            {run.label || "Automated quote run"}
          </div>
          <div className="text-muted" style={{ fontSize: 12, marginTop: 2 }}>
            Run {fmtWhen(run.run_at)}
            {run.profile ? ` · ${run.profile}` : ""}
          </div>
        </div>
        <div style={{ textAlign: "right", fontSize: 13 }}>
          <div>
            <span className="text-accent" style={{ fontWeight: 700 }}>
              {quotedCount}/{rows.length}
            </span>{" "}
            <span className="text-muted">quoted</span>
          </div>
          <div className="text-muted" style={{ fontSize: 11 }}>{statusBadge(run.status)}</div>
        </div>
      </div>

      <div className="panel" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Status</th>
              <th>Annual</th>
              <th>Monthly</th>
              <th>Quote #</th>
              <th>Coverage notes</th>
              <th>Quoted at</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-muted">No outcomes recorded for this run.</td>
              </tr>
            ) : (
              rows.map((q) => (
                <tr key={`${run.id}-${q.registry_id}`}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{q.brand}</div>
                    <div className="text-muted" style={{ fontSize: 11 }}>{q.registry_id}</div>
                  </td>
                  <td>{statusBadge(q.status)}</td>
                  <td style={{ fontWeight: 700 }}>
                    {q.annual_premium != null ? `$${q.annual_premium.toFixed(2)}` : "—"}
                  </td>
                  <td>{q.monthly_premium != null ? `$${q.monthly_premium.toFixed(2)}/mo` : "—"}</td>
                  <td className="text-muted">{q.quote_id || "—"}</td>
                  <td className="text-muted" style={{ maxWidth: 300 }}>{q.coverage_notes || "—"}</td>
                  <td className="text-muted" style={{ whiteSpace: "nowrap" }}>
                    <div>{fmtDate(q.timestamp)}</div>
                    <div style={{ fontSize: 11 }}>{fmtTime(q.timestamp)}</div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default async function HistoryPage({ searchParams }: Props) {
  const params = await searchParams;
  const tab: "fake" | "real" = params.tab === "fake" ? "fake" : "real";
  // My profiles = real-applicant runs (profile not flagged "fake"); Fake profiles = runs
  // that used a generated fake identity (profile label contains "fake").
  const allRuns = getQuoteHistory();
  const runs = allRuns.filter((r) => (tab === "fake" ? r.kind === "fake" : r.kind !== "fake"));
  const selectedId = params.run ? Number(params.run) : undefined;
  const selected = runs.find((r) => r.id === selectedId) ?? runs[0];

  const header = (
    <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
      <nav
        style={{
          maxWidth: 1100, margin: "0 auto", padding: "14px 24px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}
      >
        <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>
          QuoteDrive
        </Link>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Link href="/quotes" className="btn">Your quotes</Link>
          <Link href="/quote" className="btn">New quote</Link>
        </div>
      </nav>
    </header>
  );

  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      {header}
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <h1 style={{ fontSize: 26, margin: "0 0 4px" }}>Quote history</h1>
        <p className="text-muted" style={{ margin: "0 0 20px", fontSize: 13 }}>
          Every time the automated quotes run, the results are archived here with their date and time.
          Select a run on the left to review what was quoted — and whether each carrier succeeded.
        </p>

        {/* Tab bar: real-applicant runs vs fake-profile runs */}
        <div style={{ display: "flex", gap: 10, marginBottom: 22 }}>
          <Link
            href="/history?tab=real"
            className={tab === "real" ? "btn btn-primary" : undefined}
            style={tab === "real" ? { padding: "9px 16px" } : { padding: "9px 16px", border: "1px solid rgba(255,255,255,0.15)", textDecoration: "none", color: "inherit" }}
          >
            My profiles ({allRuns.filter((r) => r.kind !== "fake").length})
          </Link>
          <Link
            href="/history?tab=fake"
            className={tab === "fake" ? "btn btn-primary" : undefined}
            style={tab === "fake" ? { padding: "9px 16px" } : { padding: "9px 16px", border: "1px solid rgba(255,255,255,0.15)", textDecoration: "none", color: "inherit" }}
          >
            Fake profiles ({allRuns.filter((r) => r.kind === "fake").length})
          </Link>
        </div>

        {runs.length === 0 ? (
          <div className="panel">
            <p className="text-muted" style={{ margin: 0 }}>
              {tab === "fake"
                ? "No fake-profile runs recorded yet. Run a quote with a fake profile to build up history here."
                : "No real-applicant runs recorded yet. Run a quote with your saved profile to build up history here."}
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
            {/* Run selector */}
            <aside style={{ flex: "0 0 260px", minWidth: 240 }}>
              <div className="panel" style={{ padding: 8 }}>
                <div className="text-muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", padding: "6px 10px 10px" }}>
                  Select a run
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {runs.map((r) => {
                    const active = selected && r.id === selected.id;
                    const quoted = r.outcomes.filter((o) => o.status === "quoted_comparable").length;
                    return (
                      <Link
                        key={r.id}
                        href={`/history?tab=${tab}&run=${r.id}`}
                        className={active ? "btn btn-primary" : undefined}
                        style={
                          active
                            ? { textAlign: "left", justifyContent: "flex-start", display: "flex", flexDirection: "column", alignItems: "stretch", gap: 2 }
                            : { textAlign: "left", display: "flex", flexDirection: "column", alignItems: "stretch", gap: 2, padding: "8px 10px", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, textDecoration: "none", color: "inherit" }
                        }
                      >
                        <span style={{ fontSize: 13, fontWeight: active ? 700 : 600 }}>
                          {fmtWhen(r.run_at)}
                        </span>
                        <span className="text-muted" style={{ fontSize: 11 }}>
                          {quoted}/{r.outcomes.length} quoted
                          {r.status ? ` · ${r.status.replace(/_/g, " ")}` : ""}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </aside>

            {/* Selected run */}
            <section style={{ flex: "1 1 620px", minWidth: 520 }}>
              {selected ? (
                <RunTable run={selected} />
              ) : (
                <div className="panel"><p className="text-muted" style={{ margin: 0 }}>Select a run.</p></div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
