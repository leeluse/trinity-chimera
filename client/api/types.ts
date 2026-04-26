// API Types definitions

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
