"use client";

import { useEffect, useState } from "react";
import { recordingUrl } from "@/lib/config";
import type { QuoteOutcome } from "@/lib/types";

interface Props {
  jobId: string;
  cached: QuoteOutcome[];
  heading: string;
  sub: string;
}

// Merge live job outcomes (phone quotes as they arrive) over the cached/base
// outcomes, replacing by registry_id so a real broker quote supersedes a seed.
function mergeOutcomes(base: QuoteOutcome[], live: QuoteOutcome[]): QuoteOutcome[] {
  const map = new Map<string, QuoteOutcome>();
  base.forEach((o) => map.set(o.registry_id, o));
  live.forEach((o) => map.set(o.registry_id, o));
  const quoted = [...map.values()].filter(
    (o) => o.status === "quoted_comparable" || o.status === "quoted_non_comparable"
  );
  return quoted.sort((a, b) => (a.annual_premium ?? 0) - (b.annual_premium ?? 0));
}

function Row({ q }: { q: QuoteOutcome }) {
  return (
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
  );
}

export default function LiveResults({ jobId, cached, heading, sub }: Props) {
  const [rows, setRows] = useState<QuoteOutcome[]>(cached);
  const [status, setStatus] = useState("running");
  const [progress, setProgress] = useState("");

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const r = await fetch(`/api/quote?id=${encodeURIComponent(jobId)}`);
        if (!r.ok) return;
        const j = await r.json();
        if (!active) return;
        setStatus(j.status);
        setProgress(j.total ? `${j.progress} / ${j.total} carriers called` : "");
        setRows(mergeOutcomes(cached, j.outcomes || []));
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
  }, [jobId, cached]);

  return (
    <>
      <h1 style={{ fontSize: 26, margin: "0 0 4px" }}>{heading}</h1>
      <p className="text-muted" style={{ margin: "0 0 24px", fontSize: 13 }}>
        {sub}
        {status === "running" && progress ? ` · Calling: ${progress}` : ""}
      </p>
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
                <td colSpan={6} className="text-muted">Awaiting quotes…</td>
              </tr>
            ) : (
              rows.map((q) => <Row key={q.registry_id} q={q} />)
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
