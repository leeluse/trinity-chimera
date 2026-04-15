"""
Rolling Backtest Engine - T-001 Implementation

매 틱/분마다 최근 N개월 데이터로 전략 성과 재계산
- 에이전트 단위 격리: 1개 실패해도 나머지 계속 진행
- MetricsBuffer에 결과 푸시
- WebSocket/SSE 실시간 스트리밍 지원

Author: backtest-engineer
Task: T-001
"""

import asyncio
import ast
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np

from .backtest_manager import BacktestManager
from .strategy_interface import StrategyInterface
from .strategy_loader import StrategyLoader
from ..agents.constants import AGENT_IDS

logger = logging.getLogger(__name__)


@dataclass
class RollingMetrics:
    """롤링 백테스트 결과 메트릭스"""
    agent_id: str
    timestamp: datetime
    is_score: float
    oos_score: float
    return_pct: float
    sharpe: float
    mdd: float
    profit_factor: float
    win_rate: float
    trinity_score_v2: float
    trades: int
    window_start: datetime
    window_end: datetime
    passed_gate: bool
    error: Optional[str] = None


@dataclass
class MetricsBuffer:
    """MetricsBuffer 인터페이스 - T-002와 연동됨"""
    """
    에이전트별 성과 지표를 버퍼링하고 트리거 조건 충족 시 LLMFeedbackClient 호출
    트리거: 30분 경과 OR 30틱 누적 중 먼저 도달한 조건
    """
    buffer: Dict[str, List[RollingMetrics]] = field(default_factory=dict)
    last_flush: Dict[str, datetime] = field(default_factory=dict)
    tick_count: Dict[str, int] = field(default_factory=dict)
    _trigger_callback: Optional[Callable] = None

    # 트리거 설정
    FLUSH_INTERVAL_MINUTES: int = 30
    TICK_THRESHOLD: int = 30

    def set_callback(self, callback: Callable):
        """트리거 콜백 설정 (T-003 연동용)"""
        self._trigger_callback = callback

    def __post_init__(self):
        for agent_id in AGENT_IDS:
            if agent_id not in self.buffer:
                self.buffer[agent_id] = []
                self.last_flush[agent_id] = datetime.now()
                self.tick_count[agent_id] = 0

    def push(self, agent_id: str, metrics: RollingMetrics) -> bool:
        """
        메트릭스를 버퍼에 추가
        Returns: True if buffer should be flushed, False otherwise
        """
        if agent_id not in self.buffer:
            self.buffer[agent_id] = []
            self.last_flush[agent_id] = datetime.now()
            self.tick_count[agent_id] = 0

        self.buffer[agent_id].append(metrics)
        self.tick_count[agent_id] += 1

        return self._should_flush(agent_id)

    def _should_flush(self, agent_id: str) -> bool:
        """트리거 조건 검사: 시간 OR 횟수 중 먼저 도달"""
        time_elapsed = datetime.now() - self.last_flush[agent_id]
        time_trigger = time_elapsed >= timedelta(minutes=self.FLUSH_INTERVAL_MINUTES)
        tick_trigger = self.tick_count[agent_id] >= self.TICK_THRESHOLD

        return time_trigger or tick_trigger

    def flush(self, agent_id: str) -> List[RollingMetrics]:
        """버퍼를 비우고 플러시 시간 업데이트"""
        flushed = self.buffer[agent_id].copy()
        self.buffer[agent_id] = []
        self.last_flush[agent_id] = datetime.now()
        self.tick_count[agent_id] = 0
        return flushed

    def mark_failed(self, agent_id: str, error: str, timestamp: datetime):
        """실패 정보 기록 - 분석용"""
        failed_metrics = RollingMetrics(
            agent_id=agent_id,
            timestamp=timestamp,
            is_score=0.0,
            oos_score=0.0,
            return_pct=0.0,
            sharpe=0.0,
            mdd=0.0,
            profit_factor=0.0,
            win_rate=0.0,
            trinity_score_v2=0.0,
            trades=0,
            window_start=timestamp,
            window_end=timestamp,
            passed_gate=False,
            error=error
        )
        self.buffer[agent_id].append(failed_metrics)

    def get_buffered_metrics(self, agent_id: str) -> List[RollingMetrics]:
        """현재 버퍼된 메트릭스 조회"""
        return self.buffer.get(agent_id, []).copy()


class RollingBacktestEngine:
    """
    실시간 롤링 윈도우 백테스트 엔진

    - 매 틱(분)마다 최근 N개월 데이터로 전략 성과 재계산
    - 에이전트별 독립적 실행 (격리)
    - MetricsBuffer와 연동하여 일괄 피드백 트리거
    - WebSocket/SSE를 통한 실시간 대시보드 스트리밍
    """

    def __init__(
        self,
        data_provider: Any,
        strategy_registry: Any,
        metrics_buffer: Optional[MetricsBuffer] = None,
        window_months: int = 3,
        is_days: int = 60,
        oos_days: int = 30,
        max_workers: int = 4
    ):
        """
        Args:
            data_provider: OHLCV 데이터 제공자
            strategy_registry: 전략 레지스트리 (Supabase 등)
            metrics_buffer: MetricsBuffer 인스턴스 (T-002 연동)
            window_months: 롤링 윈도우 크기 (월)
            is_days: In-Sample 기간 (일)
            oos_days: Out-of-Sample 기간 (일)
            max_workers: 병렬 실행 워커 수
        """
        self.data_provider = data_provider
        self.strategy_registry = strategy_registry
        self.metrics_buffer = metrics_buffer or MetricsBuffer()
        self.backtest_manager = BacktestManager()

        self.window_months = window_months
        self.is_days = is_days
        self.oos_days = oos_days

        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._subscribers: List[Callable[[RollingMetrics], None]] = []
        self._running = False
        self._tick_count = 0

    # ==================== Public API ====================

    def subscribe(self, callback: Callable[[RollingMetrics], None]):
        """대시보드 스트리밍을 위한 콜백 등록"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[RollingMetrics], None]):
        """콜백 해제"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def start(self, interval_seconds: int = 60):
        """
        실시간 롤링 백테스트 시작
        - interval_seconds: 틱 간격 (기본 60초 = 1분)
        """
        self._running = True
        logger.info(f"RollingBacktestEngine started (interval={interval_seconds}s)")

        while self._running:
            try:
                await self._run_tick()
                self._tick_count += 1
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Critical error in backtest loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    def stop(self):
        """엔진 중지"""
        self._running = False
        logger.info("RollingBacktestEngine stopped")

    async def run_single_tick(self) -> Dict[str, RollingMetrics]:
        """
        단일 틱 실행 (수동/테스트용)
        Returns: {agent_id: RollingMetrics}
        """
        return await self._run_tick()

    # ==================== Core Implementation ====================

    async def _run_tick(self) -> Dict[str, RollingMetrics]:
        """
        단일 틱 실행: 모든 에이전트에 대해 롤링 백테스트
        - 에이전트 단위 격리: 개별 실패 시에도 다른 에이전트 계속
        """
        results: Dict[str, RollingMetrics] = {}
        timestamp = datetime.now()

        logger.debug(f"Running tick #{self._tick_count} at {timestamp}")

        for agent_id in AGENT_IDS:
            try:
                metrics = await self._run_single_agent_backtest(agent_id, timestamp)
                results[agent_id] = metrics

                # MetricsBuffer 푸시 및 플러시 판단
                should_flush = self.metrics_buffer.push(agent_id, metrics)
                if should_flush:
                    await self._trigger_llm_feedback(agent_id)

            except Exception as e:
                logger.error(f"Agent {agent_id} backtest failed: {e}")
                # 실패 정보를 MetricsBuffer에 기록
                self.metrics_buffer.mark_failed(agent_id, str(e), timestamp)

        # 실시간 스트리밍
        await self._broadcast_results(results)

        return results

    async def _run_single_agent_backtest(
        self,
        agent_id: str,
        timestamp: datetime
    ) -> RollingMetrics:
        """
        단일 에이전트에 대한 롤링 백테스트 실행
        """
        # 1. 롤링 윈도우 데이터 가져오기
        data = await self._fetch_rolling_window()
        if data is None or data.empty:
            raise ValueError(f"No data available for backtest")

        # 2. 현재 활성 전략 가져오기
        strategy = await self._get_active_strategy(agent_id)
        if strategy is None:
            raise ValueError(f"No active strategy for agent {agent_id}")

        # 3. IS/OOS 백테스트 실행
        is_data, oos_data = self.backtest_manager.split_data(
            data, train_days=self.is_days, val_days=self.oos_days
        )

        is_metrics = self.backtest_manager.run_backtest(strategy, is_data)
        oos_metrics = self.backtest_manager.run_backtest(strategy, oos_data)

        # 4. Profit Factor, Win Rate 계산 (T-005)
        pf_wr = self._calculate_pf_wr(strategy, data)

        # 5. Trinity Score v2 계산 (T-006)
        trinity_v2 = self._calculate_trinity_score_v2(
            oos_metrics['return'],
            oos_metrics['sharpe'],
            oos_metrics['mdd'],
            pf_wr['profit_factor'],
            pf_wr['win_rate']
        )

        # 6. Validation Gate 확인
        passed = self.backtest_manager.validation_gate(
            is_metrics['trinity_score'],
            oos_metrics['trinity_score'],
            threshold=0.7
        )

        return RollingMetrics(
            agent_id=agent_id,
            timestamp=timestamp,
            is_score=is_metrics['trinity_score'],
            oos_score=oos_metrics['trinity_score'],
            return_pct=oos_metrics['return'],
            sharpe=oos_metrics['sharpe'],
            mdd=oos_metrics['mdd'],
            profit_factor=pf_wr['profit_factor'],
            win_rate=pf_wr['win_rate'],
            trinity_score_v2=trinity_v2,
            trades=oos_metrics['trades'],
            window_start=data.index[0],
            window_end=data.index[-1],
            passed_gate=passed
        )

    async def _fetch_rolling_window(self) -> Optional[pd.DataFrame]:
        """
        최근 window_months 데이터 가져오기

        데이터 소스 우선순위:
        1. data_provider 인터페이스 (설정된 경우)
        2. CSV 파일 로드 (기본값: mock_ohlcv_data.csv )
        3. 합성 데이터 생성 (폴백)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.window_months * 30)

        # 1. data_provider 인터페이스 확인
        if self.data_provider is not None:
            if hasattr(self.data_provider, 'get_data_range'):
                return await self.data_provider.get_data_range(start_date, end_date)
            elif hasattr(self.data_provider, 'get_recent_data'):
                return await self.data_provider.get_recent_data(
                    symbol="BTC/USDT",
                    timeframe="1h",
                    lookback_days=self.window_months * 30
                )

        # 2. CSV 파일 로드 시도
        try:
            import os
            csv_path = os.getenv('DATA_CSV_PATH', 'data/mock_ohlcv_data.csv')
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                # 최근 윈도우 데이터만 필터링
                return df[(df.index >= start_date) & (df.index <= end_date)]
        except Exception as e:
            logger.warning(f"CSV load failed: {e}")

        # 3. 합성 데이터 생성 (폴백)
        logger.warning("Generating synthetic data as fallback")
        return self._generate_synthetic_data(start_date, end_date)

    def _generate_synthetic_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """테스트/폴백용 합성 OHLCV 데이터 생성"""
        periods = int((end_date - start_date).total_seconds() / 3600)  # Hourly data
        if periods < 24:
            periods = 24

        np.random.seed(42)
        price_changes = np.random.normal(0.0001, 0.01, periods)
        prices = 50000 * np.exp(np.cumsum(price_changes))

        dates = pd.date_range(start=start_date, periods=periods, freq='h')

        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.001, periods)),
            'high': prices * (1 + abs(np.random.normal(0, 0.002, periods))),
            'low': prices * (1 - abs(np.random.normal(0, 0.002, periods))),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, periods)
        }, index=dates)

        return df

    async def _get_active_strategy(self, agent_id: str) -> Optional[StrategyInterface]:
        """
        StrategyRegistry에서 현재 활성 전략 가져오기
        """
        if self.strategy_registry is None:
            return None

        strategy_data = await self.strategy_registry.get_active_strategy(agent_id)
        if strategy_data is None:
            return None

        # strategy_data가 문자열(코드)인지 dict인지 확인
        if isinstance(strategy_data, str):
            strategy_code = strategy_data
            class_name = self._extract_class_name(strategy_code)
        elif isinstance(strategy_data, dict):
            strategy_code = strategy_data.get('code', '')
            class_name = strategy_data.get('class_name') or self._extract_class_name(strategy_code)
        else:
            logger.error(f"Unknown strategy_data type: {type(strategy_data)}")
            return None

        if not strategy_code or not class_name:
            logger.error(f"Missing strategy_code or class_name for {agent_id}")
            return None

        # StrategyLoader를 통해 StrategyInterface 인스턴스 생성
        try:
            strategy = StrategyLoader.load_strategy(strategy_code, class_name)
            return strategy
        except Exception as e:
            logger.error(f"Failed to load strategy for {agent_id}: {e}")
            return None

    def _extract_class_name(self, code: str) -> Optional[str]:
        """코드에서 클래스 이름 추출"""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    return node.name
        except Exception as e:
            logger.error(f"Failed to extract class name: {e}")
        return None

    async def _trigger_llm_feedback(self, agent_id: str):
        """
        MetricsBuffer 플러시 시 LLMFeedbackClient 트리거 (T-003 연동)
        """
        buffered = self.metrics_buffer.flush(agent_id)
        logger.info(f"Triggering LLM feedback for {agent_id} ({len(buffered)} metrics)")

        # T-003 (llm-feedback-engineer)와 연동됨
        # evolution_package = self._assemble_evolution_package(agent_id, buffered)
        # await llm_feedback_client.trigger(evolution_package)

    # ==================== Metrics Calculations ====================

    def _calculate_pf_wr(
        self,
        strategy: StrategyInterface,
        data: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Profit Factor 및 Win Rate 계산 (T-005)
        """
        prices = data['close'].values
        signals = []
        trades_pnl = []
        position = 0
        entry_price = 0

        for i in range(len(data)):
            signal = strategy.generate_signal(data.iloc[:i+1])
            signals.append(signal)

            if signal == 1 and position == 0:
                entry_price = prices[i]
                position = 1
            elif signal == -1 and position == 1:
                exit_price = prices[i]
                pnl = (exit_price - entry_price) / entry_price
                trades_pnl.append(pnl)
                position = 0

        # 미체결 포지션 정리
        if position == 1:
            pnl = (prices[-1] - entry_price) / entry_price
            trades_pnl.append(pnl)

        if not trades_pnl:
            return {'profit_factor': 0.0, 'win_rate': 0.0}

        winning_trades = [p for p in trades_pnl if p > 0]
        losing_trades = [p for p in trades_pnl if p < 0]

        # Profit Factor
        if losing_trades:
            profit_factor = sum(winning_trades) / abs(sum(losing_trades))
        else:
            profit_factor = float('inf') if winning_trades else 0.0

        # Win Rate
        win_rate = len(winning_trades) / len(trades_pnl)

        return {
            'profit_factor': round(profit_factor, 4) if profit_factor != float('inf') else 0.0,
            'win_rate': round(win_rate, 4)
        }

    def _calculate_trinity_score_v2(
        self,
        return_val: float,
        sharpe: float,
        mdd: float,
        profit_factor: float,
        win_rate: float
    ) -> float:
        """
        Trinity Score v2 계산 (T-006)
        Trinity Score v2 = Return × 0.30 + Sharpe × 25 × 0.25 + (1+MDD)×100 × 0.20 + PF × 20 × 0.15 + WinRate×100 × 0.10
        """
        score = (
            return_val * 0.30
            + sharpe * 25 * 0.25
            + (1 + mdd) * 100 * 0.20
            + profit_factor * 20 * 0.15
            + win_rate * 100 * 0.10
        )
        return round(score, 4)

    # ==================== Broadcasting ====================

    async def _broadcast_results(self, results: Dict[str, RollingMetrics]):
        """
        WebSocket/SSE를 통한 실시간 스트리밍
        """
        if not self._subscribers:
            return

        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(results)
                else:
                    callback(results)
            except Exception as e:
                logger.error(f"Broadcast callback failed: {e}")

    # ==================== Health & Metrics ====================

    def get_status(self) -> Dict[str, Any]:
        """엔진 상태 조회"""
        return {
            'running': self._running,
            'tick_count': self._tick_count,
            'window_months': self.window_months,
            'is_days': self.is_days,
            'oos_days': self.oos_days,
            'buffer_status': {
                agent_id: {
                    'tick_count': self.metrics_buffer.tick_count[agent_id],
                    'buffered_count': len(self.metrics_buffer.buffer[agent_id]),
                    'last_flush': self.metrics_buffer.last_flush[agent_id]
                }
                for agent_id in AGENT_IDS
            }
        }
