"""레짐 귀속 분석 파이프라인
특정 파라미터가 잘 작동한 구간의 시장 조건을 자동으로 추출한다.

흐름:
  1. OHLCV 전체 기간 로드
  2. N일 윈도우로 슬라이딩 → 각 구간 백테스트 + 시장 피처 계산
  3. [피처 × 성과] 상관분석
  4. 결정 트리로 조건 추출 → 한국어 규칙 출력
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from server.modules.chat.skills._base import format_sse
from server.modules.engine.runtime import run_skill_backtest
from server.modules.engine.utils import extract_symbol, extract_timeframe
from server.shared.market.provider import fetch_ohlcv_dataframe

logger = logging.getLogger(__name__)

# ─── 설정 상수 ────────────────────────────────────────────────────────────────
_WINDOW_DAYS   = 30   # 각 분석 윈도우 길이
_STEP_DAYS     = 15   # 윈도우 이동 보폭
_MIN_WINDOWS   = 5    # 최소 유효 윈도우 수
_MIN_TRADES    = 3    # 윈도우당 최소 거래 수

# ─── 시장 피처 계산 ────────────────────────────────────────────────────────────

def _compute_features(df: pd.DataFrame) -> Dict[str, float]:
    """OHLCV 구간 → 정량 피처 dict."""
    if len(df) < 20:
        return {}

    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    volume = df["volume"].astype(float)
    n      = len(close)

    # 1. 방향성: 선형 회귀 기울기 (z-score 단위)
    x = np.arange(n)
    slope, _ = np.polyfit(x, close.values, 1)
    trend_strength = slope / (close.mean() or 1) * n  # 전체 구간 대비 변화율

    # 2. 변동성: ATR% (14봉 평균)
    tr_list = []
    c_arr = close.values
    h_arr = high.values
    l_arr = low.values
    for i in range(1, len(c_arr)):
        tr_list.append(max(h_arr[i] - l_arr[i],
                          abs(h_arr[i] - c_arr[i-1]),
                          abs(l_arr[i] - c_arr[i-1])))
    atr = float(np.mean(tr_list[-14:]) if len(tr_list) >= 14 else np.mean(tr_list))
    atr_pct = atr / (close.mean() or 1) * 100

    # 3. 모멘텀: 구간 전체 수익률
    momentum = float((close.iloc[-1] - close.iloc[0]) / (close.iloc[0] or 1) * 100)

    # 4. 거래량 서지: 후반부 평균 / 전반부 평균
    mid = n // 2
    vol_early = float(volume.iloc[:mid].mean() or 1)
    vol_late  = float(volume.iloc[mid:].mean() or 1)
    vol_surge = vol_late / vol_early

    # 5. 변동성 레짐: 고가-저가 범위 / 중간가
    range_pct = float((high.max() - low.min()) / (close.mean() or 1) * 100)

    # 6. 평균 수익률(일별 변화율) 절댓값 → "소란스러움" 지표
    daily_returns = close.pct_change().dropna().abs()
    noise_pct = float(daily_returns.mean() * 100)

    return {
        "trend_strength": round(trend_strength, 4),  # 양=상승, 음=하락
        "atr_pct":        round(atr_pct, 3),         # 높을수록 고변동
        "momentum":       round(momentum, 2),         # 구간 전체 수익률
        "vol_surge":      round(vol_surge, 3),        # >1 = 거래량 증가
        "range_pct":      round(range_pct, 2),        # 구간 가격 범위
        "noise_pct":      round(noise_pct, 4),        # 일별 잡음
    }


# ─── 결정 트리 규칙 추출 ──────────────────────────────────────────────────────

def _extract_tree_rules(
    X: pd.DataFrame,
    y: pd.Series,
) -> List[str]:
    """sklearn 결정 트리 학습 → 한국어 규칙 리스트 반환."""
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
    except ImportError:
        return ["sklearn 없음 — pip install scikit-learn"]

    if X.shape[0] < 6 or y.nunique() < 2:
        return ["데이터 부족 — 윈도우를 늘려주세요."]

    clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=2, random_state=42)
    clf.fit(X, y)

    # 트리 텍스트 파싱 → 한국어 규칙
    raw = export_text(clf, feature_names=list(X.columns))
    rules = _parse_tree_to_korean(raw, X.columns.tolist(), clf, X, y)
    return rules


_FEATURE_KO = {
    "trend_strength": "추세 강도",
    "atr_pct":        "ATR(변동성)%",
    "momentum":       "구간 수익률%",
    "vol_surge":      "거래량 증가율",
    "range_pct":      "가격 범위%",
    "noise_pct":      "일별 잡음%",
}


def _parse_tree_to_korean(raw_text: str, feature_names: List[str], clf, X: pd.DataFrame, y: pd.Series) -> List[str]:
    """export_text 결과를 읽기 쉬운 한국어 규칙 리스트로 변환."""
    import re

    lines    = raw_text.strip().split("\n")
    n_good   = int(y.sum())
    n_bad    = int((y == 0).sum())
    n_total  = len(y)
    accuracy = round(clf.score(X, y) * 100, 1)

    rules: List[str] = []
    rules.append(f"결정 트리 정확도: {accuracy}% (좋은구간 {n_good}개 / 전체 {n_total}개)")
    rules.append("")

    # 리프 노드만 추출하여 경로 복원
    leaf_paths = _collect_leaf_paths(lines)
    for path_conds, label, samples in leaf_paths:
        if not path_conds:
            continue
        cond_strs = []
        for feat, op, val in path_conds:
            ko = _FEATURE_KO.get(feat, feat)
            val_str = f"{float(val):.3g}"
            sym = ">" if op == ">" else "≤"
            cond_strs.append(f"{ko} {sym} {val_str}")

        emoji = "✅" if label == 1 else "❌"
        verdict = "좋은 구간" if label == 1 else "나쁜 구간"
        rules.append(f"{emoji} {verdict} 조건")
        for c in cond_strs:
            rules.append(f"   → {c}")
        rules.append(f"   (해당 구간 {samples}개)")
        rules.append("")

    return rules


def _collect_leaf_paths(lines: List[str]) -> List[Tuple[List, int, int]]:
    """트리 텍스트에서 리프 경로 수집."""
    import re
    stack: List[Tuple[int, Any]] = []  # (depth, condition)
    results = []

    for line in lines:
        depth = (len(line) - len(line.lstrip("|"))) // 4 + (1 if line.lstrip("|").startswith(" ") else 0)
        content = line.strip().lstrip("|- ")

        # 분기 조건
        m = re.match(r"(\w+)\s*([<>]=?)\s*([\d.\-e]+)", content)
        if m:
            feat, op, val = m.group(1), m.group(2), m.group(3)
            while stack and stack[-1][0] >= depth:
                stack.pop()
            # > 방향이면 True 분기
            if ">" in op:
                stack.append((depth, (feat, ">", val)))
            else:
                stack.append((depth, (feat, "<=", val)))
            continue

        # 리프 노드 (class: X)
        m2 = re.match(r"class:\s*(\d+)\s*\|\s*samples:\s*(\d+)|class:\s*(\d+)", content)
        if not m2:
            # export_text 포맷: "class: 1"
            m2 = re.match(r"class:\s*(\d+)", content)
        if m2:
            label = int(m2.group(1) or m2.group(3) or 0)
            path_conds = [c for (_, c) in stack if c is not None]
            samples_m = re.search(r"samples:\s*(\d+)", content)
            samples = int(samples_m.group(1)) if samples_m else "?"
            results.append((path_conds, label, samples))

    return results


# ─── 상관분석 요약 ────────────────────────────────────────────────────────────

def _correlation_summary(df: pd.DataFrame) -> List[str]:
    """피처-수익률 상관계수 → 한국어 요약."""
    lines = ["**피처-수익률 상관관계:**"]
    corr = df[[c for c in df.columns if c != "total_return"]].corrwith(df["total_return"])
    corr_sorted = corr.abs().sort_values(ascending=False)

    for feat in corr_sorted.index:
        r = corr[feat]
        ko = _FEATURE_KO.get(feat, feat)
        bar = "█" * int(abs(r) * 10)
        direction = "↑수익 증가" if r > 0 else "↓수익 감소"
        lines.append(f"  {ko:15s} r={r:+.2f} {bar} ({direction})")
    return lines


# ─── 윈도우 슬라이딩 백테스트 ────────────────────────────────────────────────

async def _run_windowed_analysis(
    strategy_code: str,
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    context: Dict[str, Any],
    progress_cb,
) -> pd.DataFrame:
    """각 윈도우마다 백테스트 + 피처 계산 → DataFrame 반환."""
    from server.shared.market.provider import parse_date_to_ms

    start_ms = parse_date_to_ms(start_date, end_of_day=False)
    end_ms   = parse_date_to_ms(end_date, end_of_day=True)
    if not start_ms or not end_ms:
        return pd.DataFrame()

    # 전체 OHLCV 한 번만 다운로드
    df_full = fetch_ohlcv_dataframe(
        symbol=symbol, interval=interval,
        limit=5000, start_ms=start_ms, end_ms=end_ms,
    )
    if df_full.empty:
        return pd.DataFrame()

    window_ms  = _WINDOW_DAYS  * 24 * 3600 * 1000
    step_ms    = _STEP_DAYS    * 24 * 3600 * 1000
    leverage   = float(context.get("leverage", 10.0))

    rows = []
    cursor = start_ms
    total_steps = max(1, (end_ms - start_ms - window_ms) // step_ms + 1)
    step_i = 0

    while cursor + window_ms <= end_ms:
        win_start_ms = cursor
        win_end_ms   = cursor + window_ms
        step_i += 1
        progress_cb(step_i, int(total_steps))

        win_start_dt = datetime.fromtimestamp(win_start_ms / 1000, tz=timezone.utc)
        win_end_dt   = datetime.fromtimestamp(win_end_ms   / 1000, tz=timezone.utc)
        ws = win_start_dt.strftime("%Y-%m-%d")
        we = win_end_dt.strftime("%Y-%m-%d")

        # 윈도우 OHLCV 슬라이싱
        mask = (df_full["timestamp"] >= win_start_dt) & (df_full["timestamp"] <= win_end_dt)
        df_win = df_full[mask].reset_index(drop=True)

        feats = _compute_features(df_win)
        if not feats:
            cursor += step_ms
            continue

        # 백테스트 (이 윈도우 구간만)
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda ws=ws, we=we: run_skill_backtest(
                    symbol=symbol,
                    interval=interval,
                    strategy="custom",
                    leverage=leverage,
                    start_date=ws,
                    end_date=we,
                    include_candles=False,
                    code=strategy_code,
                ),
            )
        except Exception as e:
            logger.debug("window backtest failed %s~%s: %s", ws, we, e)
            cursor += step_ms
            continue

        if not result.get("success"):
            cursor += step_ms
            continue

        m = result.get("metrics", {})
        n_trades = int(m.get("total_trades", 0))
        if n_trades < _MIN_TRADES:
            cursor += step_ms
            continue

        row = {
            "window_start": ws,
            "window_end":   we,
            "total_return": float(m.get("total_return", 0)),
            "sharpe":       float(m.get("sharpe_ratio", 0)),
            "win_rate":     float(m.get("win_rate", 0)),
            "n_trades":     n_trades,
            **feats,
        }
        rows.append(row)
        cursor += step_ms

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ─── 메인 파이프라인 ──────────────────────────────────────────────────────────

async def run_regime_pipeline(
    message: str,
    context: Dict[str, Any],
    strategy_code: str,
    session_memory: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    try:
        if not strategy_code:
            yield format_sse({"type": "error", "content": "❌ 분석할 전략이 없습니다. 먼저 전략을 생성해주세요."})
            yield format_sse({"type": "done"})
            return

        symbol    = extract_symbol(message, context.get("symbol", "BTCUSDT"))
        interval  = extract_timeframe(message, context.get("timeframe", "1h"))

        # 날짜 범위
        from server.modules.engine.utils import resolve_backtest_dates
        start_date, end_date = resolve_backtest_dates(context)

        yield format_sse({
            "type": "stage", "stage": 1,
            "label": f"📊 레짐 분석 준비 — {symbol} {interval} ({start_date} ~ {end_date})",
        })
        yield format_sse({
            "type": "analysis",
            "content": (
                f"**레짐 귀속 분석 시작**\n"
                f"- 심볼: {symbol} / 타임프레임: {interval}\n"
                f"- 분석 기간: {start_date} ~ {end_date}\n"
                f"- 윈도우: {_WINDOW_DAYS}일 / 이동 보폭: {_STEP_DAYS}일\n"
                f"- 각 구간마다 백테스트 + 시장 피처 계산 중..."
            ),
        })

        # 진행 상황 콜백
        progress_state = {"done": 0, "total": 0}

        def progress_cb(done: int, total: int):
            progress_state["done"]  = done
            progress_state["total"] = total

        yield format_sse({
            "type": "stage", "stage": 2,
            "label": f"⚙️ {_WINDOW_DAYS}일 윈도우 슬라이딩 백테스트 중...",
        })

        df = await _run_windowed_analysis(
            strategy_code=strategy_code,
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            context=context,
            progress_cb=progress_cb,
        )

        if df.empty or len(df) < _MIN_WINDOWS:
            yield format_sse({
                "type": "analysis",
                "content": (
                    f"⚠️ 유효한 분석 윈도우가 {len(df)}개로 부족합니다 (최소 {_MIN_WINDOWS}개 필요).\n"
                    "기간을 늘리거나 윈도우 크기를 줄여주세요."
                ),
            })
            yield format_sse({"type": "done"})
            return

        yield format_sse({
            "type": "status",
            "content": f"✅ {len(df)}개 윈도우 분석 완료 → 조건 추출 중...",
        })

        # ── 상관분석 ────────────────────────────────────────────────
        yield format_sse({"type": "stage", "stage": 3, "label": "🔍 피처-성과 상관분석 중..."})

        feature_cols = ["trend_strength", "atr_pct", "momentum", "vol_surge", "range_pct", "noise_pct"]
        corr_lines = _correlation_summary(df[feature_cols + ["total_return"]])

        # ── 결정 트리 ────────────────────────────────────────────────
        median_ret = df["total_return"].median()
        df["label"] = (df["total_return"] > median_ret).astype(int)  # 중앙값 기준 이진 분류

        X = df[feature_cols]
        y = df["label"]

        tree_rules = _extract_tree_rules(X, y)

        # ── 좋은 구간 / 나쁜 구간 통계 ─────────────────────────────
        good = df[df["label"] == 1]
        bad  = df[df["label"] == 0]

        def _stat(subset: pd.DataFrame, col: str) -> str:
            if subset.empty:
                return "N/A"
            return f"{subset[col].mean():.2f}"

        stats_lines = [
            f"**구간별 평균 성과 (중앙값 기준 분류)**",
            f"",
            f"| 항목 | 좋은 구간 ({len(good)}개) | 나쁜 구간 ({len(bad)}개) |",
            f"|------|----------|----------|",
            f"| 평균 수익률% | {_stat(good, 'total_return')} | {_stat(bad, 'total_return')} |",
            f"| 평균 Sharpe | {_stat(good, 'sharpe')} | {_stat(bad, 'sharpe')} |",
            f"| 평균 승률% | {_stat(good, 'win_rate')} | {_stat(bad, 'win_rate')} |",
            f"| 평균 ATR% | {_stat(good, 'atr_pct')} | {_stat(bad, 'atr_pct')} |",
            f"| 평균 추세강도 | {_stat(good, 'trend_strength')} | {_stat(bad, 'trend_strength')} |",
            f"| 평균 거래량배율 | {_stat(good, 'vol_surge')} | {_stat(bad, 'vol_surge')} |",
        ]

        # ── 출력 ────────────────────────────────────────────────────
        yield format_sse({
            "type": "analysis",
            "content": "\n".join(stats_lines),
        })

        yield format_sse({
            "type": "analysis",
            "content": "\n".join(corr_lines),
        })

        yield format_sse({"type": "stage", "stage": 4, "label": "🌳 결정 트리 조건 추출..."})
        yield format_sse({
            "type": "analysis",
            "content": "**결정 트리로 추출한 시장 조건 규칙:**\n\n" + "\n".join(tree_rules),
        })

        # ── 요약 해석 ─────────────────────────────────────────────
        best_feat = max(feature_cols, key=lambda c: abs(df[c].corr(df["total_return"])))
        best_corr = df[best_feat].corr(df["total_return"])
        best_ko   = _FEATURE_KO.get(best_feat, best_feat)
        direction = "높을수록" if best_corr > 0 else "낮을수록"

        good_atr = float(good["atr_pct"].mean()) if not good.empty else 0
        bad_atr  = float(bad["atr_pct"].mean())  if not bad.empty  else 0

        summary = (
            f"**요약 해석**\n\n"
            f"이 전략에서 성과에 가장 큰 영향을 미친 요소는 **{best_ko}** (상관계수 {best_corr:+.2f})입니다.\n"
            f"{best_ko}이 {direction} 수익률이 높은 경향이 있습니다.\n\n"
            f"ATR 기준으로 보면, 좋은 구간의 평균 변동성은 **{good_atr:.2f}%**, "
            f"나쁜 구간은 **{bad_atr:.2f}%**였습니다.\n\n"
            f"**실전 적용 제안:** 위 조건이 충족될 때만 이 전략을 활성화하는 "
            f"레짐 필터를 전략 코드에 추가하면 오버피팅 없이 성과를 개선할 수 있습니다."
        )
        yield format_sse({"type": "analysis", "content": summary})
        yield format_sse({"type": "done"})

    except Exception as e:
        logger.exception("regime pipeline error")
        yield format_sse({"type": "error", "content": f"❌ 레짐 분석 오류: {e}"})
        yield format_sse({"type": "done"})
