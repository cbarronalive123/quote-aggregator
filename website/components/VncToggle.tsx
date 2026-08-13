"use client";

import { useEffect, useState } from "react";

export default function VncToggle() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d) => setEnabled(!!d.vnc_enabled))
      .catch(() => setEnabled(false));
  }, []);

  const toggle = async () => {
    const next = !enabled;
    setBusy(true);
    setEnabled(next);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vnc_enabled: next }),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className="btn btn-primary"
      onClick={toggle}
      disabled={busy || enabled === null}
      style={{ padding: "10px 18px", fontSize: 14 }}
    >
      VNC live-view of the scripts: {enabled === null ? "…" : enabled ? "ON" : "OFF"}
    </button>
  );
}
