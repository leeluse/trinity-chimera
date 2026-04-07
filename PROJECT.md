# PROJECT.md — Trinity AI Trading System

> LLM 에이전트들이 스스로 전략을 생성하고, 백테스트로 검증하고,
> 결과를 보고 전략을 개선하는 과정을 실시간으로 반복하는 시스템.

---

## 1. 핵심 루프
```
시장 데이터 (OHLCV + Regime) + 이전 백테스트 결과
│ ▼ LLM → 전략 생성
│ ▼ 백테스트 실행 → Trinity Score 계산
│ ▼ 결과를 LLM에게 피드백 → 개선 결정 + 전략 로그 기록
│ └──────────────── 반복
```

---

## 2. 전략 생성 방식 (LLM)
에이전트는 두 가지 모드로 전략을 생성한다.

### Mode 1 — 파라미터 조정 (초기)
기존 전략 템플릿 안에서 수치를 변경.

### Mode 2 — 전략 자유 생성 (목표)
지표 선택, 진입/청산 조건, 포지션 사이징까지 LLM이 직접 설계.
- **구현 방식**: 동적 Python 코드 생성 및 샌드박스 실행 (B-Mode).
- **보안**: `ast` 기반 정적 분석 및 `multiprocessing` 타임아웃 적용.

---

## 3. LLM 입력 구조
- **시장 맥락**: 현재 Market Regime (HMM 기반), 변동성, 주요 지표 트렌드.
- **성과 피드백**: 이전 버전의 Trinity Score, MDD, 승률, 거래 횟수 및 구체적인 손실 구간 로그.
- **제약 조건**: 사용 가능한 라이브러리 목록, 타임아웃 제한, 메모리 제한.

---

## 4. Trinity Score
Trinity Score = Return × 0.40 + Sharpe × 25 × 0.35 + (1 + MDD) × 100 × 0.25

---

## 5. 에이전트 구성
- **Momentum Hunter**: 추세 추종 및 가속도 기반 돌파 전략 특화.
- **Mean Reverter**: 과매수/과매도 구간의 평균 회귀 및 변동성 기반 역추세 특화.
- **Macro Trader**: 거시 지표 및 장기 추세 분석 기반 전략 특화.
- **Chaos Agent**: 비정형 데이터 및 실험적 가설 기반의 고위험-고수익 전략 특화.

---

## 6. 시스템 구조
```
trinity-chimery/
├── run                # 통합 실행 스크립트 (front, api, slack) ✅
├── front/             # Next.js 14 대시보드 (포트 3000) ✅
│   └── package.json   # 'npm run front' 단축 명령어 포함 ✅
├── api/               # FastAPI + WebSocket (포트 8000) ✅
│   ├── main.py        # 서버 진입점 및 엔드포인트 ✅
│   └── services/      # 자가 개선 핵심 로직 (Mock 기반 구현 중) 
└── ai_trading/        # 트레이딩 엔진 및 AI 로직
    ├── core/          # HMM Regime, Triple Barrier, 전략 로더/인터페이스, 백테스트 매니저 ✅
    ├── rl/            # Gymnasium 환경 및 PPO/SAC 학습 로직
    ├── agents/        # 에이전트 페르소나 및 전략 생성 로직
    ├── battle/        # 에이전트 간 경쟁 및 포트폴리오 관리
    ├── freqai/        # FreqAI 기반 학습 데이터 관리
    └── tests/         # 샌드박스 및 통합 테스트
```

---

## 7. 실행 및 인프라
- **Database**: Supabase (PostgreSQL) - 전략 버전, 성과 지표, 진화 로그 저장.
- **Scheduler**: APScheduler - 에이전트별 자율 진화 루프 관리.
- **실행 방법**: 루트의 `./run` 스크립트를 통해 서비스별 즉시 실행 가능.

---

## 8. 설계 결정 (ADR)
- **ADR-001**: 전략 생성 — 템플릿 $\rightarrow$ 자유 생성 점진적 확장 (B-Mode 채택).
- **ADR-002**: LLM 입력 = 백테스트 결과 + 실시간 시장 데이터.
- **ADR-003**: Trinity Score를 LLM 목표 수치로 사용.
- **ADR-006**: 과적합 방지를 위해 In-Sample/Out-of-Sample 분리 및 보수적 비용 모델 적용.
- **ADR-007**: Supabase를 이용한 경량 전략 이력 및 메트릭 저장.