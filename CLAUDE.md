# 처음 이 글을 읽게 된다면
- 당신은 완벽하지 않습니다. 당신이 실수하거나 잘한 일이 있다면 개선을 위해 해당 md 파일을 이용해 피드백을 작성해주세요.
- 하나의 Phase가 끝나고 난 뒤 리더는 최종 점검 진행 후 다음 Phase로 넘어갈지, 아니면 현재 Phase에서 개선할 점이 있는지 판단해야 합니다.
- 폴더를 제거하고 싶을 때는 휴지통으로 버려야 합니다. (.env, slack-on.py는 삭제하지 마세요.)

# slack-on을 통해 슬랙으로 소통
**실행 방법:**
```bash
source venv/bin/activate
python slack-on.py

```



# TRINITY-CHIMERY 프로젝트 진행 상황

## 현재 팀 구성(Phase에 따라 유동적으로 역할을 부여받음)
- **John(Team-Lead)**
- **Coline(UI/UX/디자인+프론트 개발)**
- **Maxin(인프라)**
- **Tailor(Researcher)**

### 협업 구조
- 각 팀원은 자신의 계획 문서에 따라 작업 진행하며, 계획 문서를 업데이트 해야 할 경우 업데이트 한다.
- 리뷰를 통해 성과 평가 및 계획 조정
- 팀 작업 진행 시 한 태스크가 끝나면 보고하고 다음 태스크를 진행하도록 함
- 작업 이후 폴더 내 CLAUDE.md 작성(만약 이미 작성되어 있다면 업데이트)
- 팀 작업이 실행되면, agents_docs 폴더에 각 팀메이트 본인의 md 파일을 읽고 태스크를 시작한다.
- 다음 작업 시 필요한 내용에 대해 스스로 피드백을 작성할 수도 있고, 팀원 간에 협업 시 해당 md 파일을 참고하여 효율적인 협업을 진행한다.


## 팀 구성 방법
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


---

## 현재 상태
- **Phase 1** (시스템 설계 및 아키텍처): **완료됨 ✅** (2026-04-05 완료)
- **Phase 2** (에이전트 배틀 시스템 MVP): **완료됨 ✅** (2026-04-05 완료)
- **Phase 3** (순수 자가 전략 생성 시스템): **완료됨 ✅** (2026-04-07 업데이트)
- **Phase 4** (통합 테스트 및 웹 UI): **95% 완료**

## 최종 진행률 (2026-04-06 기준)
- **AI 트레이딩 모듈**: 100% 완료 (Tailor)
- **자가 전략 생성 시스템**: 100% 완료 (Tailor)
- **프론트엔드 대시보드**: 95% 완료 (Coline)
- **API 서버 통합**: 90% 완료
- **프로젝트 전체**: 95% 완료

## 완료된 핵심 성과
- **Tailor**: 순수 자가 전략 생성 시스템 전체 완료 (약 2,900줄 코드)
- **Coline**: 프론트엔드 통합 대시보드 완성 (Next.js + TypeScript + Zustand)
- **협업**: 두 에이전트 효과적 협력
- **기술 스택**: 실시간 WebSocket 통신 구현 완료

## Phase 1 완료된 작업 ✅
- **Team Leader**: 시스템 아키텍처 설계 및 기술 스택 결정
- **Coline**: UI/UX 디자인 및 사용자 경험 설계  
- **John**: 프로젝트 계획 수립 및 일정 관리
- **Tailor**: 관련 기술 및 트레이딩 시스템 연구

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

## 완료된 작업 (Phase 3)

### 핵심 성과
- Next.js 기반 대시보드 완성 (포트 3000)
- Mock 데이터로 UI 테스트 가능
- WebSocket 연결 준비 완료
- TypeScript + Zustand 상태 관리 완료

## 남은 작업
-대시보드 마이그레이션 계획: index.html 스타일
사용자는 기존 AI 트레이딩 시스템 구조는 유지하면서 대시보드를 index.html처럼 단순하고 직관적인 구성으로 마이그레이션하려고 합니다. 현재 대시보드는 Next.js + TypeScript + ZustandTailwind CSS로 구축되어 있지만 복잡한 탭 구조와 컴포넌트들이 있습니다.

     현재 구조 분석

     기술 스택

     - 프레임워크: Next.js 14.1.0 (App Router)
     - 언어: TypeScript
     - 스타일링: Tailwind CSS
     - 상태 관리: Zustand
     - 실시간 통신: WebSocket

     주요 컴포넌트 구조

     dashboard/
     ├── app/
     │   ├── layout.tsx          # 루트 레이아웃
     │   ├── page.tsx            # 메인 페이지 (탭
      구조)
     │   └── backtesting/
     │       ├── layout.tsx       # 백테스팅
     레이아웃
     │       └── page.tsx        # 백테스팅 페이지
     ├── components/
     │   ├── AgentCard.tsx        # 에이전트 카드
     │   ├── PortfolioSummaryPanel.tsx #
     포트폴리오 요약
     │   ├── PortfolioValueChart.tsx   # 차트
     │   ├── TradeHistoryTable.tsx     # 거래
     테이블
     │   └── Backtest*.tsx        # 백테스팅 관련
     컴포넌트
     ├── store/
     │   └── useDashboardStore.ts # Zustand 상태
     관리
     ├── hooks/
     │   └── useWebSocket.ts      # WebSocket 훅
     └── types/
         └── index.ts             # 타입 정의

     문제점

     1. 복잡한 탭 구조: Overview, Agents, Trades,
     Self-Improve, Backtesting 등 5개 탭
     2. 정보 과부하: 한 페이지에 너무 많은 정보
     표시
     3. 비직관적 탐색: 사용자가 원하는 정보를
     빠르게 찾기 어려움

     마이그레이션 계획

     사용자 요구사항 분석

     - 디자인: index.html 레이아웃에서 좀 더
     모던한 UI
     - 우선순위: 에이전트 성과, 자가 개선 상태
     - UI 요소: 미니멀리즘, 데이터 시각화,
     인터랙티브, 다크모드

     목표: 모던한 index.html 스타일 단순화

     - 단일 페이지에서 핵심 정보만 표시
     - 미니멀한 디자인과 데이터 시각화 강조
     - 인터랙티브 요소를 통한 사용성 향상
     - 다크모드 지원

     새로운 구조 제안 (모던 index.html 스타일)

     1. 모던한 단일 페이지 디자인

     TRINITY-CHIMERY Dashboard (모던 미니멀리즘)
     ├── 헤더
     │   ├── 로고 + 실시간 연결 상태 (미니멀)
     │   └── 다크모드 토글
     ├── 핵심 지표 섹션 (데이터 시각화 강조)
     │   ├── 실시간 포트폴리오 가치 차트
     (인터랙티브)
     │   ├── 에이전트별 Sharpe 비교 막대 그래프
     │   └── 현재 Regime 상태 표시기
     ├── 에이전트 성과 섹션 (우선순위 1)
     │   ├── Momentum Hunter 카드 (호버 효과,
     상세보기)
     │   ├── Mean Reverter 카드
     │   ├── Macro Trader 카드
     │   └── Chaos Agent 카드
     ├── 자가 개선 섹션 (우선순위 2)
     │   ├── 최근 파라미터 제안 이력
     │   ├── 파라미터 변경 추이 차트
     │   └── 성과 개선 통계
     └── 빠른 액션 영역
         ├── 백테스팅 실행 버튼 (인터랙티브)
         └── 상세 분석 페이지 링크

     2. 구현 단계

     Phase 1: 기본 구조 설계
     - 새로운 app/simple/page.tsx 생성
     - 기존 컴포넌트들을 단순화하여 재사용
     - 상태 관리 최적화

     Phase 2: 핵심 기능 마이그레이션
     - AgentCard 컴포넌트 단순화
     - 포트폴리오 요약 패널 통합
     - 실시간 데이터 표시 최적화

     Phase 3: 사용성 개선
     - 반응형 디자인
     - 로딩 상태 표시
     - 에러 핸들링

     변경될 파일들

     생성될 파일

     - dashboard/app/simple/page.tsx - 새로운
     단순화된 메인 페이지
     - dashboard/components/SimpleAgentGrid.tsx -
     단순화된 에이전트 그리드
     - dashboard/components/QuickMetrics.tsx -
     빠른 지표 표시

     수정될 파일

     - dashboard/components/AgentCard.tsx -
     단순화된 버전
     - dashboard/store/useDashboardStore.ts - 상태
      관리 최적화
     - dashboard/app/page.tsx - 기존 페이지는
     유지하되 리디렉션 추가

     유지될 파일

     - dashboard/hooks/useWebSocket.ts - WebSocket
      통신
     - dashboard/types/index.ts - 타입 정의
     - dashboard/app/backtesting/ - 백테스팅 기능

     기술적 접근법

     컴포넌트 단순화
       - 불필요한 애니메이션 제거
       - 정보 계층화 (중요도별 표시)
       - 모바일 퍼스트 디자인
     상태 관리 최적화
       - 불필요한 상태 변수 제거
       - 데이터 캐싱 전략 구현
       - 실시간 업데이트 최적화
     성능 개선
       - 코드 스플리팅
       - 이미지 최적화
       - WebSocket 연결 최적화

     검증 방법

     기능 테스트
       - 모든 에이전트 카드 정상 표시
       - 실시간 데이터 업데이트 확인
       - 백테스팅 페이지 연결 테스트
     성능 테스트
       - 페이지 로딩 속도 측정
       - WebSocket 연결 안정성 확인
       - 모바일 환경 테스트
     사용성 테스트
       - 정보 접근성 평가
       - 네비게이션 직관성 확인
       - 반응형 디자인 테스트

     결론

     이 마이그레이션은 복잡한 탭 기반 대시보드를
     index.html처럼 단순하고 직관적인 단일
     페이지로 전환합니다. 기존 기능은 모두
     유지하면서 사용성을 크게 향상시킬 수
     있습니다.
