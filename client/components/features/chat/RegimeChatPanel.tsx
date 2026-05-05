"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Bot, Play, Sparkles, Square, TerminalSquare, Zap } from "lucide-react";

interface RegimeChatPanelProps {
  context?: Record<string, unknown>;
  busy?: boolean;
  autoBusy?: boolean;
  autoRunning?: boolean;
  autoStatusLabel: string;
  autoMetaLabel?: string;
  streamStatusLabel?: string;
  streamElapsedSeconds?: number;
  chatLogLines?: string[];
  autoLastError?: string;
  autoLastSummaryPath?: string;
  autoLastStdoutTail?: string;
  autoCurrentStdoutTail?: string;
  onRunPrompt: (prompt: string) => void;
  onStartAuto: () => void;
  onStopAuto: () => void;
}

const DEFAULT_PROMPT =
  "Bull Strategy 01~04 레짐별 백테스팅 윈도우 돌려, 개선되면 코드 DB에 자동 적용해";

type LogTone = "neutral" | "info" | "good" | "warn" | "error" | "accent";

type ParsedLogLine = {
  badge: string;
  tone: LogTone;
  message: string;
  time?: string;
};

const TONE_STYLES: Record<LogTone, { text: string; badge: string }> = {
  neutral: {
    text: "text-slate-300",
    badge: "border-white/[0.16] bg-white/[0.04] text-slate-300",
  },
  info: {
    text: "text-cyan-100/95",
    badge: "border-cyan-300/40 bg-cyan-400/15 text-cyan-100",
  },
  good: {
    text: "text-emerald-100/95",
    badge: "border-emerald-300/40 bg-emerald-400/15 text-emerald-100",
  },
  warn: {
    text: "text-amber-100/95",
    badge: "border-amber-300/40 bg-amber-400/15 text-amber-100",
  },
  error: {
    text: "text-rose-100/95",
    badge: "border-rose-300/40 bg-rose-400/15 text-rose-100",
  },
  accent: {
    text: "text-indigo-100/95",
    badge: "border-indigo-300/40 bg-indigo-400/15 text-indigo-100",
  },
};

function shortenPath(pathLike: string, keepTail = 4): string {
  const raw = String(pathLike || "").trim();
  if (!raw) return raw;
  const normalized = raw.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= keepTail) return normalized;
  return `…/${parts.slice(-keepTail).join("/")}`;
}

function asPercent(value: unknown, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `${(n * 100).toFixed(digits)}%`;
}

function asNumber(value: unknown, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(digits);
}

function parsePythonMetricsDict(raw: string): Record<string, unknown> | null {
  try {
    const jsonLike = raw
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/\bNone\b/g, "null")
      .replace(/'/g, '"');
    return JSON.parse(jsonLike);
  } catch {
    return null;
  }
}

function parseLogLine(rawLine: string): ParsedLogLine {
  const line = String(rawLine || "").trim();
  if (!line) {
    return { badge: "LOG", tone: "neutral", message: "" };
  }

  // orphan/continuation lines from copied tail chunks
  if (/(timeout_sec=|max_tokens=|prompt_code_max_chars=)/i.test(line) && !line.startsWith("[")) {
    const timeout = line.match(/timeout_sec=([0-9.]+)/i)?.[1];
    const models = line.match(/models=([^ ]+)/i)?.[1];
    const maxTokens = line.match(/max_tokens=(\d+)/i)?.[1];
    const promptCap = line.match(/prompt_code_max_chars=(\d+)/i)?.[1];
    return {
      badge: "LLM",
      tone: "info",
      message:
        `timeout ${timeout || "-"}s` +
        (models ? ` · models ${models}` : "") +
        (maxTokens ? ` · tok ${Number(maxTokens).toLocaleString()}` : "") +
        (promptCap ? ` · prompt ${Number(promptCap).toLocaleString()} chars` : ""),
    };
  }

  const timeMatch = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$/);
  if (timeMatch) {
    const time = timeMatch[1];
    const rest = timeMatch[2] || "";
    const actorMatch = rest.match(/^(SYSTEM|USER|AI)\s*(.*)$/i);
    const actor = actorMatch ? actorMatch[1].toUpperCase() : "CHAT";
    const message = actorMatch ? actorMatch[2].trim() : rest.trim();
    const tone: LogTone =
      actor === "AI" ? "accent" : actor === "SYSTEM" ? "info" : "neutral";
    if (actor === "SYSTEM" && message.startsWith("[AUTO] START 요청")) {
      const args = message.match(/\(([^)]+)\)/)?.[1] || "";
      const compact = args
        ? `자동화 시작 · ${args.replace(/\s*,\s*/g, " · ")}`
        : "자동화 시작";
      return { badge: "SYSTEM", tone: "info", message: compact, time };
    }
    if (actor === "SYSTEM" && message.startsWith("[AUTO] STOP 요청")) {
      return { badge: "SYSTEM", tone: "warn", message: "자동화 중지 요청", time };
    }
    return { badge: actor, tone, message, time };
  }

  if (line.toLowerCase().startsWith("summary:")) {
    return { badge: "SUMMARY", tone: "info", message: line.slice(8).trim() };
  }

  if (line.toLowerCase().startsWith("error:")) {
    return { badge: "ERROR", tone: "error", message: line.slice(6).trim() };
  }

  const tagged = line.match(/^\[([^\]]+)\]\s*(.*)$/);
  if (tagged) {
    const tagRaw = tagged[1].trim();
    const tagKey = tagRaw.split(/\s+/)[0].toLowerCase();
    const message = tagged[2].trim();

    // Example: [B02] [progress] Bull_Strategy_02: iter 1/1 LLM request
    // Keep strategy label compact and parse the inner event for readability.
    if (/^b\d{2}$/i.test(tagRaw) && message.startsWith("[")) {
      const inner = parseLogLine(message);
      return {
        badge: tagRaw.toUpperCase(),
        tone: inner.tone,
        message: inner.message ? `${inner.badge} · ${inner.message}` : message,
      };
    }

    // Example: [Bull_Strategy_02 iter 1] regime=Bull score=...
    const iterTag = tagRaw.match(/^Bull_Strategy_0?(\d+)\s+iter\s+(\d+)$/i);
    if (iterTag) {
      const strategyNo = iterTag[1];
      const iterNo = iterTag[2];
      const pf = message.match(/\bPF=([0-9.\-]+)/i)?.[1];
      const monthly = message.match(/\bmonthly=([+\-]?[0-9.]+%?)/i)?.[1];
      const mdd = message.match(/\bMDD=([+\-]?[0-9.]+%?)/i)?.[1];
      const trades = message.match(/\btrades=(\d+)/i)?.[1];
      const accepted = /accepted=True|accepted=true/.test(message);
      const rejected = /accepted=False|accepted=false/.test(message);
      const tone: LogTone = accepted ? "good" : rejected ? "neutral" : "accent";
      return {
        badge: "ITER",
        tone,
        message:
          `Bull ${strategyNo} · iter ${iterNo}` +
          (pf ? ` · PF ${pf}` : "") +
          (monthly ? ` · M ${monthly}` : "") +
          (mdd ? ` · MDD ${mdd}` : "") +
          (trades ? ` · trades ${Number(trades).toLocaleString()}` : ""),
      };
    }

    const toneMap: Record<string, LogTone> = {
      info: "info",
      data: "accent",
      regime: "accent",
      batch: "info",
      baseline: "warn",
      progress: "info",
      mutate: "accent",
      iter: "accent",
      retry: "warn",
      apply: "good",
      done: "good",
      warn: "warn",
      skip: "neutral",
      stderr: "error",
      error: "error",
    };
    const tone = toneMap[tagKey] || "neutral";

    if (tagKey === "batch") {
      const serial = /temporary serial mode/i.test(message);
      const m = message.match(/^parallel=(\d+)\s+strategies=(.+)$/i);
      if (m) {
        const parallel = Number(m[1] || 1);
        const names = (m[2] || "")
          .split(",")
          .map((s) => s.trim().replace(/Bull_Strategy_/g, "Bull "))
          .filter(Boolean);
        return {
          badge: "BATCH",
          tone: "info",
          message: `동시 ${parallel}개 · ${names.join(", ")}`,
        };
      }
      if (serial) {
        return { badge: "BATCH", tone: "warn", message: "타임아웃 감지 · 임시 직렬 모드(1개) 전환" };
      }
    }

    if (tagKey === "warn") {
      if (/^litellm unreachable/i.test(message)) {
        return {
          badge: "WARN",
          tone: "warn",
          message: "LiteLLM 연결 점검 실패 · 재시도 중",
        };
      }
    }

    if (tagKey === "mutate") {
      const base = message.match(/^(\S+):\s+micro baseline score=([0-9.\-]+)\s+segments=(\d+)$/i);
      if (base) {
        return {
          badge: "MUTATE",
          tone: "accent",
          message: `${base[1].replace(/Bull_Strategy_/g, "Bull ")} · micro base ${asNumber(base[2])} · seg ${base[3]}`,
        };
      }
      const count = message.match(/^(\S+):\s+candidates=(\d+)$/i);
      if (count) {
        return {
          badge: "MUTATE",
          tone: "accent",
          message: `${count[1].replace(/Bull_Strategy_/g, "Bull ")} · 룰 후보 ${count[2]}개`,
        };
      }
      const micro = message.match(/^(\S+):\s+(\S+)\s+micro_score=([0-9.\-]+)\s+delta=([+\-][0-9.\-]+)$/i);
      if (micro) {
        const delta = Number(micro[4]);
        return {
          badge: "MUTATE",
          tone: delta > 0 ? "good" : "neutral",
          message:
            `${micro[1].replace(/Bull_Strategy_/g, "Bull ")} · ${micro[2]} · ` +
            `micro ${asNumber(micro[3])} · Δ ${asNumber(delta)}`,
        };
      }
      const full = message.match(/^(\S+):\s+(\S+)\s+full_score=([0-9.\-]+)\s+accepted=(True|False|true|false)$/i);
      if (full) {
        const accepted = String(full[4]).toLowerCase() === "true";
        return {
          badge: "MUTATE",
          tone: accepted ? "good" : "warn",
          message:
            `${full[1].replace(/Bull_Strategy_/g, "Bull ")} · ${full[2]} · ` +
            `full ${asNumber(full[3])} · ${accepted ? "채택" : "보류"}`,
        };
      }
    }

    if (tagKey === "retry") {
      return {
        badge: "RETRY",
        tone: "warn",
        message: "LLM 타임아웃 · 모델 재시도",
      };
    }

    if (tagKey === "iter") {
      const rej = message.match(/^(\S+)\s+rejected\(llm\):\s+(.+)$/i);
      if (rej) {
        const strategy = rej[1].replace(/Bull_Strategy_/g, "Bull ");
        const reason = rej[2];
        return {
          badge: "ITER",
          tone: "error",
          message: `${strategy} · LLM 실패 · ${reason}`,
        };
      }
    }

    if (tagKey === "llm") {
      const timeout = message.match(/timeout_sec=([0-9.]+)/i)?.[1];
      const models = message.match(/models=([^ ]+)/i)?.[1];
      const maxTokens = message.match(/max_tokens=(\d+)/i)?.[1];
      const promptCap = message.match(/prompt_code_max_chars=(\d+)/i)?.[1];
      return {
        badge: "LLM",
        tone: "info",
        message:
          `timeout ${timeout || "-"}s` +
          (models ? ` · models ${models}` : "") +
          (maxTokens ? ` · tok ${Number(maxTokens).toLocaleString()}` : "") +
          (promptCap ? ` · prompt ${Number(promptCap).toLocaleString()} chars` : ""),
      };
    }

    if (tagKey === "info") {
      const runDir = message.match(/^run_dir=(.+)$/);
      if (runDir) {
        return {
          badge: "INFO",
          tone: "info",
          message: `run dir: ${shortenPath(runDir[1], 5)}`,
        };
      }
      const strategies = message.match(/^strategies=(.+)$/);
      if (strategies) {
        const items = strategies[1]
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        const pretty = items
          .map((s) =>
            s
              .replace(/\[db\]/gi, "")
              .replace(/Bull_Strategy_/g, "Bull ")
              .replace(/_/g, " ")
              .trim()
          )
          .join(", ");
        return {
          badge: "INFO",
          tone: "info",
          message: `strategies ${items.length}개: ${pretty}`,
        };
      }
    }

    if (tagKey === "data") {
      const m = message.match(/^loaded cache:\s+(.+)\s+bars=(\d+)$/);
      if (m) {
        return {
          badge: "DATA",
          tone: "accent",
          message: `cache: ${shortenPath(m[1], 3)} · bars ${Number(m[2]).toLocaleString()}`,
        };
      }
    }

    if (tagKey === "regime") {
      const m = message.match(/^labels=(.+)$/);
      if (m) {
        return {
          badge: "REGIME",
          tone: "accent",
          message: `labels: ${shortenPath(m[1], 5)}`,
        };
      }
    }

    if (tagKey === "baseline") {
      const m = message.match(/^(\S+)\s+weak=(True|False|true|false)\s+score=([0-9.]+)\s+metrics=(\{.*\})$/);
      if (m) {
        const name = m[1].replace(/Bull_Strategy_/g, "Bull ");
        const weak = String(m[2]).toLowerCase() === "true";
        const score = Number(m[3]);
        const metrics = parsePythonMetricsDict(m[4]) || {};
        return {
          badge: "BASE",
          tone: weak ? "warn" : "good",
          message:
            `${name} · ${weak ? "weak" : "ok"} · score ${asNumber(score)} · ` +
            `PF ${asNumber(metrics.profit_factor)} · M ${asPercent(metrics.monthly_return)} · ` +
            `MDD ${asPercent(metrics.mdd)} · trades ${Number(metrics.trades || 0).toLocaleString()} · ` +
            `win ${asPercent(metrics.win_rate)}`,
        };
      }
    }

    if (tagKey === "progress") {
      const itStart = message.match(/^(\S+):\s+iterations=(\d+)\s+start$/);
      if (itStart) {
        return {
          badge: "STEP",
          tone: "info",
          message: `${itStart[1].replace(/Bull_Strategy_/g, "Bull ")} · iterations ${itStart[2]} 시작`,
        };
      }
      const itReq = message.match(/^(\S+):\s+iter\s+(\d+)\/(\d+)\s+LLM request$/i);
      if (itReq) {
        return {
          badge: "STEP",
          tone: "info",
          message: `${itReq[1].replace(/Bull_Strategy_/g, "Bull ")} · iter ${itReq[2]}/${itReq[3]} · LLM 요청`,
        };
      }
      const itRsp = message.match(/^(\S+):\s+iter\s+(\d+)\/(\d+)\s+LLM response received$/i);
      if (itRsp) {
        return {
          badge: "STEP",
          tone: "accent",
          message: `${itRsp[1].replace(/Bull_Strategy_/g, "Bull ")} · iter ${itRsp[2]}/${itRsp[3]} · 응답 수신`,
        };
      }
      const itScore = message.match(/^(\S+):\s+iter\s+(\d+)\/(\d+)\s+score=([0-9.\-]+)\s+accepted=(True|False|true|false)$/i);
      if (itScore) {
        return {
          badge: "STEP",
          tone: String(itScore[5]).toLowerCase() === "true" ? "good" : "neutral",
          message:
            `${itScore[1].replace(/Bull_Strategy_/g, "Bull ")} · iter ${itScore[2]}/${itScore[3]} · ` +
            `score ${asNumber(itScore[4])} · ${String(itScore[5]).toLowerCase() === "true" ? "채택" : "보류"}`,
        };
      }

      const itDone = message.match(/^(\S+):\s+done\s+improved=(True|False|true|false)\s+best_score=([0-9.\-]+)$/i);
      if (itDone) {
        const improved = String(itDone[2]).toLowerCase() === "true";
        return {
          badge: "STEP",
          tone: improved ? "good" : "warn",
          message:
            `${itDone[1].replace(/Bull_Strategy_/g, "Bull ")} · 완료 · ` +
            `${improved ? "개선됨" : "개선 없음"} · best ${asNumber(itDone[3])}`,
        };
      }
    }

    if (tagKey === "done") {
      const summary = message.match(/^summary=(.+)$/);
      if (summary) {
        return {
          badge: "DONE",
          tone: "good",
          message: `완료 · summary: ${shortenPath(summary[1], 5)}`,
        };
      }
    }

    if (tagKey === "stderr") {
      const timeout = message.match(/timeout value=([0-9.]+)/i);
      if (/timeout/i.test(message)) {
        return {
          badge: "ERROR",
          tone: "error",
          message: `LLM 요청 타임아웃${timeout ? ` (${timeout[1]}s)` : ""} · 재시도 대기`,
        };
      }
      return { badge: "ERROR", tone: "error", message };
    }

    return { badge: tagRaw.toUpperCase(), tone, message };
  }

  return { badge: "LOG", tone: "neutral", message: line };
}

function LogViewer({
  lines,
  emptyMessage,
}: {
  lines: string[];
  emptyMessage: string;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines]);

  if (!lines.length) {
    return (
      <div className="mt-2 rounded-lg border border-white/[0.08] bg-black/25 p-2 text-[10px] leading-relaxed text-slate-400">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="mt-2 max-h-44 space-y-1 overflow-y-auto pr-1">
      {lines.map((line, idx) => {
        const parsed = parseLogLine(line);
        const toneStyle = TONE_STYLES[parsed.tone];
        return (
          <div key={`${idx}-${line.slice(0, 24)}`} className="flex items-start gap-1.5 py-0.5">
            <span
              className={`inline-flex min-w-[54px] justify-center rounded px-1.5 py-0.5 text-[9px] font-bold tracking-[0.08em] border ${toneStyle.badge}`}
            >
              {parsed.badge}
            </span>
            <div className="min-w-0 flex-1">
              {parsed.time ? (
                <div className="mb-0.5 text-[9px] text-slate-500">{parsed.time}</div>
              ) : null}
              <div className={`break-all font-mono text-[10px] leading-relaxed ${toneStyle.text}`}>
                {parsed.message || line}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function RegimeChatPanel({
  context = {},
  busy = false,
  autoBusy = false,
  autoRunning = false,
  autoStatusLabel,
  autoMetaLabel = "",
  streamStatusLabel = "",
  streamElapsedSeconds = 0,
  chatLogLines = [],
  autoLastError = "",
  autoLastSummaryPath = "",
  autoLastStdoutTail = "",
  autoCurrentStdoutTail = "",
  onRunPrompt,
  onStartAuto,
  onStopAuto,
}: RegimeChatPanelProps) {
  const [customPrompt, setCustomPrompt] = useState(DEFAULT_PROMPT);
  const autoLogLines = useMemo(() => {
    const src = autoRunning ? autoCurrentStdoutTail : autoLastStdoutTail;
    const lines = String(src || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    // drop immediate duplicates for cleaner visual scan
    return lines.filter((line, idx) => idx === 0 || line !== lines[idx - 1]);
  }, [autoCurrentStdoutTail, autoLastStdoutTail, autoRunning]);

  const quickPrompts = useMemo(
    () => [
      {
        title: "레짐 라벨링",
        desc: "1h 레짐 기준 생성 + 검증",
        icon: Activity,
        prompt: "BTCUSDT 1h 2021-01-01~2026-01-31 레짐 라벨링 실행하고 검증 결과 보여줘",
      },
      {
        title: "레짐별 성과",
        desc: "Bull 01~04 구간별 성능 분석",
        icon: Sparkles,
        prompt: "Bull Strategy 01~04 레짐별 성과 분석표 만들어줘",
      },
      {
        title: "OOS 윈도우",
        desc: "윈도우 기반 리그 테스트",
        icon: Zap,
        prompt: "Bull Strategy 01~04 레짐별 백테스팅 윈도우 돌려",
      },
      {
        title: "Auto Fix",
        desc: "개선 시 DB 자동 반영",
        icon: Bot,
        prompt: DEFAULT_PROMPT,
      },
    ],
    []
  );

  const symbol = String(context?.symbol || "BTCUSDT");
  const tf = String(context?.timeframe || "15m");
  const start = String(context?.start_date || "2021-01-01");
  const end = String(context?.end_date || "2026-01-31");

  return (
    <div className="h-full overflow-y-auto no-scrollbar p-2">
      <div className="rounded-2xl border border-cyan-500/20 bg-[radial-gradient(circle_at_10%_0%,rgba(34,211,238,0.12),rgba(15,23,42,0.82)_42%)] p-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-black tracking-[0.16em] text-cyan-200 uppercase">Regime Chat</h3>
          <span className="text-[10px] text-cyan-100/70">{symbol} · {tf}</span>
        </div>
        <p className="mt-2 text-[11px] text-slate-300/90 leading-relaxed">
          레짐 전용 루프 페이지입니다. 버튼 클릭만으로 라벨링, OOS 백테스트, LLM 리팩토링까지 실행합니다.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
            기간 {start} ~ {end}
          </span>
          <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
            자동화 5m / 폴백 30m
          </span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2">
        {quickPrompts.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.title}
              onClick={() => onRunPrompt(item.prompt)}
              disabled={busy}
              className="w-full rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-left transition-all hover:border-cyan-400/35 hover:bg-cyan-500/5 disabled:opacity-50 disabled:cursor-not-allowed"
              title={item.prompt}
            >
              <div className="flex items-start gap-2">
                <Icon size={14} className="mt-0.5 text-cyan-300" />
                <div>
                  <div className="text-[11px] font-bold text-slate-100">{item.title}</div>
                  <div className="text-[10px] text-slate-400">{item.desc}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">Automation</div>
          <div className="text-[10px] text-slate-500">{autoStatusLabel}</div>
        </div>
        {autoMetaLabel ? <div className="mt-1 text-[10px] text-slate-500">{autoMetaLabel}</div> : null}
        <div className="mt-2 flex items-center gap-2">
          {autoRunning ? (
            <button
              onClick={onStopAuto}
              disabled={autoBusy}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/30 bg-rose-500/10 px-2.5 py-1.5 text-[10px] font-bold text-rose-200 transition-all hover:bg-rose-500/20 disabled:opacity-50"
            >
              <Square size={10} />
              STOP
            </button>
          ) : (
            <button
              onClick={onStartAuto}
              disabled={autoBusy}
              className="inline-flex items-center gap-1.5 rounded-md border border-blue-400/30 bg-blue-500/10 px-2.5 py-1.5 text-[10px] font-bold text-blue-200 transition-all hover:bg-blue-500/20 disabled:opacity-50"
            >
              <Play size={10} />
              START 5m/30m
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">
            <TerminalSquare size={12} className="text-cyan-300" />
            AI Chat Stream Log
          </div>
          <div className="text-[10px] text-slate-500">
            {busy ? `실행 중 · ${streamElapsedSeconds}초` : "대기"}
          </div>
        </div>
        {streamStatusLabel ? (
          <div className="mt-1 text-[10px] text-cyan-100/80">{streamStatusLabel}</div>
        ) : null}
        <LogViewer
          lines={chatLogLines}
          emptyMessage="[log] 아직 실행 로그가 없습니다. 상단 버튼으로 레짐 작업을 실행해 주세요."
        />
      </div>

      <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">
        <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">
          <TerminalSquare size={12} className="text-blue-300" />
          Auto Runner Log
        </div>
        {autoLastSummaryPath && !autoRunning ? (
          <div className="mt-1 text-[10px] text-slate-400 break-all">summary: {autoLastSummaryPath}</div>
        ) : null}
        {autoRunning ? (
          <div className="mt-1 text-[10px] text-slate-400">summary: 실행 중 (완료 후 최신 경로 표시)</div>
        ) : null}
        {autoLastError ? (
          <div className="mt-1 text-[10px] text-rose-300/90 break-all">error: {autoLastError}</div>
        ) : null}
        <LogViewer
          lines={autoLogLines}
          emptyMessage="[auto] 아직 자동 실행 로그가 없습니다. START 5m/30m 버튼으로 시작하세요."
        />
      </div>

      <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">
        <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300">Custom Regime Command</div>
        <textarea
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          placeholder="레짐 채팅 명령을 입력하세요..."
          disabled={busy}
          className="mt-2 w-full min-h-[88px] rounded-lg border border-white/[0.08] bg-black/20 px-3 py-2 text-[11px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/40 resize-y"
        />
        <button
          onClick={() => onRunPrompt(customPrompt)}
          disabled={!customPrompt.trim() || busy}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-cyan-100 transition-all hover:bg-cyan-500/20 disabled:opacity-50"
        >
          <Zap size={10} />
          Run Regime Chat
        </button>
      </div>
    </div>
  );
}
