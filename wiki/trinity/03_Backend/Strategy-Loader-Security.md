# Strategy Loader Security

## 파일
`server/shared/market/strategy_loader.py`

## 보안 정책
- AST 파싱 기반 코드 검증
- 금지 함수: `open`, `eval`, `exec`, `__import__`
- 금지 모듈: `os`, `sys`, `subprocess`, `socket`, `pickle` 등
- 허용 모듈 prefix 화이트리스트 방식

## 동적 로딩
- 제어된 네임스페이스로 `exec` 수행
- `StrategyInterface` 상속 여부 확인
- 구형 템플릿 호환용 메서드 패치(`generate_signal`, `get_params`)
- 추상 클래스인 경우 adapter 생성 시도

## 타임아웃 실행
`execute_with_timeout()`이 별도 프로세스로 전략 실행 후 제한 시간 초과 시 강제 종료.
