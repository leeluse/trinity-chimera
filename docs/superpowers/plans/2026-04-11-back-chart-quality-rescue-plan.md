# 2026-04-11 `/back` Chart Quality Rescue Plan

## Goal

`/back`의 차트를 "동작하는 데모" 수준에서 벗어나,
실제로 오래 보고 분석할 수 있는 **Freqtrade 수동 검수용 차트 워크스페이스** 품질로 끌어올린다.

## Why This Plan Exists

- 사용자 피드백: 현재 차트의 시각 품질이 낮고, 완성도가 부족함
- 현재 상태:
  - 레이아웃 골격은 있으나 차트 가독성과 디테일이 약함
  - 차트 툴바/헤더 비율이 과도하게 커서 정보 밀도가 떨어짐
  - 거래 시그널 표현이 과하게 단순함

## Scope

- `front/app/back/_components/MarketChartPanel.tsx`
- `front/app/back/_components/ChartToolbar.tsx`
- `front/app/back/_components/TradeMarkers.tsx`
- `front/app/back/_components/mock-data.ts`
- 필요 시 `/back` 관련 보조 컴포넌트 스타일 소폭 조정

## Non-Goals

- 백엔드 API 연동 방식 변경
- 전략/백테스트 계산 로직 변경
- `/back` 외 라우트 대규모 리디자인

## Quality Targets

- 차트 헤더/툴바/축 정보의 시각적 위계 정리
- 트레이드 마커 가독성 강화 (진입/청산/손익 구분)
- 캔들/그리드/가격선 스타일을 실제 트레이딩 툴에 가까운 밸런스로 보정
- 데스크톱/중간 폭에서 레이아웃 깨짐 없이 유지

## Tasks

- [ ] T1. 차트 상단 정보 밀도 재설계
  - [ ] 심볼/타임프레임 타이포 크기 정상화
  - [ ] O/H/L/C + 변동률 표시줄을 얇고 읽기 쉽게 재배치
- [ ] T2. 좌/상단 툴바 시각 언어 정리
  - [ ] 버튼 크기/간격 축소
  - [ ] 활성/비활성 상태 대비 강화
- [ ] T3. 차트 본문 스타일 개선
  - [ ] grid/price-scale/time-scale 대비 보정
  - [ ] last-price 라인/배지 표현 개선
  - [ ] (가능하면) 볼륨 히스토그램 보조 시리즈 추가
- [ ] T4. 트레이드 시그널 표현 개선
  - [ ] marker 색/형태/라벨 규칙 명확화
  - [ ] 진입/청산/손익 전달력 강화
- [ ] T5. mock 데이터 보정
  - [ ] 추세/횡보/변동 구간이 더 자연스럽게 보이게 조정
  - [ ] marker 분포를 차트 가독성에 맞게 재조정
- [ ] T6. 검증
  - [ ] `/back` HTTP 200 확인
  - [ ] `eslint` 대상 파일 통과 확인
  - [ ] `tsc --noEmit` 실행 (기존 전역 에러와 신규 에러 구분 기록)

## Validation Checklist

- [ ] 차트가 이전 대비 덜 조잡하고 정보 밀도가 개선됨
- [ ] 차트 헤더/툴바가 과도하게 크지 않음
- [ ] 트레이드 마커가 "왜 들어가고 나왔는지" 읽기 쉬움
- [ ] 주요 색상/그리드/축이 눈 피로를 줄이면서도 구분 가능함
- [ ] 반응형에서 레이아웃 붕괴가 없음

## Approval Gate

이 계획 승인 후 코드를 수정한다.

## Status Note

해당 계획은 이후 `/back` 전체 UI 리디자인으로 확장되어,
`2026-04-11-back-ui-full-redesign-plan.md`에서 통합 완료 처리했다.
