import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
from ai_trading.core.strategy_interface import StrategyInterface

class BacktestManager:
    """
    Manages the backtesting process, including data splitting (IS/OOS),
    cost application, and robustness validation.
    """

    def __init__(self, fee: float = 0.0005, slippage_min: float = 0.0001, slippage_max: float = 0.0003):
        self.fee = fee
        self.slippage_min = slippage_min
        self.slippage_max = slippage_max

    def split_data(self, data: pd.DataFrame, train_days: int = 30, val_days: int = 30) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Splits the data into In-Sample (Training) and Out-of-Sample (Validation) sets.
        Works with both hourly and daily OHLCV data.

        Args:
            data: OHLCV DataFrame with datetime index
            train_days: Number of days for training (IS) period
            val_days: Number of days for validation (OOS) period

        Returns:
            Tuple of (train_set, val_set) DataFrames
        """
        # Calculate total window size needed
        total_window = train_days + val_days

        # Detect data frequency (hourly vs daily)
        # Check if we have more than one row per day on average
        if len(data) > 1:
            avg_hours_between_rows = (data.index[-1] - data.index[0]).total_seconds() / 3600 / (len(data) - 1)
            is_hourly = avg_hours_between_rows < 2  # If average is less than 2 hours, treat as hourly
        else:
            is_hourly = False

        rows_per_day = 24 if is_hourly else 1

        # Calculate required rows
        required_rows = total_window * rows_per_day

        # Use the last 'total_window' days of data
        recent_data = data.tail(required_rows)

        # If we don't have enough data, take what we can
        if len(recent_data) < required_rows:
            # Fallback: split the available data 50/50
            mid = len(data) // 2
            return data.iloc[:mid], data.iloc[mid:]

        split_point = train_days * rows_per_day
        train_set = recent_data.iloc[:split_point]
        val_set = recent_data.iloc[split_point:split_point + (val_days * rows_per_day)]

        return train_set, val_set

    def calculate_trinity_score(self, return_val: float, sharpe: float, mdd: float) -> float:
        """
        Trinity Score = Return * 0.40 + Sharpe * 25 * 0.35 + (1 + MDD) * 100 * 0.25
        """
        score = (return_val * 0.40) + (sharpe * 25 * 0.35) + ((1 + mdd) * 100 * 0.25)
        return round(score, 4)

    def validation_gate(self, is_score: float, oos_score: float, threshold: float = 0.7) -> bool:
        """
        A strategy is successful if OOS score is > threshold% of IS score.
        Returns True if passed, False if rejected (overfitting detected).
        """
        if is_score <= 0:
            return bool(oos_score > 0)
        return bool((oos_score / is_score) >= threshold)

    def apply_trading_costs(self, execution_price: float, side: int) -> float:
        """
        Applies a fixed fee and random slippage to the execution price.
        side: 1 for Buy, -1 for Sell
        """
        slippage = np.random.uniform(self.slippage_min, self.slippage_max)
        total_cost_pct = self.fee + slippage

        if side == 1: # Buy: Price increases
            return execution_price * (1 + total_cost_pct)
        elif side == -1: # Sell: Price decreases
            return execution_price * (1 - total_cost_pct)
        return execution_price

    def run_backtest(self, strategy: StrategyInterface, data: pd.DataFrame) -> Dict[str, Any]:
        """
        A simplified backtest loop to integrate costs and returns.
        This would typically be more complex.
        """
        balance = 10000.0
        position = 0
        trades = 0

        prices = data['close'].values
        signals = []
        equity_curve = [balance]

        # In a real scenario, generate_signal would be called in a loop or vectorized
        # For this manager, we simulate the loop to apply costs per trade
        for i in range(len(data)):
            # Simplified: pass slice of data to strategy
            signal = strategy.generate_signal(data.iloc[:i+1])
            signals.append(signal)

            # Trade execution logic
            if signal == 1 and position == 0: # Buy
                cost_price = self.apply_trading_costs(prices[i], 1)
                position = balance / cost_price
                balance = 0
                trades += 1
            elif signal == -1 and position > 0: # Sell
                cost_price = self.apply_trading_costs(prices[i], -1)
                balance = position * cost_price
                position = 0
                trades += 1

            # Track equity curve for MDD calculation
            current_value = balance if position == 0 else position * prices[i]
            equity_curve.append(current_value)

        final_value = balance if position == 0 else position * prices[-1]
        total_return = (final_value - 10000.0) / 10000.0

        # Calculate MDD from equity curve
        mdd = self._calculate_mdd(equity_curve)

        # Calculate Sharpe ratio (simplified)
        sharpe = self._calculate_sharpe(equity_curve)

        return {
            "return": total_return,
            "sharpe": sharpe,
            "mdd": mdd,
            "trinity_score": self.calculate_trinity_score(total_return, sharpe, mdd),
            "trades": trades
        }

    def _calculate_mdd(self, equity_curve: list) -> float:
        """Calculate Maximum Drawdown from equity curve."""
        if len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return -max_dd  # Return negative value

    def _calculate_sharpe(self, equity_curve: list) -> float:
        """Calculate simplified Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] > 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)

        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe (simplified)
        return (mean_return / std_return) * np.sqrt(252)

    def validate_strategy(self, strategy: StrategyInterface, data: pd.DataFrame,
                          train_days: int = 30, val_days: int = 30,
                          threshold: float = 0.7) -> Dict[str, Any]:
        """
        Complete IS/OOS validation workflow for strategy validation.

        Steps:
        1. Split data into IS (train) and OOS (validation) sets
        2. Run backtest on IS data
        3. Run backtest on OOS data
        4. Calculate Trinity Score for both periods
        5. Apply validation gate (OOS score >= threshold * IS score)

        Args:
            strategy: The strategy to validate
            data: OHLCV DataFrame
            train_days: Number of days for IS period
            val_days: Number of days for OOS period
            threshold: Minimum ratio of OOS/IS score to pass (default 0.7)

        Returns:
            Dict with IS metrics, OOS metrics, validation result, and scores
        """
        # Step 1: Split data
        is_data, oos_data = self.split_data(data, train_days, val_days)

        # Step 2: Run backtest on IS data
        is_metrics = self.run_backtest(strategy, is_data)

        # Step 3: Run backtest on OOS data
        oos_metrics = self.run_backtest(strategy, oos_data)

        # Step 4: Get scores
        is_score = is_metrics['trinity_score']
        oos_score = oos_metrics['trinity_score']

        # Step 5: Apply validation gate
        passed = self.validation_gate(is_score, oos_score, threshold)

        # Calculate ratio
        ratio = oos_score / is_score if is_score > 0 else float('inf') if oos_score > 0 else 0.0

        return {
            "is_metrics": is_metrics,
            "oos_metrics": oos_metrics,
            "is_score": is_score,
            "oos_score": oos_score,
            "ratio": round(ratio, 4),
            "passed": passed,
            "threshold": threshold
        }
