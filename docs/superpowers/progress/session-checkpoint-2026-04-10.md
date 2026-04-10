# Session Checkpoint - 2026-04-10

## 완료된 항목
- [x] `trn`의 tmux 구조를 현재 프로젝트 디렉터리 기준으로 재설계
- [x] `front`/`api` 실행 경로를 `run` 스크립트와 맞춤
- [x] `ai_trading` 전용 작업 창 유지
- [x] 계획 문서 체크리스트 갱신
- [x] 현재 상태 기록 문서 생성
- [x] 실제 tmux 세션 생성 검증 완료
- [x] `trn stop` 및 `trn kill` 동작 검증 완료
- [x] `api/main.py` 환경변수 로딩 수정
- [x] `SUPABASE_URL`/`SUPABASE_KEY` 누락으로 인한 API 부팅 실패 해결
- [x] `api` import/부팅 경로 재검증 완료
- [x] `run`에 `front`/`api` 포트 중복 실행 방지 로직 추가
- [x] `trn` tmux 패인을 `zsh -f`로 띄워 셸 경고 제거
- [x] 에이전트 코드를 `ai_trading/agents/`로 이동하고 `api/services/`는 래퍼로 정리
- [x] `api.main`과 `SelfImprovementService`를 새 canonical 경로로 연결
- [x] `ai_trading.agents` 패키지 import 검증 완료
- [x] `PROJECT.md`를 현재 아키텍처 기준으로 상세 재작성
- [x] 에이전트 이름 매핑 제거 및 `agent_id` 기준 통일
- [x] `PROJECT.md`를 전략 개선 운영 기준서로 재작성하고 Claude/Codex 협업 원칙 명시

## 진행 중인 사항
- 현재 보류 중인 수정 없음

## 다음 세션 목표
1. `run` 또는 `README`의 실행 안내를 `trn` 기준으로 더 맞출지 검토
2. 필요 시 tmux 창 구성을 미세 조정
3. 새 요구가 생기면 그때 추가 반영
