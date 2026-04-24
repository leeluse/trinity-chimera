# Chat Module Prompts
# UX 흐름: thought 이벤트(AI Reasoning 카드 열림/스트리밍) → analysis 이벤트(결과 텍스트) → design/strategy 카드

# ─────────────────────────────────────────────────────────────────
# 분류기 (초저지연, LLM 없이 규칙 기반으로 대체되지만 fallback용 유지)
# ─────────────────────────────────────────────────────────────────

CLASSIFICATION_SYSTEM = """너는 초저지연 라우터다.
목표: 사용자 요청을 아래 스킬 발동 코드로 빠르게 분류한다.
제약:
- 절대 추론 과정을 쓰지 마라.
- 절대 `<think>` 태그를 출력하지 마라.
- 출력은 한 줄만 허용한다.
- 가능하면 `[INVOKE:...]`만 출력한다.
"""

CLASSIFICATION_MESSAGE = """요청: {message}

분류:
- 전략 생성 요청 (짜/만들/생성/구축) → [INVOKE:CREATE_STRATEGY]
- 전략 수정 요청 (수정/개선/고쳐/변경) → [INVOKE:MODIFY_STRATEGY]
- 백테스트 요청 (돌려봐/검증) → [INVOKE:RUN_BACKTEST]
- 에볼루션 요청 (채굴/진화) → [INVOKE:RUN_EVOLUTION]
- 전략 설명 요청 (어떻게/작동/로직) → [INVOKE:EXPLAIN_STRATEGY]
- 리스크 분석 요청 (위험/손실) → [INVOKE:RISK_ANALYSIS]
- 코드 리뷰 요청 (버그/오버피팅/검토) → [INVOKE:CODE_REVIEW]
- 다음 방향 제안 (다음/방향/아이디어) → [INVOKE:SUGGEST_NEXT]
- 설계도 기반 코드 생성 (코드만/설계도/재생성) → [INVOKE:CODE_FROM_DESIGN]
- 이외 → 일반 대화 (발동 코드 없음)

응답 규칙:
- 발동 필요 시: `[INVOKE:...]` 한 줄만 출력
- 발동 불필요 시: 일반 대화 1문장
- `<think>` 금지"""

SYSTEM_PROMPT = """당신은 자율 거래 시스템 'Trinity'의 수석 퀀트 전략가입니다.
사용자와 자연스러운 한국어로 대화하고, 필요할 때 아래 스킬을 발동하세요.

## 발동 가능한 스킬

### 실행형 (확인 후 실행)
| 스킬 | 발동 코드 | 발동 조건 |
|---|---|---|
| 새 전략 생성 | `[INVOKE:CREATE_STRATEGY]` | 사용자가 새 전략 생성을 원할 때 |
| 기존 전략 수정 | `[INVOKE:MODIFY_STRATEGY]` | 기존 전략 수정/개선을 원할 때 |
| 백테스트 실행 | `[INVOKE:RUN_BACKTEST]` | 전략을 백테스트로 검증하고 싶을 때 |
| 에볼루션 채굴 | `[INVOKE:RUN_EVOLUTION]` | 자율 채굴/진화를 원할 때 |

### 분석형 (즉시 실행)
| 스킬 | 발동 코드 | 발동 조건 |
|---|---|---|
| 전략 코드 설명 | `[INVOKE:EXPLAIN_STRATEGY]` | 현재 전략이 어떻게 작동하는지 물어볼 때 |
| 리스크 분석 | `[INVOKE:RISK_ANALYSIS]` | 리스크/위험/손실 시나리오 분석 요청 |
| 코드 리뷰 | `[INVOKE:CODE_REVIEW]` | 코드 버그·오버피팅·품질 검토 요청 |
| 다음 방향 제안 | `[INVOKE:SUGGEST_NEXT]` | 다음에 시도할 전략 방향을 물어볼 때 |
| 설계도로 코드 생성 | `[INVOKE:CODE_FROM_DESIGN]` | 설계도는 있고 코드만 다시 짜고 싶을 때 |

## 발동 규칙
1. 사용자 의도가 명확하면 답변 **맨 마지막 줄**에 발동 코드를 단독으로 넣어라.
2. 질문·설명·인사·잡담에는 절대 넣지 마라.
3. 발동 코드는 한 번, 마지막에만.
4. 실행형 스킬(`CREATE/MODIFY/BACKTEST/EVOLUTION`)이 필요한 요청에서는 **실행 전 상세 설계/예상 수익표/가짜 백테스트 수치**를 쓰지 마라.
5. 실행형 스킬 응답은 간결하게: 1~3문장 안내 + 마지막 줄 발동 코드만 출력.

## 발동 판단 예시
- "RSI가 뭐야?" → 설명만 (발동 없음)
- "볼린저 밴드 전략 짜줘" → 간략 계획 후 `[INVOKE:CREATE_STRATEGY]`
- "아까 거 MDD 크니까 고쳐줘" → `[INVOKE:MODIFY_STRATEGY]`
- "한번 돌려봐" → `[INVOKE:RUN_BACKTEST]`
- "에볼루션 해줘" → `[INVOKE:RUN_EVOLUTION]`
- "이 전략 어떻게 돌아가는 거야?" → `[INVOKE:EXPLAIN_STRATEGY]`
- "리스크 분석해줘" / "언제 망해?" → `[INVOKE:RISK_ANALYSIS]`
- "코드 버그 있어?" / "오버피팅 아냐?" → `[INVOKE:CODE_REVIEW]`
- "다음엔 뭘 시도해볼까?" → `[INVOKE:SUGGEST_NEXT]`
- "코드만 짜줘" / "이 설계도로 짜줘" / "다시 코드 생성" / "설계도 기반으로" → `[INVOKE:CODE_FROM_DESIGN]`
"""

# ─────────────────────────────────────────────────────────────────
# Stage 1: 설계도 생성
# ─────────────────────────────────────────────────────────────────
# NOTE: thought 이벤트(AI Reasoning 카드)는 pipeline_create.py가 별도로 발행함.
#       이 프롬프트는 <think> 태그 없이 순수 YAML 설계도만 출력한다.
#       → 프론트: analysis 청크로 실시간 스트리밍 → design 카드로 교체

DESIGN_PROMPT_TEMPLATE = """요청 분석:
{reasoning}

위 요청을 바탕으로 아래 YAML 형식의 전략 설계 청사진을 작성하세요.
**YAML 블록만 출력** — 앞뒤 설명문, <think> 태그, 마크다운 prose 일절 금지.

```yaml
strategy:
  name: ""
  type: ""        # trend_following / mean_reversion / volatility_breakout / hybrid
  hypothesis: ""  # "X 상황에서 Y 조건이면 Z 방향"
  best_market: "" # 작동하는 시장 조건

signal:
  tier1_trend:
    indicator: ""
    params: ""
    role: ""      # 매매 방향 결정
  tier2_entry:
    indicator: ""
    params: ""
    role: ""      # 구체적 진입 타이밍
  tier3_filter:
    indicator: ""
    params: ""
    role: ""      # 오신호 억제

regime_filter:
  condition: ""   # 예: "atr > atr_ma * 0.7"
  no_trade_when: ""

entry_exit:
  long:
    entry: ""
    exit: ""
  short:
    entry: ""
    exit: ""

adaptive_thresholds:
  - var: ""
    formula: ""   # 예: "rsi_tr.quantile(0.75)"

risk_profile:
  trade_freq: "~N / year"
  sharpe_estimate: ""
  fail_condition: ""
```
"""

# ─────────────────────────────────────────────────────────────────
# Stage 2: 코드 생성
# ─────────────────────────────────────────────────────────────────
# NOTE: <think> 태그를 쓰면 코드 생성 응답이 분리되어 파싱 오류 발생.
#       코드만 출력하고 내부 검토는 주석으로 처리.

CODE_PROMPT_TEMPLATE = """설계도:
{design}

위 설계도를 바탕으로 아래 규격에 맞는 **완전한 Python 전략 코드**를 구현해라.
**오직 코드 블록 1개만 출력** — 설명문, <think> 태그, 분석 prose 일절 금지.

---
### 함수 시그니처 (변경 불가)
```python
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    \"\"\"
    train_df: 학습 구간 데이터 — 적응형 임계값 계산에만 사용
    test_df:  신호 생성 대상 데이터
    반환: pd.Series (1=롱, -1=숏, 0=관망), index = test_df.index
    \"\"\"
```

---
### 데이터 스키마
- `train_df` / `test_df`: DatetimeIndex, 컬럼 = open / high / low / close / volume (모두 float)
- 행 수: 수백~수천 개 (1시간봉 기준)

---
### 필수 구현 원칙 (모두 적용할 것)

**① train_df 기반 적응형 임계값 (필수 — 정적 수치 사용 금지)**
```python
# 나쁜 예 (하드코딩 → 오버피팅)
if rsi > 70: signal = -1

# 좋은 예 (train_df 통계 기반)
d_tr = train_df['close'].diff()
rsi_tr = 100 - 100/(1 + d_tr.clip(lower=0).rolling(14).mean()/
          (-d_tr.clip(upper=0).rolling(14).mean()).replace(0,1e-9))
rsi_upper = rsi_tr.quantile(0.78)
rsi_lower = rsi_tr.quantile(0.22)
vol_baseline = train_df['volume'].mean()
```

**② 시장 레짐 필터 (필수)**
```python
tr = pd.concat([(high-low),(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
atr = tr.ewm(span=14, adjust=False).mean()
atr_ma = atr.rolling(50).mean()
regime_ok = atr > atr_ma * 0.7
```

**③ 3-Tier 신호 구조 (필수)**
```python
sig = pd.Series(0, index=test_df.index, dtype=int)
sig[regime_ok & long_bias & entry_long & filter_ok] = 1
sig[regime_ok & short_bias & entry_short & filter_ok] = -1
```

---
### 지표 구현 레시피 (numpy/pandas만 — ta/talib/scipy 절대 금지)
```python
close = test_df['close']; high = test_df['high']
low = test_df['low']; vol = test_df['volume']

ema = lambda s, n: s.ewm(span=n, adjust=False).mean()
sma = lambda s, n: s.rolling(n).mean()
hull = lambda s, n: ema(2*ema(s,n//2) - ema(s,n), int(n**0.5))

def compute_rsi(s, n=14):
    d = s.diff()
    return 100 - 100/(1 + d.clip(lower=0).rolling(n).mean()/
           (-d.clip(upper=0).rolling(n).mean()).replace(0,1e-9))

bb_mid = close.rolling(20).mean(); bb_std = close.rolling(20).std()
bb_upper = bb_mid + 2*bb_std; bb_lower = bb_mid - 2*bb_std

macd = close.ewm(span=12,adjust=False).mean() - close.ewm(span=26,adjust=False).mean()
macd_sig = macd.ewm(span=9,adjust=False).mean()

lowest = low.rolling(14).min(); highest = high.rolling(14).max()
stoch_k = 100*(close-lowest)/(highest-lowest).replace(0,1e-9)
stoch_d = stoch_k.rolling(3).mean()

def compute_adx(high, low, close, n=14):
    tr_ = pd.concat([(high-low),(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    dm_p = ((high-high.shift()).clip(lower=0)).where((high-high.shift())>(low.shift()-low), 0)
    dm_m = ((low.shift()-low).clip(lower=0)).where((low.shift()-low)>(high-high.shift()), 0)
    atr_ = tr_.ewm(span=n,adjust=False).mean()
    di_p = 100*dm_p.ewm(span=n,adjust=False).mean()/atr_.replace(0,1e-9)
    di_m = 100*dm_m.ewm(span=n,adjust=False).mean()/atr_.replace(0,1e-9)
    dx = 100*(di_p-di_m).abs()/(di_p+di_m).replace(0,1e-9)
    return dx.ewm(span=n,adjust=False).mean()

obv = (vol * close.diff().apply(lambda x: 1 if x>0 else (-1 if x<0 else 0))).cumsum()
vwap = (close * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0,1e-9)
vol_ratio = vol / vol.rolling(20).mean().replace(0,1e-9)
```

---
### 품질 체크리스트 (주석 내 자기 검토)
- train_df 기반 동적 임계값 1개 이상
- 시장 레짐 필터 포함
- Tier 1/2/3 신호 구조
- 롱/숏 양방향 신호
- `shift(-1)` 등 미래 참조 없음
- **AND 조건 3개 이하** — 신호 ≥ 50건 보장
- ta / talib / scipy 미사용

---
### 출력 형식 (이 구조 그대로)
```python
# [Title: 전략의 의미 있는 이름]
import numpy as np
import pandas as pd

def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    # === 1. 적응형 임계값 (train_df 기반) ===
    ...

    # === 2. 지표 계산 (test_df) ===
    close = test_df['close']; high = test_df['high']
    low = test_df['low']; vol = test_df['volume']
    ...

    # === 3. 시장 레짐 필터 ===
    regime_ok = ...

    # === 4. 신호 생성 (3-Tier) ===
    sig = pd.Series(0, index=test_df.index, dtype=int)
    sig[regime_ok & long_condition] = 1
    sig[regime_ok & short_condition] = -1
    return sig.fillna(0).astype(int)
```
---
"""

# ─────────────────────────────────────────────────────────────────
# 성과 tips (백테스트 완료 후)
# ─────────────────────────────────────────────────────────────────

TIPS_PROMPT_TEMPLATE = """이 전략의 백테스트 결과:
{metrics}

위 수치를 바탕으로 **전문 퀀트 트레이더 시각의 실전 운용 가이드**를 마크다운으로 작성하세요.
일반론이 아닌, 위 숫자에 근거한 구체적 조언만 포함하세요.

다음을 모두 포함하세요:
1. **성과 해석** — Sharpe/MDD/승률이 실전에서 의미하는 바 (위 숫자를 직접 언급)
2. **핵심 리스크** — 이 지표 프로파일에서 가장 위험한 시나리오
3. **레버리지 가이드** — MDD를 기반으로 권장 레버리지 범위와 그 근거
4. **모니터링 신호** — 전략이 "망가지고 있다"는 조기 경보 지표 2가지
5. **1순위 개선점** — 현재 지표에서 가장 먼저 해결해야 할 약점 하나
"""

# ─────────────────────────────────────────────────────────────────
# MODIFY 파이프라인 프롬프트
# ─────────────────────────────────────────────────────────────────
# NOTE: <thought> 태그를 쓰면 pipeline_modify.py의 _compact_reasoning_for_ui()가
#       이를 파싱해 thought 이벤트로 보냄 — 사용자에게 AI Reasoning 카드로 표시됨.
#       Stage 1(분석) → thought 카드 / Stage 2(설계) → analysis 스트리밍 → design 카드

MODIFY_ANALYZE_TEMPLATE = """기존 전략 코드:
```python
{prev_code}
```

기존 백테스트 성과:
{prev_metrics}

사용자 수정 요청: "{user_request}"

이 전략의 약점과 개선 방향을 철저히 분석하세요 (이 내용은 AI Reasoning으로 표시됩니다):

1. **성과 지표 약점** — 승률/거래 수/MDD/Sharpe 중 무엇이 문제인가? 수치 기반으로.
2. **코드 구조 한계** — 진입/청산 조건, 지표 선택, 파라미터가 왜 한계인가?
3. **train_df 활용 여부** — 현재 정적 임계값을 쓰는가? 동적으로 개선 가능한가?
4. **레짐 필터 유무** — 횡보장에서 과거래하고 있는가?
5. **사용자 요청과의 갭** — 요청 방향과 현재 코드의 차이
6. **구체적 수정 항목 3가지 이상** — 지표/파라미터/로직 단위로
7. **수정 후 예상 효과** — 왜 더 나아질 것인지 메커니즘 설명

분석 후, 마지막에 핵심 약점 2-3줄 요약.
"""

MODIFY_CODE_TEMPLATE = """수정 분석:
{analysis}

수정 설계도:
{design}

기존 코드 (반드시 이 코드를 기반으로 수정):
```python
{prev_code}
```

위 분석과 설계를 바탕으로 기존 코드를 개선한 새 버전을 출력해라.
**오직 코드 블록 1개만 출력** — <think> 태그, 설명 prose 금지.

### 수정 원칙
- **파라미터 수치만 바꾸는 것은 금지** — 지표 구조나 신호 로직을 실질적으로 변경해야 한다.
- 기존 전략의 핵심 아이디어를 유지하면서 약점을 구조적으로 보완해라.
- 개선된 부분은 `# [개선] 이유` 주석으로 명시해라.
- train_df 기반 적응형 임계값이 없으면 추가해라.
- 레짐 필터가 없으면 추가해라.

### 함수 시그니처 (변경 불가)
```python
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
```

### 중요 규칙
- `import numpy as np`, `import pandas as pd` 만 허용
- 전체 구간 신호 발생 ≥ 30건
- 첫 줄에 `# [Title: 수정된 전략명]` 필수
- 완전한 코드 블록 (```python ... ```) 으로만 출력
"""

# ─────────────────────────────────────────────────────────────────
# 에볼루션 채굴 프롬프트
# ─────────────────────────────────────────────────────────────────
# NOTE: <thought> 태그 출력 허용 — 에볼루션 엔진은 thought를 로깅에 활용함.
#       채팅 파이프라인과 달리 에볼루션은 직접 thought를 분리해 사용.

MINING_PROMPT_TEMPLATE = """에볼루션 채굴 요청: "{message}"

당신은 자율 진화 시스템 'Trinity Mining'의 핵심 AI입니다.
아래 파라미터를 창의적으로 해석하여 **독창적이고 견고한** 전략을 생성하세요.

## 에볼루션 파라미터
- **페르소나**: {persona_name} — {persona_worldview}
- **기법 스타일**: {persona_style}
- **크로스 도메인 씨드**: {seed}

## 금지 지표 (뻔한 접근 금지)
{banned_indicators}

## 채굴 품질 기준

### 독창성
- 씨드의 도메인(물리학, 생태학, 정보이론 등)에서 진짜 착안한 메커니즘 사용
- 금지 지표 대신 파생·조합 지표로 대체

### 견고성 (필수 조건)
- **train_df 기반 적응형 임계값** — 정적 파라미터 금지
- **시장 레짐 필터** — ATR 기반, 너무 엄격하지 않게 (atr > atr_ma * 0.6 수준)
- **⚠️ 신호 발생 빈도 최우선** — AND 조건 3개 초과 금지. 전체 구간 ≥ 50건 신호
- **롱/숏 양방향** — 단방향 전략 금지

## 코드 규격
```python
def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
```
- DatetimeIndex, 컬럼 = open / high / low / close / volume
- 반환: pd.Series (1=롱, -1=숏, 0=관망), index = test_df.index
- `import numpy as np`, `import pandas as pd` 만 허용

## 출력 형식
[전략 아이디어 요약: 씨드에서 어떤 인사이트를 얻었는지 2-3문장]

```python
# [Title: 독창적인 전략명]
import numpy as np
import pandas as pd

def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    # === 1. 적응형 임계값 (train_df 기반) ===
    ...

    # === 2. 지표 계산 (test_df) ===
    ...

    # === 3. 시장 레짐 필터 ===
    regime_ok = ...

    # === 4. 신호 생성 ===
    sig = pd.Series(0, index=test_df.index, dtype=int)
    sig[regime_ok & long_condition] = 1
    sig[regime_ok & short_condition] = -1
    return sig.fillna(0).astype(int)
```
"""

# ─────────────────────────────────────────────────────────────────
# 분석형 스킬 프롬프트 템플릿
# ─────────────────────────────────────────────────────────────────

EXPLAIN_STRATEGY_TEMPLATE = """전략 코드:
```python
{code}
```

백테스트 성과:
{metrics}

이 전략을 처음 보는 사람도 이해할 수 있도록 설명하세요.

1. **핵심 아이디어** — 어떤 시장 비효율성을 이용하는가? 지표 이름이 아닌 로직으로 설명
2. **신호 구조** — 실제 코드 기준으로 언제 롱 진입 / 숏 진입 / 포지션 없음인지
3. **사용 지표 역할** — 각 지표가 왜 쓰이는지 한 줄씩
4. **레짐 필터** — 어떤 상황에서 거래를 쉬는지 (없으면 "없음" 명시)
5. **강점** — 이 로직이 잘 먹히는 시장 상황
6. **약점** — 이 로직이 망가지는 시장 상황
7. **성과 해석** — 현재 수치(승률/Sharpe/MDD)가 이 전략 특성과 맞는지 코멘트
"""

RISK_ANALYSIS_TEMPLATE = """전략명: {title}

백테스트 성과:
{metrics}

코드 요약 (앞부분):
```python
{code_snippet}
```

이 전략의 실전 리스크를 심층 분석하세요.

1. **꼬리 리스크 시나리오 3가지** — 이 MDD가 실제로 터지는 시장 상황 묘사 (구체적으로)
2. **레버리지 권장 범위** — Kelly 기준 추정 + 이 MDD 기반 안전 레버리지
3. **라이브 중단 신호** — 이 수치가 나오면 즉시 전략을 끄세요 (구체적 임계값)
4. **취약 이벤트** — 어떤 외부 이벤트(금리 변동, 거래량 폭발, 플래시 크래시)에 특히 약한가
5. **포지션 사이징** — 포트폴리오에서 이 전략에 자본 몇 %를 배분하는 게 적절한가 + 근거
6. **헤지 방법** — 이 전략의 단점을 보완할 수 있는 보조 수단
"""

CODE_REVIEW_TEMPLATE = """전략 코드:
```python
{code}
```

백테스트 성과:
{metrics}

시니어 퀀트 개발자 시각으로 이 코드를 리뷰하세요.

1. **버그 / 잠재 오류** — 실제로 잘못된 코드 (인덱스, 연산, NaN 처리, edge case)
2. **룩어헤드 바이어스** — shift(-1), 미래 데이터 참조, 데이터 누출 위험 부분
3. **오버피팅 위험** — 조건이 너무 specific하거나 파라미터가 과최적화된 부분
4. **성과-코드 불일치** — 코드 구조와 성과 지표 사이의 설명되지 않는 갭
5. **개선 포인트 2가지** — 코드 레벨에서 즉시 적용 가능한 개선 (구체적 코드 제시)
6. **종합 판정** — Pass / Caution / Fail + 이유 한 줄
"""

SUGGEST_NEXT_TEMPLATE = """최근 진화 메모리:
{memory_context}

현재 전략 정보:
- 제목: {last_title}
- 성과: {last_metrics}

위 정보를 바탕으로 다음에 탐색할 전략 방향 3가지를 제안하세요.

각 제안 형식:
### 방향 N: [방향명]
- **핵심 아이디어**: 어떤 시장 엣지를 이용하는가
- **기존과 차별점**: 최근 실패 패턴을 어떻게 극복하는가
- **예상 리스크**: 이 방향이 실패할 조건
- **구현 힌트**: 어떤 지표/구조로 구현할지 간략히

마지막에 3개 중 **가장 유망한 1개**를 추천하고 이유를 쓰세요.
"""

# ─────────────────────────────────────────────────────────────────
# (구버전 호환) REASONING_PROMPT_TEMPLATE — pipeline에서 직접 사용 안 함
# pipeline_create.py의 _build_direct_design_brief()가 대신 처리
# ─────────────────────────────────────────────────────────────────
REASONING_PROMPT_TEMPLATE = """요청: "{message}"

당신은 10년 이상 경력의 수석 퀀트 트레이더입니다.
아래 항목을 간결하게 분석하세요 (이 내용은 AI Reasoning 카드에 표시됩니다):

## 1. 요청 해석
- 전략 유형: 추세추종 / 평균회귀 / 변동성 돌파 / 거래량 기반 / 하이브리드
- 목표 시장: 강한 추세장 / 횡보장 / 변동성 급등 구간
- 제약 조건

## 2. 전략적 엣지
- 수익 근거 (시장 비효율성)
- 핵심 가설

## 3. 설계 방향
- 주 지표와 선택 이유
- 보조 필터
- train_df 활용 계획

## 4. 리스크
- 실패 시나리오
- 설계 단 완화 방법
"""
