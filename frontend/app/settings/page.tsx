"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type HealthResp = {
  status: string;
  ollama: "connected" | "unreachable";
  default_model: string;
  current_weights: Record<string, number>;
};

const SIGNAL_LABELS: Record<string, string> = {
  retention: "Retention",
  laughter: "Laughter",
  volume: "Volume",
  emotion: "Emotion",
  tempo: "Tempo",
};

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResp | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/health`);
      if (r.ok) setHealth(await r.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted mt-1">시스템 상태와 현재 가중치 스냅샷.</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:text-white disabled:opacity-50"
        >
          {loading ? "확인 중…" : "새로고침"}
        </button>
      </div>

      {health && (
        <>
          <section className="mb-8 rounded-md border border-border bg-card p-5">
            <h2 className="font-semibold mb-4">시스템</h2>
            <div className="grid gap-3">
              <Row label="API 서버" value="정상" ok />
              <Row
                label="Ollama"
                value={health.ollama === "connected" ? "연결됨" : "연결 불가"}
                ok={health.ollama === "connected"}
              />
              <Row label="기본 모델" value={health.default_model} />
            </div>
          </section>

          <section className="rounded-md border border-border bg-card p-5">
            <h2 className="font-semibold mb-1">현재 가중치</h2>
            <p className="text-xs text-muted mb-4">
              Phase 2 자동 조정 또는 초기값. Evolution 페이지에서 전체 이력 확인 가능.
            </p>
            <div className="grid gap-3">
              {Object.entries(health.current_weights).map(([sig, w]) => (
                <div key={sig} className="flex items-center gap-3">
                  <span className="w-24 text-sm">{SIGNAL_LABELS[sig] ?? sig}</span>
                  <div className="flex-1 h-2 rounded-full bg-background overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full"
                      style={{ width: `${(w * 100).toFixed(1)}%` }}
                    />
                  </div>
                  <span className="text-sm tabular-nums w-10 text-right">
                    {(w * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted">{label}</span>
      <span className={ok === false ? "text-red-400" : ok ? "text-green-400" : ""}>
        {value}
      </span>
    </div>
  );
}
