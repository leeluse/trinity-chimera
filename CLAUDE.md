# 처음 이 글을 읽게 된다면
- 당신은 완벽하지 않습니다. 당신이 실수하거나 잘한 일이 있다면 개선을 위해 해당 md 파일을 이용해 피드백을 작성해주세요.
- 하나의 Phase가 끝나고 난 뒤 리더는 최종 점검 진행 후 다음 Phase로 넘어갈지, 아니면 현재 Phase에서 개선할 점이 있는지 판단해야 합니다.
- 폴더를 제거하고 싶을 때는 휴지통으로 버려야 합니다. (.env, slack-on.py는 삭제하지 마세요.)
- 프로젝트를 개발하면서 '하나라도' 기능을 개선하거나, 수정을 하거나, 파일을 제거하면 해당 기능의 폴더 내 CLAUDE.md에 문서화를 진행하세요. CLAUDE.md 문서는 항상 업데이트 되어 있어야 하며 100줄 내외로 유지되야 합니다.
- 무언가 구현, 또는 수정하기 전 변경 내역이 존재한다면 push 진행 후 시작하세요.
- 


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

## 완료된 핵실 성과
- **Tailor**: 순수 자가 전략 생성 시스템 전체 완료 (약 2,900줄 코드)
- **Coline**: 프론트엔드 통합 대시보드 완성 (Next.js + TypeScript + Zustand)
- **협업**: 두 에이전트 효과적 협력
- **기술 스택**: 실시간 WebSocket 통신 구현 완료

## 실수 방지 기록 (2026-04-07)

### 문서화 시 주의사항
- **통합 명령어 문서화 시**: run 스크립트의 모든 명령어를 빠짐없이 확인하고 문서에 포함할 것
- **실수 내용**: `./run api` 명령어가 CLAUDE.md 문서에서 누락됨
- **원인**: 문서 작성 시 run 파일의 모든 case 문을 확인하지 않음
- **해결**: 문서에 `./run api` 명령어 추가 완료

### 앞으로의 방향
- 문서 업데이트 시 실제 파일과 일치하는지 항상 확인
- run 스크립트가 수정될 경우 문서도 즉시 업데이트
- 새로운 서비스가 추가될 때마다 문서에 반영

## 개발 명령어 (Runner Script)
프로젝트 루트에서 `./run` 명령어를 사용하여 각 서비스를 쉽게 실행할 수 있습니다.

```bash
chmod +x run       # 최초 실행 시 권한 부여 필요
./run front        # 프론트엔드 대시보드 실행
./run api          # 백엔드 API 서버 실행
./run slack        # 슬랙 에이전트 실행
```

### 개별 서비스 실행 (상세)

#### 프론트엔드
```bash
cd front
npm run dev    # 개발 서버 실행
npm run build  # 프로덕션 빌드
npm run start  # 프로덕션 서버 실행
```

### 백엔드 실행
```bash
cd api
python main.py  # 포트 8000에서 FastAPI 서버 실행
```

### 통합 실행 (프론트 + 백엔드)
```bash
# 터미널 1: 백엔드 실행
cd api && python main.py

# 터미널 2: 프론트엔드 실행  
cd front && npm run front
```

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

- 2가지 트레이딩 전략 에이전트 구현 (모멘텀 헌터, 평균회귀)
- 배틀 시스템을 통한 에이전트 간 경쟁 구조
- 포트폴리오 추적 및 성과 모니터링


- Next.js 기반 대시보드 완성 (포트 3000)
- 프레임워크: Next.js 14.1.0 (App Router)
- 언어: TypeScript
- 스타일링: Tailwind CSS
- 상태 관리: Zustand
- 실시간 통신: WebSocket

주요 컴포넌트 구조 계획 및 구현

     dashboard/
     ├── app/
     │   ├── layout.tsx          # 루트 레이아웃
     │   ├── page.tsx            # 메인 페이지 (탭 구조)
     ├── components/
     ├── store/
     │   └── useDashboardStore.ts # Zustand 상태 관리
     ├── hooks/
     │   └── useWebSocket.ts      # WebSocket 훅(미완)
     └── types/
         └── index.ts             # 타입 정의
