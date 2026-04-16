# Quickstart

## 로컬 실행
```bash
./run server
./run client
```

## 공개 터널 실행 (고정 서브도메인)
```bash
./run public
```

## 상태 확인
```bash
./run public-status
```

## 핵심 화면
- 대시보드: `http://localhost:3000`
- 백테스트/채팅: `http://localhost:3000/backtest`
- API 상태: `http://localhost:8000/api/system/status`

## 최초 점검 체크리스트
1. `.env`에 `SUPABASE_URL`, `SUPABASE_KEY` 설정
2. `.env`에 LLM 경로(`OLLAMA_*` 또는 `OPENAI_*`/`ANTHROPIC_*`) 설정
3. `./run server` 후 `GET /api/system/automation` 응답 확인
4. `./run client` 후 대시보드 로그/메트릭 폴링 확인
