"use client";

import { useEffect, useState } from "react";

interface Settings {
  vnc_enabled: boolean;
  max_retries: number;
  quote_timeout_seconds: number;
  phone_call_on_blocked: boolean;
  phone_agent_url: string;
}

export default function AutomationSettings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d) =>
        setSettings({
          vnc_enabled: !!d.vnc_enabled,
          max_retries: Number(d.max_retries) || 2,
          quote_timeout_seconds: Number(d.quote_timeout_seconds) || 600,
          phone_call_on_blocked: d.phone_call_on_blocked !== false,
          phone_agent_url: d.phone_agent_url || "http://127.0.0.1:8765",
        })
      )
      .catch(() => setSettings({ vnc_enabled: false, max_retries: 2, quote_timeout_seconds: 600, phone_call_on_blocked: true, phone_agent_url: "http://127.0.0.1:8765" }));
  }, []);

  const save = async () => {
    if (!settings) return;
    setBusy(true);
    setSaved(false);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      setSaved(true);
    } finally {
      setBusy(false);
    }
  };

  const toggleVnc = async () => {
    if (!settings) return;
    const next = { ...settings, vnc_enabled: !settings.vnc_enabled };
    setSettings(next);
    setBusy(true);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
    } finally {
      setBusy(false);
    }
  };

  if (!settings) {
    return <div className="text-muted">Loading settings…</div>;
  }

  const row: React.CSSProperties = {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 16, padding: "12px 0", borderBottom: "1px solid rgba(255,255,255,0.08)",
  };

  return (
    <div>
      <div style={row}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontWeight: 600 }}>Show the scripts running live (VNC)</div>
          <p className="text-muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            When ON, the quote scripts open a visible browser on the server&apos;s virtual display
            (watch at <code>http://localhost:6080/vnc.html</code>); when OFF they run minimized/off-screen.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={toggleVnc} disabled={busy} style={{ padding: "10px 18px", flex: "0 0 auto" }}>
          {settings.vnc_enabled ? "ON" : "OFF"}
        </button>
      </div>

      <div style={row}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontWeight: 600 }}>Retries per carrier</div>
          <p className="text-muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            If a carrier&apos;s form stalls or a modal blocks it, retry the whole flow from scratch this
            many times before giving up.
          </p>
        </div>
        <input
          type="number"
          min={1}
          max={10}
          value={settings.max_retries}
          onChange={(e) => setSettings({ ...settings, max_retries: Number(e.target.value) })}
          style={{ width: 80, padding: "8px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.05)", color: "inherit", flex: "0 0 auto" }}
        />
      </div>

      <div style={row}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontWeight: 600 }}>Call a carrier when its online quote is blocked</div>
          <p className="text-muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            When a carrier&apos;s online quote is gated (e.g. Allstate on the server), place a call to
            its sales line using the phone agent on your connected Android phone.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setSettings({ ...settings, phone_call_on_blocked: !settings.phone_call_on_blocked })} disabled={busy} style={{ padding: "10px 18px", flex: "0 0 auto" }}>
          {settings.phone_call_on_blocked ? "ON" : "OFF"}
        </button>
      </div>

      <div style={row}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontWeight: 600 }}>Phone agent URL</div>
          <p className="text-muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            Where the phone-agent call server is reachable from this server (e.g. via an SSH
            reverse tunnel). Defaults to <code>http://127.0.0.1:8765</code>.
          </p>
        </div>
        <input
          type="text"
          value={settings.phone_agent_url}
          onChange={(e) => setSettings({ ...settings, phone_agent_url: e.target.value })}
          style={{ width: 240, padding: "8px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.05)", color: "inherit", flex: "0 0 auto" }}
        />
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16 }}>
        <button type="button" className="btn btn-primary" onClick={save} disabled={busy} style={{ padding: "10px 18px" }}>
          {busy ? "Saving…" : "Save"}
        </button>
        {saved && <span className="text-accent" style={{ fontSize: 13 }}>Saved ✓</span>}
      </div>
    </div>
  );
}
