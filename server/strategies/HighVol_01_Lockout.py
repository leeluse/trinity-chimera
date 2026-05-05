import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def atr(h, l, c, n=14):
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def adx(h, l, c, n=14):
    up = h.diff()
    down = -l.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = pd.concat(
        [(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)

    atr_v = tr.ewm(alpha=1 / n, adjust=False).mean()

    plus_di = (
        100
        * pd.Series(plus_dm, index=c.index)
        .ewm(alpha=1 / n, adjust=False)
        .mean()
        / (atr_v + 1e-9)
    )

    minus_di = (
        100
        * pd.Series(minus_dm, index=c.index)
        .ewm(alpha=1 / n, adjust=False)
        .mean()
        / (atr_v + 1e-9)
    )

    dx = 100 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9)
    adx_v = dx.ewm(alpha=1 / n, adjust=False).mean()

    return adx_v, plus_di, minus_di


def prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    required = ["open", "high", "low", "close", "volume"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=required)


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """
    HighVol Strategy 01
    Lockout (Risk Circuit Breaker)

    고변동성 구간에서 신규 진입을 완전 차단하고
    기존 포지션을 신속히 청산하는 규칙 기반 회로 차단기.

    전략이 아닌 규칙(Rule)이므로:
      - 신호는 0 (포지션 없음) 고정
      - HighVol 구간 진입 자체를 막는 것이 목적

    Return:
        0 = no position (always)
    """

    if test_df is None or len(test_df) == 0:
        return pd.Series(dtype=int)

    train = (
        prepare_ohlcv(train_df)
        if train_df is not None and len(train_df) > 0
        else pd.DataFrame()
    )
    test = prepare_ohlcv(test_df)

    if len(test) == 0:
        return pd.Series(0, index=test_df.index, dtype=int)

    required = ["open", "high", "low", "close", "volume"]

    # =========================
    # 1. Indicator full context
    # =========================
    if len(train) > 0:
        df_full = pd.concat([train[required], test[required]])
    else:
        df_full = test[required].copy()

    df_full = df_full.sort_index()
    df_full = df_full[~df_full.index.duplicated(keep="last")]

    c_full = df_full["close"]
    h_full = df_full["high"]
    l_full = df_full["low"]

    atr14_full = atr(h_full, l_full, c_full, 14)
    atr14_ma_full = atr14_full.rolling(20).mean()      # ATR 기준선
    atr14_pct_full = atr14_full / (atr14_ma_full + 1e-9)  # ATR 배율

    adx14_full, _, _ = adx(h_full, l_full, c_full, 14)

    # 일간 수익률 표준편차 (rolling 20봉) — 단기 변동성 폭발 감지
    ret_full = c_full.pct_change()
    vol_20_full = ret_full.rolling(20).std()
    vol_ma_full = vol_20_full.rolling(60).mean()
    vol_spike_full = vol_20_full / (vol_ma_full + 1e-9)

    # =========================
    # 2. Shift context (경계 데이터 1봉 추가)
    # =========================
    if len(train) > 0:
        df_ctx = pd.concat([train[required].iloc[-1:], test[required]])
    else:
        df_ctx = test[required].copy()

    df_ctx = df_ctx.sort_index()
    df_ctx = df_ctx[~df_ctx.index.duplicated(keep="last")]

    idx = df_ctx.index

    atr14_pct = atr14_pct_full.reindex(idx)
    adx14 = adx14_full.reindex(idx)
    vol_spike = vol_spike_full.reindex(idx)

    # =========================
    # 3. HighVol regime detection
    # =========================
    # 세 가지 조건 중 하나라도 충족하면 HighVol 구간으로 판정
    atr_spike = atr14_pct > 2.0           # ATR이 20봉 평균의 2배 초과
    adx_surge = adx14 > 40                # ADX 40 초과: 극단적 추세 / 폭락
    vol_explosion = vol_spike > 2.5       # 단기 변동성이 기준의 2.5배 초과

    highvol_regime = (
        atr_spike.shift(1).fillna(False) |    # 전봉 기준으로 판정 (Lookahead 방지)
        adx_surge.shift(1).fillna(False) |
        vol_explosion.shift(1).fillna(False)
    )

    # =========================
    # 4. Signal: HighVol이면 강제 0 (포지션 없음)
    # HighVol이 아닌 구간도 0 — 이 파일은 "차단기" 역할
    # =========================
    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    # HighVol 구간 명시적 마킹 (모두 0이지만 추후 디버깅용)
    # signal[highvol_regime] = 0  # 이미 0이므로 생략

    first_test_pos = df_ctx.index.get_loc(test.index[0])

    for i in range(len(df_ctx)):
        if i < first_test_pos:
            signal.iloc[i] = 0
            continue

        # HighVol 여부와 무관하게 항상 포지션 없음
        signal.iloc[i] = 0

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)
