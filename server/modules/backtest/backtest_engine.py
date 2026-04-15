"""
신뢰도 높은 백테스트 엔진
--------------------------
LLM이 생성한 전략을 다음 방법론으로 검증:
  1. Train / Validation / Test 엄격 분리
  2. Walk-Forward Optimization (WFO)
  3. Monte Carlo 시뮬레이션 (경로 불확실성)
  4. 여러 시장 구간 동시 테스트 (불/베어/횡보)
  5. 현실적 비용 모델 (수수료 + 슬리피지 + 펀딩비)

Usage:
    engine = BacktestEngine(df, fee_rate=0.001, slippage=0.0005)
    result = engine.run_full_validation(strategy_func)
    print(result.summary())
"""

import warnings
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────
# 결과 컨테이너
# ─────────────────────────────────────────────

@dataclass
class PeriodResult:
    name: str
    start: str
    end: str
    total_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    profit_factor: float
    calmar: float


@dataclass
class ValidationResult:
    strategy_name: str
    period_results: list[PeriodResult] = field(default_factory=list)
    wfo_results: list[PeriodResult] = field(default_factory=list)
    monte_carlo: dict = field(default_factory=dict)
    regime_results: dict = field(default_factory=dict)  # bull/bear/sideways별
    is_robust: bool = False
    verdict: str = ""

    def summary(self) -> str:
        lines = [
            f"\n{'='*55}",
            f"  전략: {self.strategy_name}",
            f"{'='*55}",
            f"  최종 판정: {'✅ ROBUST' if self.is_robust else '❌ NOT ROBUST'}",
            f"  {self.verdict}",
            f"\n  [ Walk-Forward 구간별 결과 ]",
        ]
        for r in self.wfo_results:
            lines.append(
                f"  {r.name:15s} | 수익:{r.total_return:+.1%} "
                f"Sharpe:{r.sharpe:.2f} MDD:{r.max_drawdown:.1%} "
                f"거래:{r.n_trades}"
            )
        if self.monte_carlo:
            mc = self.monte_carlo
            lines += [
                f"\n  [ Monte Carlo ({mc['n_sims']}회 시뮬레이션) ]",
                f"  수익률 중앙값: {mc['median_return']:+.1%}",
                f"  5% VaR:       {mc['var_5pct']:+.1%}",
                f"  파산 확률:    {mc['ruin_prob']:.1%}",
            ]
        if self.regime_results:
            lines.append(f"\n  [ 시장 상황별 성과 ]")
            for regime, r in self.regime_results.items():
                lines.append(
                    f"  {regime:10s} | 수익:{r['mean_return']:+.1%} "
                    f"Sharpe:{r['mean_sharpe']:.2f}"
                )
        lines.append('='*55)
        return "\n".join(lines)


# ─────────────────────────────────────────────
# 핵심 메트릭 계산
# ─────────────────────────────────────────────

def compute_metrics(returns: pd.Series, n_trades: int, name: str,
                    start: str, end: str, freq: int = 24) -> PeriodResult:
    """일간/시간봉 수익률 시리즈 → 성과 지표 계산"""
    if len(returns) < 5 or returns.std() == 0:
        return PeriodResult(name, start, end, 0, 0, 0, 0, 0, n_trades, 0, 0)

    ann = freq * 365  # 연간 봉 수 (1h = 8760)
    total_ret = (1 + returns).prod() - 1
    mu = returns.mean()
    sigma = returns.std() + 1e-10

    sharpe = (mu / sigma) * np.sqrt(ann)

    downside = returns[returns < 0].std() + 1e-10
    sortino = (mu / downside) * np.sqrt(ann)

    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    max_dd = dd.min()

    calmar = (total_ret / abs(max_dd)) if max_dd != 0 else 0

    pos = returns[returns > 0]
    neg = returns[returns < 0]
    win_rate = len(pos) / len(returns) if len(returns) > 0 else 0
    profit_factor = (pos.sum() / abs(neg.sum())) if neg.sum() != 0 else 0

    return PeriodResult(
        name=name, start=start, end=end,
        total_return=total_ret, sharpe=sharpe, sortino=sortino,
        max_drawdown=max_dd, win_rate=win_rate, n_trades=n_trades,
        profit_factor=profit_factor, calmar=calmar
    )


# ─────────────────────────────────────────────
# 현실적 거래 시뮬레이터
# ─────────────────────────────────────────────

class RealisticSimulator:
    """
    수수료 + 슬리피지 + 포지션 사이징을 반영한
    단순하고 빠른 벡터화 시뮬레이터.
    LLM 전략은 signal Series (1=롱, -1=숏, 0=플랫)를 반환한다고 가정.
    """

    def __init__(
        self,
        fee_rate: float = 0.001,      # 편도 수수료 (0.1%)
        slippage: float = 0.0005,     # 슬리피지 (0.05%)
        funding_rate: float = 0.0001, # 펀딩비 (8h당 0.01%)
        max_position: float = 1.0,    # 최대 포지션 비율
        use_kelly: bool = True,       # Kelly 포지션 사이징
    ):
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.funding_rate = funding_rate
        self.max_position = max_position
        self.use_kelly = use_kelly

    def run(self, df: pd.DataFrame, signal: pd.Series) -> tuple[pd.Series, int]:
        """
        signal: +1 / 0 / -1 시리즈 (df.index와 같은 인덱스)
        반환: (bar별 수익률 Series, 거래 횟수)
        """
        close = df["close"].reindex(signal.index)
        price_ret = close.pct_change().fillna(0)

        # 포지션 크기 (Kelly 적용 시 신호 강도에 따라 조정)
        position = signal.shift(1).fillna(0)  # 1봉 지연 — 다음 봉 시가 진입 가정
        position = position.clip(-self.max_position, self.max_position)

        # 거래 비용 (포지션 변화가 있을 때만)
        pos_change = position.diff().abs().fillna(0)
        total_cost = pos_change * (self.fee_rate + self.slippage)

        # 펀딩비 (포지션 보유 중 매 봉마다)
        funding_cost = position.abs() * self.funding_rate / 3  # 1h 기준 (8h/3)

        # 전략 수익률
        strategy_ret = position * price_ret - total_cost - funding_cost

        n_trades = int((pos_change > 0.01).sum())
        return strategy_ret, n_trades


# ─────────────────────────────────────────────
# Walk-Forward Optimization
# ─────────────────────────────────────────────

class WalkForwardValidator:
    """
    시간순으로 train → test → train → test 반복
    각 구간에서 파라미터 최적화 후 다음 구간에서 검증
    """

    def __init__(
        self,
        train_bars: int = 2000,   # 훈련 구간 길이
        test_bars: int = 500,     # 검증 구간 길이
        step_bars: int = 250,     # 슬라이딩 스텝
        min_periods: int = 4,     # 최소 구간 수
    ):
        self.train_bars = train_bars
        self.test_bars = test_bars
        self.step_bars = step_bars
        self.min_periods = min_periods

    def generate_splits(self, n: int) -> list[tuple[slice, slice]]:
        splits = []
        start = 0
        while start + self.train_bars + self.test_bars <= n:
            train_sl = slice(start, start + self.train_bars)
            test_sl  = slice(start + self.train_bars,
                             start + self.train_bars + self.test_bars)
            splits.append((train_sl, test_sl))
            start += self.step_bars
        return splits

    def run(
        self,
        df: pd.DataFrame,
        strategy_fn: Callable,
        simulator: RealisticSimulator,
        callback: Optional[Callable[[str], None]] = None,
    ) -> list[PeriodResult]:
        splits = self.generate_splits(len(df))
        if len(splits) < self.min_periods:
            msg = f"  [WFO] 데이터 부족 — {len(splits)}개 구간만 생성됨"
            print(msg)
            if callback: callback(msg)

        results = []
        for i, (train_sl, test_sl) in enumerate(splits):
            train_df = df.iloc[train_sl]
            test_df  = df.iloc[test_sl]

            try:
                # 전략 함수: train 데이터로 파라미터 최적화 후 signal 반환
                signal = strategy_fn(train_df, test_df)
                returns, n_trades = simulator.run(test_df, signal)

                result = compute_metrics(
                    returns, n_trades,
                    name=f"WFO-{i+1:02d}",
                    start=str(test_df.index[0])[:10],
                    end=str(test_df.index[-1])[:10],
                )
                results.append(result)
                
                # 매 구간마다 상세 실시간 보고
                if callback:
                    msg = f"  ├─ 구간 {i+1:02d} ({result.start} ~ {result.end}): 익절 {result.total_return*100:+.2f}% | 샤프 {result.sharpe:.2f}"
                    callback(msg)
            except Exception as e:
                msg = f"  [WFO] {i+1}번 구간 실패: {e}"
                print(msg)
                if callback: callback(msg)

        return results


# ─────────────────────────────────────────────
# Monte Carlo 시뮬레이션
# ─────────────────────────────────────────────

class MonteCarloValidator:
    """
    실제 수익률을 재샘플링해서 운의 영향을 분리.
    "이 성과가 운인가 실력인가"를 수치로 보여줌.
    """

    def __init__(self, n_sims: int = 1000, ruin_threshold: float = -0.50):
        self.n_sims = n_sims
        self.ruin_threshold = ruin_threshold  # -50% = 파산 기준

    def run(self, returns: pd.Series) -> dict:
        if len(returns) < 30:
            return {}

        r = returns.values
        n = len(r)
        sim_finals = []

        rng = np.random.default_rng(42)
        for _ in range(self.n_sims):
            # 실제 수익률을 무작위 순서로 재배열
            shuffled = rng.choice(r, size=n, replace=True)
            cum_ret = (1 + shuffled).prod() - 1
            sim_finals.append(cum_ret)

        sim_finals = np.array(sim_finals)
        actual_ret = (1 + returns).prod() - 1

        # 누적 경로 중 파산(-50%) 도달 비율
        ruin_count = 0
        for _ in range(self.n_sims):
            path = np.cumprod(1 + rng.choice(r, size=n, replace=True))
            if (path - 1).min() < self.ruin_threshold:
                ruin_count += 1

        percentile = stats.percentileofscore(sim_finals, actual_ret)

        return {
            "n_sims": self.n_sims,
            "actual_return": actual_ret,
            "median_return": float(np.median(sim_finals)),
            "var_5pct": float(np.percentile(sim_finals, 5)),
            "var_1pct": float(np.percentile(sim_finals, 1)),
            "ruin_prob": ruin_count / self.n_sims,
            "actual_percentile": percentile,  # 몇 %ile에 위치하는가
            "is_skill": percentile > 75,       # 상위 25%면 스킬로 간주
        }


# ─────────────────────────────────────────────
# 시장 구간 분류
# ─────────────────────────────────────────────

def classify_regimes(df: pd.DataFrame, window: int = 100) -> pd.Series:
    """
    단순 규칙 기반 Regime 분류 (HMM 없이 빠르게):
      - bull    : 롤링 수익률 > +5%
      - bear    : 롤링 수익률 < -5%
      - sideways: 그 외
    """
    roll_ret = df["close"].pct_change(window)
    regime = pd.Series("sideways", index=df.index)
    regime[roll_ret > 0.05] = "bull"
    regime[roll_ret < -0.05] = "bear"
    return regime


# ─────────────────────────────────────────────
# 메인 엔진
# ─────────────────────────────────────────────

class BacktestEngine:
    """
    전체 검증 파이프라인을 조율하는 메인 클래스.

    Parameters
    ----------
    df          : OHLCV DataFrame (index=DatetimeIndex, columns=open/high/low/close/volume)
    fee_rate    : 편도 수수료 (기본 0.1%)
    slippage    : 슬리피지 (기본 0.05%)
    train_ratio : 개발 구간 비율
    test_ratio  : 최종 테스트 비율 (나머지는 WFO)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        fee_rate: float = 0.001,
        slippage: float = 0.0005,
        train_ratio: float = 0.60,
        test_ratio: float = 0.20,
        freq: int = 24,           # 하루 봉 수 (1h=24, 4h=6, 1d=1)
    ):
        self.df = df.copy()
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.freq = freq

        n = len(df)
        self.train_end  = int(n * train_ratio)
        self.wfo_end    = int(n * (1 - test_ratio))
        self.test_start = self.wfo_end

        self.sim = RealisticSimulator(fee_rate=fee_rate, slippage=slippage)

        # WFO 파라미터를 WFO 구간 길이 기준으로 계산
        wfo_len = self.wfo_end - self.train_end
        _train  = max(100, wfo_len // 4)
        _test   = max(50,  wfo_len // 8)
        _step   = max(25,  _test // 2)
        self.wfo = WalkForwardValidator(
            train_bars=_train,
            test_bars=_test,
            step_bars=_step,
        )
        self.mc = MonteCarloValidator(n_sims=500)

        print(f"데이터 분할:")
        print(f"  개발 구간  : {str(df.index[0])[:10]} ~ {str(df.index[self.train_end])[:10]} ({self.train_end}봉)")
        print(f"  WFO 구간   : {str(df.index[self.train_end])[:10]} ~ {str(df.index[self.wfo_end])[:10]}")
        print(f"  최종 테스트: {str(df.index[self.test_start])[:10]} ~ {str(df.index[-1])[:10]} ({n - self.test_start}봉)")

    def run_full_validation(
        self,
        strategy_fn: Callable,
        strategy_name: str = "LLM Strategy",
        run_test_set: bool = False,  # 개발 중엔 False — Test Set은 마지막에만
        callback: Optional[Callable[[str], None]] = None,
    ) -> ValidationResult:
        """
        strategy_fn(train_df, test_df) → signal Series
        """
        result = ValidationResult(strategy_name=strategy_name)

        # 1. Walk-Forward Validation
        msg1 = "[1/4] Walk-Forward Validation 실행 중..."
        print(f"\n{msg1}")
        if callback: callback(msg1)
        
        wfo_df = self.df.iloc[self.train_end:self.wfo_end]
        result.wfo_results = self.wfo.run(wfo_df, strategy_fn, self.sim, callback=callback)

        if not result.wfo_results:
            result.verdict = "WFO 구간 부족으로 검증 불가"
            return result

        # 2. 전체 WFO 수익률 집계
        all_wfo_returns = []
        total_trades = 0
        for r in result.wfo_results:
            # 수익률 재생성 (집계용)
            try:
                test_start_idx = self.df.index.get_loc(r.start, method="nearest")
                sub_df = self.df.iloc[test_start_idx:test_start_idx + self.wfo.test_bars]
                train_start = max(0, test_start_idx - self.wfo.train_bars)
                train_df = self.df.iloc[train_start:test_start_idx]
                signal = strategy_fn(train_df, sub_df)
                rets, _ = self.sim.run(sub_df, signal)
                all_wfo_returns.append(rets)
                total_trades += r.n_trades
            except Exception:
                pass

        if all_wfo_returns:
            combined_rets = pd.concat(all_wfo_returns)
        else:
            combined_rets = pd.Series(dtype=float)

        # 3. Monte Carlo
        msg2 = f"[2/4] Monte Carlo 시뮬레이션 ({self.mc.n_sims}회)..."
        print(msg2)
        if callback: callback(msg2)
        if len(combined_rets) > 30:
            result.monte_carlo = self.mc.run(combined_rets)

        # 4. Regime별 성과
        msg3 = "[3/4] 시장 구간별 분석..."
        print(msg3)
        if callback: callback(msg3)
        result.regime_results = self._analyze_by_regime(strategy_fn)

        # 5. 최종 테스트 (선택)
        if run_test_set:
            msg4 = "[4/4] 최종 테스트 구간 실행..."
            print(msg4)
            if callback: callback(msg4)
            test_df = self.df.iloc[self.test_start:]
            train_df = self.df.iloc[self.train_end:self.test_start]
            try:
                signal = strategy_fn(train_df, test_df)
                rets, n_trades = self.sim.run(test_df, signal)
                result.period_results.append(compute_metrics(
                    rets, n_trades, "FINAL_TEST",
                    str(test_df.index[0])[:10],
                    str(test_df.index[-1])[:10],
                    self.freq,
                ))
            except Exception as e:
                print(f"  최종 테스트 실패: {e}")
        else:
            msg4 = "[4/4] 최종 테스트 구간 보류 (Mining Mode)"
            print(msg4)
            if callback: callback(msg4)

        # 6. 종합 판정
        result.is_robust, result.verdict = self._judge(result)
        return result

    def _analyze_by_regime(self, strategy_fn: Callable) -> dict:
        regimes = classify_regimes(self.df)
        wfo_df = self.df.iloc[self.train_end:self.wfo_end]
        wfo_regimes = regimes.iloc[self.train_end:self.wfo_end]

        regime_stats = {}
        for reg in ["bull", "bear", "sideways"]:
            mask = wfo_regimes == reg
            if mask.sum() < 100:
                continue
            sub_df = wfo_df[mask]

            # Regime 구간을 연속 슬라이스로 분할해서 각각 실행
            sharpes, rets = [], []
            segments = self._get_segments(mask)
            for seg_df in segments:
                if len(seg_df) < 50:
                    continue
                train_df = self.df.iloc[max(0, self.train_end - self.wfo.train_bars):self.train_end]
                try:
                    signal = strategy_fn(train_df, seg_df)
                    r, _ = self.sim.run(seg_df, signal)
                    if len(r) > 0:
                        m = compute_metrics(r, 0, reg, "", "")
                        sharpes.append(m.sharpe)
                        rets.append(m.total_return)
                except Exception:
                    pass

            if sharpes:
                regime_stats[reg] = {
                    "mean_sharpe": float(np.mean(sharpes)),
                    "mean_return": float(np.mean(rets)),
                    "n_segments": len(sharpes),
                }
        return regime_stats

    def _get_segments(self, mask: pd.Series, min_len: int = 50) -> list:
        """Boolean mask → 연속 구간 DataFrame 리스트"""
        segments = []
        in_seg = False
        start = None
        for i, v in enumerate(mask):
            if v and not in_seg:
                start = i
                in_seg = True
            elif not v and in_seg:
                if i - start >= min_len:
                    segments.append(self.df.iloc[start:i])
                in_seg = False
        if in_seg and len(mask) - start >= min_len:
            segments.append(self.df.iloc[start:])
        return segments

    def _judge(self, result: ValidationResult) -> tuple[bool, str]:
        """WFO + Monte Carlo 결과를 종합해서 신뢰도 판정"""
        if not result.wfo_results:
            return False, "검증 불가"

        sharpes = [r.sharpe for r in result.wfo_results]
        mdds = [r.max_drawdown for r in result.wfo_results]
        pos_sharpe_ratio = sum(1 for s in sharpes if s > 0) / len(sharpes)

        issues = []
        passes = []

        # 1. WFO 일관성 (양의 Sharpe 비율)
        if pos_sharpe_ratio >= 0.70:
            passes.append(f"WFO 구간 {pos_sharpe_ratio:.0%}에서 양의 Sharpe")
        else:
            issues.append(f"WFO 구간 {pos_sharpe_ratio:.0%}만 양의 Sharpe (기준: 70%)")

        # 2. 평균 Sharpe
        mean_sharpe = np.mean(sharpes)
        if mean_sharpe > 0.5:
            passes.append(f"평균 Sharpe {mean_sharpe:.2f} > 0.5")
        else:
            issues.append(f"평균 Sharpe {mean_sharpe:.2f} 부족 (기준: 0.5)")

        # 3. 최대 낙폭
        worst_mdd = min(mdds)
        if worst_mdd > -0.30:
            passes.append(f"최악 MDD {worst_mdd:.1%} 허용 범위")
        else:
            issues.append(f"최악 MDD {worst_mdd:.1%} 과다 (기준: -30%)")

        # 4. Monte Carlo 파산 확률
        if result.monte_carlo:
            ruin = result.monte_carlo.get("ruin_prob", 1.0)
            if ruin < 0.10:
                passes.append(f"파산 확률 {ruin:.1%} < 10%")
            else:
                issues.append(f"파산 확률 {ruin:.1%} 과다 (기준: <10%)")

        is_robust = len(issues) == 0
        if is_robust:
            verdict = "✅ 모든 기준 통과: " + " | ".join(passes)
        else:
            verdict = "❌ 문제: " + " | ".join(issues)
            if passes:
                verdict += " / 통과: " + " | ".join(passes)

        return is_robust, verdict


# ─────────────────────────────────────────────
# 편의 함수: LLM 생성 전략 코드 → 실행 가능 함수로 변환
# ─────────────────────────────────────────────

def strategy_from_code(code: str) -> Callable:
    """
    LLM이 생성한 전략 코드 문자열을 실행 가능한 함수로 변환.
    신규/구형 모든 전략 코드를 지원하며, Strategy/Signal 클래스를 자동 주입함.
    """
    import pandas as pd
    import numpy as np

    # 하이브리드 지원을 위한 기본 클래스 정의
    class Signal:
        def __init__(self, entry=False, exit=False, direction="long"):
            self.entry = entry
            self.exit = exit
            self.direction = direction

    class Strategy:
        name = "Base"
        def generate_signals(self, data, params): return Signal()

    namespace = {
        "pd": pd,
        "np": np,
        "Strategy": Strategy,
        "Signal": Signal,
        "DataFrame": pd.DataFrame,
        "Series": pd.Series
    }

    try:
        exec(code, namespace)
    except Exception as e:
        raise RuntimeError(f"Code syntax error: {e}")

    # 1. 신규 엔진 규격 (generate_signal 함수) 검색
    if "generate_signal" in namespace:
        original_fn = namespace["generate_signal"]

        # 안전장치가 적용된 래퍼 함수 생성
        def safe_generate_signal(train_df, test_df):
            # 데이터 길이 확인 (안전장치)
            if len(test_df) < 20:
                return pd.Series(0, index=test_df.index, dtype=int)

            # 컬럼명 검증 및 소문자 변환
            required_cols = {"open", "high", "low", "close", "volume"}
            if not required_cols.issubset(test_df.columns):
                # 컬럼명을 소문자로 변환 시도
                test_df = test_df.rename(columns=str.lower)
                if not required_cols.issubset(test_df.columns):
                    raise ValueError(f"test_df must contain columns {required_cols}")

            return original_fn(train_df, test_df)

        return safe_generate_signal

    # 2. 구형/하이브리드 클래스 방식 호환 처리
    for name, obj in namespace.items():
        # (Strategy) 상속을 받았거나, 혹은 generate_signals 메서드를 직접 가지고 있는 클래스 탐색
        if isinstance(obj, type) and obj is not Strategy:
            has_method = hasattr(obj, 'generate_signals')
            is_sub = issubclass(obj, Strategy) if 'Strategy' in locals() or 'Strategy' in globals() or 'Strategy' in namespace else False
            
            if has_method or is_sub:
                def wrapped_strategy(train_df, test_df):
                    try:
                        inst = obj()
                        signals = []
                        current_val = 0
                        for i in range(len(test_df)):
                            # 최소 데이터 확보 전까지는 0(관망) 신호 유지
                            if i < 1: 
                                signals.append(0)
                                continue
                                
                            # 매 루프마다 현재까지의 데이터만 전달
                            sub_df = test_df.iloc[:i+1]
                            s = inst.generate_signals(sub_df, {})
                            
                            if hasattr(s, 'entry') and s.entry: 
                                current_val = 1 if getattr(s, 'direction', 'long') == 'long' else -1
                            elif hasattr(s, 'exit') and s.exit: 
                                current_val = 0
                                
                            signals.append(current_val)
                        return pd.Series(signals, index=test_df.index).fillna(0)
                    except Exception as e:
                        # 0 같은 불친절한 에러를 방지하기 위해 상세 에러 로깅
                        raise RuntimeError(f"Strategy Internal Error: {e}")
                return wrapped_strategy

    raise ValueError("코드에서 generate_signal 함수 또는 유효한 Strategy 클래스를 찾을 수 없습니다.")

    raise ValueError("코드에서 generate_signal 함수 또는 Strategy 클래스를 찾을 수 없습니다.")
