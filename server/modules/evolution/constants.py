import os
from typing import List


ALL_AGENT_IDS = [
    "momentum_hunter",
    "mean_reverter",
    "macro_trader",
    "chaos_agent",
]


def _parse_csv_agent_ids(raw: str) -> List[str]:
    selected: List[str] = []
    for token in raw.split(","):
        agent_id = token.strip()
        if not agent_id:
            continue
        if agent_id in ALL_AGENT_IDS and agent_id not in selected:
            selected.append(agent_id)
    return selected


def _resolve_active_agent_ids() -> List[str]:
    raw_ids = (os.getenv("EVOLUTION_ACTIVE_AGENT_IDS", "") or "").strip()
    parsed_ids = _parse_csv_agent_ids(raw_ids)
    if parsed_ids:
        return parsed_ids

    raw_count = (os.getenv("EVOLUTION_AGENT_COUNT", "1") or "1").strip()
    try:
        count = int(raw_count)
    except ValueError:
        count = 1
    count = max(1, min(count, len(ALL_AGENT_IDS)))
    return list(ALL_AGENT_IDS[:count])


# 전체 에이전트 카탈로그 (유효성 검사/채팅 라우팅용)
AGENT_IDS = list(ALL_AGENT_IDS)

# 실제 자동 루프 대상 에이전트 목록 (env 제어, 기본값 1개)
ACTIVE_AGENT_IDS = _resolve_active_agent_ids()

BANNED_INDICATORS = [
    "RSI", "MACD", "볼린저밴드", "이동평균", "SMA", "EMA",
    "스토캐스틱", "Stochastic", "Golden Cross", "ATR (단독 사용)"
]

CROSS_DOMAIN_SEEDS = [
    "포식자-피식자 Lotka-Volterra 방정식: 매수자(포식자)와 매도자(피식자) 개체수 동역학",
    "열역학 엔트로피: 가격 분포의 무질서도가 최대일 때를 반전 신호로",
    "지진 전조현상 Omori 법칙: 큰 움직임 이후 여진 패턴으로 추가 방향 예측",
    "면역계 항원-항체 반응: 가격 이상치를 항원으로 보고 시스템이 '항체'를 생성하는 패턴",
    "음향학 공명 주파수: 가격 진동의 고유 주파수 분석으로 공명 구간 탐지",
    "철새 무리 방향 전환: 거래량 급변과 가격 방향 전환의 임계점 감지",
    "지질학 퇴적 지층: 가격 지지/저항을 '압력 지층'으로 보고 지층 붕괴 시점 포착",
    "유체역학 난류 전환: 가격 흐름이 층류에서 난류로 전환되는 레이놀즈 수 계산",
    "생태계 천이 이론: 시장이 '개척종 → 극상종' 단계를 거치는 패턴 포착",
    "양자 터널링 효과: 지지/저항을 '퍼텐셜 장벽'으로 보고 작은 확률의 돌파 포착",
]

PERSONAS = [
    {
        "name": "노이즈 고고학자",
        "worldview": "다른 모든 참가자가 버리는 노이즈 안에 진짜 알파가 있다. 쓰레기통을 뒤진다.",
        "style": "분 단위 노이즈 패턴, 극단값, 이상치에 집중",
    },
    {
        "name": "시간 지질학자",
        "worldview": "가격은 지층이다. 수백만 건의 의사결정이 퇴적된 압력 지점을 찾는다.",
        "style": "오래된 고점/저점의 기억 효과, 시간 거리 가중치",
    },
    {
        "name": "군중 심리 역이용자",
        "worldview": "군중이 패닉할 때가 기회다. 두려움 지수가 극단일 때 반대로 간다.",
        "style": "거래량 급증 후 반전, 극단적 캔들 이후 되돌림",
    },
    {
        "name": "시장 기생충",
        "worldview": "큰 참가자들의 손절 흐름이 먹이다. 억지로 만들어진 움직임을 추적한다.",
        "style": "유동성 사냥 패턴, 스탑헌팅 구간 이후 반전",
    },
    {
        "name": "시간 차익거래자",
        "worldview": "같은 정보도 시간축에서 다르게 소화된다. 반응 속도의 차이를 이용한다.",
        "style": "멀티 타임프레임 비동기 신호, 시간 지연 상관관계",
    },
]
