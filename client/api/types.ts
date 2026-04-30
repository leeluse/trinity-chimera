// API Types definitions





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
