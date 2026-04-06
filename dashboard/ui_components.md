# TRINITY-CHIMERY UI 컴포넌트 명세서

## 문서 정보
- **작성자:** Coline (UI/UX Design)
- **작성일:** 2026-04-05
- **버전:** 1.0
- **상태:** Phase 1 설계

---

## 1. 개요

### 1.1 목적
TRINITY-CHIMERY 트레이딩 시스템의 실시간 모니터링 및 데이터 시각화를 위한 React 기반 UI 컴포넌트 명세서입니다.

### 1.2 범위
- Phase 2 구현된 시스템 기반 시각화
- Phase 3 LLM Arbiter 통합 대시보드
- 실시간 데이터 스트리밍 인터페이스

### 1.3 기술 스택
| 분류 | 기술 |
|------|------|
| 프레임워크 | React 18 + TypeScript |
| 스타일링 | Tailwind CSS |
| 차트 라이브러리 | Chart.js (기본), D3.js (고급 시각화) |
| 상태 관리 | Zustand |
| 실시간 통신 | WebSocket |
| 빌드 도구 | Vite |

---

## 2. 데이터 모델

### 2.1 핵심 데이터 구조

```typescript
// Agent 성과 메트릭
interface AgentMetrics {
  name: string;
  allocation: number;           // 0.0 ~ 1.0
  pnl_24h: number;             // 24시간 PnL (%)
  pnl_7d: number;              // 7일 PnL (%)
  pnl_total: number;           // 누적 PnL (%)
  sharpe: number;              // 샤프 비율
  max_drawdown: number;        // 최대 낙폭 (0.0 ~ 1.0)
  win_rate: number;            // 승률 (0.0 ~ 1.0)
  open_positions: number;      // 현재 보유 포지션 수
  regime: string;              // 현재 감지된 레짐
  trade_count: number;         // 거래 횟수
}

// 포트폴리오 상태
interface PortfolioState {
  total_capital: number;
  total_pnl_24h: number;
  total_pnl_7d: number;
  total_pnl_total: number;
  agent_metrics: Record<string, AgentMetrics>;
  timestamp: string;             // ISO 8601
}

// 에이전트 투표/행동
interface AgentVote {
  name: string;
  action: number;              // -1.0 ~ 1.0 (포지션 비율)
  confidence: number;          // 0.0 ~ 1.0
}

// 거래 기록
interface Trade {
  id: string;
  agent_name: string;
  action: number;                // -1.0 ~ 1.0
  pnl: number;
  timestamp: string;
  symbol?: string;
  entry_price?: number;
  exit_price?: number;
}

// Arbiter 재배분 결정
interface ArbiterDecision {
  timestamp: string;
  old_allocations: Record<string, number>;
  new_allocations: Record<string, number>;
  reasoning: string;
  warnings?: string[];
}

// 시장 데이터
interface MarketData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  regime?: string;
}

// 배틀 스텝 결과
interface BattleStep {
  step: number;
  timestamp: string;
  market_obs: {
    regime: string;
    close: number;
    [key: string]: any;
  };
  agent_actions: Record<string, number>;
  net_signal: number;
}
```

---

## 3. 컴포넌트 명세

### 3.1 차트 컴포넌트

#### PortfolioValueChart
**목적:** 포트폴리오 가치 변화를 실시간으로 표시

```typescript
interface PortfolioValueChartProps {
  data: {
    timestamp: string;
    total_value: number;
    pnl: number;
  }[];
  height?: number;
  showGrid?: boolean;
  timeRange?: '1h' | '24h' | '7d' | '30d' | 'all';
}
```

**기능:**
- 라인 차트 (총 자본)
- 영역 차트 (PnL 누적)
- 줌/팬
- 툴팁 (시간, 가치, 변화율)
- 시간 범위 필터

**데이터 소스:** `PortfolioState` 히스토리

---

#### AgentPerformanceChart
**목적:** 에이전트별 성과 비교

```typescript
interface AgentPerformanceChartProps {
  agents: AgentMetrics[];
  metric: 'pnl_24h' | 'pnl_7d' | 'pnl_total' | 'sharpe' | 'win_rate';
  chartType: 'bar' | 'radar' | 'line';
  height?: number;
}
```

**기능:**
- 바 차트 (단일 메트릭 비교)
- 레이더 차트 (다중 메트릭 프로필)
- 라인 차트 (시간별 추적)
- 컬러 코딩 (양수/음수)
- 정렬 기능

---

#### TradeHistoryTable
**목적:** 거래 실행 이력 표시

```typescript
interface TradeHistoryTableProps {
  trades: Trade[];
  pageSize?: number;
  filterable?: boolean;
  sortable?: boolean;
  agentFilter?: string[];
  dateRange?: { start: string; end: string };
}
```

**기능:**
- 페이지네이션
- 필터링 (에이전트, 결과, 날짜)
- 정렬 (시간, PnL)
- 실시간 업데이트
- 내보내기 (CSV)

---

#### MarketDataOverlay
**목적:** OHLCV 차트에 에이전트 매매 포인트 오버레이

```typescript
interface MarketDataOverlayProps {
  ohlcv: MarketData[];
  trades: Trade[];
  height?: number;
  showVolume?: boolean;
  indicators?: string[];
}
```

**기능:**
- 캔들스틱 차트
- 거래량 막대
- 매수 포인트 마커 (초록색 ▲)
- 매도 포인트 마커 (빨간색 ▼)
- 기술적 지표 오버레이 (선택적)

---

#### AllocationPieChart
**목적:** 현재 자본 배분 비율 시각화

```typescript
interface AllocationPieChartProps {
  allocations: Record<string, number>;
  showLegend?: boolean;
  interactive?: boolean;
  onSliceClick?: (agent: string) => void;
}
```

**기능:**
- 도넛 차트
- 퍼센트 표시
- 변화 애니메이션
- 클릭 이벤트

---

### 3.2 모니터링 컴포넌트

#### AgentCard
**목적:** 개별 에이전트 상태 요약 카드

```typescript
interface AgentCardProps {
  metrics: AgentMetrics;
  isActive?: boolean;
  trend?: 'up' | 'down' | 'neutral';
  onClick?: () => void;
}
```

**레이아웃:**
```
┌─────────────────────────────────────┐
│ [아이콘]  Agent Name           [상태]│
├─────────────────────────────────────┤
│ Allocation: 30%                     │
│ PnL (24h):  +2.5%  ▲               │
│ PnL (7d):   +8.2%  ▲               │
│ Sharpe:     1.85                    │
│ Win Rate:   65%                     │
│ Open Pos:   2                       │
│ Regime:     [Bull]                  │
└─────────────────────────────────────┘
```

---

#### PortfolioSummaryPanel
**목적:** 포트폴리오 전체 상태 요약

```typescript
interface PortfolioSummaryPanelProps {
  state: PortfolioState;
  previousState?: PortfolioState;
  refreshInterval?: number;
}
```

**레이아웃:**
```
┌─────────────────────────────────────┐
│ PORTFOLIO SUMMARY                   │
├─────────────────────────────────────┤
│ Total Capital    $100,000.00         │
│ Total PnL (24h)   +1.6%  ▲         │
│ Total PnL (7d)   +18.0%  ▲         │
│ Active Agents        4               │
│ Last Update    2026-04-05 09:23     │
└─────────────────────────────────────┘
```

---

#### ArbiterDecisionLog
**목적:** LLM Arbiter 재배분 결정 로그

```typescript
interface ArbiterDecisionLogProps {
  decisions: ArbiterDecision[];
  maxEntries?: number;
  showReasoning?: boolean;
}
```

**레이아웃:**
```
┌─────────────────────────────────────┐
│ ARBITER DECISIONS                   │
├─────────────────────────────────────┤
│ [09:00] Reallocation Executed      │
│   Before → After                     │
│   Mom: 30% → 35% (+5%)              │
│   Rev: 30% → 25% (-5%)              │
│   ...                                │
│   Reason: Bull regime detected...    │
├─────────────────────────────────────┤
│ [02:00] Reallocation Executed      │
│   ...                                │
└─────────────────────────────────────┘
```

---

#### BattleStepMonitor
**목적:** 실시간 배틀 스텝 모니터링

```typescript
interface BattleStepMonitorProps {
  currentStep: BattleStep;
  history: BattleStep[];
  autoScroll?: boolean;
}
```

**레이아웃:**
```
┌─────────────────────────────────────┐
│ BATTLE STEP #1,234        [Live]  │
├─────────────────────────────────────┤
│ Market: Bull | $45,000              │
│                                      │
│ Agent Actions:                       │
│   Momentum    +0.80  ████████░░    │
│   MeanRev     -0.30  ███░░░░░░░    │
│   Macro       +0.50  █████░░░░░    │
│   Chaos       -0.60  ██████░░░░    │
│                                      │
│ Net Signal:   +0.035 (Small Long)    │
└─────────────────────────────────────┘
```

---

### 3.3 레이아웃 컴포넌트

#### DashboardLayout
**목적:** 대시보드 전체 레이아웃

```typescript
interface DashboardLayoutProps {
  children: React.ReactNode;
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  collapsed?: boolean;
}
```

**구조:**
```
┌─────────────────────────────────────────────┐
│                 Header                      │
├──────────┬──────────────────────────────────┤
│          │                                  │
│ Sidebar  │         Main Content            │
│          │                                  │
│          │  ┌──────────┐  ┌──────────┐     │
│          │  │  Chart   │  │  Chart   │     │
│          │  └──────────┘  └──────────┘     │
│          │                                  │
│          │  ┌──────────────────────┐       │
│          │  │      Table           │       │
│          │  └──────────────────────┘       │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

---

#### RealtimeIndicator
**목적:** 실시간 연결 상태 표시

```typescript
interface RealtimeIndicatorProps {
  status: 'connected' | 'disconnected' | 'reconnecting';
  lastUpdate?: string;
  latency?: number;
}
```

---

## 4. 페이지 구성

### 4.1 메인 대시보드 (/dashboard)
**구성:**
- PortfolioSummaryPanel (상단)
- PortfolioValueChart (좌측 상단)
- AgentPerformanceChart (우측 상단)
- AgentCard[] (중앙)
- AllocationPieChart (우측)

### 4.2 에이전트 상세 (/agents/:name)
**구성:**
- AgentCard (헤더)
- AgentPerformanceChart (시간별)
- TradeHistoryTable
- MarketDataOverlay (해당 에이전트 거래 표시)

### 4.3 거래 내역 (/trades)
**구성:**
- TradeHistoryTable (풀스크린)
- 필터 패널
- 내보내기 버튼

### 4.4 Arbiter 로그 (/arbiter)
**구성:**
- ArbiterDecisionLog
- Allocation 변화 추적 차트

### 4.5 실시간 배틀 (/battle)
**구성:**
- BattleStepMonitor
- MarketDataOverlay (실시간)
- AgentCard[] (현재 행동 표시)

---

## 5. 색상 시스템

### 5.1 시맨틱 색상
| 의미 | 색상 | HEX |
|------|------|-----|
| 상승/양수 | Green | #10B981 |
| 하락/음수 | Red | #EF4444 |
| 중립 | Gray | #6B7280 |
| 경고 | Yellow | #F59E0B |
| 정보 | Blue | #3B82F6 |
| 성공 | Emerald | #059669 |

### 5.2 에이전트 색상
| 에이전트 | 색상 | HEX |
|----------|------|-----|
| Momentum Hunter | Orange | #F97316 |
| Mean Reverter | Cyan | #06B6D4 |
| Macro Trader | Purple | #8B5CF6 |
| Chaos Agent | Pink | #EC4899 |

### 5.3 레짐 색상
| 레짐 | 색상 | HEX |
|------|------|-----|
| Bull | Green | #10B981 |
| Bear | Red | #EF4444 |
| Sideways | Yellow | #F59E0B |
| Volatile | Purple | #8B5CF6 |
| Unknown | Gray | #6B7280 |

---

## 6. 반응형 브레이크포인트

| 브레이크포인트 | 너비 | 레이아웃 |
|---------------|------|----------|
| Mobile | < 640px | 단일 열, 축소된 차트 |
| Tablet | 640px - 1024px | 2열 그리드 |
| Desktop | > 1024px | 3-4열 그리드 |
| Wide | > 1440px | 최대 4열, 확장 차트 |

---

## 7. WebSocket 이벤트

### 7.1 서버 → 클라이언트
```typescript
// 포트폴리오 상태 업데이트
interface PortfolioUpdateEvent {
  type: 'portfolio';
  data: PortfolioState;
}

// 배틀 스텝 업데이트
interface BattleStepEvent {
  type: 'battle_step';
  data: BattleStep;
}

// Arbiter 결정
interface ArbiterDecisionEvent {
  type: 'arbiter_decision';
  data: ArbiterDecision;
}

// 새 거래
interface NewTradeEvent {
  type: 'new_trade';
  data: Trade;
}

// 에이전트 메트릭 업데이트
interface AgentUpdateEvent {
  type: 'agent_update';
  data: AgentMetrics;
}
```

### 7.2 클라이언트 → 서버
```typescript
// 구독 요청
interface SubscribeRequest {
  action: 'subscribe';
  channels: string[];
}

// 시간 범위 변경
interface TimeRangeRequest {
  action: 'set_range';
  range: string;
}

// 에이전트 필터
interface FilterRequest {
  action: 'filter';
  agents: string[];
}
```

---

## 8. 성능 최적화

### 8.1 데이터 가상화
- TradeHistoryTable: react-window 사용
- 차트: 데이터 포인트 제한 (최대 1000개)

### 8.2 메모이제이션
- AgentCard: React.memo
- 차트: useMemo로 데이터 변환

### 8.3 번들 크기
- Chart.js: treeshaking
- D3.js: 필요한 모듈만 import
- 아이콘: 개별 import

---

## 9. 접근성

### 9.1 ARIA 레이블
- 모든 차트에 `aria-label` 추가
- 실시간 업데이트 시 `aria-live` 사용

### 9.2 키보드 탐색
- Tab 순서 최적화
- 차트 내부 포커스 관리

### 9.3 색상 대비
- WCAG 2.1 AA 준수
- 색상 외에도 패턴/텍스트 구분 제공

---

## 10. 문서 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0 | 2026-04-05 | Coline | 초기 작성 |
