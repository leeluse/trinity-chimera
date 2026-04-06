# TRINITY-CHIMERY Dashboard - Phase 2+ 진행 중

## 작성자: Coline (UI/UX Design)
## 업데이트일: 2026-04-06
## 상태: 🔄 Phase 2+ 진행 중 (Next.js 앱 구조 완료)

---

## 개요

Phase 1의 데이터 시각화 컴포넌트 설계 및 구현이 완료되었습니다. React + TypeScript + Tailwind CSS 기반의 모니터링 대시보드 컴포넌트 아키텍처를 설계하고, P0/P1/P2 레벨의 핵심 컴포넌트를 구현했습니다.

---

## 완료된 작업

### 1. 설계 문서

| 문서 | 경로 | 내용 |
|------|------|------|
| UI 컴포넌트 명세서 | `/docs/ui_components.md` | 8개 핵심 컴포넌트 명세, 타입 정의, WebSocket 이벤트 |
| 설계 보고서 | `/docs/COLINE_PLAN.md` | 모니터링 요구사항 분석, 아키텍처 설계, 기술 스택 |

### 2. 타입 정의

**파일:** `/dashboard/types/index.ts`

```typescript
// 핵심 인터페이스
- AgentMetrics (에이전트 성과 지표)
- PortfolioState (포트폴리오 상태)
- Trade (거래 기록)
- ArbiterDecision (재배분 결정)
- BattleStep (배틀 스텝)
- MarketData (시장 데이터)
- WebSocketEvent (실시간 이벤트)
- MarketRegime (시장 레짐 타입)
```

### 3. P0 핵심 컴포넌트

| 컴포넌트 | 파일 | 기능 |
|----------|------|------|
| AgentCard | `components/AgentCard.tsx` | 개별 에이전트 상태 카드 |
| PortfolioSummaryPanel | `components/PortfolioSummaryPanel.tsx` | 포트폴리오 요약 |
| RealtimeIndicator | `components/RealtimeIndicator.tsx` | 실시간 연결 상태 |
| PortfolioValueChart | `components/PortfolioValueChart.tsx` | 포트폴리오 가치 차트 |

### 4. P1 컴포넌트

| 컴포넌트 | 파일 | 기능 |
|----------|------|------|
| TradeHistoryTable | `components/TradeHistoryTable.tsx` | 거래 이력 테이블 (페이지네이션, 필터, CSV) |
| ArbiterDecisionLog | `components/ArbiterDecisionLog.tsx` | Arbiter 결정 로그 |
| AgentPerformanceChart | `components/AgentPerformanceChart.tsx` | 에이전트 성과 비교 차트 |

### 5. P2 시각화 컴포넌트

| 컴포넌트 | 파일 | 기능 |
|----------|------|------|
| HMMRegimeVisualizer | `components/HMMRegimeVisualizer.tsx` | HMM Regime 시각화 |
| TripleBarrierVisualizer | `components/TripleBarrierVisualizer.tsx` | Triple Barrier 결과 시각화 |

### 6. 인프라

| 구성 요소 | 파일 | 기능 |
|-----------|------|------|
| WebSocket Hook | `hooks/useWebSocket.ts` | 실시간 연결, 재연결, 지연 시간 측정 |
| Dashboard Store | `store/useDashboardStore.ts` | Zustand 상태 관리 |

---

## 디렉토리 구조

```
dashboard/
├── components/
│   ├── AgentCard.tsx
│   ├── AgentPerformanceChart.tsx
│   ├── ArbiterDecisionLog.tsx
│   ├── HMMRegimeVisualizer.tsx
│   ├── PortfolioSummaryPanel.tsx
│   ├── PortfolioValueChart.tsx
│   ├── RealtimeIndicator.tsx
│   ├── TradeHistoryTable.tsx
│   └── TripleBarrierVisualizer.tsx
├── hooks/
│   └── useWebSocket.ts
├── pages/
│   └── (대시보드 페이지 추가 예정)
├── store/
│   └── useDashboardStore.ts
├── types/
│   └── index.ts
├── utils/
│   └── (유틸리티 추가 예정)
└── CLAUDE.md
```

---

## 기술 스택

| 분류 | 기술 | 버전 |
|------|------|------|
| 프레임워크 | React | 18.x |
| 언어 | TypeScript | 5.x |
| 스타일링 | Tailwind CSS | 3.x |
| 상태 관리 | Zustand | 4.x |
| 차트 | SVG (커스텀) | - |
| 실시간 통신 | WebSocket | Native |

---

## 컴포넌트 특징

### 공통
- ✅ TypeScript 타입 안전성
- ✅ Tailwind CSS 다크모드 (`dark:` 접두사)
- ✅ 반응형 디자인
- ✅ 접근성 고려 (적절한 색상 대비, 구조적 마크업)

### 성능
- ✅ 메모이제이션 (`useMemo`) 적용
- ✅ 데이터 제한 (최대 1000개 거래 기록)

### 상호작용
- ✅ 필터링 (Agent별, 결과별, 시간 범위)
- ✅ 정렬 (시간, PnL 등)
- ✅ 페이지네이션
- ✅ 확장/축소 (ArbiterDecisionLog)

---

## 데이터 인터페이스

### WebSocket 이벤트

```typescript
type WebSocketEventType = 
  | 'portfolio'
  | 'agent_update' 
  | 'new_trade'
  | 'arbiter_decision'
  | 'battle_step';

interface WebSocketEvent {
  type: WebSocketEventType;
  data: PortfolioState | AgentMetrics | Trade | ArbiterDecision | BattleStep;
}
```

### Store Actions

```typescript
- setPortfolio(state: PortfolioState)
- updateAgent(name: string, metrics: Partial<AgentMetrics>)
- addTrade(trade: Trade)
- addDecision(decision: ArbiterDecision)
- handleWebSocketEvent(event: WebSocketEvent)
```

---

## 앞으로의 작업 (Phase 2)

### 통합 작업
- [ ] WebSocket 백엔드 연결 (John API 완료 후)
- [ ] HMM Regime 데이터 연동 (John 완료 후)
- [ ] Triple Barrier 데이터 연동 (Tailor 완료 후)

### 대시보드 페이지
- [ ] 메인 대시보드 레이아웃
- [ ] 에이전트 상세 페이지
- [ ] 거래 내역 페이지
- [ ] Arbiter 로그 페이지

### 테스트
- [ ] Storybook 설정
- [ ] 통합 테스트 시나리오
- [ ] WebSocket 연동 테스트

---

## 참고 문서

- `/docs/ui_components.md` - 컴포넌트 명세서
- `/docs/COLINE_PLAN.md` - 상세 설계 문서
- `/ai_trading/agents/CLAUDE.md` - 에이전트 페르소나

---

## 협업 포인트

### John (시스템 아키텍처)
- WebSocket API 엔드포인트
- HMM Regime 인터페이스
- 전체 시스템 아키텍처

### Tailor (기술 연구)
- Triple Barrier 출력 구조
- 레이블링 결과 데이터
- ML 성과 메트릭

---

## Phase 2+ 진행 상황 (2026-04-06)

### ✅ 새로 완료된 작업

#### Next.js 앱 라우터 구조
- `app/layout.tsx` - 루트 레이아웃 (dark 모드 기본값)
- `app/page.tsx` - 메인 대시보드 (4개 탭: Overview, Agents, Trades, Arbiter)
- `app/globals.css` - Tailwind 설정 + 커스텀 CSS 변수

#### 설정 파일
- `package.json` - Next.js 14 + React 18 + Zustand
- `next.config.js` - API/WebSocket 프록시 설정
- `tailwind.config.js` - 다크모드 + 테마 설정
- `postcss.config.js` - Tailwind 처리
- `tsconfig.json` - TypeScript 설정

#### WebSocket 통합
- `useWebSocket` hook을 메인 페이지에 연결
- 실시간 연결 상태, 지연 시간 표시
- WebSocket 이벤트 타입별 핸들러 구현

#### 업데이트된 컴포넌트
- `PortfolioSummaryPanel` - 새로운 props 구조 (개별 값 전달)

### 📁 업데이트된 디렉토리 구조

```
dashboard/
├── app/                      # ✅ Next.js 14 App Router
│   ├── layout.tsx           # 루트 레이아웃
│   ├── page.tsx             # 메인 대시보드 (WebSocket 연결됨)
│   └── globals.css          # 스타일
├── components/              # 10개 컴포넌트 준비됨
├── hooks/
│   └── useWebSocket.ts      # WebSocket 연결
├── store/
│   └── useDashboardStore.ts # Zustand 상태 관리
├── types/
│   └── index.ts             # TypeScript 타입
├── next.config.js           # ✅ API 프록시
├── tailwind.config.js       # ✅ 테마 설정
├── postcss.config.js       # ✅ 추가됨
├── package.json            # ✅ 추가됨
├── tsconfig.json           # ✅ 설정 완료
└── CLAUDE.md               # ✅ 업데이트됨
```

### 🎯 실행 방법

```bash
cd dashboard
npm install        # 의존성 설치
npm run dev        # 개발 서버 실행
# → http://localhost:3000
```

### 📊 메인 대시보드 구성

**Header:**
- TRINITY-CHIMERY 로고
- 탭 네비게이션 (Overview, Agents, Trades, Arbiter)
- 실시간 연결 상태 표시기

**Overview 탭:**
- PortfolioSummaryPanel (총 자본, PnL 요약)
- PortfolioValueChart (포트폴리오 가치 추적)
- AgentCard 그리드 (활성 에이전트)
- TradeHistoryTable (최근 거래)
- ArbiterDecisionLog (최근 재배분 결정)

### 🔄 현재 진행 중

1. **Tailor 대기 중** - Phase 3 LLM Arbiter 인터페이스 정의
2. **WebSocket 백엔드 연결** - API 서버 완료 후 테스트

### 📋 다음 작업 예정

- [ ] Phase 3용 LLM Arbiter 확장 컴포넌트
- [ ] 자가 전략 생성 결과 UI
- [ ] 시장 분석 인사이트 패널
- [ ] 실제 WebSocket 데이터 연동 테스트

---

**Phase 1 완료 → Phase 2+ 진행 중. Next.js 앱 구조 완료, WebSocket 통합 완료.**
