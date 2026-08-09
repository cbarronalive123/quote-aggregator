import Link from "next/link";
import { getCalls, getMarket } from "@/lib/repo";
import { config } from "@/lib/config";

export const dynamic = "force-dynamic";

export default function CallsPage() {
  const calls = getCalls();
  const market = getMarket();
  const callbackRoutes = market.filter(
    (m) => m.status === "callback_required" || m.status === "manual_handoff"
  );

  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <nav style={{ maxWidth: 1100, margin: "0 auto", padding: "14px 24px", display: "flex", justifyContent: "space-between" }}>
          <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>QuoteDrive</Link>
          <span className="badge">Operator · Internal</span>
        </nav>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <h1 style={{ fontSize: 24, margin: "0 0 4px" }}>Call Center (internal)</h1>
        <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>
          The phone agent is a side tool used only when a carrier won&apos;t quote through browser
          automation. It runs in the separate <code>phone-agent</code> project; call records are
          written to the shared database.
        </p>

        {callbackRoutes.length > 0 && (
          <div className="panel" style={{ padding: 20, marginBottom: 24 }}>
            <h2 style={{ margin: "0 0 12px", fontSize: 16 }}>Routes needing a call</h2>
            <table>
              <thead>
                <tr>
                  <th>Brand</th>
                  <th>Group</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {callbackRoutes.map((m) => (
                  <tr key={m.registry_id}>
                    <td>{m.brand_or_program}</td>
                    <td>{m.insurer_group}</td>
                    <td className="text-muted">{m.distribution_type}</td>
                    <td><span className="badge text-accent">{m.status}</span></td>
                    <td>
                      <a href={config.phoneAgentUrl} target="_blank" rel="noreferrer">Open phone agent →</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h2 style={{ margin: "0 0 12px", fontSize: 16 }}>Call history</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Brand</th>
                <th>Direction</th>
                <th>Status</th>
                <th>Recording</th>
                <th>Outcome</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {calls.length === 0 ? (
                <tr><td colSpan={6} className="text-muted">No calls yet.</td></tr>
              ) : (
                calls.map((c) => (
                  <tr key={c.id}>
                    <td>{c.brand}</td>
                    <td className="text-muted">{c.direction}</td>
                    <td><span className="badge text-accent">{c.status}</span></td>
                    <td className="text-muted">{c.recording_path}</td>
                    <td className="text-muted" style={{ maxWidth: 320 }}>{c.outcome_notes}</td>
                    <td className="text-muted">{c.timestamp}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
