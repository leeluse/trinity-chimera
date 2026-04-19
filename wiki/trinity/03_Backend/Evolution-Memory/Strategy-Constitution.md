# Strategy Constitution

진화 후보의 채택/거절 기준입니다. 이 문서는 사람이 읽고 고칠 수 있으며,
아래 JSON 블록은 런타임에서 직접 파싱됩니다.

<!-- CONFIG_START -->
{
  "hard_gates": {
    "min_win_rate": 0.45,
    "min_profit_factor": 1.2,
    "min_total_return": 0.0,
    "max_drawdown": 0.25,
    "min_total_trades": 30,
    "min_sharpe_ratio": 0.3
  },
  "quick_gates": {
    "min_win_rate": 0.38,
    "min_profit_factor": 1.05,
    "min_total_return": -0.02,
    "max_drawdown": 0.35,
    "min_total_trades": 10,
    "min_sharpe_ratio": -0.1
  },
  "budgets": {
    "max_candidates_per_cycle": 2,
    "max_llm_calls_per_cycle": 2
  },
  "memory": {
    "recent_failures_for_prompt": 5,
    "recent_successes_for_prompt": 3,
    "dedupe_window": 120
  }
}
<!-- CONFIG_END -->
