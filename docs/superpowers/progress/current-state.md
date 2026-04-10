# Current State

## 진행 상황
- `trn` tmux 실행 스크립트를 현재 저장소 구조(`front/`, `api/`, `ai_trading/`)에 맞게 재구성했다.
- `front`와 `api`는 루트 `run` 스크립트를 기준으로 실행하도록 맞췄다.
- `ai_trading`은 별도 작업 창으로 유지했다.
- 실제 tmux 검증에서 세션 생성, `stop`, `kill` 동작이 정상 확인되었다.
- `api/main.py`는 이제 루트 `.env`와 `api/.env`를 모두 읽도록 바뀌었고, `SUPABASE_URL`/`SUPABASE_KEY` 누락으로 즉시 죽던 문제를 해결했다.
- `run`은 `front`/`api` 실행 전 각각 3000/8000 포트 점유 여부를 확인하고, 이미 떠 있으면 중복 기동을 막는다.
- `trn`은 tmux 패인을 `zsh -f`로 띄워서 `nvm`/bash 안내 경고를 피하도록 정리했다.
- 에이전트 코드 이동이 완료되어 `ai_trading/agents/`가 canonical 위치가 되었고, `api/services/`는 호환 래퍼로 남겼다.
- 에이전트 이름 매핑을 제거하고, 백엔드/프론트가 공통으로 `agent_id`를 사용하도록 통일했다.
- `PROJECT.md`를 전략 개선 운영 기준서로 다시 써서, Claude/Codex 협업 방식과 평가 원칙을 명시했다.

## 확인된 내용
- `run`은 현재 `front`, `api`, `slack` 명령을 지원한다.
- 저장소 루트에서 `slack-on.py`는 존재하지 않는다.
- `trn`은 더 이상 `backend/frontend/engine` 전제를 사용하지 않는다.
- `api`는 `PYTHONPATH=.. ../venv/bin/python main.py` 기준으로 정상 import 및 부팅 경로 진입이 확인되었다.

## 남은 검증
- 별도 후속 수정은 현재 없다.
- 추가 구조 변경이 생기면 그때 다시 문서화한다.
