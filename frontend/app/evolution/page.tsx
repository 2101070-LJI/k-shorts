"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const SIGNAL_COLORS: Record<string, string> = {
  retention: "#FFE100",
  laughter: "#F472B6",
  volume: "#60A5FA",
  emotion: "#34D399",
  tempo: "#A78BFA",
};

type WeightRow = {
  effective_from: string;
  w_retention: number;
  w_laughter: number;
  w_volume: number;
  w_emotion: number;
  w_tempo: number;
  update_reason: string;
};

type WeightsResp = {
  history: WeightRow[];
  current: Record<string, number>;
  next_cron: string | null;
};

type PerfPoint = { clip_id: number; created_at: string; score: number; views: number };
type CompareRow = { signal: string; top: number; bot: number };
type Insights = {
  total_clips: number;
  total_views: number;
  total_feedbacks: number;
  biggest_grower: { signal: string; delta: number } | null;
  improvement_pct: number;
  weight_updates: number;
  learning_status: string;
};

export default function EvolutionPage() {
  const [weights, setWeights] = useState<WeightsResp | null>(null);
  const [perf, setPerf] = useState<PerfPoint[]>([]);
  const [compare, setCompare] = useState<CompareRow[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  async function loadAll() {
    setError("");
    try {
      const [w, p, c, i] = await Promise.all([
        fetch(`${API_BASE}/evolution/weights`).then((r) => r.json()),
        fetch(`${API_BASE}/evolution/performance`).then((r) => r.json()),
        fetch(`${API_BASE}/evolution/signal-comparison`).then((r) => r.json()),
        fetch(`${API_BASE}/evolution/insights`).then((r) => r.json()),
      ]);
      setWeights(w);
      setPerf(p);
      setCompare(c);
      setInsights(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패");
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      await fetch(`${API_BASE}/evolution/refresh`, { method: "POST" });
      await loadAll();
    } finally {
      setRefreshing(false);
    }
  }

  const weightSeries = (weights?.history ?? []).map((h) => ({
    date: h.effective_from.slice(0, 10),
    retention: h.w_retention,
    laughter: h.w_laughter,
    volume: h.w_volume,
    emotion: h.w_emotion,
    tempo: h.w_tempo,
  }));

  const perfSeries = perf.map((p) => ({
    date: p.created_at.slice(0, 10),
    score: Number(p.score.toFixed(3)),
  }));

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Evolution</h1>
          <p className="text-muted mt-1">
            가중치가 어떻게 변해왔고, 그 결과 성과는 어떻게 달라졌는지.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-black hover:opacity-90 disabled:opacity-50"
        >
          {refreshing ? "수집 중…" : "지표 수동 새로고침"}
        </button>
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-red-500 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {insights && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 mb-10">
          <InsightCard label="총 클립" value={insights.total_clips.toString()} />
          <InsightCard
            label="총 조회수"
            value={insights.total_views.toLocaleString()}
          />
          <InsightCard label="피드백" value={`${insights.total_feedbacks}`} />
          <InsightCard
            label="학습 상태"
            value={insights.learning_status}
            sub={
              insights.improvement_pct !== 0
                ? `${insights.improvement_pct > 0 ? "+" : ""}${insights.improvement_pct}%`
                : undefined
            }
          />
        </div>
      )}

      {insights?.biggest_grower && (
        <div className="mb-10 rounded-md border border-accent/30 bg-accent/5 px-4 py-3 text-sm">
          가장 크게 성장한 신호:{" "}
          <span className="font-semibold text-accent">
            {insights.biggest_grower.signal}
          </span>{" "}
          ({insights.biggest_grower.delta > 0 ? "+" : ""}
          {insights.biggest_grower.delta.toFixed(3)}) · 가중치 업데이트 {insights.weight_updates}회
        </div>
      )}

      <ChartCard title="가중치 변화 (스택 영역)" subtitle={nextCronLine(weights?.next_cron)}>
        {weightSeries.length < 2 ? (
          <EmptyHint text="업데이트 이력이 1회 이하입니다. 10개 이상 클립이 누적되면 자동 조정이 시작됩니다." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={weightSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {Object.keys(SIGNAL_COLORS).map((s) => (
                <Area
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stackId="1"
                  stroke={SIGNAL_COLORS[s]}
                  fill={SIGNAL_COLORS[s]}
                  fillOpacity={0.6}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="성과 트렌드 (performance_score 추이)">
        {perfSeries.length === 0 ? (
          <EmptyHint text="업로드된 숏츠가 아직 없습니다. YouTube 업로드 후 지표가 수집되면 표시됩니다." />
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={perfSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} domain={[0, 1]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="score" stroke="#FFE100" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="상위 25% vs 하위 25% 신호 비교">
        {compare.length === 0 ? (
          <EmptyHint text="6개 이상의 성과 데이터가 필요합니다." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={compare}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="signal" stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Bar dataKey="top" fill="#FFE100" name="상위 25%" />
              <Bar dataKey="bot" fill="#666" name="하위 25%" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8 rounded-md border border-border bg-card p-5">
      <h2 className="text-lg font-semibold mb-1">{title}</h2>
      {subtitle && <p className="text-xs text-muted mb-4">{subtitle}</p>}
      {children}
    </section>
  );
}

function InsightCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
      {sub && <div className="text-xs text-accent mt-1">{sub}</div>}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <div className="text-sm text-muted py-10 text-center">{text}</div>;
}

function nextCronLine(next: string | null | undefined): string {
  if (!next) return "자동 cron 비활성";
  const d = new Date(next);
  return `다음 자동 수집: ${d.toLocaleString()}`;
}

const tooltipStyle = {
  backgroundColor: "#1a1a1a",
  border: "1px solid #333",
  fontSize: "12px",
};
