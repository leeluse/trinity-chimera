/**
 * NIM-TRADE Dashboard Type Definitions
 */

/** 개별 에이전트 성과 지표 */
export interface AgentMetrics {
  name: string;
  allocation: number;           // 0.0 ~ 1.0
  pnl_24h: number;             // 24시간 PnL
  pnl_7d: number;              // 7일 PnL
  pnl_total: number;           // 누적 PnL
  sharpe: number;              // 샤프 비율
  max_drawdown: number;        // 최대 낙폭 (0.0 ~ 1.0)
  win_rate: number;            // 승률 (0.0 ~ 1.0)
  open_positions: number;      // 현재 보유 포지션 수
  regime: string;              // 현재 감지된 레짐
  trade_count: number;         // 거래 횟수
}

/** 포트폴리오 상태 */
export interface PortfolioState {
  total_capital: number;
  total_pnl_24h: number;
  total_pnl_7d: number;
  total_pnl_total: number;
  agent_metrics: Record<string, AgentMetrics>;
  timestamp: string;             // ISO 8601
}

/** 에이전트 투표/행동 */
export interface AgentVote {
  name: string;
  action: number;              // -1.0 ~ 1.0 (포지션 비율)
  confidence: number;          // 0.0 ~ 1.0
}

/** 거래 기록 */
export interface Trade {
  id: string;
  agent_name: string;
  action: number;                // -1.0 ~ 1.0
  pnl: number;
  timestamp: string;
  symbol?: string;
  entry_price?: number;
  exit_price?: number;
}

/** Arbiter 재배분 결정 */
export interface ArbiterDecision {
  timestamp: string;
  old_allocations: Record<string, number>;
  new_allocations: Record<string, number>;
  reasoning: string;
  warnings?: string[];
}

/** 시장 데이터 */
export interface MarketData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  regime?: string;
}

/** 배틀 스텝 결과 */
export interface BattleStep {
  step: number;
  timestamp: string;
  market_obs: {
    regime: string;
    close: number;
    [key: string]: any;
  };
  agent_actions: Record<string, number>;
  net_signal: number;
}

/** WebSocket 이벤트 타입 */
export type WebSocketEventType =
  | 'portfolio'
  | 'battle_step'
  | 'arbiter_decision'
  | 'new_trade'
  | 'agent_update';

/** WebSocket 이벤트 */
export interface WebSocketEvent {
  type: WebSocketEventType;
  data: PortfolioState | BattleStep | ArbiterDecision | Trade | AgentMetrics;
}

/** 포트폴리오 가치 데이터 포인트 */
export interface PortfolioValuePoint {
  timestamp: string;
  total_value: number;
  pnl: number;
  pnl_pct: number;
}

/** 시각화 메트릭 타입 */
export type MetricType =
  | 'pnl_24h'
  | 'pnl_7d'
  | 'pnl_total'
  | 'sharpe'
  | 'win_rate'
  | 'max_drawdown'
  | 'allocation';

/** 차트 타입 */
export type ChartType = 'line' | 'bar' | 'radar' | 'pie' | 'area';

/** 시간 범위 */
export type TimeRange = '1h' | '24h' | '7d' | '30d' | 'all';

/** 실시간 연결 상태 */
export type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting';

/** 에이전트 페르소나 타입 */
export type AgentPersona =
  | 'momentum_hunter'
  | 'mean_reverter'
  | 'macro_trader'
  | 'chaos_agent';

/** 시장 레짐 타입 */
export type MarketRegime = 'bull' | 'bear' | 'sideways' | 'volatile' | 'unknown';

/** 색상 테마 */
export interface ThemeConfig {
  /** 시맨틱 색상 */
  colors: {
    profit: string;           // 수익/상승
    loss: string;             // 손실/하락
    neutral: string;          // 중립
    warning: string;          // 경고
    info: string;             // 정보
    success: string;          // 성공
  };
  /** 에이전트 색상 */
  agentColors: Record<AgentPersona, string>;
  /** 레짐 색상 */
  regimeColors: Record<MarketRegime, string>;
}
