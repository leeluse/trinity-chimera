# 처음 이 글을 읽게 된다면
- 당신은 완벽하지 않습니다. 당신이 실수하거나 잘한 일이 있다면 개선을 위해 해당 md 파일을 이용해 피드백을 작성해주세요.
- 하나의 Phase가 끝나고 난 뒤 리더는 최종 점검 진행 후 다음 Phase로 넘어갈지, 아니면 현재 Phase에서 개선할 점이 있는지 판단해야 합니다.


# NIM-TRADE 프로젝트 진행 상황
## 중요: Phase 1부터 시행해야 함
**현재 상태: Phase 2가 완료되었으나 Phase 1이 건너뛰어짐**
- 올바른 접근법: Phase 1 → Phase 2 → Phase 3 → Phase 4 순차적 진행 필요
- Phase 1이 건너뛰어져 시스템 설계 기반 없이 Phase 2가 구현됨
- Phase 1의 시스템 설계 및 아키텍처 작업이 필수적으로 선행되어야 함

## Phase 1 팀 구성 (시스템 설계 단계)
- **Architect**: 시스템 아키텍처 설계 및 기술 스택 결정
- **Designer**: UI/UX 디자인 및 사용자 경험 설계  
- **Planner**: 프로젝트 계획 수립 및 일정 관리
- **Researcher**: 관련 기술 및 트레이딩 시스템 연구

## Phase 1 주요 작업 항목
1. 시스템 아키텍처 설계 (멀티레이어 구조 정의)
2. 기술 스택 결정 (Python, FastAPI, Next.js 등)
3. 데이터베이스 설계 (시장 데이터, 트레이딩 기록)
4. API 설계 (에이전트 통신, 시장 데이터 인터페이스)
5. 보안 및 인증 시스템 설계
6. 모니터링 및 로깅 시스템 설계

## 현재 상태
- **Phase 1** (시스템 설계 및 아키텍처): **완료됨 ✅** (2026-04-05 완료)
- **Phase 2** (에이전트 배틀 시스템 MVP): 진행 예정
- **Phase 3** (LLM Arbiter 및 자가 전략 생성): 진행 예정
- **Phase 4** (통합 테스트 및 웹 UI): 미완료

## Phase 1 완료된 작업 ✅

### 완료된 핵심 모듈
- **HMM Regime Classifier** (`ai_trading/core/hmm_regime.py`) - John
  - 15개 단위 테스트 통과, 정확도 검증 완료
  - 3개 regime (Bull/Sideways/Bear) 분류
  - 실시간 예측 인터페이스 구현

- **Triple Barrier Labeler** (`ai_trading/core/triple_barrier.py`) - Tailor
  - Triple Barrier 알고리즘 완전 구현
  - Barrier 설정: TP 2x ATR, SL 1x ATR, 시간 20봉
  - 레이블: {-1, 0, 1} (SL, Time, TP)
  - 샘플 가중치: 1.0 (명확), 0.3 (불확실)

- **RL Trading Environment** (`ai_trading/rl/trading_env.py`) - John
  - Gymnasium 인터페이스 완전 구현
  - 26개 단위 테스트 통과
  - 포지션 관리 및 수수료 모델 포함

- **PPO Training Script** (`ai_trading/rl/train_rl.py`) - Tailor
  - PPO 알고리즘 연구 및 구현
  - 학습 파이프라인 설계 완료

- **UI/UX 컴포넌트** (`dashboard/components/`) - Coline
  - 10개 React 컴포넌트 구현 완료
  - AgentCard, PortfolioValueChart 등
  - Tailwind CSS 스타일링 완료

## 완료된 작업 (Phase 2)

### 핵심 기능
- 2가지 트레이딩 전략 에이전트 구현 (모멘텀 헌터, 평균회귀)
- 배틀 시스템을 통한 에이전트 간 경쟁 구조
- 포트폴리오 추적 및 성과 모니터링

## 다음 단계 (Phase 3)

### 주요 목표
1. **LLM Arbiter 개발**: 에이전트 간 자본 재배분을 위한 지능형 중재자
2. **자가 전략 생성**: LLM을 활용한 새로운 트레이딩 전략 자동 생성
3. **향상된 의사결정 시스템**: 실시간 시장 분석 및 전략 최적화

### 예상 구현 항목
- llm_arbiter.py: LLM 기반 자본 배분 시스템
- strategy_generator.py: 자가 전략 생성 엔진
- market_analyzer.py: 실시간 시장 분석 모듈
- enhanced_dashboard.py: LLM Arbiter 통합 대시보드

## 남은 작업 요약
- 🔄 Phase 3: LLM Arbiter 및 자가 전략 생성 (진행 예정)
- ⏳ Phase 4: 통합 테스트 및 웹 UI 개발
- ⏳ Freqtrade 연동
- ⏳ 실제 API 연동

## Phase 1 팀 구성 및 협업 구조
### Phase 1 팀 구성
- **Team Leader**: 시스템 아키텍처 설계 및 기술 스택 결정
- **Coline**: UI/UX 디자인 및 사용자 경험 설계  
- **John**: 프로젝트 계획 수립 및 일정 관리
- **Tailor**: 관련 기술 및 트레이딩 시스템 연구


### 팀 구성 시 주의사항 (중요!)
### 팀 생성 시 발생한 문제와 해결책
**문제**: 팀 생성 시 일부 팀원만 실제로 등록되고 나머지는 통신 불가 상태 발생
**원인**: TeamCreate 후 Agent 스폰 시 팀 구성원들이 올바르게 등록되지 않음
**해결**: 팀 생성 후 모든 팀원이 실제로 등록되었는지 반드시 확인

### 팀 생성 및 관리 체크리스트
1. **팀 생성**: TeamCreate로 팀 생성
2. **팀원 스폰**: Agent tool로 모든 팀원 스폰 (team_name 파라미터 필수)
3. **등록 확인**: 팀 구성 파일(`~/.claude/teams/{team-name}/config.json`)에서 모든 팀원이 members 배열에 등록되었는지 확인
4. **backendType 확인**: 모든 팀원의 backendType이 "in-process"로 설정되어야 함
5. **subscriptions 설정**: 팀원 간 통신을 위해 subscriptions가 올바르게 설정되었는지 확인
6. **통신 테스트**: 팀원 간 SendMessage로 통신 테스트

### 문제 발생 시 대처 방법
- **팀원이 작업을 시작하지 않을 때**: 팀 구성 파일을 확인하고 팀원들이 실제로 등록되었는지 확인
- **통신이 안 될 때**: subscriptions 설정과 backendType을 확인
- **팀 재구성 필요 시**: 모든 팀원을 종료(shutdown_request)한 후 팀 삭제 및 재생성

### Phase 1 팀 subscriptions 설정
- team-lead: subscriptions: ["coline", "John", "Tailor"]
- Coline: subscriptions: ["team-lead", "John", "Tailor"]
- John: subscriptions: ["team-lead", "Coline", "Tailor"]
- Tailor: subscriptions: ["team-lead", "John", "Coline"]


## 팀원 역할 업데이트
- **Chalie → Coline** (UI/UX Design)
- **Jessie → John** (프로젝트 계획 및 관리)
- **Serina → Tailor** (기술 연구)

## 업데이트된 팀 subscriptions 설정
- John: subscriptions: ["Coline", "Tailor"]
- Coline: subscriptions: ["John", "Tailor"]
- Tailor: subscriptions: ["John", "Coline"]

## 협업 구조
- 각 팀원은 자신의 계획 문서에 따라 작업 진행
- 일일 스탠드업을 통해 진행 상황 공유
- 주간 리뷰를 통해 성과 평가 및 계획 조정

## 다음 단계
1. 팀 생성: TeamCreate로 팀 생성
2. 팀원 스폰: Agent tool로 모든 팀원 스폰
3. 등록 확인: 팀 구성 파일에서 모든 팀원 등록 확인
4. 작업 시작: 각 팀원별 계획 문서에 따라 작업 진행

## Phase 1 협업 구조
- 팀 작업 진행 시 한 태스크가 끝나면 보고하고 다음 태스크를 진행하도록 함
- 작업 이후 폴더 내 CLAUDE.md 작성(만약 이미 작성되어 있다면 업데이트)
- 팀 작업이 실행되면, agents_docs 폴더에 각 팀메이트 본인의 md 파일을 읽고 태스크를 시작한다.
- 다음 작업 시 필요한 내용에 대해 스스로 피드백을 작성할 수도 있고, 팀원 간에 협업 시 해당 md 파일을 참고하여 효율적인 협업을 진행한다.