import Link from "next/link";
import AutomationSettings from "@/components/AutomationSettings";
import {
  autoQuoteProviders,
  type ProviderQuestion,
  type QuoteProvider,
} from "@/data/quoteProviders";

export const dynamic = "force-dynamic";

// --- Comparison-table helpers -------------------------------------------------
// Maps a shared ("canonical") question to the same question on each provider's
// form, so the same row in the comparison table lines up across belairdirect,
// Aviva and Allstate. Each row holds a label plus per-provider matcher patterns
// (the question's field text). A provider that doesn't ask the question shows "—".
interface CompareRow {
  label: string;
  providers: Record<string, RegExp[]>;
}

const COMPARE_ROWS: CompareRow[] = [
  { label: "Year", providers: { belairdirect: [/^Year$/], aviva: [/year\?$/], allstate: [/^Year$/] } },
  { label: "Make", providers: { belairdirect: [/^Make$/], aviva: [/make\?$/], allstate: [/^Make$/] } },
  { label: "Model", providers: { belairdirect: [/^Model$/], aviva: [/model\?$/], allstate: [/^Model$/] } },
  { label: "Purchase / ownership condition (New/Used/Demo)", providers: { belairdirect: [/Condition of the car/], aviva: [/condition of your car/], allstate: [/new, used or a dealership demo/] } },
  { label: "Purchase date (month/year)", providers: { belairdirect: [/^$/], aviva: [/buy or lease your car/], allstate: [/^Purchase month$|^Purchase year$/] } },
  { label: "Annual kilometres", providers: { belairdirect: [/Yearly kilometres/], aviva: [/drive per year/], allstate: [/drive in one year/] } },
  { label: "Commute days per week", providers: { belairdirect: [/^$/], aviva: [/days a week do you commute/], allstate: [/^$/] } },
  { label: "One-way commute kilometres", providers: { belairdirect: [/distance you drive to work or school/], aviva: [/commute.*one-way|one-way.*commute/i], allstate: [/one way to work or school/] } },
  { label: "Vehicle used for / business use", providers: { belairdirect: [/^$/], aviva: [/business or commercial/], allstate: [/vehicle used for/] } },
  { label: "Winter tires", providers: { belairdirect: [/^$/], aviva: [/winter tires/i], allstate: [/winter tires installed/i] } },
  { label: "Anti-theft device", providers: { belairdirect: [/Anti-theft system/], aviva: [/anti-theft device/i], allstate: [/anti-theft tracking system/i] } },
  { label: "Coverage start date", providers: { belairdirect: [/^$/], aviva: [/coverage to start/i], allstate: [/coverage to start|coverage start date/i] } },
  { label: "First name", providers: { belairdirect: [/^First name$/], aviva: [/^First name$/], allstate: [/^First name$/] } },
  { label: "Last name", providers: { belairdirect: [/^Last name$/], aviva: [/^Last name$/], allstate: [/^Last name$/] } },
  { label: "Date of birth", providers: { belairdirect: [/Date of birth/], aviva: [/Date of birth/], allstate: [/^Date of birth$/] } },
  { label: "Gender / Sex", providers: { belairdirect: [/Gender identity/], aviva: [/^Sex$/], allstate: [/^Gender$/] } },
  { label: "Marital status", providers: { belairdirect: [/^$/], aviva: [/^Marital status$/], allstate: [/marital status/i] } },
  { label: "Licence class", providers: { belairdirect: [/licence class/i], aviva: [/licence class/i], allstate: [/class of your current/i] } },
  { label: "First licensed (age or date)", providers: { belairdirect: [/first driver's licence/], aviva: [/get this driver’s licence/], allstate: [/first licensed/i] } },
  { label: "Years with insurer / prior insurance", providers: { belairdirect: [/years with current insurer/], aviva: [/continuous car insurance/], allstate: [/currently insured/i] } },
  { label: "Driving convictions / violations", providers: { belairdirect: [/^$/], aviva: [/driving convictions/i], allstate: [/minor violation/i] } },
  { label: "At-fault accidents", providers: { belairdirect: [/^$/], aviva: [/at-fault accidents/i], allstate: [/auto claims/i] } },
  { label: "Bundling / combined policy discount", providers: { belairdirect: [/^$/], aviva: [/Combined Policy Discount/i], allstate: [/^$/] } },
  { label: "Telematics program", providers: { belairdirect: [/^$/], aviva: [/Aviva Journey/i], allstate: [/Drivewise/i] } },
  { label: "Phone number", providers: { belairdirect: [/^Phone number$/], aviva: [/^Phone number$/], allstate: [/^Phone number$/] } },
  { label: "Phone type", providers: { belairdirect: [/^Phone type$/], aviva: [/^Phone type$/], allstate: [/^$/] } },
  { label: "Email address", providers: { belairdirect: [/^Email$/], aviva: [/^Email address$/], allstate: [/^Email address$/] } },
  { label: "Postal code", providers: { belairdirect: [/^Postal code$/], aviva: [/^Postal code$/], allstate: [/^Postal code$/] } },
  { label: "Privacy / quote consent", providers: { belairdirect: [/Terms of Use & Privacy/i], aviva: [/^$/], allstate: [/collect/i] } },
  { label: "Marketing / communications consent", providers: { belairdirect: [/Permission to contact/], aviva: [/electronic communications/i], allstate: [/receive email/i] } },
];

// Saved applicant profile used to run the auto-quote scripts (test data for the repo).
// Replace locally with your own profile — do not commit real PII.
interface SavedProfileValue { value: string; note?: string }

const SAVED_PROFILE: Record<string, SavedProfileValue> = {
  "Year": { value: "2019", note: "2019 Honda Accord" },
  "Make": { value: "HONDA" },
  "Model": { value: "ACCORD EX 4DR", note: "Sample VIN for testing" },
  "Purchase / ownership condition (New/Used/Demo)": { value: "Used", note: "Bought used in 2019" },
  "Purchase date (month/year)": { value: "June 2019" },
  "Annual kilometres": { value: "12,000 km" },
  "Commute days per week": { value: "5 days" },
  "One-way commute kilometres": { value: "10 km" },
  "Vehicle used for / business use": { value: "No (pleasure)" },
  "Winter tires": { value: "Yes" },
  "Anti-theft device": { value: "No" },
  "Coverage start date": { value: "09/01/2026" },
  "First name": { value: "Test" },
  "Last name": { value: "Driver" },
  "Date of birth": { value: "1985-05-10" },
  "Gender / Sex": { value: "Male (M)" },
  "Marital status": { value: "Single" },
  "Licence class": { value: "G", note: "Full licence" },
  "First licensed (age or date)": { value: "Jun 2003", note: "Age 18" },
  "Years with insurer / prior insurance": { value: "3+ years" },
  "Driving convictions / violations": { value: "None" },
  "At-fault accidents": { value: "None" },
  "Bundling / combined policy discount": { value: "No" },
  "Telematics program": { value: "—", note: "Declined (benchmark)" },
  "Phone number": { value: "416-555-0101" },
  "Phone type": { value: "Mobile" },
  "Email address": { value: "test@example.com" },
  "Postal code": { value: "M5V 2T6", note: "Toronto, ON" },
  "Privacy / quote consent": { value: "Yes" },
  "Marketing / communications consent": { value: "No" },
};

function findQuestion(provider: QuoteProvider, patterns: RegExp[]): ProviderQuestion | undefined {
  return provider.questions.find((q) => patterns.some((p) => p.test(q.field)));
}

function formatAnswer(q: ProviderQuestion | undefined): string {
  if (!q) return "—";
  if (q.options && q.options.length) {
    const labels = q.options.map((o) => o.label);
    const joined = labels.join(" / ");
    return joined.length > 110 ? `${labels.slice(0, 4).join(" / ")} … (+${labels.length - 4})` : joined;
  }
  return q.normal && q.normal !== "(leave blank)" ? q.normal : "free-form";
}

const COMPARE_ORDER = ["belairdirect", "aviva", "allstate"];

function ComparisonTable({ providers }: { providers: QuoteProvider[] }) {
  const byId = Object.fromEntries(providers.map((p) => [p.id, p]));
  return (
    <div className="panel" style={{ overflowX: "auto", marginTop: 12 }}>
      <table>
        <thead>
          <tr>
            <th>Question</th>
            <th style={{ backgroundColor: "rgba(0,230,118,0.10)" }}>Saved profile (test)</th>
            {COMPARE_ORDER.map((id) => {
              const p = byId[id];
              return <th key={id}>{p ? p.brand : id}</th>;
            })}
          </tr>
        </thead>
        <tbody>
          {COMPARE_ROWS.map((row, i) => {
            const saved = SAVED_PROFILE[row.label];
            return (
              <tr key={i} style={{ verticalAlign: "top" }}>
                <td style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{row.label}</td>
                <td style={{ fontSize: 12, backgroundColor: "rgba(0,230,118,0.06)" }}>
                  <span className="text-accent" style={{ fontWeight: 600 }}>
                    {saved ? saved.value : "—"}
                  </span>
                  {saved?.note && <div className="text-muted" style={{ fontSize: 10, marginTop: 3 }}>{saved.note}</div>}
                </td>
                {COMPARE_ORDER.map((id) => {
                  const p = byId[id];
                  const q = p ? findQuestion(p, row.providers[id] ?? []) : undefined;
                  const text = formatAnswer(q);
                  const present = q !== undefined;
                  return (
                    <td key={id} style={{ fontSize: 12 }}>
                      <span style={{ color: present ? undefined : "#7a8196" }}>
                        {q ? (q.type === "text" || q.type === "number" || q.type === "email" || q.type === "tel" || q.type === "date" ? `(${q.type}) ${text}` : text) : text}
                      </span>
                      {q?.note && <div className="text-muted" style={{ fontSize: 10, marginTop: 3 }}>{q.note}</div>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function QuestionTable({ questions }: { questions: ProviderQuestion[] }) {
  return (
    <div className="panel" style={{ overflowX: "auto", marginTop: 12 }}>
      <table>
        <thead>
          <tr>
            <th>Step</th>
            <th>Question</th>
            <th>Type</th>
            <th>Answers</th>
            <th>Normal answer</th>
          </tr>
        </thead>
        <tbody>
          {questions.map((q, i) => (
            <tr key={i} style={{ verticalAlign: "top" }}>
              <td className="text-muted">{q.step}</td>
              <td>
                {q.field}
                {q.required && <span className="badge" style={{ marginLeft: 6 }}>required</span>}
              </td>
              <td className="text-muted">{q.type}</td>
              <td>
                {q.options && q.options.length ? (
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {q.options.map((o) => (
                      <li key={o.value} style={{ fontSize: 12, margin: "2px 0" }}>
                        {o.label}
                        {o.value && <span className="text-muted" style={{ fontSize: 11 }}> · {o.value}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-muted">free-form</span>
                )}
              </td>
              <td>
                <span className="text-accent" style={{ fontSize: 12 }}>{q.normal ?? "—"}</span>
                {q.note && (
                  <div className="text-muted" style={{ fontSize: 11, marginTop: 4 }}>{q.note}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SettingsPage() {
  const inProgress = autoQuoteProviders.filter((p) => p.questions.length > 0);
  const planned = autoQuoteProviders.filter((p) => p.questions.length === 0);

  return (
    <div className="page-bg" style={{ minHeight: "100vh" }}>
      <header className="hero-bg" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <nav style={{ maxWidth: 1100, margin: "0 auto", padding: "14px 24px", display: "flex", justifyContent: "space-between" }}>
          <Link href="/" className="text-accent" style={{ fontWeight: 700, fontSize: 17 }}>QuoteDrive</Link>
          <span className="badge">Settings · Internal</span>
        </nav>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <h1 style={{ fontSize: 24, margin: "0 0 4px" }}>Quote Providers — Settings</h1>
        <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>
          The unique auto quote providers we plan to get real quotes for, and the full list of
          questions each form asks (with every answer option). Captured via Playwright MCP.
        </p>

        {/* Runtime behaviour toggles */}
        <h2 style={{ fontSize: 18, margin: "28px 0 12px" }}>Quote automation behaviour</h2>
        <div className="panel" style={{ padding: 18 }}>
          <AutomationSettings />
        </div>

        {/* Provider overview table */}
        <h2 style={{ fontSize: 18, margin: "28px 0 12px" }}>Unique auto quote providers</h2>
        <div className="panel" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Underwriter</th>
                <th>Channel</th>
                <th>Form kind</th>
                <th>Questions</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {autoQuoteProviders.map((p) => (
                <tr key={p.id}>
                  <td className="text-accent" style={{ fontWeight: 600 }}>{p.brand}</td>
                  <td className="text-muted">{p.legal_underwriter}</td>
                  <td className="text-muted">{p.channel}</td>
                  <td className="text-muted">{p.form_kind}</td>
                  <td className="text-muted">{p.questions.length > 0 ? `${p.questions.length} mapped` : "—"}</td>
                  <td><span className="badge text-accent">{p.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Comparison: same question aligned across providers */}
        <h2 style={{ fontSize: 18, margin: "36px 0 12px" }}>Side-by-side question comparison</h2>
        <p className="text-muted" style={{ margin: "0 0 4px", fontSize: 12 }}>
          Each row is one question. The green column is the real applicant profile we use to run
          the scripts (saved test profile); the other columns show the answer options (for select/radio)
          or the normal free-form value each carrier form offers. A "—" means that form doesn't ask it.
        </p>
        <ComparisonTable providers={inProgress} />

        {/* Detailed questions for providers we're actively wiring */}
        {inProgress.map((p) => (
          <div key={p.id}>
            <h2 style={{ fontSize: 18, margin: "36px 0 4px" }}>
              {p.brand} — questions for a quote
            </h2>
            <p className="text-muted" style={{ margin: "0 0 4px", fontSize: 12 }}>
              {p.legal_underwriter} ·{" "}
              <a href={p.quote_url} target="_blank" rel="noreferrer">open quote form ↗</a>
            </p>
            <QuestionTable questions={p.questions} />
          </div>
        ))}

        {planned.length > 0 && (
          <div className="panel" style={{ marginTop: 36, padding: 20 }}>
            <h3 style={{ fontSize: 15, margin: "0 0 6px" }}>Question mapping pending</h3>
            <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>
              Question lists for {planned.map((p) => p.brand).join(", ")} will be captured with the
              same Playwright MCP workflow as each form is wired up.
            </p>
          </div>
        )}
      </main>

      <footer className="hero-bg" style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "20px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", justifyContent: "space-between", fontSize: 12, color: "#7a8196", flexWrap: "wrap", gap: 8 }}>
          <span>QuoteDrive — internal settings. Personal use only; not a licensed brokerage.</span>
          <span style={{ display: "flex", gap: 14 }}>
            <Link href="/" className="text-accent">Home</Link>
            <Link href="/quotes" className="text-accent">My quotes</Link>
            <Link href="/registry" className="text-accent">Registry</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
