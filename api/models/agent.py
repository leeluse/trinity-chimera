# """
# LLM 자가 개선 시스템 데이터 모델
# """

# from pydantic import BaseModel
# from typing import List, Dict, Optional, Any
# from datetime import datetime
# from enum import Enum


# class ImprovementStatus(str, Enum):
#     """개선 상태"""
#     REQUESTED = "requested"
#     BACKTESTING = "backtesting"
#     ANALYZING = "analyzing"
#     COMPLETED = "completed"
#     FAILED = "failed"


# class AgentImprovementRequest(BaseModel):
#     """에이전트 개선 요청"""
#     current_strategy: Dict[str, Any]
#     recent_performance: Dict[str, float]  # Sharpe, MDD, WinRate 등
#     market_regime: str  # bull, sideways, bear
#     improvement_goal: Optional[str] = None


# class BacktestResult(BaseModel):
#     """백테스팅 결과"""
#     improvement_id: str
#     agent_id: str
#     strategy_params: Dict[str, Any]

#     # 성과 지표
#     total_return: float
#     sharpe_ratio: float
#     max_drawdown: float
#     win_rate: float
#     profit_factor: float

#     # Trinity Score (프론트엔드와 호환)
#     trinity_score: float

#     # 백테스팅 기간
#     start_date: datetime
#     end_date: datetime
#     duration_days: int

#     # 상세 결과
#     trades_count: int
#     avg_trade_return: float
#     best_trade_return: float
#     worst_trade_return: float

#     class Config:
#         json_encoders = {
#             datetime: lambda v: v.isoformat()
#         }


# class LLMFeedback(BaseModel):
#     """LLM 피드백"""
#     improvement_id: str
#     agent_id: str

#     # 분석 결과
#     analysis_summary: str
#     strengths: List[str]
#     weaknesses: List[str]
#     recommendations: List[str]

#     # 파라미터 개선 제안
#     parameter_suggestions: Dict[str, Dict[str, Any]]

#     # 예상 개선 효과
#     expected_improvement: Dict[str, float]  # Sharpe, Return 등
#     confidence_score: float

#     # 생성 정보
#     created_at: datetime
#     model_used: str = "claude-3-5-sonnet"


# class ImprovementProgress(BaseModel):
#     """개선 진행 상황"""
#     agent_id: str
#     current_step: ImprovementStatus
#     progress_percentage: float  # 0-100
#     estimated_completion: Optional[datetime] = None
#     current_task: str

#     # 최근 결과
#     latest_backtest: Optional[BacktestResult] = None
#     latest_feedback: Optional[LLMFeedback] = None

#     # 통계
#     total_improvements: int
#     successful_improvements: int
#     avg_improvement_score: float


# class AgentPerformanceMetrics(BaseModel):
#     """에이전트 성과 메트릭"""
#     agent_id: str
#     name: str

#     # 프론트엔드와 호환되는 메트릭
#     score: List[float]  # Trinity Score 시계열
#     return_val: List[float]  # 수익률 시계열
#     sharpe: List[float]  # 샤프지수 시계열
#     mdd: List[float]  # MDD 시계열
#     win: List[float]  # 승률 시계열

#     # 최신 값
#     current_score: float
#     current_return: float
#     current_sharpe: float
#     current_mdd: float
#     current_win_rate: float

#     # 트레이딩 통계
#     total_trades: int
#     winning_trades: int
#     losing_trades: int
#     avg_trade_duration: float  # 분 단위

#     class Config:
#         json_encoders = {
#             datetime: lambda v: v.isoformat()
#         }


# class StrategyLog(BaseModel):
#     """전략 로그"""
#     agent_id: str
#     timestamp: datetime

#     # 로그 내용
#     analysis: str  # 시장 분석
#     reason: str  # 전략 변경 이유

#     # 파라미터 변경
#     params_changes: List[Dict[str, Any]]

#     # 백테스팅 결과
#     backtest_result: Optional[BacktestResult] = None

#     class Config:
#         json_encoders = {
#             datetime: lambda v: v.isoformat()
#         }