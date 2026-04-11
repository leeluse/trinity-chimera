# 2026-04-11 `/back` UI Full Redesign Plan

## Goal

`/back` 페이지를 "대충 맞춘 데모 UI"가 아니라,
실제로 전략을 읽고 비교하고 실행하기 좋은 **Freqtrade 수동 워크벤치 UI**로 재설계한다.

## Design Direction

- 기준 스킬:
  - `frontend-design` (주 설계/구현 기준)
  - `web-design-guidelines` (보조 리뷰 기준)
- 톤:
  - 밝은 배경 기반의 professional trading workspace
  - 정보 밀도는 높이고, 장식은 절제
  - 차트/통제 패널/성과 패널의 위계를 명확히 분리

## Scope

- `front/app/back/page.tsx`
- `front/app/back/_components/*`
- 필요 시 `front/app/back/components/ParametersPanel.tsx` 역할 축소/정리
- 필요 시 `/back` 전용 스타일 상수 추가

## Non-Goals

- Freqtrade 백엔드 실행 파이프라인 구축
- 실거래 배포 로직 추가
- `/back` 외 다른 라우트 전체 리디자인

## UX Architecture

- 상단: 전략 스튜디오 헤더 + 계정/상태 바
- 좌측 메인:
  - 차트 워크스페이스
  - 실행 컨트롤 바
  - KPI 카드
  - 자산 곡선
  - 전략 코드/지표/거래 내역 탭
- 우측 사이드:
  - 전략 설명
  - 백테스트 결과 요약
  - 질의 입력 패널

## Tasks

- [x] T1. 시각 시스템 재정의
  - [x] 색상 토큰, 타이포 스케일, spacing scale 재설정
  - [x] 과도한 radius/shadow 정리
- [x] T2. 차트 영역 리디자인
  - [x] 헤더 정보 밀도 보정
  - [x] 툴바 크기/상태 표현 개선
  - [x] 마커(진입/청산/손익) 전달력 강화
- [x] T3. 컨트롤/메트릭 영역 개선
  - [x] 전략/심볼/타임프레임 조작 흐름 명확화
  - [x] CTA 버튼 위계(백테스트/배포/저장) 재정렬
- [x] T4. 하단 분석 영역 개선
  - [x] 자산곡선 가독성 강화
  - [x] 탭 패널 레이아웃/정보 구조 개선
  - [x] 거래 테이블 스캔 속도 개선
- [x] T5. 우측 사이드바 개선
  - [x] 상태 카드 요약 구조 단순화
  - [x] 설명 텍스트 길이/행간 최적화
  - [x] 질의 패널 시각 노이즈 축소
- [x] T6. 반응형/접근성 보정
  - [x] 1280px, 1024px, 768px 기준으로 레이아웃 붕괴 점검
  - [x] 대비/버튼 크기/포커스 표현 점검
- [x] T7. 검증
  - [x] `eslint` 대상 파일 통과
  - [x] `tsc --noEmit` 실행 (기존 전역 오류와 신규 오류 분리 기록)
  - [x] `curl http://127.0.0.1:3000/back` 응답 확인

## Validation Checklist

- [x] 첫 화면에서 차트가 명확한 시각적 중심임
- [x] 전략 실행 흐름이 한눈에 읽힘
- [x] 정보는 많지만 조잡하지 않음
- [x] 기존 대비 디자인 완성도가 체감되게 개선됨

## Approval Gate

이 계획 승인 후 구현을 진행한다.

## Validation Notes

- `eslint` 대상: `app/back/page.tsx`, `app/back/_components/*` 통과
- `tsc --noEmit`: `app/v2/page.tsx`의 기존 타입 에러 6건은 유지, `/back` 신규 에러는 확인되지 않음
- `/back` 응답: `HTTP/1.1 200 OK` 확인
