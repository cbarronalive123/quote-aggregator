"use client";

import { useMemo, useState } from "react";
import { formSections, type FieldDef } from "@/lib/formSchema";

// Start the form blank so it can be used for manual entry. It is only auto-filled
// when the user clicks "My profile" or "Fake profile" (those buttons fetch the
// server profile and populate the fields via loadProfile).
function initValues() {
  const v: Record<string, string> = {};
  formSections.forEach((s) =>
    s.fields.forEach((f) => {
      v[f.key] = "";
    })
  );
  return v;
}

function FieldInput({ field, value, onChange }: { field: FieldDef; value: string; onChange: (v: string) => void }) {
  const id = `f-${field.key}`;
  const shared = {
    id,
    value,
    required: field.required,
    placeholder: field.placeholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(e.target.value),
  };

  if (field.type === "select") {
    return (
      <select {...shared}>
        <option value="">Select…</option>
        {field.options?.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    );
  }
  return <input type={field.type} {...shared} />;
}

export default function QuoteForm() {
  const [values, setValues] = useState<Record<string, string>>(initValues);
  const [section, setSection] = useState(0);
  const [loadingProfile, setLoadingProfile] = useState<"my" | "fake" | null>(null);

  const set = (key: string) => (v: string) => setValues((prev) => ({ ...prev, [key]: v }));

  // Load a profile from the server: "my" = saved applicant, "fake" = freshly
  // generated unique test data. Falls back to the local defaults if the fetch fails.
  // The loading label ("Loading…" / "Generating…") stays visible for ~3s so the
  // button clearly shows it did something, then reverts to its normal label.
  const loadProfile = async (kind: "my" | "fake") => {
    const started = Date.now();
    setLoadingProfile(kind);
    try {
      const res = await fetch(kind === "my" ? "/api/profile/my" : "/api/profile/fake", {
        method: kind === "fake" ? "POST" : "GET",
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.values) {
          // Tag which profile kind was used so the history page can file this run
          // under "My profiles" (real) or "Fake profiles".
          setValues({ ...data.values, _profile_kind: kind });
          setSection(0);
        }
      }
    } catch {
      // fall through to local defaults below
    }
    // Keep the button in its "working" state for at least 3s total, then reset it.
    const elapsed = Date.now() - started;
    const remaining = Math.max(0, 3000 - elapsed);
    await new Promise((r) => setTimeout(r, remaining));
    setLoadingProfile(null);
  };

  const current = formSections[section];
  const isLast = section === formSections.length - 1;

  const next = async () => {
    if (!isLast) {
      setSection((s) => s + 1);
      return;
    }
    // Submit the one-time intake: start the aggregation, which fans out to the
    // phone agent for phone-only carriers. Then open the results page and poll.
    try {
      const res = await fetch("/api/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.job_id) {
          window.location.href = `/quotes?job_id=${encodeURIComponent(data.job_id)}`;
          return;
        }
      }
    } catch {
      // fall through to the values-only navigation below
    }
    // Fallback: persist values in the URL and show results without a live job.
    const qs = new URLSearchParams(values);
    window.location.href = `/quotes?${qs.toString()}`;
  };

  const completedCount = useMemo(
    () =>
      formSections.slice(0, section).reduce((n, s) => n + s.fields.length, 0) + current.fields.length,
    [section, current]
  );
  const totalCount = useMemo(() => formSections.reduce((n, s) => n + s.fields.length, 0), []);

  return (
    <div className="panel" style={{ maxWidth: 700, margin: "0 auto", background: "rgba(0,0,0,0.45)", padding: 24, textAlign: "left" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Get your car insurance quote</h2>
        <span className="text-muted" style={{ fontSize: 12 }}>{completedCount} / {totalCount}</span>
      </div>
      <p className="text-secondary" style={{ margin: "0 0 4px", fontSize: 14 }}>
        We ask once and reuse it to fill every carrier&apos;s form — online or by phone.
      </p>

      {/* Profile presets: load a profile's details, then submit to run the aggregator */}
      <div style={{ display: "flex", gap: 10, margin: "14px 0", flexWrap: "wrap", alignItems: "center" }}>
        <span className="text-muted" style={{ fontSize: 13 }}>Load profile:</span>
        <button
          type="button"
          className="btn"
          onClick={() => loadProfile("my")}
          disabled={loadingProfile !== null}
          style={{ border: "1px solid rgba(255,255,255,0.15)" }}
        >
          {loadingProfile === "my" ? "Loading…" : "My profile"}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => loadProfile("fake")}
          disabled={loadingProfile !== null}
          style={{ border: "1px solid rgba(255,255,255,0.15)" }}
        >
          {loadingProfile === "fake" ? "Generating…" : "Fake profile"}
        </button>
      </div>

      {/* Section stepper */}
      <div style={{ display: "flex", gap: 6, margin: "16px 0", flexWrap: "wrap" }}>
        {formSections.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(i)}
            style={{
              padding: "5px 10px",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.1)",
              background: i === section ? "linear-gradient(135deg,#4d6bff,#7f9cff)" : "rgba(255,255,255,0.04)",
              color: "#fff",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {s.title}
          </button>
        ))}
      </div>

      <h3 style={{ margin: "0 0 2px", fontSize: 16 }}>{current.title}</h3>
      <p className="text-muted" style={{ margin: "0 0 16px", fontSize: 12 }}>{current.description}</p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {current.fields.map((f) => (
          <div key={f.key} style={f.key === "vin" ? { gridColumn: "1 / -1" } : undefined}>
            <label htmlFor={`f-${f.key}`}>
              {f.label}
              {f.required && <span className="text-accent"> *</span>}
            </label>
            <FieldInput field={f} value={values[f.key]} onChange={set(f.key)} />
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 20 }}>
        <button type="button" className="btn" onClick={() => setSection((s) => Math.max(0, s - 1))} disabled={section === 0} style={{ visibility: section === 0 ? "hidden" : "visible" }}>
          Back
        </button>
        <button type="button" className="btn btn-primary" onClick={next} style={{ padding: "12px 24px", fontSize: 15 }}>
          {isLast ? "Get my quotes" : "Continue"}
        </button>
      </div>
    </div>
  );
}
