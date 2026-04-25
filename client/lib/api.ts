// API 클라이언트 유틸리티
/* eslint-disable @typescript-eslint/no-explicit-any */

const normalizeApiBase = (value: string): string => value.replace(/\/+$/, "").replace(/\/api$/, "");
const IS_PRODUCTION = process.env.NODE_ENV === "production";

// Use explicit public backend URL first (Vercel), then fallback to Next.js rewrite (/api).
const rawPublicApiBase = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const DEFAULT_TUNNEL_SUBDOMAIN = (process.env.NEXT_PUBLIC_TUNNEL_SUBDOMAIN || "lsy-super-trend").trim();
const DEFAULT_TUNNEL_HOST = (process.env.NEXT_PUBLIC_TUNNEL_HOST || "https://loca.lt").trim();
const normalizedTunnelHost = DEFAULT_TUNNEL_HOST.replace(/\/+$/, "").replace(/^http:\/\//, "https://");
const tunnelHostNoScheme = normalizedTunnelHost.replace(/^https?:\/\//, "");
const DEFAULT_TUNNEL_BASE =
  DEFAULT_TUNNEL_SUBDOMAIN && tunnelHostNoScheme
    ? normalizeApiBase(`https://${DEFAULT_TUNNEL_SUBDOMAIN}.${tunnelHostNoScheme}`)
    : "";

// In production, if no explicit API URL is provided, default to the tunnel base to ensure connectivity.
export const API_BASE = rawPublicApiBase 
  ? normalizeApiBase(rawPublicApiBase) 
  : (IS_PRODUCTION ? DEFAULT_TUNNEL_BASE : "");

const API_BASE_URL = '/api';
const RAW_FETCH_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_FETCH_TIMEOUT_MS || "30000");
const FETCH_TIMEOUT_MS = Number.isFinite(RAW_FETCH_TIMEOUT_MS)
  ? (RAW_FETCH_TIMEOUT_MS <= 0 ? 0 : Math.max(3000, RAW_FETCH_TIMEOUT_MS))
  : 30000;
const LOCAL_API_FALLBACKS = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  "http://localhost:8765",
].map(normalizeApiBase);

const withBypassHeaders = (options: RequestInit): RequestInit => ({
  ...options,
  headers: {
    ...options.headers,
    "ngrok-skip-browser-warning": "true",
    "Bypass-Tunnel-Reminder": "true",
  },
});


type FetchWithBypassOptions = RequestInit & {
  timeoutMs?: number;
};

const resolveTimeoutMs = (timeoutMs?: number): number | null => {
  if (!Number.isFinite(timeoutMs)) {
    return FETCH_TIMEOUT_MS <= 0 ? null : FETCH_TIMEOUT_MS;
  }
  const parsed = Number(timeoutMs);
  if (parsed <= 0) {
    return null;
  }
  return Math.max(3000, parsed);
};


export interface RunLoopResponse {
  success: boolean;
  iteration: number;
  queued_agents: string[];
  message: string;
}

export interface EvolutionLogEvent {
  id: number;
  created_at: string;
  level: string;
  phase: string;
  message: string;
  agent_id?: string | null;
  agent_label?: string | null;
  meta?: {
    decision?: {
      result?: string;
      status?: string;
      stage?: string;
      reason?: string;
      attempt?: number;
      attempt_budget?: number;
      llm_mode?: string;
      fingerprint?: string;
      improved?: boolean;
      strategy_id?: string | null;
      agent_alias?: string;
      agent_label?: string;
      gate_reasons?: string[];
      gate_thresholds?: Record<string, any>;
      improvement_summary?: Array<{
        metric: string;
        label?: string;
        baseline?: number;
        candidate?: number;
        delta?: number;
        baseline_display?: string;
        candidate_display?: string;
        delta_display?: string;
      }>;
      hard_gates?: Record<string, any>;
      quick_gates?: Record<string, any>;
    };
    metrics?: Record<string, any>;
    baseline_metrics?: Record<string, any>;
    verdict?: string;
  } | null;
}

export interface DecisionLogEvent {
  id: string | number;
  created_at: string;
  level: string;
  phase: string;
  message: string;
  agent_id?: string | null;
  agent_label?: string | null;
  meta?: EvolutionLogEvent["meta"];
}

export interface DashboardProgress {
  active_improvements: number;
  completed_improvements: number;
  failed_improvements: number;
  total_improvements: number;
  agents: string[];
  active_agents?: string[];
  latest_improvements: Array<{
    agent_id: string;
    status: string;
    progress: number;
    created_at: string;
    detail?: string;
  }>;
}


// API 호출 함수들 - fetchWithBypass를 사용하여 네트워크 안정성 확보
export class APIClient {
  static async runEvolutionLoop(agentIds?: string[]): Promise<RunLoopResponse> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/run-loop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent_ids: agentIds && agentIds.length > 0 ? agentIds : undefined,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to start loop: ${response.status}`);
    }

    return response.json();
  }


  static async getDashboardProgress(): Promise<DashboardProgress> {
    const ts = Date.now();
    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/improvement?_ts=${ts}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch dashboard data: ${response.status}`);
    }

    return response.json();
  }

  static async getEvolutionLog(limit = 160, agent_id?: string): Promise<EvolutionLogEvent[]> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("_ts", String(Date.now()));
    if (agent_id && agent_id !== "ALL" && agent_id !== "전체") {
      params.set("agent_id", agent_id);
    }

    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/evolution-log?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch evolution log: ${response.status}`);
    }

    const payload = await response.json();
    return Array.isArray(payload?.events) ? payload.events : [];
  }

  static async getDecisionLogs(limit = 220, agent_id?: string): Promise<DecisionLogEvent[]> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("_ts", String(Date.now()));
    if (agent_id && agent_id !== "ALL" && agent_id !== "전체") {
      params.set("agent_id", agent_id);
    }

    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/logs?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch decision logs: ${response.status}`);
    }

    const payload = await response.json();
    return Array.isArray(payload?.events) ? payload.events : [];
  }


  static async getAgentTimeseries(agentId: string, metric: string): Promise<number[]> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/timeseries?metric=${metric}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch timeseries data: ${response.status}`);
    }

    const data = await response.json();
    return data.data || [];
  }

  static async getDashboardMetrics(): Promise<DashboardMetrics> {
    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/metrics`);

    if (!response.ok) {
      throw new Error(`Failed to fetch dashboard metrics: ${response.status}`);
    }

    return response.json();
  }

  static async getAutomationStatus(): Promise<{ enabled: boolean, status: string }> {
    const response = await fetchWithBypass(`${API_BASE_URL}/system/automation`);
    if (!response.ok) throw new Error("Failed to fetch automation status");
    return response.json();
  }

  static async setAutomationStatus(enabled: boolean): Promise<{ success: boolean, enabled: boolean }> {
    const response = await fetchWithBypass(`${API_BASE_URL}/system/automation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!response.ok) throw new Error("자동화 상태 변경 실패");
    return response.json();
  }
}

export const AGENT_IDS = [
  'momentum_hunter',
  'mean_reverter',
  'macro_trader',
  'chaos_agent'
] as const;


export interface AgentPerformanceMetrics {
  agent_id: string;
  name: string;
  score: number[];
  return_val: number[];
  sharpe: number[];
  mdd: number[];
  win: number[];
  current_score: number;
  current_return: number;
  current_sharpe: number;
  current_mdd: number;
  current_win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_trade_duration: number;
}

export interface DashboardMetrics {
  total_agents: number;
  active_agents?: string[];
  agents: {
    [agentId: string]: {
      name: string;
      current_score: number;
      current_return: number;
      current_sharpe: number;
      current_mdd: number;
      current_win_rate: number;
    }
  };
  overall_metrics: {
    avg_trinity_score: number;
    best_performer: string;
    total_trades: number;
  };
}

const buildCandidates = (url: string): string[] => {
  if (url.startsWith("http")) return [url];
  const path = url.startsWith("/") ? url : `/${url}`;
  const candidates: string[] = [];
  const isHttpsPage =
    typeof window !== "undefined" && window.location?.protocol === "https:";
  const configuredRemote =
    !!API_BASE && !API_BASE.includes("localhost") && !API_BASE.includes("127.0.0.1");

  if (configuredRemote) {
    candidates.push(`${API_BASE}${path}`);
    candidates.push(path);
  } else {
    candidates.push(path);
    if (API_BASE) candidates.push(`${API_BASE}${path}`);
  }

  if (!IS_PRODUCTION) {
    for (const localBase of LOCAL_API_FALLBACKS) {
      if (isHttpsPage && localBase.startsWith("http://")) continue;
      candidates.push(`${localBase}${path}`);
    }
  }

  // Vercel(HTTPS) + local backend 조합에서 /api rewrite 실패 시 고정 터널로 자동 재시도.
  if (isHttpsPage && !configuredRemote && DEFAULT_TUNNEL_BASE) {
    candidates.push(`${DEFAULT_TUNNEL_BASE}${path}`);
  }

  return [...new Set(candidates)];
};

export const fetchWithBypass = async (url: string, options: FetchWithBypassOptions = {}) => {
  const { timeoutMs, ...requestInit } = options;
  const effectiveTimeoutMs = resolveTimeoutMs(timeoutMs);
  const candidates = buildCandidates(url);

  let lastError: unknown = null;

  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    const isLast = i === candidates.length - 1;
    const timeoutController = new AbortController();
    let abortReason: "timeout" | "aborted" | null = null;
    const timeoutId = effectiveTimeoutMs === null
      ? null
      : setTimeout(() => {
          abortReason = "timeout";
          timeoutController.abort("timeout");
        }, effectiveTimeoutMs);
    const externalSignal = requestInit.signal;
    let externalAbortListener: (() => void) | null = null;

    if (externalSignal) {
      externalAbortListener = () => {
        abortReason = "aborted";
        timeoutController.abort("aborted");
      };
      if (externalSignal.aborted) {
        if (timeoutId !== null) {
          clearTimeout(timeoutId);
        }
        throw new DOMException("Request aborted", "AbortError");
      }
      externalSignal.addEventListener("abort", externalAbortListener, { once: true });
    }

    const method = String(requestInit.method || "GET").toUpperCase();
    const requestOptions = withBypassHeaders({
      ...requestInit,
      cache: method === "GET" ? "no-store" : requestInit.cache,
      signal: timeoutController.signal,
    });

    try {
      const response = await fetch(candidate, requestOptions);
      if (!isLast && shouldRetryFallback(candidate, response)) {
        console.warn(`[API] Candidate failed, retrying: ${candidate} (Status: ${response.status})`);
        continue;
      }
      return response;
    } catch (error) {
      const normalizedError =
        error instanceof DOMException && error.name === "AbortError" && abortReason === "timeout"
          ? new Error("Request timed out")
          : error;
      lastError = normalizedError;
      console.warn(`[API] Candidate error: ${candidate}`, normalizedError);
      if (isLast) throw normalizedError;
    } finally {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
      if (externalSignal && externalAbortListener) {
        externalSignal.removeEventListener("abort", externalAbortListener);
      }
    }
  }

  throw (lastError as Error) || new Error("Failed to fetch");
};

const shouldRetryFallback = (candidate: string, response: Response): boolean => {
  const isRewriteCandidate = candidate.startsWith("/");
  if (isRewriteCandidate) {
    const vercelProxyError = response.headers.get("x-vercel-error");
    if (response.status === 404 || response.status >= 500 || !!vercelProxyError) return true;
  }

  const isConfiguredRemote =
    !!API_BASE &&
    candidate.startsWith(API_BASE) &&
    !API_BASE.includes("localhost") &&
    !API_BASE.includes("127.0.0.1");

  if (!isConfiguredRemote) return false;

  const tunnelUnavailable = response.headers.get("x-localtunnel-status") === "Tunnel Unavailable";
  const vercelProxyError = response.headers.get("x-vercel-error");
  const retryableStatus = response.status === 404 || response.status >= 500;
  const contentType = response.headers.get("content-type") || "";
  const htmlResponse = contentType.includes("text/html");

  return tunnelUnavailable || retryableStatus || htmlResponse || !!vercelProxyError;
};

// ─── Bot API ───

export interface BotConfig {
  name: string;
  strategy_id: string;
  leverage?: number;
  symbol?: string;
  timeframe?: string;
  initial_capital?: number;
  max_position_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  risk_profile?: string;
}

export const fetchStrategies = async (): Promise<any[]> => {
  try {
    const res = await fetchWithBypass(`${API_BASE_URL}/backtest/strategies`);
    const data = await res.json();
    return data.success ? data.strategies : [];
  } catch (error) {
    console.error("Failed to fetch strategies:", error);
    return [];
  }
};

export const fetchBots = async (): Promise<any[]> => {
  try {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots`);
    const data = await res.json();
    // 서버가 객체({success, bots})를 반환할 수도 있고 리스트([...])를 직접 반환할 수도 있음
    if (Array.isArray(data)) return data;
    return data && data.success && Array.isArray(data.bots) ? data.bots : [];
  } catch (error) {
    console.error("Failed to fetch bots:", error);
    return [];
  }
};

export const createBot = async (config: BotConfig): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  return res.json();
};

export const getBot = async (botId: string): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`);
  return res.json();
};

export const updateBot = async (botId: string, updates: Partial<BotConfig>): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return res.json();
};

export const deleteBot = async (botId: string): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}`, {
    method: "DELETE",
  });
  return res.json();
};

export const startBot = async (botId: string): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/start`, {
    method: "POST",
  });
  return res.json();
};

export const stopBot = async (botId: string): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/stop`, {
    method: "POST",
  });
  return res.json();
};

export const getBotState = async (botId: string): Promise<any> => {
  const res = await fetchWithBypass(`${API_BASE_URL}/bots/${botId}/state`);
  return res.json();
};

export const fetchBotTrades = async (limit = 50): Promise<any[]> => {
  try {
    const res = await fetchWithBypass(`${API_BASE_URL}/bots/trades?limit=${limit}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("Failed to fetch bot trades:", error);
    return [];
  }
};
