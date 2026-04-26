"""
╔══════════════════════════════════════════════════════════════════════╗
║         💀 Crime Pump Hunter V5 — Liquidation Guard Edition 💀       ║
║                                                                      ║
║  V4 → V5 핵심 변경: "왜 청산 당했는가"를 역설계한 업그레이드          ║
║                                                                      ║
║  [청산 방지 모듈] ★★★ NEW ★★★                                        ║
║  • 리스크 레이어 — 진입 전 레버리지/청산가/손익비 자동 계산           ║
║  • 덤프 트랩 감지 — 이미 고점 지난 IGNITION 시그널 차단               ║
║  • 청산 클러스터 히트맵 — 세력이 청산 노리는 가격대 시각화            ║
║  • 펀딩비 velocity — 현재값이 아닌 "가속도"로 전환점 포착              ║
║                                                                      ║
║  [진입 판단 모듈] ★★★ NEW ★★★                                        ║
║  • Entry Score (0~100) — 스크리닝 점수와 분리된 진입 적합성            ║
║  • 최적 진입구간 계산 — 지지/저항 기반 구체적 가격대                  ║
║  • 손절/목표가 자동 추천 — ATR 기반 동적 계산                         ║
║  • 단계별 분할진입 플랜 — 리스크 분산 진입 전략                       ║
║                                                                      ║
║  [탈출 경보 모듈] ★★★ NEW ★★★                                        ║
║  • Exit Alert — 보유 포지션 탈출 타이밍 실시간 감지                   ║
║  • 고래 이탈 시그널 — 탑트레이더가 먼저 빠지는 패턴                   ║
║  • 거래량 고갈 감지 — 펌프 후 거래량 급감 = 덤프 직전                 ║
║                                                                      ║
║  [기존 V4 유지]                                                       ║
║  • Z-Score 정규화, 펌프 단계 분류, 복합 시그니처                      ║
║  • 텔레그램 알림, JSON 스냅샷, 연속 모니터링                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import aiohttp
import json
import csv
import os
import sys
import statistics
import datetime
import math
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict, deque

# ═══════════════════════════════════════════════
# CONFIG (BYBIT V5)
# ═══════════════════════════════════════════════
START_TIMESTAMP = int(datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
HEADERS = {'User-Agent': 'CrimePumpHunter/5.0-Bybit'}
BASE_URL = "https://api.bybit.com/v5/market"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8676836144:AAExsKdTXp6FSARtFt55bmjTpZglSI04YdY")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "6774464368")

async def ensure_chat_id(session: aiohttp.ClientSession):
    global TELEGRAM_CHAT_ID
    if TELEGRAM_CHAT_ID:
        return
    
    print("\n" + "!" * 50)
    print("  📢 텔레그렘 CHAT_ID가 설정되지 않았습니다.")
    print(f"  새로 만든 봇(t.me/alt_czn_v2_bot)에게 아무 메시지나 보낸 후 엔터를 눌러주세요.")
    print("!" * 50 + "\n")
    
    while not TELEGRAM_CHAT_ID:
        input("봇에게 메시지를 보냈다면 엔터를 눌러주세요 (무시하려면 0 입력): ")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        data = await fetch(session, url)
        if data and data.get("ok") and data.get("result"):
            # 가장 최근 메시지에서 chat id 추출
            for item in reversed(data["result"]):
                if "message" in item:
                    TELEGRAM_CHAT_ID = str(item["message"]["chat"]["id"])
                    print(f"  ✅ CHAT_ID 감지 완료: {TELEGRAM_CHAT_ID}")
                    return
        print("  ❌ 메시지를 찾을 수 없습니다. 다시 시도해주세요.")

MONITOR_INTERVAL_SEC = 300
SCORE_ALERT_THRESHOLD = 80

# ── V5 리스크 설정 ──
DEFAULT_CAPITAL_USD   = 1000   # 기본 거래 자본 (변경 가능)
MAX_LEVERAGE          = 10     # 절대 최대 레버리지
RISK_PER_TRADE_PCT    = 2.0    # 트레이드당 최대 손실 허용 % (자본 대비)
ATR_PERIOD            = 14     # ATR 계산 기간

# ── 덤프 트랩 필터 임계값 ──
DUMP_TRAP_PRICE_RISE_24H  = 15.0   # 24h 이미 15% 이상 상승 → 트랩 의심
DUMP_TRAP_FUNDING_POS     = 0.15   # 펀딩비 이미 양전환 → 세력 분배 중
DUMP_TRAP_VOL_RATIO       = 5.0    # 거래량이 평균 5배 이상 → 피크 가능성
DUMP_TRAP_OI_REVERSAL     = -10.0  # OI가 다시 감소 → 포지션 청산 중

# ── V6: 200%+ 폭등 사전포착 임계값 ──
MEGA_PUMP_SHORT_RATIO_MIN = 62.0   # 숏 비율 62%+ → 스퀴즈 연료 풍부
MEGA_PUMP_FUNDING_MAX     = -0.20  # 펀딩 -0.20% 이하 → 극단적 매집
MEGA_PUMP_OI_1H_MIN       = 8.0    # OI 1h +8% → 기존 15%에서 하향 (조기감지)
MEGA_PUMP_COIL_OI_24H     = 35.0   # 가격 고정 + OI 24h 35%+ → 코일 압축
MEGA_PUMP_FUNDING_VEL     = -0.005 # 기존 -0.01 → -0.005로 민감도 상향

# ── 스코어 가중치 (V4 유지 + V5 추가 + V6 신규) ──
SCORE_WEIGHTS = {
    "funding_extreme":          35,
    "funding_negative":         15,
    "funding_very_neg":         25,
    "oi_spike":                 40,
    "oi_growth":                20,
    "oi_surge_1h":              25,
    "oi_surge_4h":              15,
    "ls_ratio_short":           35,
    "ls_ratio_mid":             15,
    "top_trader_short":         30,
    "top_trader_diverge":       25,
    "taker_buy_dominant":       30,
    "taker_sell_dominant":      20,
    "orderbook_bid_heavy":      25,
    "orderbook_ask_heavy":      15,
    "volume_spike":             30,
    "volume_extreme":           20,
    "price_momentum_1h":        20,
    "price_compression":        20,
    "mark_discount":            20,
    "liq_ratio_low":            40,
    "liq_ratio_mid":            20,
    "fdv_small":                25,
    "signature_accumulation":   40,
    "signature_spring":         35,
    "signature_ignition":       50,
    # ── V5 신규 ──
    "funding_velocity_up":      20,   # 펀딩비 빠르게 상승 중 (양전환 임박)
    "funding_velocity_down":    25,   # 펀딩비 빠르게 하락 중 (매집 심화)
    "oi_reversal_warning":     -30,   # OI 감소 반전 → 페널티
    "vol_exhaustion":          -25,   # 거래량 고갈 시작 → 페널티
    "whale_exit_signal":       -40,   # 고래 이탈 시그널 → 페널티
    # ── V6 신규: 200%+ 폭등 전용 ──
    "coil_extreme":             55,   # 가격고정 + OI폭증 + 극음펀딩 = 최강 코일
    "squeeze_fuel_max":         45,   # 숏62%+ + 극음펀딩 + OI급증 = 스퀴즈 연료 MAX
    "pre_ignition":             60,   # SPRING → IGNITION 직전 전환점 감지
    "oi_early_surge":           20,   # OI 1h 8%+ (기존 15% 대비 조기감지)
    "taker_flip":               30,   # 가격 고정 중 매수체결 60%+ = 세력 무빙
    "orderbook_thin_ask":       35,   # Ask 잔량 극소 → 조금만 올려도 폭등
    "funding_extreme_v6":       40,   # 펀딩 -0.5% 이하 극단 (V4 35점 → 중복방지로 분리)
}

# ═══════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════
@dataclass
class RiskProfile:
    """V5 핵심: 진입 전 리스크 계산 결과"""
    entry_score:          float = 0.0    # 0~100, 높을수록 진입 적합
    dump_trap_risk:       str   = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL
    dump_trap_reasons:    list  = field(default_factory=list)

    # 포지션 사이징
    recommended_leverage: float = 0.0
    max_safe_leverage:    float = 0.0
    position_size_usd:    float = 0.0   # capital 기준 추천 포지션 크기

    # 가격 레벨
    entry_zone_low:   float = 0.0
    entry_zone_high:  float = 0.0
    stop_loss:        float = 0.0
    target_1:         float = 0.0       # 1차 목표 (1R)
    target_2:         float = 0.0       # 2차 목표 (2R)
    target_3:         float = 0.0       # 3차 목표 (3R+)
    risk_reward:      float = 0.0

    # 청산 클러스터
    liq_cluster_above: float = 0.0      # 위쪽 청산 밀집 가격
    liq_cluster_below: float = 0.0      # 아래쪽 청산 밀집 가격
    liq_above_usd:     float = 0.0
    liq_below_usd:     float = 0.0

    # ATR
    atr:              float = 0.0
    atr_pct:          float = 0.0       # ATR / 현재가 %

    # 분할진입 플랜
    dca_plan:         list  = field(default_factory=list)

@dataclass
class ExitAlert:
    """V5 핵심: 보유 포지션 탈출 경보"""
    should_exit:   bool  = False
    urgency:       str   = "NONE"       # NONE / WATCH / URGENT / EMERGENCY
    exit_reasons:  list  = field(default_factory=list)
    exit_score:    float = 0.0          # 0~100, 높을수록 빨리 나가야 함

@dataclass
class FundingHistory:
    """펀딩비 히스토리 (velocity 계산용)"""
    rates:    list = field(default_factory=list)  # 최근 8개 펀딩비
    velocity: float = 0.0                          # 변화 속도
    trend:    str   = "FLAT"                       # RISING / FALLING / FLAT

@dataclass
class CoinData:
    symbol: str
    score:        int   = 0
    score_reasons: list = field(default_factory=list)
    pump_stage:   str   = ""
    confidence:   float = 0.0
    z_scores:     dict  = field(default_factory=dict)

    # ── 기본 지표 (V4 동일) ──
    funding_rate:        float = 0.0
    oi_current:          float = 0.0
    oi_change_pct_1h:    float = 0.0
    oi_change_pct_4h:    float = 0.0
    oi_change_pct_24h:   float = 0.0
    long_ratio:          float = 0.0
    short_ratio:         float = 0.0
    top_long_ratio:      float = 0.0
    top_short_ratio:     float = 0.0
    taker_buy_ratio:     float = 0.0
    taker_sell_ratio:    float = 0.0
    bid_depth_usd:       float = 0.0
    ask_depth_usd:       float = 0.0
    book_imbalance:      float = 0.0
    mark_price:          float = 0.0
    index_price:         float = 0.0
    mark_index_diff_pct: float = 0.0
    price:               float = 0.0
    price_change_1h:     float = 0.0
    price_change_4h:     float = 0.0
    price_change_24h:    float = 0.0
    volume_24h:          float = 0.0
    volume_change_pct:   float = 0.0
    scan_time:           str   = ""

    # ── V5 신규 ──
    funding_history:     FundingHistory = field(default_factory=FundingHistory)
    atr:                 float = 0.0
    atr_pct:             float = 0.0
    liq_long_usd_1pct:   float = 0.0   # 현재가 -1% 청산 볼륨
    liq_short_usd_1pct:  float = 0.0   # 현재가 +1% 청산 볼륨
    liq_clusters:        list  = field(default_factory=list)  # [(price, volume, side)]
    klines_1h:           list  = field(default_factory=list)  # ATR 계산용
    risk:                RiskProfile = field(default_factory=RiskProfile)
    exit_alert:          ExitAlert   = field(default_factory=ExitAlert)

# ═══════════════════════════════════════════════
# ASYNC HTTP
# ═══════════════════════════════════════════════
async def fetch(session: aiohttp.ClientSession, url: str, retries: int = 2) -> Optional[dict]:
    for attempt in range(retries + 1):
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                elif resp.status == 429:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
        except Exception:
            if attempt < retries:
                await asyncio.sleep(0.5)
    return None

# ═══════════════════════════════════════════════
# STEP 1: TARGET EXTRACTION (V4 동일)
# ═══════════════════════════════════════════════
async def get_target_symbols(session) -> list[str]:
    """바이비트 USDT 무기한 선물 상장 코인 추출"""
    url = f"{BASE_URL}/instruments-info?category=linear"
    data = await fetch(session, url)
    if not data or 'result' not in data or 'list' not in data['result']:
        return []
    
    symbols = []
    current_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    
    for item in data['result']['list']:
        # USDT 무기한 선물만 필터링
        if item.get('quoteCoin') == 'USDT' and item.get('status') == 'Trading' and 'PERP' in item.get('symbol', ''):
            launch_time = int(item.get('launchTime', 0))
            if launch_time >= START_TIMESTAMP:
                symbols.append(item['symbol'])
                
    # 만약 PERP 필터로 안 잡히는 일반적인 USDT 쌍들 (예: BTCUSDT)
    if not symbols:
        for item in data['result']['list']:
            if item.get('quoteCoin') == 'USDT' and item.get('status') == 'Trading':
                launch_time = int(item.get('launchTime', 0))
                if launch_time >= START_TIMESTAMP:
                    symbols.append(item['symbol'])

    # 중복 제거 및 정렬
    symbols = sorted(list(set(symbols)))
    print(f"  📋 바이비트 선물 코인: {len(symbols)}개 발견 (2025+ 상장 필터 적용)")
    return symbols

# ——————————————————————————————————————————————————————
# DATA COLLECTION (BYBIT V5)
# ——————————————————————————————————————————————————————
async def get_bybit_ticker(session, symbol: str) -> dict:
    url = f"{BASE_URL}/tickers?category=linear&symbol={symbol}"
    data = await fetch(session, url)
    if data and 'result' in data and 'list' in data['result'] and len(data['result']['list']) > 0:
        return data['result']['list'][0]
    return {}

async def get_funding_rate(session, symbol: str) -> float:
    ticker = await get_bybit_ticker(session, symbol)
    return float(ticker.get('fundingRate', 0)) * 100

async def get_mark_index(session, symbol: str) -> tuple:
    ticker = await get_bybit_ticker(session, symbol)
    mark   = float(ticker.get('markPrice', 0))
    index  = float(ticker.get('indexPrice', 0))
    diff   = ((mark - index) / index * 100) if index > 0 else 0
    return mark, index, diff

async def get_oi_multitimeframe(session, symbol: str) -> dict:
    url = f"{BASE_URL}/open-interest?category=linear&symbol={symbol}&intervalTime=1h&limit=25"
    data = await fetch(session, url)
    result = {"current": 0.0, "change_1h": 0.0, "change_4h": 0.0, "change_24h": 0.0}
    if data and 'result' in data and 'list' in data['result']:
        items = data['result']['list']
        if len(items) > 0:
            result["current"] = float(items[0].get('openInterest', 0))
            try:
                latest = result["current"]
                if len(items) >= 2  and float(items[1]['openInterest']) > 0: result["change_1h"]  = (latest - float(items[1]['openInterest'])) / float(items[1]['openInterest']) * 100
                if len(items) >= 5  and float(items[4]['openInterest']) > 0: result["change_4h"]  = (latest - float(items[4]['openInterest'])) / float(items[4]['openInterest']) * 100
                if len(items) >= 24 and float(items[-1]['openInterest']) > 0: result["change_24h"] = (latest - float(items[-1]['openInterest'])) / float(items[-1]['openInterest']) * 100
            except (KeyError, ZeroDivisionError, IndexError):
                pass
    return result

async def get_long_short_ratio(session, symbol: str) -> tuple:
    url = f"{BASE_URL}/account-ratio?category=linear&symbol={symbol}&period=5min&limit=1"
    data = await fetch(session, url)
    if data and 'result' in data and 'list' in data['result'] and len(data['result']['list']) > 0:
        buy = float(data['result']['list'][0].get('buyRatio', 0.5)) * 100
        sell = float(data['result']['list'][0].get('sellRatio', 0.5)) * 100
        return buy, sell
    return 50.0, 50.0

async def get_taker_buysell(session, symbol: str) -> tuple:
    url = f"{BASE_URL}/recent-trade?category=linear&symbol={symbol}&limit=100"
    data = await fetch(session, url)
    if data and 'result' in data and 'list' in data['result']:
        trades = data['result']['list']
        buy_vol = sum(float(t['size']) for t in trades if t['side'] == 'Buy')
        sell_vol = sum(float(t['size']) for t in trades if t['side'] == 'Sell')
        total = buy_vol + sell_vol
        if total > 0:
            return (buy_vol/total*100), (sell_vol/total*100)
    return 50.0, 50.0

async def get_orderbook_depth(session, symbol: str) -> dict:
    url = f"{BASE_URL}/orderbook?category=linear&symbol={symbol}&limit=50"
    data = await fetch(session, url)
    res = {"bid_depth": 0.0, "ask_depth": 0.0, "imbalance": 1.0}
    if data and 'result' in data:
        b = sum(float(x[0]) * float(x[1]) for x in data['result'].get('b', []))
        a = sum(float(x[0]) * float(x[1]) for x in data['result'].get('a', []))
        res["bid_depth"], res["ask_depth"] = b, a
        res["imbalance"] = (b / a) if a > 0 else 1.0
    return res

async def get_price_volume_extended(session, symbol: str) -> dict:
    t_url = f"{BASE_URL}/tickers?category=linear&symbol={symbol}"
    k_url = f"{BASE_URL}/kline?category=linear&symbol={symbol}&interval=60&limit=48"
    t_data, k_data = await asyncio.gather(fetch(session, t_url), fetch(session, k_url))
    
    res = {"price": 0.0, "price_change_1h": 0.0, "price_change_4h": 0.0, "price_change_24h": 0.0, "volume_24h": 0.0, "volume_change_pct": 0.0, "klines": []}
    
    if t_data and 'result' in t_data and 'list' in t_data['result'] and len(t_data['result']['list']) > 0:
        tick = t_data['result']['list'][0]
        res["price"] = float(tick.get('lastPrice', 0))
        res["price_change_24h"] = float(tick.get('price24hPcnt', 0)) * 100
        res["volume_24h"] = float(tick.get('turnover24h', 0))
        
    if k_data and 'result' in k_data and 'list' in k_data['result']:
        klines = k_data['result']['list'] # Bybit kline is [startTime, open, high, low, close, vol, turnover]
        res["klines"] = klines
        if len(klines) >= 2:
            try:
                now_c = float(klines[0][4])
                open_1h = float(klines[1][1])
                res["price_change_1h"] = (now_c - open_1h) / open_1h * 100 if open_1h > 0 else 0
                if len(klines) >= 5:
                    open_4h = float(klines[4][1])
                    res["price_change_4h"] = (now_c - open_4h) / open_4h * 100 if open_4h > 0 else 0
                
                recent_v = float(klines[0][6])
                past_vs = [float(k[6]) for k in klines[1:]]
                avg_v = sum(past_vs)/len(past_vs) if past_vs else 1
                res["volume_change_pct"] = (recent_v - avg_v) / avg_v * 100
            except: pass
    return res


# async def get_onchain_data(session, symbol: str) -> Optional[dict]:
#     """덱스스크리너에서 온체인 데이터 가져오기 (비활성화)"""
#     data = await fetch(session, f"https://api.dexscreener.com/latest/dex/search?q={symbol}")
#     if not data or 'pairs' not in data or not data['pairs']:
#         return None
#     main_pair  = max(data['pairs'], key=lambda x: x.get('liquidity', {}).get('usd', 0))
#     liquidity  = main_pair.get('liquidity', {}).get('usd', 0) or 0
#     fdv        = main_pair.get('fdv', 0) or 0
#     liq_ratio  = (liquidity / fdv * 100) if fdv > 0 else 0
#     return {
#         "liquidity": liquidity, "fdv": fdv,
#         "liq_ratio": liq_ratio, "chain": main_pair.get('chainId', 'unknown'),
#     }

# ══════════════════════════════════════════
# V5 신규: 펀딩비 히스토리 & velocity
# ══════════════════════════════════════════
async def get_funding_history(session, symbol: str) -> FundingHistory:
    """
    최근 8개 펀딩비 → velocity(변화 속도) 및 trend(방향) 계산
    velocity > 0 : 빠르게 양으로 이동 중 (세력 분배 신호)
    velocity < 0 : 빠르게 음으로 이동 중 (매집 심화)
    """
    url  = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}USDT&limit=8"
    data = await fetch(session, url)
    fh   = FundingHistory()
    if not data:
        return fh
    try:
        fh.rates = [float(d['fundingRate']) * 100 for d in data]
        if len(fh.rates) >= 4:
            # 선형 회귀 기울기로 velocity 추정
            n      = len(fh.rates)
            xs     = list(range(n))
            x_mean = sum(xs) / n
            y_mean = sum(fh.rates) / n
            num    = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, fh.rates))
            den    = sum((x - x_mean) ** 2 for x in xs)
            fh.velocity = (num / den) if den != 0 else 0.0
            if   fh.velocity >  0.01: fh.trend = "RISING"
            elif fh.velocity < -0.01: fh.trend = "FALLING"
            else:                     fh.trend = "FLAT"
    except (KeyError, ValueError, ZeroDivisionError):
        pass
    return fh

# ══════════════════════════════════════════
# V5 신규: ATR 계산
# ══════════════════════════════════════════
def calculate_atr(klines: list, period: int = ATR_PERIOD) -> float:
    """
    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = 14기간 평균 TR
    """
    if len(klines) < period + 1:
        return 0.0
    try:
        trs = []
        for i in range(1, len(klines)):
            high       = float(klines[i][2])
            low        = float(klines[i][3])
            prev_close = float(klines[i-1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period
    except (IndexError, ValueError, ZeroDivisionError):
        return 0.0

# ══════════════════════════════════════════
# V5 신규: 청산 클러스터 추정
# ══════════════════════════════════════════
async def get_liquidation_clusters(session, symbol: str, current_price: float) -> dict:
    """바이비트 강제청산 내역 분석 (V5)"""
    url = f"{BASE_URL}/liquidation?category=linear&symbol={symbol}&limit=50"
    data = await fetch(session, url)
    result = {"clusters": [], "above_price": 0.0, "above_vol": 0.0, "below_price": 0.0, "below_vol": 0.0}
    
    if not data or 'result' not in data or 'list' not in data['result'] or not data['result']['list']:
        return _estimate_liq_clusters(current_price)

    try:
        above_bins = defaultdict(float)
        below_bins = defaultdict(float)
        for item in data['result']['list']:
            # Bybit liquidation item: {symbol, side, size, price, updatedTime}
            p = float(item.get('price', 0))
            v = p * float(item.get('size', 0))
            if p == 0: continue
            
            diff = (p - current_price) / current_price * 100
            bucket = round(diff / 1.0) * 1.0 # 1% bin
            
            if p > current_price: above_bins[bucket] += v
            else: below_bins[bucket] += v
            
        if above_bins:
            top_a = max(above_bins, key=above_bins.get)
            result["above_price"] = current_price * (1 + top_a / 100)
            result["above_vol"] = above_bins[top_a]
        if below_bins:
            top_b = max(below_bins, key=below_bins.get)
            result["below_price"] = current_price * (1 + top_b / 100)
            result["below_vol"] = below_bins[top_b]
            
        for b, v in sorted({**above_bins, **below_bins}.items()):
            price = current_price * (1 + b / 100)
            side = "SHORT_LIQ" if b > 0 else "LONG_LIQ"
            result["clusters"].append((round(price, 6), round(v, 2), side))
    except:
        return _estimate_liq_clusters(current_price)
    return result

def _estimate_liq_clusters(current_price: float) -> dict:
    """
    실제 청산 데이터 없을 때:
    일반 레버리지 분포(5x, 10x, 20x)로 예상 청산 가격 추정
    """
    est_above = current_price * 1.05   # 10x 롱 +5% 위에서 숏 청산
    est_below = current_price * 0.95   # 10x 숏 -5% 아래서 롱 청산
    return {
        "clusters":    [(est_above, 0, "SHORT_LIQ"), (est_below, 0, "LONG_LIQ")],
        "above_price": est_above,
        "above_vol":   0.0,
        "below_price": est_below,
        "below_vol":   0.0,
    }

# ═══════════════════════════════════════════════
# STEP 3: SCORING ENGINE (V4 유지 + V6 추가)
# ═══════════════════════════════════════════════

def _calc_squeeze_fuel(coin: CoinData) -> float:
    """
    V6: 숏 스퀴즈 폭발 잠재력 0~100 점수
    200%+ 급등의 핵심 조건을 복합 평가
      - 숏비율 (연료량)
      - 펀딩비 음의 깊이 (압축 강도)
      - OI 증가율 (트리거 속도)
      - 가격 고정 기간 (코일 탄성)
      - 매수 체결 전환 (기폭 신호)
    """
    fuel = 0.0

    # 숏 비율: 55~75% 사이를 선형 스케일
    short_score = max(0.0, min(25.0, (coin.short_ratio - 50) * 1.25))
    fuel += short_score

    # 펀딩비: 0% ~ -0.5% → 0~30점
    fund_score = max(0.0, min(30.0, abs(min(coin.funding_rate, 0)) * 60))
    fuel += fund_score

    # OI 1h 증가율: 8%~30% → 0~20점
    oi_score = max(0.0, min(20.0, max(coin.oi_change_pct_1h, 0) * 0.87))
    fuel += oi_score

    # 가격 고정 (24h 변동 < 3%) → 10점 보너스
    if abs(coin.price_change_24h) < 3:
        fuel += 10.0

    # 매수 체결 우세 (58%+) → 15점 보너스
    if coin.taker_buy_ratio >= 58:
        fuel += 15.0

    # Ask 잔량 얇음 (imbalance > 2) → 추가 10점
    if coin.book_imbalance >= 2.0:
        fuel += min(10.0, (coin.book_imbalance - 2.0) * 5)

    return min(100.0, fuel)


def classify_pump_stage(coin: CoinData) -> str:
    is_neg_funding   = coin.funding_rate < -0.05
    is_deep_neg_fund = coin.funding_rate < -0.20
    is_oi_growing    = coin.oi_change_pct_24h > 10
    is_oi_surging    = coin.oi_change_pct_1h > 10 or coin.oi_change_pct_4h > 20
    is_oi_early      = coin.oi_change_pct_1h > MEGA_PUMP_OI_1H_MIN  # 8%+ 조기감지
    is_price_flat    = abs(coin.price_change_24h) < 3
    is_price_pumping = coin.price_change_1h > 3 or coin.price_change_4h > 5
    is_vol_spike     = coin.volume_change_pct > 150
    is_vol_low       = coin.volume_change_pct < -20
    is_short_heavy   = coin.short_ratio > 55
    is_short_extreme = coin.short_ratio > MEGA_PUMP_SHORT_RATIO_MIN  # 62%+
    is_taker_buying  = coin.taker_buy_ratio >= 58

    if is_neg_funding and is_oi_surging and is_vol_spike and is_short_heavy:
        return "🔥 IGNITION"
    if is_price_pumping and is_vol_spike and is_short_heavy:
        return "🔥 IGNITION"

    # V6: PRE_IGNITION — SPRING에서 IGNITION 직전 전환점
    # 가격은 아직 안 움직였지만 스퀴즈 연료가 최고조에 달한 상태
    if (is_price_flat and is_deep_neg_fund and is_short_extreme
            and is_oi_early and is_taker_buying):
        return "💥 PRE_IGNITION"
    if (is_price_flat and is_deep_neg_fund and is_short_extreme
            and coin.oi_change_pct_4h > 15):
        return "💥 PRE_IGNITION"

    if is_price_flat and is_oi_growing and is_vol_low and is_neg_funding:
        return "⚡ SPRING"
    if is_price_flat and is_oi_surging and abs(coin.price_change_1h) < 2:
        return "⚡ SPRING"
    if is_neg_funding and is_oi_growing and not is_price_pumping:
        return "🟢 ACCUMULATE"
    if is_neg_funding and is_short_heavy:
        return "🟢 ACCUMULATE"
    if coin.funding_rate > 0.05 and coin.price_change_24h > 10:
        return "⚪ DISTRIBUTE"
    return "⬜ NEUTRAL"

def calculate_score_v4(coin: CoinData) -> CoinData:
    W = SCORE_WEIGHTS
    if   coin.funding_rate < -0.5:  coin.score += W["funding_extreme"];  coin.score_reasons.append(f"🔴펀딩{coin.funding_rate:.3f}%")
    elif coin.funding_rate < -0.3:  coin.score += W["funding_very_neg"]; coin.score_reasons.append(f"🔴펀딩{coin.funding_rate:.3f}%")
    elif coin.funding_rate < -0.1:  coin.score += W["funding_negative"]; coin.score_reasons.append(f"🟠펀딩{coin.funding_rate:.3f}%")

    if   coin.oi_change_pct_24h >= 50: coin.score += W["oi_spike"];   coin.score_reasons.append(f"🔴OI24h+{coin.oi_change_pct_24h:.0f}%")
    elif coin.oi_change_pct_24h >= 20: coin.score += W["oi_growth"];  coin.score_reasons.append(f"🟠OI24h+{coin.oi_change_pct_24h:.0f}%")
    if   coin.oi_change_pct_1h  >= 15: coin.score += W["oi_surge_1h"]; coin.score_reasons.append(f"🔴OI1h+{coin.oi_change_pct_1h:.0f}%")
    if   coin.oi_change_pct_4h  >= 25: coin.score += W["oi_surge_4h"]; coin.score_reasons.append(f"🟠OI4h+{coin.oi_change_pct_4h:.0f}%")

    if   coin.short_ratio >= 60: coin.score += W["ls_ratio_short"]; coin.score_reasons.append(f"🔴숏{coin.short_ratio:.1f}%")
    elif coin.short_ratio >= 55: coin.score += W["ls_ratio_mid"];   coin.score_reasons.append(f"🟠숏{coin.short_ratio:.1f}%")
    if   coin.top_short_ratio >= 60: coin.score += W["top_trader_short"]; coin.score_reasons.append(f"🔴탑숏{coin.top_short_ratio:.1f}%")
    if   coin.top_long_ratio > 55 and coin.short_ratio > 55:
        coin.score += W["top_trader_diverge"]; coin.score_reasons.append("🟣괴리")

    if   coin.taker_buy_ratio  >= 60: coin.score += W["taker_buy_dominant"];  coin.score_reasons.append(f"🟢매수체결{coin.taker_buy_ratio:.0f}%")
    elif coin.taker_sell_ratio >= 60: coin.score += W["taker_sell_dominant"]; coin.score_reasons.append(f"🔵매도체결{coin.taker_sell_ratio:.0f}%")

    if   coin.book_imbalance >= 2.0: coin.score += W["orderbook_bid_heavy"]; coin.score_reasons.append(f"🟢Bid벽x{coin.book_imbalance:.1f}")
    elif coin.book_imbalance <= 0.5: coin.score += W["orderbook_ask_heavy"]; coin.score_reasons.append(f"🔵Ask벽x{1/coin.book_imbalance:.1f}")

    if   coin.volume_change_pct >= 400: coin.score += W["volume_extreme"]; coin.score_reasons.append(f"🔴거래량+{coin.volume_change_pct:.0f}%")
    elif coin.volume_change_pct >= 200: coin.score += W["volume_spike"];   coin.score_reasons.append(f"🟠거래량+{coin.volume_change_pct:.0f}%")

    if abs(coin.price_change_1h) >= 5:
        coin.score += W["price_momentum_1h"]; coin.score_reasons.append(f"🟡1h{coin.price_change_1h:+.1f}%")
    if abs(coin.price_change_24h) < 2 and coin.oi_change_pct_24h > 15:
        coin.score += W["price_compression"]; coin.score_reasons.append("⚡스프링압축")
    if coin.mark_index_diff_pct < -2:
        coin.score += W["mark_discount"]; coin.score_reasons.append(f"🟣마크할인{coin.mark_index_diff_pct:.1f}%")

    # if coin.liq_ratio > 0:
    #     if   coin.liq_ratio < 2.0: coin.score += W["liq_ratio_low"]; coin.score_reasons.append(f"🔴유동성{coin.liq_ratio:.2f}%")
    #     elif coin.liq_ratio < 5.0: coin.score += W["liq_ratio_mid"]; coin.score_reasons.append(f"🟠유동성{coin.liq_ratio:.2f}%")
    # if 0 < coin.fdv < 100_000_000:
    #     coin.score += W["fdv_small"]; coin.score_reasons.append(f"🟡FDV${coin.fdv/1e6:.1f}M")

    # 복합 시그니처
    has_neg_funding  = coin.funding_rate < -0.1
    has_deep_funding = coin.funding_rate < -0.20
    has_oi_increase  = coin.oi_change_pct_24h > 15
    has_short_heavy  = coin.short_ratio > 55
    has_short_extreme= coin.short_ratio > MEGA_PUMP_SHORT_RATIO_MIN  # 62%+
    has_vol_spike    = coin.volume_change_pct > 150
    has_price_flat   = abs(coin.price_change_24h) < 3
    has_oi_early     = coin.oi_change_pct_1h > MEGA_PUMP_OI_1H_MIN  # 8%+
    has_taker_buy    = coin.taker_buy_ratio >= 58

    if has_neg_funding and has_oi_increase and has_short_heavy:
        coin.score += W["signature_accumulation"]; coin.score_reasons.append("💀매집시그니처")
    if has_price_flat and coin.oi_change_pct_24h > 25 and coin.volume_change_pct < 50:
        coin.score += W["signature_spring"]; coin.score_reasons.append("💀스프링시그니처")
    if has_neg_funding and has_oi_increase and has_vol_spike and has_short_heavy:
        coin.score += W["signature_ignition"]; coin.score_reasons.append("☠️점화시그니처")

    # ── V6 신규: 200%+ 폭등 전용 시그니처 ──

    # 1. 코일 압축 극한: 가격 고정 + OI 35%+ 폭증 + 극음 펀딩
    if (has_price_flat and has_deep_funding and has_short_extreme
            and coin.oi_change_pct_24h > MEGA_PUMP_COIL_OI_24H):
        coin.score += W["coil_extreme"]; coin.score_reasons.append("🌀코일극한")

    # 2. 스퀴즈 연료 MAX: 숏62%+ + 극음펀딩 + OI 1h 조기급등
    if has_deep_funding and has_short_extreme and has_oi_early:
        coin.score += W["squeeze_fuel_max"]; coin.score_reasons.append("⚡스퀴즈MAX")

    # 3. PRE_IGNITION 직전 전환점: 매수체결 전환 + 가격아직고정
    if has_price_flat and has_taker_buy and has_deep_funding and has_oi_early:
        coin.score += W["pre_ignition"]; coin.score_reasons.append("💥PRE점화")

    # 4. OI 조기 급등 (8%~14%, 기존 15% 감지보다 빠름)
    if MEGA_PUMP_OI_1H_MIN <= coin.oi_change_pct_1h < 15:
        coin.score += W["oi_early_surge"]; coin.score_reasons.append(f"🟡OI조기+{coin.oi_change_pct_1h:.0f}%")

    # 5. 가격 고정 중 매수체결 우세 = 세력 시장가 매집
    if has_price_flat and has_taker_buy and has_neg_funding:
        coin.score += W["taker_flip"]; coin.score_reasons.append(f"🟢매집체결{coin.taker_buy_ratio:.0f}%")

    # 6. Ask 잔량 극소 (book_imbalance > 3x = 팔물량 거의 없음)
    if coin.book_imbalance >= 3.0:
        coin.score += W["orderbook_thin_ask"]; coin.score_reasons.append(f"🔴Ask극소x{coin.book_imbalance:.1f}")

    coin.pump_stage = classify_pump_stage(coin)
    return coin

# ══════════════════════════════════════════
# V5 신규: 펀딩비 velocity 보정
# ══════════════════════════════════════════
def apply_funding_velocity_score(coin: CoinData) -> CoinData:
    """
    펀딩비 가속도를 스코어에 반영
    FALLING trend (음방향 가속) → 매집 심화 → 보너스
    RISING trend  (양방향 가속) → 세력 탈출 → 페널티
    V6: velocity 임계값 -0.005 (기존 -0.01 대비 2배 민감)
    """
    fh = coin.funding_history
    # V6: MEGA_PUMP_FUNDING_VEL (-0.005) 임계값 사용 — 조기 감지
    if fh.velocity < MEGA_PUMP_FUNDING_VEL and coin.funding_rate < 0:
        coin.score += SCORE_WEIGHTS["funding_velocity_down"]
        coin.score_reasons.append(f"📉펀딩가속↓{fh.velocity:.4f}")
        # 극단적 음방향 가속 → 추가 보너스
        if fh.velocity < -0.03 and coin.funding_rate < -0.15:
            coin.score += SCORE_WEIGHTS["funding_extreme_v6"]
            coin.score_reasons.append(f"🔴펀딩극단가속{fh.velocity:.4f}")
    elif fh.trend == "RISING" and fh.velocity > 0.02:
        coin.score += SCORE_WEIGHTS["funding_velocity_up"]
        coin.score_reasons.append(f"📈펀딩전환↑{fh.velocity:.4f}")
    return coin

# ══════════════════════════════════════════
# V5 핵심: 덤프 트랩 감지
# ══════════════════════════════════════════
def detect_dump_trap(coin: CoinData) -> RiskProfile:
    """
    이미 고점을 지난 코인에 진입하는 '덤프 트랩' 감지
    청산당하는 가장 흔한 패턴:
    1. 이미 24h 15%+ 상승 → 늦은 진입
    2. 펀딩비 양전환 → 세력이 분배 시작
    3. OI 감소 반전 → 포지션 청산 중
    4. 거래량 급감 → 매수세 고갈
    5. 탑트레이더가 숏 → 스마트머니 역방향
    """
    rp = RiskProfile()
    trap_score = 0
    reasons    = []

    # ── 트랩 조건 판별 ──

    # 1. 이미 많이 오른 가격
    if coin.price_change_24h > DUMP_TRAP_PRICE_RISE_24H:
        trap_score += 30
        reasons.append(f"🚨24h+{coin.price_change_24h:.1f}% 이미 급등")
    if coin.price_change_4h > 8:
        trap_score += 20
        reasons.append(f"🚨4h+{coin.price_change_4h:.1f}% 단기 과열")

    # 2. 펀딩비 양전환 (세력이 롱으로 전환 = 분배 중)
    if coin.funding_rate > DUMP_TRAP_FUNDING_POS:
        trap_score += 25
        reasons.append(f"🚨펀딩비 양전환({coin.funding_rate:+.3f}%) → 분배 신호")
    elif coin.funding_rate > 0.05:
        trap_score += 10
        reasons.append(f"🟠펀딩비 상승 중({coin.funding_rate:+.3f}%)")

    # 3. 펀딩비 velocity 상승 (양 방향으로 빠르게 이동)
    if coin.funding_history.trend == "RISING" and coin.funding_rate > -0.05:
        trap_score += 15
        reasons.append(f"🚨펀딩비 상승 가속 → 세력 이탈 임박")

    # 4. OI 감소 반전 (포지션 청산 중)
    if coin.oi_change_pct_1h < DUMP_TRAP_OI_REVERSAL:
        trap_score += 25
        reasons.append(f"🚨OI 1h{coin.oi_change_pct_1h:.1f}% 급감 → 청산 중")
    elif coin.oi_change_pct_24h < -5 and coin.price_change_24h > 10:
        trap_score += 20
        reasons.append(f"🚨가격↑ + OI↓ 다이버전스 → 분배 확정")

    # 5. 거래량 고갈 (펌프 이후 관심 사라짐)
    if coin.volume_change_pct < -50 and coin.price_change_24h > 10:
        trap_score += 20
        coin.score += SCORE_WEIGHTS["vol_exhaustion"]
        reasons.append(f"🚨거래량 고갈({coin.volume_change_pct:.0f}%) → 펌프 종료")

    # 6. 탑트레이더 숏 + 일반 롱 (스마트머니 역방향)
    if coin.top_short_ratio > 60 and coin.long_ratio > 55:
        trap_score += 30
        coin.score += SCORE_WEIGHTS["whale_exit_signal"]
        reasons.append(f"🚨탑숏{coin.top_short_ratio:.0f}% + 일반롱{coin.long_ratio:.0f}% → 세력 이탈")

    # 7. 이미 DISTRIBUTION 단계
    if coin.pump_stage == "⚪ DISTRIBUTE":
        trap_score += 35
        reasons.append("🚨DISTRIBUTION 단계 → 절대 롱 금지")

    # ── 리스크 등급 산정 ──
    rp.dump_trap_reasons = reasons
    if   trap_score >= 80: rp.dump_trap_risk = "CRITICAL 🔴🔴🔴"
    elif trap_score >= 50: rp.dump_trap_risk = "HIGH 🔴🔴"
    elif trap_score >= 25: rp.dump_trap_risk = "MEDIUM 🟠"
    else:                  rp.dump_trap_risk = "LOW 🟢"

    return rp, trap_score

# ══════════════════════════════════════════
# V5 핵심: 리스크 기반 포지션 계산
# ══════════════════════════════════════════
def calculate_risk_profile(
    coin: CoinData,
    capital_usd: float = DEFAULT_CAPITAL_USD,
    trap_score: int = 0,
) -> RiskProfile:
    """
    ATR 기반 동적 손절 + 레버리지 추천
    트랩 점수에 따라 레버리지 자동 축소
    """
    rp, _ = detect_dump_trap(coin)
    rp.atr     = coin.atr
    rp.atr_pct = (coin.atr / coin.price * 100) if coin.price > 0 else 0

    price = coin.price
    if price <= 0:
        return rp

    # ── 손절가 = 현재가 - (1.5 * ATR) ──
    atr_stop   = coin.atr * 1.5 if coin.atr > 0 else price * 0.03  # ATR 없으면 3%
    stop_loss  = price - atr_stop
    stop_pct   = atr_stop / price * 100   # 손절까지 % 거리

    rp.stop_loss = max(stop_loss, price * 0.85)  # 최대 -15% 손절

    # ── 목표가 = R:R 기반 ──
    r          = price - rp.stop_loss           # 1R
    rp.target_1 = price + r * 1.0               # 1R (+손절폭)
    rp.target_2 = price + r * 2.0               # 2R
    rp.target_3 = price + r * 3.5               # 3.5R

    # ── 리스크 리워드 ──
    avg_target  = (rp.target_1 + rp.target_2) / 2
    rp.risk_reward = (avg_target - price) / (price - rp.stop_loss) if (price - rp.stop_loss) > 0 else 0

    # ── 레버리지 계산 ──
    # 기본: 손절 %의 역수 (손절 5% → 기본 레버리지 20x)
    # 트랩 점수로 축소, MAX_LEVERAGE로 상한
    base_leverage = min(100 / stop_pct, MAX_LEVERAGE) if stop_pct > 0 else 1.0
    # 트랩 점수에 따른 레버리지 페널티
    trap_multiplier = 1.0
    if   trap_score >= 80: trap_multiplier = 0.0    # 진입 금지
    elif trap_score >= 50: trap_multiplier = 0.3    # 70% 축소
    elif trap_score >= 25: trap_multiplier = 0.6    # 40% 축소

    rp.max_safe_leverage     = round(max(base_leverage, 1.0), 1)
    rp.recommended_leverage  = round(max(base_leverage * trap_multiplier, 1.0), 1)

    # ── 포지션 크기 ──
    # 손실 허용액 = capital * RISK_PER_TRADE_PCT%
    max_loss_usd     = capital_usd * RISK_PER_TRADE_PCT / 100
    position_size    = (max_loss_usd / (stop_pct / 100)) if stop_pct > 0 else 0
    rp.position_size_usd = min(position_size, capital_usd * 0.5)  # 최대 자본의 50%

    # ── 진입 구간 ──
    rp.entry_zone_low  = price * 0.995
    rp.entry_zone_high = price * 1.005

    # ── 청산 클러스터 반영 ──
    if hasattr(coin, '_liq_data'):
        rp.liq_cluster_above = coin._liq_data.get("above_price", 0)
        rp.liq_cluster_below = coin._liq_data.get("below_price", 0)
        rp.liq_above_usd     = coin._liq_data.get("above_vol",   0)
        rp.liq_below_usd     = coin._liq_data.get("below_vol",   0)

    # ── DCA 플랜 (3분할 진입) ──
    rp.dca_plan = [
        {"entry": round(price * 1.000, 6), "size_pct": 40, "note": "시장가 1차"},
        {"entry": round(price * 0.985, 6), "size_pct": 35, "note": "-1.5% 지정가 2차"},
        {"entry": round(price * 0.970, 6), "size_pct": 25, "note": "-3.0% 지정가 3차"},
    ]

    # ── Entry Score ──
    entry_score = 50.0
    if coin.pump_stage in ("🟢 ACCUMULATE", "⚡ SPRING"):  entry_score += 20
    if coin.pump_stage == "🔥 IGNITION":                    entry_score += 10  # 이미 점화 = 약간 늦음
    if coin.pump_stage == "⚪ DISTRIBUTE":                  entry_score -= 40
    if coin.funding_rate < -0.1:                            entry_score += 15
    if rp.risk_reward > 2:                                  entry_score += 15
    if rp.risk_reward < 1:                                  entry_score -= 20
    entry_score -= trap_score * 0.4   # 트랩 점수만큼 진입 점수 감소
    rp.entry_score = max(0, min(100, entry_score))

    return rp

# ══════════════════════════════════════════
# V5 핵심: 탈출 경보 시스템
# ══════════════════════════════════════════
def calculate_exit_alert(coin: CoinData) -> ExitAlert:
    """
    보유 포지션에서 탈출해야 할 신호를 감지
    이 함수는 '지금 들고 있다면 나와야 하는가'를 평가
    """
    ea        = ExitAlert()
    exit_score = 0
    reasons   = []

    # 1. 펀딩비 양전환 (가장 강력한 탈출 신호)
    if coin.funding_rate > 0.3:
        exit_score += 40; reasons.append(f"🚨펀딩비 극양전({coin.funding_rate:+.3f}%) → 즉시 탈출")
    elif coin.funding_rate > 0.1:
        exit_score += 25; reasons.append(f"🟠펀딩비 양전({coin.funding_rate:+.3f}%) → 일부 익절")
    elif coin.funding_history.trend == "RISING" and coin.funding_rate > -0.05:
        exit_score += 15; reasons.append(f"📈펀딩 빠른 상승 → 탈출 준비")

    # 2. OI 급감 (포지션 청산 시작)
    if coin.oi_change_pct_1h < -15:
        exit_score += 35; reasons.append(f"🚨OI 1h{coin.oi_change_pct_1h:.1f}% 붕괴 → 강제청산 시작")
    elif coin.oi_change_pct_1h < -8:
        exit_score += 20; reasons.append(f"🟠OI 1h{coin.oi_change_pct_1h:.1f}% 감소 → 청산 의심")

    # 3. 탑트레이더 롱 전환 (세력이 먼저 팔기 시작)
    if coin.top_long_ratio > 65 and coin.price_change_1h > 3:
        exit_score += 30; reasons.append(f"🚨탑트레이더 롱{coin.top_long_ratio:.0f}% → 세력 매도 중")

    # 4. 거래량 고갈 (지속 상승 불가)
    if coin.volume_change_pct < -60 and coin.price_change_4h > 10:
        exit_score += 25; reasons.append(f"🚨거래량 고갈({coin.volume_change_pct:.0f}%) → 상승 동력 소진")

    # 5. 음봉 + 매도 체결 우세
    if coin.price_change_1h < -3 and coin.taker_sell_ratio > 65:
        exit_score += 30; reasons.append(f"🚨-{abs(coin.price_change_1h):.1f}% + 매도체결{coin.taker_sell_ratio:.0f}% → 추세 반전")

    # 6. Mark 프리미엄 (선물이 현물보다 비쌈 = 과열)
    if coin.mark_index_diff_pct > 2:
        exit_score += 15; reasons.append(f"🟠마크프리미엄+{coin.mark_index_diff_pct:.2f}% → 선물 과열")

    ea.exit_score  = min(100, exit_score)
    ea.exit_reasons = reasons

    if   exit_score >= 70: ea.urgency = "EMERGENCY 🚨"; ea.should_exit = True
    elif exit_score >= 45: ea.urgency = "URGENT ⚠️";    ea.should_exit = True
    elif exit_score >= 25: ea.urgency = "WATCH 👀";     ea.should_exit = False
    else:                  ea.urgency = "HOLD 🟢";      ea.should_exit = False

    return ea

# ═══════════════════════════════════════════════
# Z-SCORE (V4 동일)
# ═══════════════════════════════════════════════
def apply_z_scores(coins: list) -> list:
    if len(coins) < 3:
        return coins
    metrics = {
        "funding": [c.funding_rate         for c in coins],
        "oi_24h":  [c.oi_change_pct_24h    for c in coins],
        "oi_1h":   [c.oi_change_pct_1h     for c in coins],
        "short":   [c.short_ratio          for c in coins],
        "vol":     [c.volume_change_pct    for c in coins],
        "taker":   [c.taker_buy_ratio      for c in coins],
    }
    for key, values in metrics.items():
        try:
            mean  = statistics.mean(values)
            stdev = statistics.stdev(values)
            if stdev == 0:
                continue
            for i, c in enumerate(coins):
                c.z_scores[key] = round((values[i] - mean) / stdev, 2)
        except statistics.StatisticsError:
            pass
    for c in coins:
        extreme_count = sum(1 for v in c.z_scores.values() if abs(v) > 1.5)
        c.confidence  = min(1.0, extreme_count / 4)
    return coins

# ═══════════════════════════════════════════════
# STEP 4: FULL COIN ANALYSIS V5
# ═══════════════════════════════════════════════
async def analyze_coin_v5(session, symbol: str, capital_usd: float = DEFAULT_CAPITAL_USD) -> Optional[CoinData]:
    try:
        (
            funding, mark_data, oi_data, ls_data,
            taker, orderbook, price_vol, funding_hist,
        ) = await asyncio.gather(
            get_funding_rate(session, symbol),
            get_mark_index(session, symbol),
            get_oi_multitimeframe(session, symbol),
            get_long_short_ratio(session, symbol),
            get_taker_buysell(session, symbol),
            get_orderbook_depth(session, symbol),
            get_price_volume_extended(session, symbol),
            get_funding_history(session, symbol),
        )

        coin = CoinData(symbol=symbol)
        coin.scan_time             = datetime.datetime.now(datetime.timezone.utc).isoformat()
        coin.funding_rate          = funding
        coin.mark_price, coin.index_price, coin.mark_index_diff_pct = mark_data
        coin.oi_current            = oi_data["current"]
        coin.oi_change_pct_1h      = oi_data["change_1h"]
        coin.oi_change_pct_4h      = oi_data["change_4h"]
        coin.oi_change_pct_24h     = oi_data["change_24h"]
        coin.long_ratio, coin.short_ratio                           = ls_data
        coin.top_long_ratio, coin.top_short_ratio                   = ls_data # Bybit은 일단 Account Ratio로 대체
        coin.taker_buy_ratio, coin.taker_sell_ratio                 = taker
        coin.bid_depth_usd         = orderbook["bid_depth"]
        coin.ask_depth_usd         = orderbook["ask_depth"]
        coin.book_imbalance        = orderbook["imbalance"]
        coin.price                 = price_vol["price"]
        coin.price_change_1h       = price_vol["price_change_1h"]
        coin.price_change_4h       = price_vol["price_change_4h"]
        coin.price_change_24h      = price_vol["price_change_24h"]
        coin.volume_24h            = price_vol["volume_24h"]
        coin.volume_change_pct     = price_vol["volume_change_pct"]
        coin.klines_1h             = price_vol.get("klines", [])
        coin.funding_history       = funding_hist

        # ATR 계산 (Bybit kline format에 맞춤 [startTime, open, high, low, close, ...])
        if coin.klines_1h:
            trs = []
            for i in range(1, len(coin.klines_1h)):
                h, l = float(coin.klines_1h[i][2]), float(coin.klines_1h[i][3])
                pc = float(coin.klines_1h[i-1][4])
                trs.append(max(h-l, abs(h-pc), abs(l-pc)))
            coin.atr = sum(trs[-14:])/14 if trs else 0
        coin.atr_pct = (coin.atr / coin.price * 100) if coin.price > 0 else 0

        # 청산 클러스터
        liq_data = await get_liquidation_clusters(session, symbol, coin.price)
        coin._liq_data = liq_data

        coin = calculate_score_v4(coin)
        coin = apply_funding_velocity_score(coin)
        _, trap_score = detect_dump_trap(coin)
        coin.risk = calculate_risk_profile(coin, capital_usd, trap_score)
        coin.exit_alert = calculate_exit_alert(coin)

        return coin
    except:
        return None

# ═══════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════
def fmt_num(n: float) -> str:
    if n >= 1_000_000_000: return f"${n/1e9:.2f}B"
    if n >= 1_000_000:     return f"${n/1e6:.1f}M"
    if n >= 1_000:         return f"${n/1e3:.0f}K"
    return f"${n:.0f}"

def fmt_price(p: float) -> str:
    if p <= 0:     return "—"
    if p >= 1:     return f"${p:.4f}"
    if p >= 0.01:  return f"${p:.6f}"
    return f"${p:.8f}"

RISK_COLOR = {
    "LOW 🟢":          "✅",
    "MEDIUM 🟠":       "⚠️",
    "HIGH 🔴🔴":       "🛑",
    "CRITICAL 🔴🔴🔴": "☠️",
}

def print_summary(results: list):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n")
    print("╔" + "═" * 140 + "╗")
    print("║" + f" 💀 CRIME PUMP HUNTER V5 — {now}".ljust(140) + "║")
    print("╠" + "═" * 140 + "╣")
    header = (
        f" {'#':<3} {'COIN':<8} {'점수':<5} {'단계':<16} {'트랩':<8} {'진입점':<6} "
        f"{'펀딩':<9} {'OI1h':<7} {'OI24h':<7} {'숏%':<6} {'탑숏%':<7} "
        f"{'1h%':<7} {'레버리지':<7} {'손절':<10} {'R:R':<6} {'신호'}"
    )
    print(f"║{header}")
    print("╠" + "═" * 140 + "╣")

    for i, c in enumerate(results[:30], 1):
        if   c.score >= 120: danger = "🔴🔴🔴"
        elif c.score >= 80:  danger = "🔴🔴 "
        elif c.score >= 50:  danger = "🟠   "
        else:                danger = "🟡   "

        trap_icon  = RISK_COLOR.get(c.risk.dump_trap_risk, "?")
        entry_bar  = f"{c.risk.entry_score:.0f}pt"
        lev_str    = f"x{c.risk.recommended_leverage:.0f}" if c.risk.recommended_leverage > 0 else "진입금지"
        sl_str     = fmt_price(c.risk.stop_loss)
        rr_str     = f"{c.risk.risk_reward:.1f}R"
        fuel       = _calc_squeeze_fuel(c)
        fuel_str   = f"💥{fuel:.0f}" if fuel >= 70 else f"{fuel:.0f}"
        # PRE_IGNITION 단계 강조
        stage_disp = f"🚨{c.pump_stage}" if "PRE_IGNITION" in c.pump_stage else c.pump_stage

        line = (
            f" {i:<3} {c.symbol:<8} {danger}{c.score:<4} {stage_disp:<20} {trap_icon:<6} {entry_bar:<8}"
            f"{c.funding_rate:+.3f}% {c.oi_change_pct_1h:+.0f}%{'':>2} "
            f"{c.oi_change_pct_24h:+.0f}%{'':>2} "
            f"{c.short_ratio:.0f}%{'':>2} {fuel_str:<7} "
            f"{c.price_change_1h:+.1f}%{'':>1} "
            f"{lev_str:<8} {sl_str:<12} {rr_str:<6} "
            f"{' '.join(c.score_reasons[:3])}"
        )
        print(f"║{line}")
    print("╚" + "═" * 140 + "╝")

def print_deep_dive_v5(coin: CoinData, rank: int, capital_usd: float = DEFAULT_CAPITAL_USD):
    """V5 핵심: 리스크 관리 + 청산 클러스터 포함 상세 분석"""
    rp = coin.risk
    ea = coin.exit_alert
    fh = coin.funding_history

    # ── 헤더 ──
    stage_prefix = "🚨🚨🚨" if coin.pump_stage == "💥 PRE_IGNITION" else ""
    print(f"\n{'═' * 75}")
    print(f"  💀 #{rank} {coin.symbol}  |  점수: {coin.score}  |  단계: {stage_prefix}{coin.pump_stage}")
    print(f"  트랩 리스크: {rp.dump_trap_risk}   진입점수: {rp.entry_score:.0f}/100   탈출경보: {ea.urgency}")

    # V6: 스퀴즈 연료 게이지 출력
    squeeze_fuel = _calc_squeeze_fuel(coin)
    fuel_bar = "█" * int(squeeze_fuel / 10) + "░" * (10 - int(squeeze_fuel / 10))
    print(f"  💥 스퀴즈 연료: [{fuel_bar}] {squeeze_fuel:.0f}/100  {'← 200%+ 폭등 잠재력' if squeeze_fuel >= 70 else ''}")
    print(f"{'═' * 75}")

    # ── 덤프 트랩 경고 ──
    if rp.dump_trap_reasons:
        print(f"\n  🚨 덤프 트랩 경고:")
        for r in rp.dump_trap_reasons:
            print(f"     {r}")

    # ── 탈출 경보 ──
    if ea.exit_reasons:
        print(f"\n  {'🚨' if ea.should_exit else '👀'} 탈출 경보 ({ea.urgency}) [score={ea.exit_score:.0f}]:")
        for r in ea.exit_reasons:
            print(f"     {r}")

    print(f"\n  ┌─ 선물 시장")
    print(f"  │  가격: {fmt_price(coin.price)}  |  ATR(1h): {fmt_price(coin.atr)} ({coin.atr_pct:.2f}%)")
    print(f"  │  펀딩: {coin.funding_rate:+.4f}%  velocity: {fh.velocity:+.5f}  trend: {fh.trend}")
    if fh.rates:
        rate_str = " → ".join(f"{r:+.3f}%" for r in fh.rates[-4:])
        print(f"  │  펀딩이력: {rate_str}")
    print(f"  │  OI:  현재 {coin.oi_current:,.0f}  | 1h {coin.oi_change_pct_1h:+.1f}%  | 4h {coin.oi_change_pct_4h:+.1f}%  | 24h {coin.oi_change_pct_24h:+.1f}%")
    print(f"  │  Mark: {fmt_price(coin.mark_price)}  Index: {fmt_price(coin.index_price)}  괴리: {coin.mark_index_diff_pct:+.3f}%")

    print(f"  │")
    print(f"  ├─ 포지션 분석")
    print(f"  │  일반 L/S:     롱 {coin.long_ratio:.1f}% / 숏 {coin.short_ratio:.1f}%")
    print(f"  │  탑트레이더:   롱 {coin.top_long_ratio:.1f}% / 숏 {coin.top_short_ratio:.1f}%")
    print(f"  │  Taker:        매수 {coin.taker_buy_ratio:.1f}% / 매도 {coin.taker_sell_ratio:.1f}%")
    print(f"  │  1h: {coin.price_change_1h:+.2f}%  4h: {coin.price_change_4h:+.2f}%  24h: {coin.price_change_24h:+.2f}%")

    print(f"  │")
    print(f"  ├─ 🛡️  리스크 관리  (자본 ${capital_usd:,.0f} 기준)")
    print(f"  │")
    print(f"  │  ┌─────────────────────────────────────────────┐")
    print(f"  │  │  진입 구간:   {fmt_price(rp.entry_zone_low)} ~ {fmt_price(rp.entry_zone_high)}")
    
    stop_pct_str = f"({((rp.stop_loss/coin.price-1)*100):+.1f}%)" if coin.price > 0 else "(—%)"
    print(f"  │  │  손   절:     {fmt_price(rp.stop_loss)}  {stop_pct_str}")
    
    t1_pct_str = f"({((rp.target_1/coin.price-1)*100):+.1f}%)" if coin.price > 0 else "(—%)"
    print(f"  │  │  목표1(1R):   {fmt_price(rp.target_1)}  {t1_pct_str}")
    
    t2_pct_str = f"({((rp.target_2/coin.price-1)*100):+.1f}%)" if coin.price > 0 else "(—%)"
    print(f"  │  │  목표2(2R):   {fmt_price(rp.target_2)}  {t2_pct_str}")
    
    t3_pct_str = f"({((rp.target_3/coin.price-1)*100):+.1f}%)" if coin.price > 0 else "(—%)"
    print(f"  │  │  목표3(3.5R): {fmt_price(rp.target_3)}  {t3_pct_str}")
    print(f"  │  │  손익비:      {rp.risk_reward:.2f}R")
    print(f"  │  │")
    print(f"  │  │  추천 레버리지:  x{rp.recommended_leverage:.0f}  (최대 안전: x{rp.max_safe_leverage:.0f})")
    print(f"  │  │  포지션 크기:   ${rp.position_size_usd:,.0f}  (자본의 {rp.position_size_usd/capital_usd*100:.0f}%)")
    print(f"  │  └─────────────────────────────────────────────┘")

    print(f"  │")
    print(f"  ├─ 📍 청산 클러스터")
    if rp.liq_cluster_above > 0:
        print(f"  │  위 청산 밀집: {fmt_price(rp.liq_cluster_above)}  (숏 청산 → 롱에 유리)")
    else:
        est_above = coin.price * 1.05
        print(f"  │  위 청산 추정: {fmt_price(est_above)}  (+5% 추정, 데이터 부족)")
    if rp.liq_cluster_below > 0:
        print(f"  │  아래 청산 밀집: {fmt_price(rp.liq_cluster_below)}  ⚠️ 세력 롱 청산 타겟 가능")
    else:
        est_below = coin.price * 0.95
        print(f"  │  아래 청산 추정: {fmt_price(est_below)}  (-5% 추정, 데이터 부족)")

    print(f"  │")
    print(f"  ├─ 📐 분할진입 플랜 (DCA)")
    for step in rp.dca_plan:
        print(f"  │  {step['note']}: {fmt_price(step['entry'])}  ({step['size_pct']}%)")

    print(f"  │")
    print(f"  ├─ 📊 Z-Scores")
    for k, v in coin.z_scores.items():
        bar = "█" * min(int(abs(v) * 3), 15)
        direction = "▲" if v > 0 else "▼"
        print(f"  │  {k:<10}: {v:+.2f} {direction} {bar}")

    print(f"  │")
    print(f"  └─ 신호: {' | '.join(coin.score_reasons)}")
    print()

# ═══════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════
async def send_telegram_alert(session, coin: CoinData):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    rp = coin.risk
    ea = coin.exit_alert
    trap_icon = RISK_COLOR.get(rp.dump_trap_risk, "?")

    exit_block = ""
    if ea.should_exit:
        exit_block = f"\n🚨 *탈출 경보*: {ea.urgency}\n" + "\n".join(ea.exit_reasons[:3])

    fuel = _calc_squeeze_fuel(coin)
    fuel_bar = "█" * int(fuel / 10) + "░" * (10 - int(fuel / 10))
    pre_tag = "🚨🚨 *PRE_IGNITION 포착* 🚨🚨\n" if "PRE_IGNITION" in coin.pump_stage else ""

    msg = (
        f"💀 *Crime Pump Alert V6*\n\n"
        f"{pre_tag}"
        f"*{coin.symbol}*  Score: {coin.score}  |  {coin.pump_stage}\n"
        f"트랩리스크: {rp.dump_trap_risk}  {trap_icon}\n"
        f"진입점수: {rp.entry_score:.0f}/100\n"
        f"💥 스퀴즈연료: [{fuel_bar}] {fuel:.0f}/100\n\n"
        f"펀딩: {coin.funding_rate:+.3f}% ({coin.funding_history.trend})\n"
        f"OI: 1h {coin.oi_change_pct_1h:+.1f}% | 24h {coin.oi_change_pct_24h:+.1f}%\n"
        f"숏비율: {coin.short_ratio:.0f}%  탑숏: {coin.top_short_ratio:.0f}%\n"
        f"매수체결: {coin.taker_buy_ratio:.0f}%\n\n"
        f"━━━ 리스크 관리 ━━━\n"
        f"진입: {fmt_price(rp.entry_zone_low)} ~ {fmt_price(rp.entry_zone_high)}\n"
        f"손절: {fmt_price(rp.stop_loss)}  목표: {fmt_price(rp.target_2)}\n"
        f"레버리지: x{rp.recommended_leverage:.0f}  R:R={rp.risk_reward:.1f}\n"
        f"{exit_block}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        await session.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"
        })
    except Exception:
        pass

# ═══════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════
def save_csv(results: list, filename: str = ""):
    if not filename:
        filename = f"pump_v5_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow([
            "순위", "코인", "점수", "단계", "신뢰도",
            "트랩리스크", "진입점수", "탈출경보",
            "펀딩%", "펀딩trend", "OI_1h%", "OI_4h%", "OI_24h%",
            "숏%", "탑숏%", "체결매수%", "1h%", "4h%", "24h%",
            "ATR%", "손절가", "목표1", "목표2", "레버리지", "R:R",
            "신호"
        ])
        for i, c in enumerate(results, 1):
            rp = c.risk
            ea = c.exit_alert
            w.writerow([
                i, c.symbol, c.score, c.pump_stage, f"{c.confidence:.2f}",
                rp.dump_trap_risk, f"{rp.entry_score:.0f}", ea.urgency,
                f"{c.funding_rate:.4f}", c.funding_history.trend,
                f"{c.oi_change_pct_1h:.2f}", f"{c.oi_change_pct_4h:.2f}", f"{c.oi_change_pct_24h:.2f}",
                f"{c.short_ratio:.1f}", f"{c.top_short_ratio:.1f}", f"{c.taker_buy_ratio:.1f}",
                f"{c.price_change_1h:.2f}", f"{c.price_change_4h:.2f}", f"{c.price_change_24h:.2f}",
                f"{c.atr_pct:.2f}", fmt_price(rp.stop_loss), fmt_price(rp.target_1), fmt_price(rp.target_2),
                f"{rp.recommended_leverage:.0f}", f"{rp.risk_reward:.2f}",
                " | ".join(c.score_reasons)
            ])
    print(f"  💾 {filename} 저장 완료")
    return filename

def save_json_snapshot(results: list, filename: str = ""):
    if not filename:
        filename = f"snapshot_v5_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
    data = []
    for c in results:
        data.append({
            "symbol": c.symbol, "score": c.score, "stage": c.pump_stage,
            "confidence": c.confidence, "scan_time": c.scan_time,
            "trap_risk": c.risk.dump_trap_risk, "entry_score": c.risk.entry_score,
            "exit_urgency": c.exit_alert.urgency,
            "funding": c.funding_rate, "funding_trend": c.funding_history.trend,
            "oi_1h": c.oi_change_pct_1h, "oi_4h": c.oi_change_pct_4h, "oi_24h": c.oi_change_pct_24h,
            "short_ratio": c.short_ratio, "top_short": c.top_short_ratio,
            "taker_buy": c.taker_buy_ratio, "price": c.price,
            "price_1h": c.price_change_1h, "price_4h": c.price_change_4h, "price_24h": c.price_change_24h,
            "atr_pct": c.atr_pct, "stop_loss": c.risk.stop_loss,
            "target_1": c.risk.target_1, "target_2": c.risk.target_2,
            "leverage": c.risk.recommended_leverage, "rr": c.risk.risk_reward,
            "volume_24h": c.volume_24h,
            "z_scores": c.z_scores, "reasons": c.score_reasons,
            "trap_reasons": c.risk.dump_trap_reasons, "exit_reasons": c.exit_alert.exit_reasons,
        })
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📸 {filename} 스냅샷 저장 완료")

# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════
async def run_scan(session, capital_usd: float = DEFAULT_CAPITAL_USD) -> list:
    print("🔍 [1/4] 타겟 코인 추출...")
    symbols = await get_target_symbols(session)
    print(f"  ✅ 2025년 이후 상장 선물 코인: {len(symbols)}개\n")
    if not symbols:
        print("❌ 조건에 맞는 코인 없음")
        return []

    print(f"📊 [2/4] {len(symbols)}개 병렬 분석 중 (V5 지표: 청산클러스터 + ATR + 펀딩velocity)...")
    results     = []
    batch_size  = 15  # V5는 API 더 많이 씀
    for i in range(0, len(symbols), batch_size):
        batch        = symbols[i:i + batch_size]
        batch_results = await asyncio.gather(*[analyze_coin_v5(session, s, capital_usd) for s in batch])
        results.extend([r for r in batch_results if r is not None])
        done = min(i + batch_size, len(symbols))
        print(f"  ⏳ {done}/{len(symbols)} ({done/len(symbols)*100:.0f}%)")
        if i + batch_size < len(symbols):
            await asyncio.sleep(1.2)

    print(f"\n📈 [3/4] Z-Score 정규화 + 랭킹...")
    results = apply_z_scores(results)
    results.sort(key=lambda x: x.score, reverse=True)

    print(f"✅ [4/4] 분석 완료 — {len(results)}개\n")
    print_summary(results)

    print("\n" + "═" * 75)
    print("  🔬 TOP 5 상세 분석 (리스크 관리 포함)")
    print("═" * 75)
    for i, c in enumerate(results[:5], 1):
        print_deep_dive_v5(c, i, capital_usd)

    # V6: PRE_IGNITION 포착 — 200%+ 잠재 코인
    pre_ignition = [c for c in results if "PRE_IGNITION" in c.pump_stage]
    high_fuel    = [c for c in results
                    if "PRE_IGNITION" not in c.pump_stage and _calc_squeeze_fuel(c) >= 70]
    if pre_ignition or high_fuel:
        print("\n" + "💥" * 30)
        print("  💥 V6: 200%+ 폭등 잠재 코인 (PRE_IGNITION + 연료MAX)")
        print("💥" * 30)
        for c in (pre_ignition + high_fuel)[:8]:
            fuel = _calc_squeeze_fuel(c)
            print(f"  {c.symbol:<10} 단계:{c.pump_stage:<22} 연료:{fuel:.0f}/100  "
                  f"펀딩:{c.funding_rate:+.3f}%  숏:{c.short_ratio:.0f}%  "
                  f"OI1h:{c.oi_change_pct_1h:+.0f}%  신호:{' '.join(c.score_reasons[:3])}")

    # 즉시 탈출 경보
    exit_alerts = [c for c in results if c.exit_alert.should_exit]
    if exit_alerts:
        print("\n" + "🚨" * 35)
        print("  🚨 긴급 탈출 경보 대상")
        print("🚨" * 35)
        for c in exit_alerts[:5]:
            print(f"  {c.symbol}  {c.exit_alert.urgency}  |  {' | '.join(c.exit_alert.exit_reasons[:2])}")

    return results

async def main():
    print("╔" + "═" * 65 + "╗")
    print("║" + " 💀 Crime Pump Hunter V5 — Liquidation Guard Edition".ljust(65) + "║")
    print("╚" + "═" * 65 + "╝\n")

    # 자본 설정
    cap_input   = input(f"💰 거래 자본 USD (기본 {DEFAULT_CAPITAL_USD}): ").strip()
    capital_usd = float(cap_input) if cap_input.replace('.','').isdigit() else DEFAULT_CAPITAL_USD
    print(f"  → 자본: ${capital_usd:,.0f}  |  트레이드당 최대 손실: ${capital_usd * RISK_PER_TRADE_PCT / 100:,.0f} ({RISK_PER_TRADE_PCT}%)\n")

    connector = aiohttp.TCPConnector(limit=25)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Telegram Chat ID 확인
        await ensure_chat_id(session)
        
        print("실행 모드:")
        print("  [1] 단일 스캔")
        print("  [2] 연속 모니터링")
        print("  [3] 보유 포지션 탈출 감시 (심볼 직접 입력)")
        mode = input("모드 (1/2/3): ").strip()

        if mode == "3":
            # 보유 포지션 탈출 감시
            symbols_input = input("감시할 코인 (콤마 구분, 예: BTC,ETH,XRP): ").strip().upper()
            watch_symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]
            if not watch_symbols:
                print("코인을 입력해주세요")
                return
            interval = int(input(f"스캔 간격 초 (기본 60): ").strip() or "60")
            print(f"\n👁️  탈출 감시 시작: {watch_symbols}  (Ctrl+C 종료)\n")
            try:
                while True:
                    for symbol in watch_symbols:
                        coin = await analyze_coin_v5(session, symbol, capital_usd)
                        if coin:
                            ea = coin.exit_alert
                            now = datetime.datetime.now().strftime("%H:%M:%S")
                            status = f"[{now}] {symbol:<8} {ea.urgency:<20} 점수:{ea.exit_score:.0f}"
                            if ea.exit_reasons:
                                status += f"  → {ea.exit_reasons[0]}"
                            print(status)
                            if ea.should_exit and TELEGRAM_BOT_TOKEN:
                                await send_telegram_alert(session, coin)
                    print()
                    await asyncio.sleep(interval)
            except KeyboardInterrupt:
                print("\n🛑 감시 종료")

        elif mode == "2":
            interval = int(input(f"리스캔 간격 초 (기본 {MONITOR_INTERVAL_SEC}): ").strip() or str(MONITOR_INTERVAL_SEC))
            print(f"\n🔄 연속 모니터링 시작 (Ctrl+C 종료)\n")
            prev_scores = {}
            scan_count  = 0
            results     = []
            try:
                while True:
                    scan_count += 1
                    print(f"\n{'━' * 65}")
                    print(f"  📡 스캔 #{scan_count}")
                    print(f"{'━' * 65}\n")
                    
                    results = await run_scan(session, capital_usd)
                    
                    for c in results[:10]:
                        prev  = prev_scores.get(c.symbol, 0)
                        delta = c.score - prev
                        if delta >= 20:
                            print(f"  ⚠️  {c.symbol} 점수 급상승: {prev} → {c.score} (+{delta})")
                        if c.score >= SCORE_ALERT_THRESHOLD:
                            await send_telegram_alert(session, c)
                    # V6: PRE_IGNITION 코인 즉시 알림 (점수 무관)
                    for c in results:
                        if "PRE_IGNITION" in c.pump_stage:
                            fuel = _calc_squeeze_fuel(c)
                            print(f"  💥 PRE_IGNITION: {c.symbol}  연료:{fuel:.0f}  펀딩:{c.funding_rate:+.3f}%")
                            await send_telegram_alert(session, c)
                            
                    prev_scores = {c.symbol: c.score for c in results}
                    save_json_snapshot(results)
                    print(f"\n  ⏰ 다음 스캔: {interval}초 후...")
                    await asyncio.sleep(interval)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n\n🛑 모니터링 중단")
                if results and input("마지막 결과 CSV 저장? (y/n): ").strip().lower() == 'y':
                    save_csv(results)

        else:
            results = await run_scan(session, capital_usd)
            if results:
                print()
                if input("💾 CSV 저장? (y/n): ").strip().lower() == 'y':
                    save_csv(results)
                if input("📸 JSON 스냅샷 저장? (y/n): ").strip().lower() == 'y':
                    save_json_snapshot(results)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
