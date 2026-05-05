# Core Features

## 1) Evolution Loop
- 에이전트별 현재 전략 로드
- LLM 후보 코드 생성
- 고급 백테스트 검증(WFO/Monte Carlo)
- 점수 비교 후 반영/거절
- 대시보드 이벤트 로그 기록

## 2) Dashboard Monitoring
- 4초 간격 폴링으로 진행 상태 표시
- 메트릭 시계열(점수/수익률/샤프/MDD/승률)
- RUN LOOP 버튼으로 즉시 수동 진화 실행
- 자동화 토글(`Auto Live / Paused`)

## 3) Chat-Driven Strategy Mining
- SSE 기반 단계형 파이프라인
- 일반 대화와 전략 생성 모드 분기
- 전략 코드 추출 + 백테스트 + 팁 생성
- 전략 배포(`POST /api/chat/deploy`) 지원

## 4) Backtest Workbench
- 전략 목록 조회/코드 로드/코드 직접 실행
- 캔들+마커+자산곡선 시각화
- 상세 성과 지표(수익, PF, 연속 손익, 롱/숏 통계)
- 리더보드/LLM 분석 API 지원

## 5) Public Access Operation
- `run public`로 로컬 백엔드 + localtunnel 운영
- 고정 서브도메인 기반 외부 접근
- 터널 장애시 자동 재접속 루프
