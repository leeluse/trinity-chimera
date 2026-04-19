# Dashboard UI

## 엔트리
`client/app/page.tsx`

## 주요 동작
- 4초 주기 폴링
  - `getDashboardProgress()`
  - `getDashboardMetrics()`
  - `getEvolutionLog()`
  - `getAutomationStatus()`
- 시계열 차트는 agent별 metric을 병합 렌더링
- RUN LOOP 클릭 시 `POST /api/agents/run-loop`
- 자동화 토글 시 `POST /api/system/automation`

## 로그 패널
- 컴포넌트: `client/components/panel/sections/EvolutionLogPanel.tsx`
- phase별 색/아이콘 매핑
- 에이전트별 컬러 하이라이트
- Auto Live/Paused 상태 버튼 제공

## UI 구성요소
- `PageLayout`
- `DashboardRightPanel`
- `PerformanceChart`, `AgentsList`, `MetricSelector`
