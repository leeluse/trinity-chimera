"""
Adaptive_Fib_786_886_Retracement Strategy
==========================================
Hypothesis: Deep retracements to 0.786-0.886 Fibonacci levels in established trends,
confirmed by adaptive volatility thresholds, produce high-probability mean reversion
entries with favorable risk/reward.

Requirements:
    pip install ccxt pandas numpy pandas-ta
"""

import ccxt
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timezone
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────
# 1. CONFIG
# ─────────────────────────────────────────
CONFIG = {
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "fetch_limit": 2000,          # OHLCV candles to download
    "train_ratio": 0.7,           # 70% train / 30% test split

    # Tier 1 – Trend
    "ema_fast": 50,
    "ema_slow": 200,

    # Tier 2 – Fibonacci
    "fib_lookback": 50,
    "fib_levels": [0.786, 0.886],
    "fib_tolerance": 0.005,       # ±0.5 % zone around exact level

    # Tier 3 – RSI
    "rsi_period": 14,

    # Regime Filter
    "adx_period": 14,
    "atr_period": 14,
    "adx_min": 20,
    "atr_sma_period": 20,
    "atr_low_mult": 0.6,          # no-trade when atr < atr_ma * 0.6
    "chop_zone_pct": 0.02,        # no-trade within 2% of EMA200

    # Adaptive Thresholds (computed on train set)
    "rsi_long_quantile": 0.20,
    "rsi_short_quantile": 0.80,
    "atr_quantile": 0.40,
    "atr_rolling_window": 50,

    # Risk / Position sizing
    "initial_capital": 10_000.0,
    "risk_per_trade_pct": 0.01,   # 1 % of capital per trade
}


# ─────────────────────────────────────────
# 2. DATA FETCHING
# ─────────────────────────────────────────
def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Download OHLCV candles from Binance via ccxt."""
    exchange = ccxt.binance({"enableRateLimit": True})
    print(f"[Data] Fetching {limit} × {timeframe} candles for {symbol} ...")
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("datetime", inplace=True)
    df.drop(columns=["timestamp"], inplace=True)
    print(f"[Data] {len(df)} rows | {df.index[0]} → {df.index[-1]}")
    return df


# ─────────────────────────────────────────
# 3. INDICATOR CALCULATION
# ─────────────────────────────────────────
def compute_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Attach all required indicators to the dataframe in-place."""
    df = df.copy()

    # EMA trend
    df["ema_fast"] = ta.ema(df["close"], length=cfg["ema_fast"])
    df["ema_slow"] = ta.ema(df["close"], length=cfg["ema_slow"])

    # RSI
    df["rsi"] = ta.rsi(df["close"], length=cfg["rsi_period"])

    # ATR
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=cfg["atr_period"])
    df["atr_ma20"] = df["atr"].rolling(cfg["atr_sma_period"]).mean()
    df["atr_ma50"] = df["atr"].rolling(cfg["atr_rolling_window"]).mean()

    # ADX
    adx_result = ta.adx(df["high"], df["low"], df["close"], length=cfg["adx_period"])
    df["adx"] = adx_result[f"ADX_{cfg['adx_period']}"]

    # Rolling Fibonacci swing highs / lows
    lb = cfg["fib_lookback"]
    df["swing_high"] = df["high"].rolling(lb).max()
    df["swing_low"]  = df["low"].rolling(lb).min()
    df["fib_range"]  = df["swing_high"] - df["swing_low"]

    # Long (price retraces down into zone)
    df["fib_786_long"] = df["swing_high"] - df["fib_range"] * 0.786
    df["fib_886_long"] = df["swing_high"] - df["fib_range"] * 0.886

    # Short (price retraces up into zone)
    df["fib_786_short"] = df["swing_low"] + df["fib_range"] * 0.786
    df["fib_886_short"] = df["swing_low"] + df["fib_range"] * 0.886

    # Mid-level for TP
    df["fib_500"] = df["swing_low"] + df["fib_range"] * 0.50

    df.dropna(inplace=True)
    return df


# ─────────────────────────────────────────
# 4. ADAPTIVE THRESHOLDS  (train-set only)
# ─────────────────────────────────────────
def compute_adaptive_thresholds(train_df: pd.DataFrame, cfg: dict) -> dict:
    """Derive quantile-based thresholds from the training slice."""
    rsi_thresh_long  = train_df["rsi"].quantile(cfg["rsi_long_quantile"])
    rsi_thresh_short = train_df["rsi"].quantile(cfg["rsi_short_quantile"])
    adaptive_atr_threshold = (
        train_df["atr_ma50"]
        .rolling(cfg["atr_rolling_window"])
        .mean()
        .quantile(cfg["atr_quantile"])
    )
    print(f"[Thresholds] RSI long < {rsi_thresh_long:.2f} | RSI short > {rsi_thresh_short:.2f}")
    print(f"[Thresholds] Adaptive ATR min = {adaptive_atr_threshold:.6f}")
    return {
        "rsi_thresh_long":      rsi_thresh_long,
        "rsi_thresh_short":     rsi_thresh_short,
        "adaptive_atr_threshold": adaptive_atr_threshold,
    }


# ─────────────────────────────────────────
# 5. SIGNAL GENERATION
# ─────────────────────────────────────────
def generate_signals(df: pd.DataFrame, thresholds: dict, cfg: dict) -> pd.DataFrame:
    """Return df with signal column: 1=long, -1=short, 0=flat."""
    df = df.copy()
    rsi_tl = thresholds["rsi_thresh_long"]
    rsi_ts = thresholds["rsi_thresh_short"]
    atr_thresh = thresholds["adaptive_atr_threshold"]

    tol = cfg["fib_tolerance"]

    # ── Regime filters ────────────────────────────────────────────────────────
    regime_ok = (
        (df["atr"] > atr_thresh) &          # enough volatility
        (df["atr"] > df["atr_ma20"] * cfg["atr_low_mult"]) &  # not vol collapse
        (df["adx"] > cfg["adx_min"])         # trend strength
    )
    not_chop = (df["close"] - df["ema_slow"]).abs() / df["ema_slow"] > cfg["chop_zone_pct"]

    # ── Tier 1: trend direction ───────────────────────────────────────────────
    trend_long  = df["close"] > df["ema_slow"]
    trend_short = df["close"] < df["ema_slow"]

    # ── Tier 2: price inside fib zone (with tolerance) ────────────────────────
    in_fib_long = (
        (df["close"] <= df["fib_786_long"] * (1 + tol)) &
        (df["close"] >= df["fib_886_long"] * (1 - tol))
    )
    in_fib_short = (
        (df["close"] >= df["fib_786_short"] * (1 - tol)) &
        (df["close"] <= df["fib_886_short"] * (1 + tol))
    )

    # ── Tier 3: RSI exhaustion filter ─────────────────────────────────────────
    rsi_long_ok  = df["rsi"] < rsi_tl
    rsi_short_ok = df["rsi"] > rsi_ts

    # ── Combined signals ──────────────────────────────────────────────────────
    long_signal  = trend_long  & in_fib_long  & rsi_long_ok  & regime_ok & not_chop
    short_signal = trend_short & in_fib_short & rsi_short_ok & regime_ok & not_chop

    df["signal"] = 0
    df.loc[long_signal,  "signal"] = 1
    df.loc[short_signal, "signal"] = -1
    return df


# ─────────────────────────────────────────
# 6. BACKTESTER
# ─────────────────────────────────────────
def backtest(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Event-driven backtest with:
      - Stop loss at swing_low * 0.995 (long) / swing_high * 1.005 (short)
      - Take profit at fib_0.5 level
    Returns a trades DataFrame.
    """
    capital = cfg["initial_capital"]
    risk_pct = cfg["risk_per_trade_pct"]

    trades = []
    position = None   # None | {"side", "entry_price", "sl", "tp", "qty", "entry_time"}

    for ts, row in df.iterrows():
        # ── Check open position for exit ──────────────────────────────────────
        if position is not None:
            side = position["side"]
            sl   = position["sl"]
            tp   = position["tp"]
            hit_sl = (side == "long"  and row["low"]  <= sl) or \
                     (side == "short" and row["high"] >= sl)
            hit_tp = (side == "long"  and row["high"] >= tp) or \
                     (side == "short" and row["low"]  <= tp)

            if hit_sl or hit_tp:
                exit_price = sl if hit_sl else tp
                pnl_pct = (exit_price - position["entry_price"]) / position["entry_price"]
                if side == "short":
                    pnl_pct = -pnl_pct
                pnl_usd = pnl_pct * position["qty"] * position["entry_price"]
                capital += pnl_usd
                trades.append({
                    "entry_time":  position["entry_time"],
                    "exit_time":   ts,
                    "side":        side,
                    "entry_price": position["entry_price"],
                    "exit_price":  exit_price,
                    "sl":          sl,
                    "tp":          tp,
                    "pnl_usd":     round(pnl_usd, 4),
                    "pnl_pct":     round(pnl_pct * 100, 4),
                    "result":      "TP" if hit_tp else "SL",
                    "capital":     round(capital, 2),
                })
                position = None

        # ── Check for new entry (only if flat) ───────────────────────────────
        if position is None and row["signal"] != 0:
            side = "long" if row["signal"] == 1 else "short"
            entry = row["close"]

            if side == "long":
                sl = row["swing_low"] * 0.995
                tp = row["fib_500"]
            else:
                sl = row["swing_high"] * 1.005
                tp = row["fib_500"]

            risk_per_unit = abs(entry - sl)
            if risk_per_unit <= 0:
                continue

            risk_usd = capital * risk_pct
            qty = risk_usd / risk_per_unit          # units (e.g. BTC)

            position = {
                "side":        side,
                "entry_price": entry,
                "sl":          sl,
                "tp":          tp,
                "qty":         qty,
                "entry_time":  ts,
            }

    trades_df = pd.DataFrame(trades)
    return trades_df


# ─────────────────────────────────────────
# 7. PERFORMANCE METRICS
# ─────────────────────────────────────────
def calc_metrics(trades_df: pd.DataFrame, initial_capital: float) -> dict:
    if trades_df.empty:
        return {"error": "No trades generated"}

    total   = len(trades_df)
    wins    = (trades_df["pnl_usd"] > 0).sum()
    losses  = total - wins
    win_rate = wins / total * 100

    gross_profit = trades_df[trades_df["pnl_usd"] > 0]["pnl_usd"].sum()
    gross_loss   = abs(trades_df[trades_df["pnl_usd"] <= 0]["pnl_usd"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    net_pnl = trades_df["pnl_usd"].sum()
    final_capital = trades_df["capital"].iloc[-1]
    total_return_pct = (final_capital - initial_capital) / initial_capital * 100

    # Sharpe (annualised, daily returns from hourly trades)
    trades_df = trades_df.copy()
    trades_df["exit_date"] = pd.to_datetime(trades_df["exit_time"]).dt.date
    daily_pnl = trades_df.groupby("exit_date")["pnl_usd"].sum()
    sharpe = float("nan")
    if len(daily_pnl) > 1 and daily_pnl.std() != 0:
        sharpe = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252)

    # Max Drawdown
    cumulative = trades_df["capital"]
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_dd = drawdown.min() * 100

    return {
        "total_trades":   total,
        "wins":           int(wins),
        "losses":         int(losses),
        "win_rate":       round(win_rate, 2),
        "profit_factor":  round(profit_factor, 3),
        "net_pnl_usd":   round(net_pnl, 2),
        "total_return_%": round(total_return_pct, 2),
        "max_drawdown_%": round(max_dd, 2),
        "sharpe_ratio":   round(sharpe, 3),
        "initial_capital": initial_capital,
        "final_capital":   round(final_capital, 2),
    }


# ─────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────
def main():
    cfg = CONFIG

    # ── Fetch & prepare data ──────────────────────────────────────────────────
    raw_df = fetch_ohlcv(cfg["symbol"], cfg["timeframe"], cfg["fetch_limit"])
    df     = compute_indicators(raw_df, cfg)

    # ── Train / Test split ────────────────────────────────────────────────────
    split_idx  = int(len(df) * cfg["train_ratio"])
    train_df   = df.iloc[:split_idx]
    test_df    = df.iloc[split_idx:]

    print(f"\n[Split] Train: {len(train_df)} rows | Test: {len(test_df)} rows")
    print(f"        Train: {train_df.index[0]} → {train_df.index[-1]}")
    print(f"        Test:  {test_df.index[0]}  → {test_df.index[-1]}\n")

    # ── Compute adaptive thresholds from TRAIN only ───────────────────────────
    thresholds = compute_adaptive_thresholds(train_df, cfg)

    # ── Generate signals & backtest on TEST set ───────────────────────────────
    test_signals = generate_signals(test_df, thresholds, cfg)
    trades       = backtest(test_signals, cfg)

    # ── Print results ─────────────────────────────────────────────────────────
    metrics = calc_metrics(trades, cfg["initial_capital"])

    print("=" * 50)
    print("  BACKTEST RESULTS  (Out-of-Sample)")
    print("=" * 50)
    for k, v in metrics.items():
        print(f"  {k:<22} {v}")
    print("=" * 50)

    print("\n[Trades Preview]")
    if not trades.empty:
        print(trades[["entry_time", "exit_time", "side", "entry_price",
                       "exit_price", "pnl_usd", "result", "capital"]].tail(20).to_string())

    # ── Optional: save trades to CSV ─────────────────────────────────────────
    if not trades.empty:
        out = "adaptive_fib_786_886_trades.csv"
        trades.to_csv(out, index=False)
        print(f"\n[Saved] Trades → {out}")

    return trades, metrics


if __name__ == "__main__":
    trades_df, perf = main()
