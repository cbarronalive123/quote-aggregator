"use client";

import { useEffect, useState } from "react";
import type { QuoteOutcome } from "@/lib/types";

interface Props {
  jobId: string;
  heading: string;
  sub: string;
}

// The direct-rate carriers the automation runs for. Each shows a live status as its
// script completes (pending → quoted / blocked) rather than a stale cached quote.
const CARRIERS = [
  { registry_id: "belairdirect", brand: "belairdirect" },
  { registry_id: "aviva", brand: "Aviva Direct" },
  { registry_id: "allstate", brand: "Allstate" },
];

function StatusBadge({ q }: { q?: QuoteOutcome }) {
  if (!q) return <span className="badge text-muted">Pending…</span>;
  if (q.status === "quoted_comparable" || q.status === "quoted_non_comparable") {
    return <span className="badge text-accent">Quoted</span>;
  }
  return <span className="badge text-muted">{q.status.replace(/_/g, " ")}</span>;
}

export default function LiveResults({ jobId, heading, sub }: Props) {
  const [outcomes, setOutcomes] = useState<QuoteOutcome[]>([]);
  const [running, setRunning] = useState(true);
  const [progress, setProgress] = useState(0);
  const [total, setTotal] = useState(0);
  const [percent, setPercent] = useState<number | null>(null);
  const [label, setLabel] = useState<string>("");
  const [attempt, setAttempt] = useState<number>(1);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const r = await fetch(`/api/quote?id=${encodeURIComponent(jobId)}`);
        if (!r.ok) return;
        const j = await r.json();
        if (!active) return;
        setRunning(j.status === "running");
        setProgress(j.progress ?? 0);
        setTotal(j.total ?? 0);
        setOutcomes(j.outcomes || []);
        if (typeof j.progress_percent === "number") setPercent(j.progress_percent);
        if (j.progress_label) setLabel(j.progress_label);
        if (j.progress_attempt) setAttempt(j.progress_attempt);
      } catch {
        /* keep last known state */
      }
    };
    poll();
    const t = setInterval(poll, 3000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [jobId]);

  const phonePlaceholder = outcomes.find((o) => o.registry_id === "mobile-app-call");

  return (
    <>
      <h1 style={{ fontSize: 26, margin: "0 0 4px" }}>{heading}</h1>
      <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>{sub}</p>

      {running && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 14, display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  width: 16, height: 16, flex: "0 0 auto", borderRadius: "50%",
                  border: "2px solid rgba(255,255,255,0.25)", borderTopColor: "#7f9cff",
                  animation: "spin 1s linear infinite",
                }}
              />
              Working — running the quote scripts…
            </span>
            <span className="text-muted" style={{ fontSize: 12 }}>carrier {progress} / {total}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ flex: 1, height: 10, background: "rgba(255,255,255,0.1)", borderRadius: 999, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%", width: `${percent ?? 0}%`,
                  background: "linear-gradient(90deg,#4d6bff,#7f9cff)", borderRadius: 999,
                  transition: "width .5s ease",
                }}
              />
            </div>
            <span style={{ fontSize: 13, fontWeight: 700, minWidth: 46, textAlign: "right" }}>
              {percent ?? 0}%
            </span>
          </div>
          {label && (
            <div className="text-muted" style={{ fontSize: 12, marginTop: 6, textTransform: "capitalize" }}>
              Now: {label}{attempt > 1 ? ` (attempt ${attempt})` : ""}
            </div>
          )}
        </div>
      )}

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
            </tr>
          </thead>
          <tbody>
            {CARRIERS.map((c) => {
              const q = outcomes.find((o) => o.registry_id === c.registry_id);
              return (
                <tr key={c.registry_id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{q?.brand || c.brand}</div>
                    <div className="text-muted" style={{ fontSize: 11 }}>{c.registry_id}</div>
                  </td>
                  <td><StatusBadge q={q} /></td>
                  <td style={{ fontWeight: 700 }}>
                    {q?.annual_premium != null ? `$${q.annual_premium.toFixed(2)}` : "—"}
                  </td>
                  <td>{q?.monthly_premium != null ? `$${q.monthly_premium.toFixed(2)}/mo` : "—"}</td>
                  <td className="text-muted">{q?.quote_id || "—"}</td>
                  <td className="text-muted" style={{ maxWidth: 300 }}>{q?.coverage_notes || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {phonePlaceholder && (
        <p className="text-muted" style={{ marginTop: 14, fontSize: 12 }}>
          A phone call for this submission was created for the mobile app; the parsed phone
          quote appears here when the agent captures it.
        </p>
      )}
    </>
  );
}
