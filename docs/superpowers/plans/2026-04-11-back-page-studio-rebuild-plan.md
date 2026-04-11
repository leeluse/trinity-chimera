# 2026-04-11 `/back` Page Freqtrade Studio Rebuild Plan

## Goal

`/back` 페이지를 현재의 실험실형 다크 대시보드에서,
사용자가 제공한 레퍼런스 스크린샷에 가까운 **Freqtrade 기반 전략 스튜디오 + 수동 백테스트 워크벤치**로 재구성한다.

핵심 목표:

- 차트 중심 레이아웃
- `Freqtrade` 결과를 사람이 검수하는 수동 실험실로 역할 명확화
- 우측 전략 요약/실행 상태/질의 패널
- 하단 성과 카드 + 자산 곡선 + 탭 구조
- 대형 단일 파일 해체 및 명확한 컴포넌트 분리
- Next 16 / React 19 기준의 최신 App Router 구조 유지

## Reference Inputs

- 사용자 제공 스크린샷
- 로컬 참고 프로젝트:
  - `/Users/lsy/Desktop/project/Laplace-s-demon/frontend/components/charts/CandleStickChart.tsx`
  - `/Users/lsy/Desktop/project/Laplace-s-demon/frontend/app/research/page.tsx`
- 현재 구현:
  - `/Users/lsy/Desktop/project/trinity-chimery/front/app/back/page.tsx`
  - `/Users/lsy/Desktop/project/trinity-chimery/front/app/back/components/ParametersPanel.tsx`

## Assumptions

- 사용자가 언급한 `Laplace-d-demon`은 로컬에서 확인된 `/Users/lsy/Desktop/project/Laplace-s-demon`을 의미한다고 가정한다.
- 이번 단계에서는 `/back`을 **Freqtrade 결과를 읽고, 여러 기간/심볼/전략을 사람이 수동 실험하는 화면**으로 정의한다.
- 차트는 스크린샷과 가장 가까운 UX를 위해 `lightweight-charts` 기반 캔들 차트로 구성하는 방향을 우선 검토한다.
- LLM 자동 진화 루프용 빠른 screening 엔진은 별도로 유지하고, `/back`은 사람이 보는 truth-for-humans 화면으로 본다.

## Non-Goals

- 이번 작업에서 백엔드 API 설계 전체를 새로 바꾸지는 않는다.
- 실거래/배포 로직을 구현하지 않는다.
- Supabase 스키마를 변경하지 않는다.
- LLM 내부 평가 루프를 `/back`에 섞지 않는다.

## File Targets

### Primary edits

- [ ] `front/app/back/page.tsx`
- [ ] `front/package.json`
- [ ] `front/package-lock.json`
- [ ] `front/app/globals.css` 또는 `/back` 전용 스타일 분리 파일
- [ ] `/back`에서 사용할 데이터 어댑터 또는 mock contract 파일

### New components (planned)

- [ ] `front/app/back/_components/types.ts`
- [ ] `front/app/back/_components/mock-data.ts`
- [ ] `front/app/back/_components/BacktestStudioShell.tsx`
- [ ] `front/app/back/_components/StudioTopBar.tsx`
- [ ] `front/app/back/_components/MarketChartPanel.tsx`
- [ ] `front/app/back/_components/ChartToolbar.tsx`
- [ ] `front/app/back/_components/FreqtradeControls.tsx`
- [ ] `front/app/back/_components/StrategySummarySidebar.tsx`
- [ ] `front/app/back/_components/MetricGrid.tsx`
- [ ] `front/app/back/_components/MetricCard.tsx`
- [ ] `front/app/back/_components/EquityCurvePanel.tsx`
- [ ] `front/app/back/_components/StrategyTabs.tsx`
- [ ] `front/app/back/_components/StudioActionBar.tsx`
- [ ] `front/app/back/_components/TradeMarkers.tsx` 또는 chart overlay helper
- [ ] `front/app/back/_components/TradesTable.tsx`
- [ ] `front/app/back/_components/BacktestStatusCard.tsx`

## Data Source Direction

### Primary source for `/back`

- [ ] `Freqtrade` 결과물 기반 구조 채택
- [ ] candle 시계열 + trade log + equity curve + headline metrics를 중심 데이터 계약으로 정의

### Not primary for `/back`

- [ ] `BacktestManager`는 화면 주 데이터 소스로 사용하지 않음
- [ ] 필요 시 빠른 비교용 보조 데이터로만 고려

### Required UI-facing payloads

- [ ] candle data
- [ ] trade markers
- [ ] recent trades
- [ ] equity curve
- [ ] summary metrics
- [ ] strategy description / rationale
- [ ] backtest timerange metadata

## Planned UI Structure

### 1. Top studio bar

- [ ] 전략 이름 / 성과 배지 / 심볼 / 타임프레임 / 기간 선택
- [ ] Freqtrade 수동 실험용 전략 선택기
- [ ] 화면 상단의 밝은 워크벤치 톤 정리

### 2. Main chart workspace

- [ ] 대형 캔들 차트
- [ ] 가격/타임 축
- [ ] 차트 툴바 아이콘
- [ ] Freqtrade trade log 기반 매수/매도/청산 마커 오버레이
- [ ] hover 시 trade detail / pnl / reason 표시 가능하도록 구조 준비
- [ ] 스크린샷에 가까운 밝은 트레이딩 보드 느낌 반영

### 3. Execution controls beneath chart

- [ ] 전략 선택 드롭다운
- [ ] 심볼/타임프레임/기간 컨트롤
- [ ] `백테스트 실행`, `배포`, `저장`, `복사`
- [ ] 사람이 수동으로 여러 구간을 돌려볼 수 있는 실험 컨트롤 우선 배치

### 4. Metric summary row

- [ ] 총 수익률
- [ ] 최대 낙폭
- [ ] 승률
- [ ] 수익 팩터
- [ ] 샤프 비율

### 5. Lower analysis area

- [ ] 탭: `코드 / 지표 / 거래 내역`
- [ ] 자산 곡선 패널
- [ ] 거래 리스트 / 진입-청산 기록 / exit reason 표시
- [ ] 추후 코드 보기 확장 가능하도록 슬롯화

### 6. Right strategy sidebar

- [ ] 전략 설명 카드
- [ ] 생성 완료 / 백테스트 완료 카드
- [ ] 핵심 성과 요약
- [ ] 질문 입력 UI
- [ ] Freqtrade 실행 상태와 최근 백테스트 결과를 요약하는 카드 구조

## Planned Refactor Principles

### Component boundaries

- [ ] page는 orchestration만 담당
- [ ] UI primitive/section 컴포넌트는 `_components/`로 이동
- [ ] 타입/포맷터/mock-data 분리
- [ ] chart-specific state는 chart panel 안으로 국소화
- [ ] Freqtrade 결과 파싱/가공은 UI 렌더링과 분리

### React/Next principles

- [ ] 인터랙션 필요한 부분만 client component 유지
- [ ] 하드코딩된 거대 JSX 블록 해체
- [ ] 최신 Next App Router 관례 유지
- [ ] 불필요한 `useCallback/useMemo` 남용 없이 필요한 곳만 사용

### Visual principles

- [ ] 현재의 네온 다크 랩 무드 제거
- [ ] 레퍼런스처럼 밝고 정제된 트레이딩 워크벤치 톤 적용
- [ ] 카드/패널/차트 영역의 위계 명확화
- [ ] 모바일/중간 폭에서도 무너지지 않게 반응형 구성
- [ ] PreqTrade/TradingView 느낌은 가져오되 로컬 구현은 컴포넌트 수준으로 통제

## Implementation Steps

- [ ] Step 1. 현재 `/back`의 데이터/상태/레이아웃 책임 분해
- [ ] Step 2. `Laplace-s-demon`의 `CandleStickChart`와 `research` 페이지에서 재사용 포인트 추출
- [ ] Step 3. `/back`용 Freqtrade 데이터 계약(mock 포함) 정의
- [ ] Step 4. `/back/_components` 구조 생성
- [ ] Step 5. 메인 레이아웃을 밝은 스튜디오 구조로 재조립
- [ ] Step 6. 캔들 차트 + trade marker overlay 구성
- [ ] Step 7. 우측 Freqtrade 요약 패널과 하단 메트릭/에쿼티/거래탭 구성
- [ ] Step 8. 기존 `ParametersPanel`의 역할을 축소하거나 Freqtrade controls로 교체
- [ ] Step 9. 타입체크/린트/페이지 렌더 검증
- [ ] Step 10. 문서 업데이트 (`research.md`, 필요 시 progress 문서)

## Validation Checklist

- [ ] `/back` 페이지가 최신 구조로 렌더링됨
- [ ] 거대한 단일 JSX 블록이 의미 있는 컴포넌트로 분리됨
- [ ] 캔들형 차트 워크벤치가 화면의 중심이 됨
- [ ] Freqtrade trade markers가 차트 오버레이 구조에 반영됨
- [ ] 우측 요약 패널이 스크린샷과 유사한 정보 구조를 가짐
- [ ] 하단 메트릭과 자산 곡선이 독립 섹션으로 정리됨
- [ ] 여러 기간/심볼/전략을 수동으로 돌려보는 화면 구조가 확보됨
- [ ] `npm run lint` 또는 대상 파일 lint 확인
- [ ] 필요한 경우 `npm run build` 또는 최소 type/lint 검증

## Risks

- `lightweight-charts` 도입 시 의존성 추가 필요
- 기존 `ParametersPanel`과 새 워크벤치 UX 간 중복 역할 발생 가능
- mock 기반 화면과 실제 Freqtrade 결과 연동 지점이 섞이면 구조가 다시 커질 수 있음
- 시각적 복제에 치우치면 컴포넌트 경계가 다시 흐려질 수 있음
- 차트 오버레이 데이터 스키마를 처음부터 잘못 잡으면 나중에 재작업 비용이 큼

## Approval Gate

이 계획이 승인되면 다음을 진행한다.

1. `/back` 전용 컴포넌트 트리 생성
2. Freqtrade 수동 실험실 기준의 차트/메트릭/사이드바 리빌드 구현
3. lint/type 검증
4. 관련 문서 업데이트
