"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ClipRow = {
  id: number;
  source_url: string;
  source_video_id: string;
  start_time: number;
  end_time: number;
  title: string | null;
  template_id: string;
  llm_model: string;
  llm_score: number | null;
  created_at: string;
  yt_video_id: string | null;
};

export default function HistoryPage() {
  const [rows, setRows] = useState<ClipRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/clips`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setRows(await r.json());
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "load failed"));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <h1 className="text-3xl font-bold mb-8">History</h1>

      {error && (
        <div className="rounded-md border border-red-500 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {rows?.length === 0 && (
        <p className="text-muted">아직 편집된 클립이 없습니다. Edit 탭에서 영상을 넣어보세요.</p>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card text-muted">
              <tr>
                <th className="text-left px-4 py-3">날짜</th>
                <th className="text-left px-4 py-3">제목</th>
                <th className="text-left px-4 py-3">구간</th>
                <th className="text-left px-4 py-3">템플릿</th>
                <th className="text-left px-4 py-3">모델</th>
                <th className="text-right px-4 py-3">⭐</th>
                <th className="text-left px-4 py-3">YouTube</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-border hover:bg-card/50">
                  <td className="px-4 py-3 text-muted whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString("ko-KR")}
                  </td>
                  <td className="px-4 py-3">{r.title ?? "—"}</td>
                  <td className="px-4 py-3 text-muted whitespace-nowrap">
                    {fmt(r.start_time)} → {fmt(r.end_time)}
                  </td>
                  <td className="px-4 py-3">{r.template_id}</td>
                  <td className="px-4 py-3 text-muted">{r.llm_model}</td>
                  <td className="px-4 py-3 text-right">
                    {r.llm_score != null ? r.llm_score.toFixed(1) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {r.yt_video_id ? (
                      <a
                        href={`https://www.youtube.com/shorts/${r.yt_video_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent hover:underline"
                      >
                        열기 ↗
                      </a>
                    ) : (
                      <span className="text-muted">미업로드</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
