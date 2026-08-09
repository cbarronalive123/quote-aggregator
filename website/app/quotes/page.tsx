import Link from "next/link";
import { getQuotes } from "@/lib/repo";
import { getAggregation } from "@/lib/aggregate";
import { recordingUrl } from "@/lib/config";
import LiveResults from "@/components/LiveResults";
import type { QuoteOutcome } from "@/lib/types";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

function describeVehicle(params: Record<string, string | undefined>) {
  const vehicle =
    params.vehicle_make && params.vehicle_model
      ? `${params.vehicle_year} ${params.vehicle_make} ${params.vehicle_model}${params.trim ? ` ${params.trim}` : ""}`
      : "2012 RAM 1500 Big Horn Quad Cab 4WD";
  const postal = params.postal_code || "N2B 2T4";
  return { vehicle, postal };
}

function quoted(rows: QuoteOutcome[]): QuoteOutcome[] {
  return rows
    .filter((q) => q.status === "quoted_comparable" || q.status === "quoted_non_comparable")
    .sort((a, b) => (a.annual_premium ?? 0) - (b.annual_premium ?? 0));
}

function StaticTable({ rows }: { rows: QuoteOutcome[] }) {
  return (
    <div className="panel" style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Annual</th>
            <th>Monthly</th>
            <th>Coverage notes</th>
            <th>How quoted</th>
            <th>Listen</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-muted">No quotes yet. Submit the intake form to start.</td>
            </tr>
          ) : (
            rows.map((q) => (
              <tr key={q.registry_id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{q.brand}</div>
                  <div className="text-muted" style={{ fontSize: 11 }}>{q.quote_id}</div>
                </td>
                <td style={{ fontWeight: 700 }}>{q.annual_premium != null ? `$${q.annual_premium.toFixed(2)}` : "—"}</td>
                <td>{q.monthly_premium != null ? `$${q.monthly_premium.toFixed(2)}/mo` : "—"}</td>
                <td className="text-muted" style={{ maxWidth: 340 }}>{q.coverage_notes}</td>
                <td>
                  <span className="badge text-accent">
                    {q.source === "phone" ? "Phone agent" : "Automated"}
                  </span>
                </td>
                <td>
                  {q.source === "phone" && recordingUrl(q.recording) ? (
                    <a
                      className="btn"
                      href={recordingUrl(q.recording)}
                      target="_blank"
                      rel="noreferrer"
                      title={`Play call recording: ${q.recording}`}
                    >
                      ▶ Play
                    </a>
                  ) : (
                    <span className="text-muted" style={{ fontSize: 12 }}>—</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default async function QuotesPage({ searchParams }: Props) {
  const params = await searchParams;
  const { vehicle, postal } = describeVehicle(params);
  const sub = `${vehicle} · ${postal} · sorted by annual cost. Coverage differences are listed before price — we never call the lowest number the &quot;best&quot; without showing what differs.`;

  const header = (
    <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
      <nav style={{ maxWidth: 1100, margin: "0 auto", padding: "14px 24px", display: "flex", justifyContent: "space-between" }}>
        <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>QuoteDrive</Link>
        <Link href="/" className="btn">New quote</Link>
      </nav>
    </header>
  );

  const jobId = params.job_id;
  const base = quoted(getQuotes());

  if (jobId && getAggregation(jobId)) {
    return (
      <div className="page-bg" style={{ minHeight: "100vh" }}>
        {header}
        <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
          <LiveResults jobId={jobId} cached={base} heading="Your quotes" sub={sub} />
          <p className="text-muted" style={{ marginTop: 20, fontSize: 12 }}>
            Calls to phone-only carriers are placed in sequence after you submit the form; the play
            button opens the recording that produced a phone-sourced premium.
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      {header}
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <h1 style={{ fontSize: 26, margin: "0 0 4px" }}>Your quotes</h1>
        <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>{sub}</p>
        <StaticTable rows={base} />
        <p className="text-muted" style={{ marginTop: 20, fontSize: 12 }}>
          Phone-sourced premiums came from recorded calls made on your behalf; the play button opens the
          call that produced the quoted price. Evidence for each quote is available to the operator.
        </p>
      </main>
    </div>
  );
}
