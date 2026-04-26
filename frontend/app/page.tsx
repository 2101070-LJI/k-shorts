"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

type Stage = "connected" | "download" | "asr" | "signals" | "scoring" | "render" | "done" | "error" | "heartbeat";

type Progress = { stage: Stage; pct: number; message: string };

type Candidate = {
  start: number;
  end: number;
  title: string;
  reason: string;
  score: number;
  template_id: string;
  output_path: string | null;
  clip_id: number | null;
};

type Job = {
  id: string;
  source_url: string;
  status: string;
  progress_pct: number;
  message: string;
  error: string | null;
  candidates: Candidate[];
};

const MODELS = [
  { value: "qwen3:8b", label: "Qwen3 8B (기본)" },
  { value: "exaone3.5:7.8b", label: "EXAONE 3.5 7.8B" },
];

export default function EditPage() {
  const [url, setUrl] = useState("");
  const [model, setModel] = useState(MODELS[0].value);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => () => wsRef.current?.close(), []);

  async function cancel() {
    if (!jobId) return;
    await fetch(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
    setProgress(null);
  }

  async function start() {
    if (!url.trim()) return;
    setError("");
    setJob(null);
    setJobId(null);
    setProgress({ stage: "connected", pct: 0, message: "작업 생성 중…" });

    let jid: string;
    try {
      const r = await fetch(`${API_BASE}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), template_id: "clean", llm_model: model }),
      });
      if (!r.ok) throw new Error(`POST /edit → HTTP ${r.status}`);
      const created: Job = await r.json();
      jid = created.id;
      setJobId(jid);
    } catch (e) {
      setError(e instanceof Error ? e.message : "편집 시작 실패");
      setProgress(null);
      return;
    }

    const ws = new WebSocket(`${WS_BASE}/ws/jobs/${jid}`);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      const p = JSON.parse(ev.data) as Progress;
      if (p.stage === "heartbeat") return;
      setProgress(p);
      if (p.stage === "done" || p.stage === "error") ws.close();
      if (p.stage === "done") loadJob(jid);
      if (p.stage === "error") setError(p.message);
    };
    ws.onerror = () => setError("WebSocket 연결 오류");
  }

  async function loadJob(jid: string) {
    const r = await fetch(`${API_BASE}/jobs/${jid}`);
    if (r.ok) setJob(await r.json());
  }

  const running = progress && progress.stage !== "done" && progress.stage !== "error";

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold mb-2">한국 예능 숏츠 자동 편집</h1>
      <p className="text-muted mb-10">롱폼 유튜브 URL을 입력하세요 (30분~1시간).</p>

      <div className="flex gap-3 flex-wrap">
        <input
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={!!running}
          className="flex-1 min-w-0 rounded-md bg-card border border-border px-4 py-3 text-white placeholder:text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          disabled={!!running}
          className="rounded-md bg-card border border-border px-3 py-3 text-sm text-white focus:border-accent focus:outline-none disabled:opacity-50"
        >
          {MODELS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        {running ? (
          <button
            onClick={cancel}
            className="rounded-md border border-red-500 px-5 py-3 text-sm text-red-400 hover:bg-red-500/10"
          >
            취소
          </button>
        ) : (
          <button
            onClick={start}
            className="rounded-md bg-accent px-6 py-3 font-semibold text-black hover:opacity-90"
          >
            편집 시작
          </button>
        )}
      </div>

      {progress && (
        <div className="mt-8 rounded-md border border-border bg-card p-5">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-muted">{progress.stage}</span>
            <span>{Math.round(progress.pct)}%</span>
          </div>
          <div className="h-2 rounded-full bg-background overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${progress.pct}%` }}
            />
          </div>
          <p className="mt-3 text-sm text-muted">{progress.message}</p>
        </div>
      )}

      {error && (
        <div className="mt-6 rounded-md border border-red-500 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {job?.candidates && job.candidates.length > 0 && (
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {job.candidates.map((c, i) => (
            <CandidateCard key={i} candidate={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const videoSrc = candidate.output_path
    ? `${API_BASE}/clips/${candidate.output_path.replace(/\\/g, "/")}`
    : null;
  const [vote, setVote] = useState<1 | -1 | null>(null);
  const [sending, setSending] = useState(false);

  async function record(label: 1 | -1) {
    if (candidate.clip_id == null || sending) return;
    setSending(true);
    try {
      const r = await fetch(`${API_BASE}/preferences/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clip_id: candidate.clip_id, label }),
      });
      if (r.ok) setVote(label);
    } finally {
      setSending(false);
    }
  }

  const disabled = candidate.clip_id == null || sending;

  return (
    <div className="rounded-md border border-border bg-card overflow-hidden">
      {videoSrc ? (
        <video
          src={videoSrc}
          controls
          muted
          className="w-full aspect-[9/16] bg-black"
        />
      ) : (
        <div className="w-full aspect-[9/16] bg-black" />
      )}
      <div className="p-4">
        <div className="font-semibold">{candidate.title}</div>
        <div className="text-xs text-muted mt-1">
          {formatTime(candidate.start)} → {formatTime(candidate.end)} · ⭐ {candidate.score.toFixed(1)}
        </div>
        <p className="mt-3 text-sm text-muted">{candidate.reason}</p>
        <div className="mt-4 flex gap-2">
          <button
            onClick={() => record(1)}
            disabled={disabled}
            className={`flex-1 rounded-md border px-3 py-2 text-sm transition ${
              vote === 1
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-muted hover:border-accent hover:text-white"
            } disabled:opacity-50`}
          >
            👍 {vote === 1 ? "저장됨" : "좋아요"}
          </button>
          <button
            onClick={() => record(-1)}
            disabled={disabled}
            className={`flex-1 rounded-md border px-3 py-2 text-sm transition ${
              vote === -1
                ? "border-red-500 bg-red-500/10 text-red-400"
                : "border-border text-muted hover:border-red-500 hover:text-white"
            } disabled:opacity-50`}
          >
            👎 {vote === -1 ? "저장됨" : "별로"}
          </button>
        </div>
      </div>
    </div>
  );
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
