"""
봇 데모 트레이딩 시뮬레이터
기존 BacktestEngine을 재사용하되, 실시간 틱 단위 실행을 위해 간소화
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class BotSimulator:
    """봇 시뮬레이션 엔진"""

    def __init__(
        self,
        bot_id: str,
        strategy_code: str,
        strategy_name: str,
        config: Dict[str, Any]
    ):
        self.bot_id = bot_id
        self.strategy_code = strategy_code
        self.strategy_name = strategy_name
        self.config = config

        # 설정 파싱
        self.symbol = config.get("symbol", "BTCUSDT")
        self.timeframe = config.get("timeframe", "1h")
        self.leverage = config.get("leverage", 1.0)
        self.initial_capital = config.get("initial_capital", 10000)
        self.max_position_pct = config.get("max_position_pct", 10)
        self.stop_loss_pct = config.get("stop_loss_pct")
        self.take_profit_pct = config.get("take_profit_pct")
        self.risk_profile = config.get("risk_profile", "moderate")
        self.reinvest = config.get("reinvest", False)

        # 시뮬레이션 상태
        self.current_price: Optional[float] = None
        self.current_position: Optional[str] = None  # "LONG", "SHORT", None
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None
        self.trades: list = []

        # 계좌 상태
        self.equity = self.initial_capital
        self.balance = self.initial_capital
        self.unrealized_pnl = 0
        self.realized_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # 지표 계산용
        self.peak_equity = self.initial_capital
        self.mdd_pct = 0
        self.returns_history = []

        # 전략 함수 컴파일
        self.strategy_func = self._compile_strategy()

    def _compile_strategy(self):
        """전략 코드 컴파일"""
        try:
            namespace = {}
            exec(self.strategy_code, namespace)

            # generate_signal 함수 또는 Strategy 클래스 찾기
            if "generate_signal" in namespace:
                return namespace["generate_signal"]
            elif "Strategy" in namespace:
                return namespace["Strategy"]()
            else:
                logger.error(f"Bot {self.bot_id}: No generate_signal function or Strategy class found")
                return None
        except Exception as e:
            logger.error(f"Bot {self.bot_id}: Failed to compile strategy: {e}")
            return None

    async def update_state(self, new_price: float, timestamp: datetime) -> Dict[str, Any]:
        """현재 틱 업데이트 및 신호 생성"""
        if not self.strategy_func:
            return self._get_state_snapshot()

        self.current_price = new_price

        try:
            # 신호 생성 (간단한 버전: 진입/청산 여부만)
            signal = self._generate_signal()

            # 신호 실행
            if signal == "LONG" and self.current_position is None:
                self._open_position("LONG", new_price, timestamp)
            elif signal == "SHORT" and self.current_position is None:
                self._open_position("SHORT", new_price, timestamp)
            elif signal == "EXIT" and self.current_position:
                self._close_position(new_price, timestamp)

            # 손절/수익실현 체크
            self._check_sl_tp(new_price, timestamp)

            # 미실현 손익 업데이트
            self._update_unrealized_pnl(new_price)

            # 자산 갱신 및 MDD 업데이트
            current_equity = self.balance + self.unrealized_pnl
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            
            drawdown = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0
            if drawdown > self.mdd_pct:
                self.mdd_pct = drawdown

        except Exception as e:
            logger.error(f"Bot {self.bot_id}: Error updating state: {e}")

        return self._get_state_snapshot()

    def _generate_signal(self) -> Optional[str]:
        """전략 함수를 호출해 신호 생성"""
        if not self.strategy_func or not self.current_price:
            return None

        try:
            # 간단한 데이터프레임 생성 (마지막 1개 행)
            import pandas as pd
            df = pd.DataFrame({
                'close': [self.current_price],
                'high': [self.current_price * 1.001],
                'low': [self.current_price * 0.999],
                'volume': [1000],
                'open': [self.current_price]
            })

            # 전략 호출 객체 확인
            target_func = self.strategy_func
            if not callable(target_func) and hasattr(target_func, "generate_signal"):
                target_func = target_func.generate_signal
            
            if callable(target_func):
                import inspect
                sig = inspect.signature(target_func)
                num_params = len(sig.parameters)
                
                if num_params >= 2:
                    result = target_func(df, df)
                else:
                    result = target_func(df)
                if isinstance(result, dict) and 'action' in result:
                    action = result['action'].upper()
                    if action == 'BUY' or action == 'LONG':
                        return 'LONG'
                    elif action == 'SELL' or action == 'SHORT':
                        return 'SHORT'
                    elif action == 'EXIT' or action == 'CLOSE':
                        return 'EXIT'
                elif isinstance(result, str):
                    if result.upper() in ['LONG', 'BUY']:
                        return 'LONG'
                    elif result.upper() in ['SHORT', 'SELL']:
                        return 'SHORT'
                    elif result.upper() in ['EXIT', 'CLOSE']:
                        return 'EXIT'
        except Exception as e:
            logger.error(f"Bot {self.bot_id}: Error generating signal: {e}")

        return None

    def _open_position(self, direction: str, price: float, timestamp: datetime):
        """포지션 오픈"""
        self.current_position = direction
        self.entry_price = price
        self.entry_time = timestamp
        logger.info(f"Bot {self.bot_id}: Opened {direction} at ${price} @ {timestamp}")

    def _close_position(self, close_price: float, timestamp: datetime):
        """포지션 클로즈"""
        if not self.entry_price or not self.current_position:
            return

        # 손익 계산
        if self.current_position == "LONG":
            pnl = (close_price - self.entry_price) * self.leverage
        else:  # SHORT
            pnl = (self.entry_price - close_price) * self.leverage

        position_size = (self.balance * self.max_position_pct / 100) * self.leverage
        realized_pnl = pnl * position_size / self.entry_price

        # 수익률 기록 (샤프 지수용)
        ret_pct = realized_pnl / self.balance if self.balance > 0 else 0
        self.returns_history.append(ret_pct)

        # 계좌 업데이트
        self.balance += realized_pnl
        self.realized_pnl += realized_pnl
        self.total_trades += 1
        if realized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # 거래 기록
        self.trades.append({
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "close_time": timestamp.isoformat(),
            "close_price": close_price,
            "direction": self.current_position,
            "pnl": realized_pnl,
            "pnl_pct": ret_pct * 100
        })

        logger.info(f"Bot {self.bot_id}: Closed {self.current_position} at ${close_price} @ {timestamp}, PnL=${realized_pnl:.2f}")

        # 상태 초기화
        self.current_position = None
        self.entry_price = None
        self.entry_time = None

    def _check_sl_tp(self, current_price: float, timestamp: datetime):
        """손절/수익실현 체크"""
        if not self.entry_price or not self.current_position:
            return

        # 손절 체크
        if self.stop_loss_pct:
            if self.current_position == "LONG":
                sl_price = self.entry_price * (1 - self.stop_loss_pct / 100)
                if current_price <= sl_price:
                    self._close_position(current_price, timestamp)
                    return
            else:  # SHORT
                sl_price = self.entry_price * (1 + self.stop_loss_pct / 100)
                if current_price >= sl_price:
                    self._close_position(current_price, timestamp)
                    return

        # 수익실현 체크
        if self.take_profit_pct:
            if self.current_position == "LONG":
                tp_price = self.entry_price * (1 + self.take_profit_pct / 100)
                if current_price >= tp_price:
                    self._close_position(current_price, timestamp)
            else:  # SHORT
                tp_price = self.entry_price * (1 - self.take_profit_pct / 100)
                if current_price <= tp_price:
                    self._close_position(current_price, timestamp)

    def _update_unrealized_pnl(self, current_price: float):
        """미실현 손익 업데이트"""
        if not self.entry_price or not self.current_position:
            self.unrealized_pnl = 0
            return

        if self.current_position == "LONG":
            self.unrealized_pnl = (current_price - self.entry_price) * self.leverage
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.leverage

    def _get_state_snapshot(self) -> Dict[str, Any]:
        """현재 상태 스냅샷"""
        import numpy as np
        self.equity = self.balance + self.unrealized_pnl

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        # 샤프지수 계산 (거래별 수익률 기준)
        sharpe = 0
        if len(self.returns_history) > 1:
            mean_ret = np.mean(self.returns_history)
            std_ret = np.std(self.returns_history)
            if std_ret > 0:
                # 연환산 없이 간단한 비율로 표시 (필요시 조정 가능)
                sharpe = mean_ret / std_ret * np.sqrt(252) # 임의의 연환산 factor

        return {
            "bot_id": self.bot_id,
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "position": self.current_position,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "equity": round(self.equity, 2),
            "balance": round(self.balance, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "total_return_pct": round((self.equity - self.initial_capital) / self.initial_capital * 100, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(win_rate, 2),
            "mdd_pct": round(self.mdd_pct * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "recent_trades": self.trades[-10:] if self.trades else []  # 최근 10거래
        }
