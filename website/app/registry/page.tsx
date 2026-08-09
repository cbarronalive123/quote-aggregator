import Link from "next/link";
import { getMarket } from "@/lib/repo";

export const dynamic = "force-dynamic";

export default function RegistryPage() {
  const market = getMarket();

  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <nav style={{ maxWidth: 1100, margin: "0 auto", padding: "14px 24px", display: "flex", justifyContent: "space-between" }}>
          <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>QuoteDrive</Link>
          <span className="badge">Operator · Internal</span>
        </nav>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <h1 style={{ fontSize: 24, margin: "0 0 4px" }}>Market Registry (internal)</h1>
        <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>
          Loaded from the unified database (<code>market_registry.db</code> seed). This is the operator view.
        </p>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Brand</th>
                <th>Group</th>
                <th>Underwriter</th>
                <th>Channel</th>
                <th>Scope</th>
                <th>Status</th>
                <th>Rate Source</th>
              </tr>
            </thead>
            <tbody>
              {market.map((m) => (
                <tr key={m.registry_id}>
                  <td>{m.brand_or_program}</td>
                  <td>{m.insurer_group}</td>
                  <td className="text-muted">{m.legal_underwriter}</td>
                  <td className="text-muted">{m.distribution_type}</td>
                  <td className="text-muted">{m.product_scope}</td>
                  <td><span className="badge text-accent">{m.status}</span></td>
                  <td className="text-muted">{m.distinct_rate_source_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
