# Chat Pipeline

## 파일
- Router: `server/modules/chat/router.py`
- Handler: `server/modules/chat/handler.py`
- Prompt Templates: `server/modules/chat/prompts.py`

## SSE 이벤트 타입
- `stage`
- `thought`
- `analysis`
- `strategy`
- `backtest`
- `error`
- `done`

## 단계별 처리
1. 사용자 메시지 저장 (`chat_messages`)
2. 의도 분석
3. 전략 설계
4. 코드 생성
5. 백테스트 실행
6. 운영 팁 생성
7. 결과 저장 및 스트리밍 종료

## 마이닝 모드
- 메시지에 `에볼루션` 포함 시 페르소나+씨드 조합 모드 활성화
- 금지 지표(`BANNED_INDICATORS`) 적용
- 고급 검증 엔진 호출

## 전략 배포
`POST /api/chat/deploy`에서 `save_system_strategy` 호출로 DB 라이브러리에 저장.
