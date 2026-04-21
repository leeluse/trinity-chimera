# Conventions

## 코드 구조 원칙
- API 라우트는 `server/modules/*/router.py`
- 핵심 도메인 로직은 `server/modules/*` 내부
- 공통 인프라는 `server/shared/*`
- UI는 `client/app` + `client/components`

## 전략 코드 규칙
- 최소 인터페이스: `generate_signal`, `get_params`
- 불필요한 외부 의존성 import 금지
- 과도한 미래참조/리페인트 금지

## 운영 규칙
- 자동화는 기본 pause에서 시작
- 수동 RUN LOOP로 즉시 트리거 가능
- 공용 접근은 tunnel 생존성 모니터링 필수

## 문서 업데이트 규칙
- 구조 변경 시 `Module-Map`, `Repository-Tree`, `Route-Map` 동시 업데이트
