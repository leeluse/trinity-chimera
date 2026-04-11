// API 클라이언트 유틸리티
/* eslint-disable @typescript-eslint/no-explicit-any */

const API_BASE_URL = '/api';
const normalizeApiBase = (value: string): string => value.replace(/\/+$/, "").replace(/\/api$/, "");
export const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL || "");
const IS_PRODUCTION = process.env.NODE_ENV === "production";
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

export interface AgentImprovementRequest {
  current_strategy: any;
  recent_performance: {
    sharpe: number;
    mdd: number;
    win_rate: number;
  };
  market_regime: string;
  improvement_goal?: string;
}

export interface ImprovementResponse {
  success: boolean;
  improvement_id: string;
  status: string;
  message: string;
}

export interface DashboardProgress {
  active_improvements: number;
  completed_improvements: number;
  failed_improvements: number;
  total_improvements: number;
  agents: string[];
  latest_improvements: Array<{
    agent_id: string;
    status: string;
    progress: number;
    created_at: string;
  }>;
}

export interface BacktestResult {
  improvement_id: string;
  agent_id: string;
  strategy_params: any;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  trinity_score: number;
  start_date: string;
  end_date: string;
  duration_days: number;
  trades_count: number;
  avg_trade_return: number;
  best_trade_return: number;
  worst_trade_return: number;
}

export interface LLMFeedback {
  improvement_id: string;
  agent_id: string;
  analysis_summary: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  parameter_suggestions: any;
  expected_improvement: any;
  confidence_score: number;
  created_at: string;
  model_used: string;
}

// API 호출 함수들 - fetchWithBypass를 사용하여 네트워크 안정성 확보
export class APIClient {
  static async requestImprovement(
    agentId: string,
    request: AgentImprovementRequest
  ): Promise<ImprovementResponse> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/improve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API 요청 실패: ${response.status}`);
    }

    return response.json();
  }

  static async getDashboardProgress(): Promise<DashboardProgress> {
    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/improvement`);

    if (!response.ok) {
      throw new Error(`대시보드 데이터 조회 실패: ${response.status}`);
    }

    return response.json();
  }

  static async getBacktestResult(agentId: string): Promise<BacktestResult | null> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/backtest`);

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new Error(`백테스팅 결과 조회 실패: ${response.status}`);
    }

    return response.json();
  }

  static async getFeedbackHistory(agentId: string): Promise<LLMFeedback[]> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/feedback`);

    if (!response.ok) {
      throw new Error(`피드백 이력 조회 실패: ${response.status}`);
    }

    return response.json();
  }

  static async getAgentPerformance(agentId: string): Promise<any> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/performance`);

    if (!response.ok) {
      throw new Error(`에이전트 성과 데이터 조회 실패: ${response.status}`);
    }

    return response.json();
  }

  static async getAgentTimeseries(agentId: string, metric: string): Promise<number[]> {
    const response = await fetchWithBypass(`${API_BASE_URL}/agents/${agentId}/timeseries?metric=${metric}`);

    if (!response.ok) {
      throw new Error(`시계열 데이터 조회 실패: ${response.status}`);
    }

    const data = await response.json();
    return data.data || [];
  }

  static async getDashboardMetrics(): Promise<DashboardMetrics> {
    const response = await fetchWithBypass(`${API_BASE_URL}/dashboard/metrics`);

    if (!response.ok) {
      throw new Error(`대시보드 메트릭 조회 실패: ${response.status}`);
    }

    return response.json();
  }
}

export const AGENT_IDS = [
  'momentum_hunter',
  'mean_reverter',
  'macro_trader',
  'chaos_agent'
] as const;

// Trinity Score 계산 함수
export function calculateTrinityScore(
  totalReturn: number,
  sharpe: number,
  maxDrawdown: number
): number {
  return (totalReturn * 0.4) + (sharpe * 25 * 0.35) + ((1 + Math.max(maxDrawdown, -0.3)) * 100 * 0.25);
}

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
      candidates.push(`${localBase}${path}`);
    }
  }

  return [...new Set(candidates)];
};

export const fetchWithBypass = async (url: string, options: RequestInit = {}) => {
  const candidates = buildCandidates(url);
  const requestOptions = withBypassHeaders(options);

  let lastError: unknown = null;

  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    const isLast = i === candidates.length - 1;

    try {
      const response = await fetch(candidate, requestOptions);
      if (!isLast && shouldRetryFallback(candidate, response)) {
        console.warn(`[API] Candidate failed, retrying: ${candidate} (Status: ${response.status})`);
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      console.warn(`[API] Candidate error: ${candidate}`, error);
      if (isLast) throw error;
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
  const retryableStatus = response.status >= 500;
  const contentType = response.headers.get("content-type") || "";
  const htmlResponse = contentType.includes("text/html");

  return tunnelUnavailable || retryableStatus || htmlResponse;
};
