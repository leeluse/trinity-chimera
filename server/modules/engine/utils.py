import re
from typing import Any, Dict, Tuple
from datetime import datetime, timedelta

# -------------------------------------------------------------------------
# [Helper] 심볼 추출: 텍스트 메시지에서 BTCUSDT 같은 코인 심볼 패턴을 찾아냄
# -------------------------------------------------------------------------
def extract_symbol(message: str, fallback: str = "BTCUSDT") -> str:
    m = re.search(r"\b([A-Z]{2,10}USDT)\b", message.upper())
    if m: return m.group(1)
    m = re.search(r"\b([A-Z]{2,10})/(USDT|USD)\b", message.upper())
    if m: return f"{m.group(1)}{m.group(2)}"
    return fallback.upper()

# -------------------------------------------------------------------------
# [Helper] 타임프레임 추출: 메시지에서 1m, 1h 등 거래 주기 패턴을 식별
# -------------------------------------------------------------------------
def extract_timeframe(message: str, fallback: str = "1h") -> str:
    m = re.search(r"\b(1m|5m|15m|30m|1h|4h|1d)\b", (message or "").lower())
    return m.group(1) if m else fallback

# -------------------------------------------------------------------------
# [Helper] 날짜 해결: 컨텍스트에서 백테스트 기간을 가져오거나 기본 120일 설정
# -------------------------------------------------------------------------
def resolve_backtest_dates(context: Dict[str, Any]) -> Tuple[str, str]:
    start = str(context.get("start_date") or "").strip()
    end = str(context.get("end_date") or "").strip()
    if start and end:
        return start, end

    end_dt = datetime.utcnow().date()
    start_dt = end_dt - timedelta(days=120)
    return start_dt.isoformat(), end_dt.isoformat()

# -------------------------------------------------------------------------
# [Helper] 안전한 실수 변환: 갑작스러운 None이나 문자열 에러를 방지하며 float 변환
# -------------------------------------------------------------------------
def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
