import Link from "next/link";
import QuoteForm from "@/components/QuoteForm";

export const dynamic = "force-dynamic";

export default function QuotePage() {
  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <nav style={{ maxWidth: 1100, margin: "0 auto", padding: "14px 24px", display: "flex", justifyContent: "space-between" }}>
          <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>QuoteDrive</Link>
          <Link href="/" className="btn">← Back to home</Link>
        </nav>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <section style={{ textAlign: "center", marginBottom: 28 }}>
          <span className="badge text-accent" style={{ marginBottom: 12 }}>Auto quote intake</span>
          <h1 style={{ fontSize: 28, margin: "8px 0" }}>Tell us about your vehicle and driving</h1>
          <p className="text-secondary" style={{ maxWidth: 600, margin: "0 auto", fontSize: 15 }}>
            Fill this in once. We reuse the same details to quote every carrier&apos;s form — direct,
            broker, and specialty — and place the phone calls for the carriers that don&apos;t quote online.
          </p>
        </section>

        <QuoteForm />
      </main>

      <footer className="hero-bg" style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "20px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", justifyContent: "space-between", fontSize: 12, color: "#7a8196", flexWrap: "wrap", gap: 8 }}>
          <span>QuoteDrive — a hackathon prototype. Personal use only; not a licensed brokerage.</span>
          <span style={{ display: "flex", gap: 14 }}>
            <Link href="/" className="text-accent">Home</Link>
            <Link href="/quotes" className="text-accent">My quotes</Link>
            <Link href="/registry" className="text-accent">Registry</Link>
            <Link href="/settings" className="text-accent">Settings</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
