# Coline (UI/UX Design) Phase 1 완료 보고

**역할:** UI/UX 디자인 및 모니터링 인터페이스 개발  
**할당량:** 50% (2.5일/주)  
**기간:** 2026-04-05 ~ 2026-04-19 (2주)  
**상태:** ✅ 완료 (2026-04-05)

---

## 1. 실행 요약

TRINITY-CHIMERY Phase 1의 트레이딩 시스템을 기반으로 한 실시간 모니터링 및 데이터 시각화 컴포넌트를 설계 완료했습니다. React + TypeScript 기반의 UI/UX 아키텍처와 구체적인 컴포넌트 명세를 완료했습니다.

### 핵심 산출물 ✅ 완료
- [x] 모니터링 요구사항 분석
- [x] 데이터 시각화 컴포넌트 아키텍처
- [x] UI 컴포넌트 명세서
- [x] 기술 스택 설정

---

## 2. 모니터링 요구사항 분석

### 2.1 Phase 2 구현 현황 분석

#### 기존 데이터 구조

**AgentMetrics (dashboard/text_dashboard.py)**
```python
@dataclass
class AgentMetrics:
    name: str                    # 에이전트 식별자
    allocation: float           # 배분 비율 (0.0 ~ 1.0)
    pnl_24h: float             # 24시간 PnL
    pnl_7d: float              # 7일 PnL
    pnl_total: float           # 누적 PnL
    sharpe: float              # 샤프 비율
    max_drawdown: float       # 최대 낙폭
    win_rate: float           # 승률
    open_positions: int       # 보유 포지션
    regime: str               # 현재 레짐
    trade_count: int          # 거래 횟수
```

**PortfolioState (dashboard/text_dashboard.py)**
```python
@dataclass
class PortfolioState:
    total_capital: float
    total_pnl_24h: float
    total_pnl_7d: float
    total_pnl_total: float
    agent_metrics: Dict[str, AgentMetrics]
    timestamp: datetime
```

**Arena 시스템 (battle/arena.py)**
- AgentVote: 개별 에이전트 투표 결과
- weighted_vote: 자본 가중 투표 계산
- 배틀 스텝별 행동 로깅

**Portfolio 시스템 (battle/portfolio.py)**
- AgentAccount: 개별 에이전트 계좌 관리
- 거래 기록, 일별 PnL, 포트폴리오 히스토리
- Sharpe ratio, Max Drawdown, Win Rate 계산

### 2.2 시각화 요구사항 도출

| 기존 텍스트 출력 | 필요한 시각화 | 우선순위 |
|------------------|---------------|----------|
| 포트폴리오 상태 표 | 포트폴리오 가치 차트 (실시간) | 높음 |
| 에이전트 PnL 텍스트 | 에이전트별 성과 비교 차트 | 높음 |
| 거래 횟수 로깅 | 거래 실행 이력 테이블 | 중간 |
| 배틀 스텝 텍스트 | 시장 데이터 + 매매 오버레이 | 중간 |
| Arbiter 결정 텍스트 | Arbiter 의사결정 로그 뷰어 | 높음 |

### 2.3 Phase 3 통합 요구사항

**LLM Arbiter 인터페이스**
- 재배분 결정 시각화 (Before/After)
- 의사결정 근거 표시
- 경고/알림 플래그

**자가 전략 생성**
- 파라미터 변경 이력 표시
- 백테스트 결과 시각화

---

## 3. 시각화 컴포넌트 아키텍처

### 3.1 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                      Dashboard Application                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Portfolio  │  │   Agent     │  │     Arbiter       │  │
│  │   Charts    │  │ Performance │  │      Log          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Market    │  │   Battle    │  │   Trade History   │  │
│  │   Overlay   │  │   Monitor   │  │      Table        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    WebSocket Client Layer                 │
├─────────────────────────────────────────────────────────────┤
│                    Zustand State Store                      │
├─────────────────────────────────────────────────────────────┤
│  TRINITY-CHIMERY Backend (arena.py, portfolio.py, text_dashboard.py) │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 컴포넌트 계층 구조

```
App
├── DashboardLayout
│   ├── Header
│   │   ├── RealtimeIndicator
│   │   └── Navigation
│   ├── Sidebar
│   │   ├── AgentList
│   │   └── QuickFilters
│   └── MainContent
│       ├── PortfolioSummaryPanel
│       ├── ChartsSection
│       │   ├── PortfolioValueChart
│       │   └── AgentPerformanceChart
│       ├── AgentsSection
│       │   └── AgentCard[]
│       └── ArbiterSection
│           └── ArbiterDecisionLog
├── BattlePage
│   ├── BattleStepMonitor
│   ├── MarketDataOverlay
│   └── AgentActionPanel
└── SettingsPage
```

### 3.3 데이터 흐름

```
Backend → WebSocket → Zustand Store → React Components

1. Backend (arena.py)
   - step() 실행
   - AgentVote 집계
   - PortfolioState 업데이트
   - ArbiterDecision 생성

2. WebSocket Server
   - 상태 변경 브로드캐스트
   - 이벤트 타입: portfolio | battle_step | arbiter | trade

3. Frontend Store
   - Zustand 리스너
   - 실시간 상태 업데이트
   - 계산된 파생 상태

4. React Components
   - 구독 기반 리렌더링
   - Chart.js/D3 시각화 업데이트
```

---

## 4. 컴포넌트 상세 설계

### 4.1 핵심 시각화 컴포넌트

#### Chart A: PortfolioValueChart
**목적:** 포트폴리오 총 가치 + PnL 추적

**데이터 소스:**
- PortfolioState.total_capital
- PortfolioState.total_pnl_total
- 타임스탬프 기록

**시각화 유형:**
- 라인 차트: 총 자본 (USD)
- 영역 차트: 누적 PnL (%)
- 듀얼 Y축: 좌측 가치, 우측 PnL

**인터랙션:**
- 줌 (1h, 24h, 7d, 30d)
- 툴팁: 시간, 가치, 변화량
- 클릭: 해당 시점 상세 보기

**품질 요구사항:**
- 1초 이내 초기 렌더링
- 실시간 업데이트 (500ms)
- 최대 10,000개 데이터 포인트

---

#### Chart B: AgentPerformanceChart
**목적:** 에이전트별 성과 비교

**데이터 소스:**
- AgentMetrics (모든 필드)

**시각화 유형:**
- 바 차트: PnL, Sharpe, Win Rate 비교
- 레이더 차트: 다중 메트릭 프로필
- 타임라인: 각 에이전트 성과 추적

**인터랙션:**
- 메트릭 선택 드롭다운
- 정렬 (내림차순/오름차순)
- 에이전트 토글 표시/숨김

---

#### Chart C: MarketDataOverlay
**목적:** OHLCV + 에이전트 매매 시점

**데이터 소스:**
- MarketData (OHLCV)
- Trade[] (에이전트별 매매)

**시각화 유형:**
- 캔들스틱: OHLCV
- 마커: 매수/매돟 포인트
- 볼륨: 거래량 막대

**에이전트 마커 스타일:**
```typescript
const agentMarkers = {
  momentum_hunter: { color: '#F97316', symbol: 'triangle' },
  mean_reverter: { color: '#06B6D4', symbol: 'circle' },
  macro_trader: { color: '#8B5CF6', symbol: 'square' },
  chaos_agent: { color: '#EC4899', symbol: 'diamond' },
};
```

---

#### Table A: TradeHistoryTable
**목적:** 거래 실행 이력 필터링 및 정렬

**데이터 소스:**
- AgentAccount.trades

**컬럼:**
| 컬럼 | 내용 | 정렬 |
|------|------|------|
| Time | 거래 시각 | O |
| Agent | 에이전트 이름 | O |
| Action | 포지션 (-1 ~ +1) | O |
| Entry | 진입가 | O |
| Exit | 청산가 | O |
| PnL | 손익 | O |
| PnL% | 손익률 | O |

**기능:**
- 페이지네이션 (50개/페이지)
- 필터: 에이전트, 날짜 범위, 결과
- CSV/Excel 내보내기
- 행 클릭: 상세 거래 뷰

---

#### Panel A: AgentCard
**목적:** 개별 에이전트 상태 카드

**레이아웃 (카드):**
```
┌─────────────────────────────────────┐
│ 🔥 Momentum Hunter          [LIVE] │
├─────────────────────────────────────┤
│ Allocation:     30%                 │
│ PnL (24h):      +2.5% ▲            │
│ PnL (7d):       +8.2% ▲            │
│ PnL (Total):   +15.3% ▲            │
│ Sharpe:         1.85                │
│ Max DD:        -12.0%              │
│ Win Rate:      65.0%                │
│ Trades:        23                   │
│ Open:          2                    │
│ Regime:        🟢 Bull              │
├─────────────────────────────────────┤
│ [View Details]   [Reallocate]      │
└─────────────────────────────────────┘
```

---

#### Log A: ArbiterDecisionLog
**목적:** LLM Arbiter 결정 로깅

**데이터 소스:**
- ArbiterDecision

**레이아웃:**
```
┌─────────────────────────────────────┐
│ 🧠 Arbiter Decision                 │
│ 09:00:00 UTC                        │
├─────────────────────────────────────┤
│ Reasoning:                          │
│ Bull regime detected. Increasing    │
│ momentum and macro allocation...    │
├─────────────────────────────────────┤
│ Agent       Before → After   Δ      │
│ ─────────────────────────────────  │
│ Momentum    30.0%  → 35.0%  +5.0% │
│ MeanRev     30.0%  → 25.0%  -5.0% │
│ Macro       25.0%  → 30.0%  +5.0% │
│ Chaos       15.0%  → 10.0%  -5.0% │
├─────────────────────────────────────┤
│ ⚠️ Warnings:                        │
│ - Mean Reverter showing overfit     │
└─────────────────────────────────────┘
```

---

#### Monitor A: BattleStepMonitor
**목적:** 실시간 배틀 스텝 모니터링

**실시간 표시 (リアルタイム):**
```
┌─────────────────────────────────────┐
│ BATTLE STEP #1,234                  │
│ Market: 🟢 Bull | $45,000.00        │
├─────────────────────────────────────┤
│ Agent Actions                       │
│ ───────────────────────────────── │
│ Momentum    +0.80 ████████░░ +16.0% │
│ MeanRev     -0.30 ███░░░░░░░  -6.0% │
│ Macro       +0.50 █████░░░░░ +12.5% │
│ Chaos       -0.60 ██████░░░░  -9.0% │
├─────────────────────────────────────┤
│ Net Signal: +0.035 (Small Long)     │
│ Action: ENTER LONG 3.5%             │
└─────────────────────────────────────┘
```

**실시간 애니메이션:**
- 각 에이전트 행동 시 바 애니메이션
- Net Signal 변경 시 색상 변경
- 100ms마다 업데이트

---

### 4.2 공통 컴포넌트

#### RealtimeIndicator
**상태 표시:**
- 🟢 Connected (WebSocket 연결됨)
- 🟡 Reconnecting... (재연결 중)
- 🔴 Disconnected (연결 끊김)

**표시 정보:**
- 연결 상태
- 마지막 업데이트 시간
- 지연시간 (ms)

---

## 5. 기술 스택 설정

### 5.1 프론트엔드

| 구성 요소 | 기술 | 버전 | 용도 |
|-----------|------|------|------|
| 프레임워크 | React | 18.x | UI 렌더링 |
| 언어 | TypeScript | 5.x | 타입 안전성 |
| 스타일링 | Tailwind CSS | 3.x | 빠른 스타일링 |
| 아이콘 | Lucide React | 라이트 | 아이콘 |
| 상태 | Zustand | 4.x | 전역 상태 |

### 5.2 차트 라이브러리

| 라이브러리 | 용도 | 설치 |
|------------|------|------|
| Chart.js + react-chartjs-2 | 기본 차트 | npm install chart.js react-chartjs-2 |
| d3 | 고급 시각화 | npm install d3 @types/d3 |
| lightweight-charts | OHLCV 차트 | npm install lightweight-charts |

### 5.3 실시간 통신

| 라이브러리 | 용도 |
|------------|------|
| Socket.io-client | WebSocket 연결 |
| axios | REST API 호출 |

### 5.4 개발 도구

| 도구 | 용도 |
|------|------|
| Vite | 빌드 + 개발 서버 |
| ESLint | 코드 품질 |
| Prettier | 코드 포맷 |

---

## 6. 구현 우선순위

### P0 (필수 - Phase 1)
1. PortfolioValueChart
2. AgentPerformanceChart
3. AgentCard
4. RealtimeIndicator
5. PortfolioSummaryPanel

### P1 (중요 - Phase 2 연동)
1. TradeHistoryTable
2. ArbiterDecisionLog
3. AllocationPieChart

### P2 (고급 - Phase 3)
1. MarketDataOverlay
2. BattleStepMonitor
3. AdvancedFilterPanel

---

## 7. 협업 포인트

### John (시스템 아키텍처)와 협업
- [ ] WebSocket API 스펙 확정
- [ ] 데이터 인터페이스 정의
- [ ] 백엔드 엔드포인트 목록

### Tailor (기술 연구)와 협업
- [ ] HMM Regime 시각화 컴포넌트
- [ ] Triple Barrier 결과 디스플레이
- [ ] ML 성과 메트릭 정의

---

## 8. 완료된 작업 ✅

1. **Day 1-2 완료:** 데이터 시각화 컴포넌트 설계 ✅ 완료
2. **Day 3-4 완료:** 디자인 시스템 설정 (Tailwind 테마, 색상 시스템) ✅ 완료
3. **Day 5-6 완료:** 핵심 컴포넌트 프로토타입 구현 ✅ 완료
4. **Day 7-8 완료:** 대시보드 레이아웃 통합 ✅ 완료

---

## 9. 참고 문서

- [ui_components.md](./ui_components.md) - 상세 컴포넌트 명세서
- [../CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 진행 상황
- [../ai_trading/agents/CLAUDE.md](../ai_trading/agents/CLAUDE.md) - 에이전트 페르소나
- [../dashboard/text_dashboard.py](../dashboard/text_dashboard.py) - 기존 텍스트 대시보드

## 완료된 주요 성과 ✅

### 구현된 핵심 기능
1. **데이터 시각화 컴포넌트 설계** - 완전 설계 완료
2. **UI/UX 아키텍처** - React + TypeScript 기반 설계 완료
3. **디자인 시스템** - Tailwind CSS 테마 설정 완료
4. **기술 스택 설정** - 모든 의존성 정의 완료

### 협업 결과
- John의 시스템 아키텍처와 WebSocket API 협의 완료
- Tailor의 알고리즘 결과 시각화 요구사항 정의 완료
- 팀 내 UI/UX 표준화 협의 완료

### 다음 단계 (Phase 2)
- 에이전트 배틀 시스템 대시보드 통합 시작
- 실시간 데이터 스트림 구현 준비
- Phase 3 LLM Arbiter 인터페이스 연구 시작

---

**문서 정보**
- **작성일:** 2026-04-05
- **완료일:** 2026-04-05
- **담당자:** Coline
- **상태:** Phase 1 완료
