import Link from "next/link";

const brands = ["belairdirect", "Aviva", "Allstate", "Sonnet", "TD", "CAA", "Intact", "Wawanesa"];

const steps = [
  { title: "Tell us about your vehicle", body: "Enter your postal code, vehicle year, make and model once." },
  { title: "We reach every carrier", body: "Automated quoting plus phone agents for carriers that don't quote online." },
  { title: "Compare and choose", body: "See every premium side-by-side, hear the call that got the price, and pick your best option." },
];

const carriers = [
  { name: "Direct", desc: "belairdirect, Aviva, Allstate, Sonnet, TD, CAA, Intact, Wawanesa" },
  { name: "Broker & specialty", desc: "Erie Mutual, Verge, Bertram & Barry, APRIL Marine, Diamond, and more" },
  { name: "Phone-only", desc: "Carriers with no online rater get a real call placed on your behalf" },
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
      <section className="hero-bg" style={{ padding: "72px 24px", textAlign: "center" }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <span className="badge text-accent" style={{ marginBottom: 16 }}>
            Compare Ontario car insurance in minutes
          </span>
          <h1 style={{ fontSize: 44, margin: "12px 0", fontWeight: 800, lineHeight: 1.1 }}>
            One quote request, <br /> every auto insurer compared.
          </h1>
          <p className="text-secondary" style={{ fontSize: 17, maxWidth: 600, margin: "0 auto 36px", lineHeight: 1.6 }}>
            QuoteDrive is an auto-insurance aggregator. You fill in your details once — we quote
            across direct, broker, and specialty carriers, and even place the phone calls for the
            insurers that don&apos;t quote online.
          </p>
          <Link href="/quote" className="btn btn-primary" style={{ padding: "16px 34px", fontSize: 18, display: "inline-block" }}>
            Start your quote
          </Link>
          <div style={{ marginTop: 32, display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
            {brands.map((b) => (
              <span key={b} className="badge" style={{ fontSize: 12, color: "#b6bccb" }}>
                {b}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* What we do */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "48px 24px 0" }}>
        <h2 style={{ textAlign: "center", fontSize: 24 }}>What we do</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 20,
            marginTop: 24,
          }}
        >
          {carriers.map((c) => (
            <div key={c.name} className="panel" style={{ padding: 24 }}>
              <div className="text-accent" style={{ fontSize: 15, fontWeight: 700 }}>{c.name}</div>
              <p className="text-muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{c.desc}</p>
            </div>
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
        <div style={{ textAlign: "center", marginTop: 32 }}>
          <Link href="/quote" className="btn" style={{ padding: "13px 28px", fontSize: 15 }}>
            Get started with a free quote
          </Link>
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
            <Link href="/settings" className="text-accent">Settings</Link>
            <Link href="/calls" className="text-accent">Phone agent</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
