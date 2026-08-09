import Link from "next/link";
import QuoteForm from "@/components/QuoteForm";

const brands = ["belairdirect", "Aviva", "Allstate", "Sonnet", "TD", "CAA", "Intact", "Wawanesa"];

const steps = [
  { title: "Tell us about your vehicle", body: "Enter your postal code, vehicle year, make and model once." },
  { title: "We reach every carrier", body: "Automated quoting plus phone agents for carriers that don't quote online." },
  { title: "Compare and choose", body: "See every premium side-by-side, hear the call that got the price, and pick your best option." },
];

export default function Home() {
  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      {/* Top bar */}
      <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <nav
          style={{
            maxWidth: 1100,
            margin: "0 auto",
            padding: "14px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontWeight: 700, fontSize: 17 }} className="text-accent">
              QuoteDrive
            </span>
            <span className="text-muted" style={{ fontSize: 12 }}>
              Ontario auto insurance, compared
            </span>
          </div>
          <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
            <a href="#how" className="text-secondary" style={{ fontSize: 14 }}>How it works</a>
            <Link href="/quotes" className="btn">My quotes</Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section className="hero-bg" style={{ padding: "64px 24px", textAlign: "center" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          <span className="badge text-accent" style={{ marginBottom: 16 }}>
            Compare Ontario car insurance in minutes
          </span>
          <h1 style={{ fontSize: 40, margin: "12px 0", fontWeight: 800 }}>
            Get the best auto rate, <br /> without the legwork.
          </h1>
          <p className="text-secondary" style={{ fontSize: 16, maxWidth: 560, margin: "0 auto 32px" }}>
            One form. We quote across direct, broker, and specialty carriers — and make the phone
            calls for you when a carrier won&apos;t quote online.
          </p>
        </div>
        <QuoteForm />
        <div style={{ marginTop: 28, display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          {brands.map((b) => (
            <span key={b} className="badge" style={{ fontSize: 12, color: "#b6bccb" }}>
              {b}
            </span>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" style={{ maxWidth: 1100, margin: "0 auto", padding: "48px 24px" }}>
        <h2 style={{ textAlign: "center", fontSize: 24 }}>How it works</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 20,
            marginTop: 24,
          }}
        >
          {steps.map((s, i) => (
            <div key={s.title} className="panel" style={{ padding: 24 }}>
              <div className="text-accent" style={{ fontSize: 28, fontWeight: 800 }}>0{i + 1}</div>
              <h3 style={{ fontSize: 16, margin: "8px 0" }}>{s.title}</h3>
              <p className="text-muted" style={{ fontSize: 13, margin: 0 }}>{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust strip */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px 48px" }}>
        <div className="panel" style={{ padding: 24, textAlign: "center" }}>
          <p className="text-muted" style={{ margin: 0, fontSize: 13, maxWidth: 720, marginInline: "auto" }}>
            Coverage shown side-by-side, so price isn&apos;t the only thing you compare. Every premium
            comes with its coverage assumptions, and every quote has evidence behind it.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="hero-bg" style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "20px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", justifyContent: "space-between", fontSize: 12, color: "#7a8196", flexWrap: "wrap", gap: 8 }}>
          <span>QuoteDrive — a hackathon prototype. Personal use only; not a licensed brokerage.</span>
          <span style={{ display: "flex", gap: 14 }}>
            <Link href="/quotes" className="text-accent">My quotes</Link>
            <Link href="/registry" className="text-accent">Registry</Link>
            <Link href="/calls" className="text-accent">Phone agent</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
