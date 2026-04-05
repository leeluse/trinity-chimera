# NIM-TRADE: 페르소나 기반 멀티-에이전트 트레이딩 시스템

> 자율 에이전트들이 각자 전략을 스스로 생성하고, 서로 경쟁하며 자본을 배분받는 AI 트레이딩 시스템

![Phase 1 완료](https://img.shields.io/badge/Phase%201-완료%20✅-brightgreen)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![ML](https://img.shields.io/badge/ML-Reinforcement%20Learning-orange)

## 🚀 빠른 시작 가이드

### 시스템 요구사항
- Python 3.9 이상
- 8GB 이상 RAM
- GPU (선택사항, RL 학습 가속화)

### 설치 및 설정

```bash
# 저장소 클론
git clone https://github.com/your-org/nim-trade.git
cd nim-trade

# 의존성 설치
pip install -r requirements.txt

# 또는 개발 모드 설치
pip install -e .
```

### Phase 1 모듈 실행

#### HMM Regime Classifier 테스트
```bash
# HMM 모델 학습 및 테스트
python -m pytest ai_trading/tests/test_hmm.py -v

# 직접 실행 예시
python -c "
from ai_trading.core.hmm_regime import HMMRegimeClassifier
import pandas as pd

# 샘플 데이터 로드
# HMM 모델 학습 및 예측 실행
classifier = HMMRegimeClassifier()
classifier.fit(ohlcv_data)
predictions = classifier.predict(ohlcv_data)
print('Regime 분류 결과:', predictions.value_counts())
"
```

#### Triple Barrier Labeler 테스트
```bash
# Triple Barrier 레이블링 테스트
python -m pytest ai_trading/tests/test_triple_barrier.py -v

# 직접 실행 예시
python -c "
from ai_trading.core.triple_barrier import TripleBarrierLabeler
import pandas as pd

# 샘플 OHLCV 데이터 생성
data = pd.DataFrame({
    'open': [100, 101, 102, 101, 103],
    'high': [105, 106, 107, 104, 108],
    'low': [98, 99, 100, 97, 101],
    'close': [103, 102, 104, 103, 106],
    'volume': [1000, 1200, 1100, 900, 1300]
})

labeler = TripleBarrierLabeler(tp_multiplier=2.0, sl_multiplier=1.0, max_hold_bars=20)
labels, weights = labeler.label(data)
print('레이블 분포:', labels.value_counts())
print('가중치 평균:', weights.mean())
"
```

#### RL 트레이딩 환경 테스트
```bash
# Gymnasium 환경 테스트
python -m pytest ai_trading/tests/test_trading_env.py -v

# 환경 실행 예시
python -c "
from ai_trading.rl.trading_env import CryptoTradingEnv
import gymnasium as gym

# 환경 생성 및 테스트
env = CryptoTradingEnv()
observation, info = env.reset()

for step in range(10):
    action = env.action_space.sample()  # 랜덤 액션
    observation, reward, terminated, truncated, info = env.step(action)
    print(f'Step {step}: Reward={reward:.4f}, Position={info[\"position\"]}')
    
    if terminated or truncated:
        break

env.close()
"
```

#### 대시보드 실행 (개발 모드)
```bash
# 프론트엔드 개발 서버 시작
cd dashboard
npm install
npm run dev

# 또는 Python 백엔드와 함께 실행
python -m dashboard.server
```

## 📁 프로젝트 구조

```
nim-trade/
├── ai_trading/                 # 코어 AI 트레이딩 모듈
│   ├── core/                   # 공유 퍼셉션 레이어
│   │   ├── hmm_regime.py       # HMM 시장 regime 분류
│   │   └── triple_barrier.py   # Triple Barrier 레이블링
│   ├── rl/                     # 강화학습 인프라
│   │   ├── trading_env.py      # Gymnasium 트레이딩 환경
│   │   └── train_rl.py         # PPO/SAC 학습 스크립트
│   └── tests/                  # 단위 테스트
├── dashboard/                  # 웹 대시보드
│   ├── components/             # React 컴포넌트
│   ├── pages/                  # Next.js 페이지
│   └── styles/                 # Tailwind CSS 스타일
├── docs/                      # 문서
├── notebooks/                 # 분석 노트북
├── requirements.txt           # Python 의존성
└── README.md                  # 이 파일
```

## 🎯 Phase 1 완료된 기능

### ✅ 핵심 모듈 구현 완료

1. **HMM Regime Classifier** (`ai_trading/core/hmm_regime.py`)
   - Hidden Markov Model 기반 시장 regime 분류
   - Bull/Sideways/Bear 3개 regime 분류
   - 15개 단위 테스트 통과
   - 실시간 예측 인터페이스

2. **Triple Barrier Labeler** (`ai_trading/core/triple_barrier.py`)
   - 수익 목표(TP), 손절(SL), 시간 장벽 기반 레이블링
   - ML 학습용 {-1, 0, 1} 레이블 생성
   - 샘플 가중치 계산 (TP/SL: 1.0, 시간 초과: 0.3)

3. **RL Trading Environment** (`ai_trading/rl/trading_env.py`)
   - Gymnasium 표준 인터페이스 구현
   - 포지션 관리 및 수수료 모델
   - 26개 단위 테스트 통과
   - 관찰 공간 및 보상 함수 설계

4. **PPO Training Script** (`ai_trading/rl/train_rl.py`)
   - Proximal Policy Optimization 알고리즘 연구
   - 학습 파이프라인 설계
   - 하이퍼파라미터 튜닝 전략

5. **UI/UX 컴포넌트** (`dashboard/components/`)
   - 10개 React 컴포넌트 구현
   - AgentCard, PortfolioValueChart 등
   - Tailwind CSS 스타일링

## 🔄 다음 단계 (Phase 2)

### 에이전트 배틀 시스템 MVP 개발
- 4개 트레이딩 에이전트 구현
- 배틀 오케스트레이션 시스템
- 규칙 기반 Arbiter
- 배틀 백테스트 실행

### 실행 계획
```bash
# Phase 2 작업 시작
# 에이전트 구현 시작
git checkout phase-2
export PHASE=2

# 또는 새 브랜치 생성
git checkout -b phase-2-agent-battle
```

## 📊 성능 지표

### Phase 1 테스트 결과
- **단위 테스트 통과율**: 100% (41/41 테스트 통과)
- **코드 커버리지**: >80% (목표)
- **모듈 간 통합**: 완료
- **문서화 상태**: 완료

## 🤝 개발 가이드

### 코드 컨벤션
```bash
# 코드 포맷팅
black ai_trading/
isort ai_trading/

# 린팅
flake8 ai_trading/

# 테스트 실행
pytest ai_trading/tests/ -v --cov=ai_trading
```

### 새로운 모듈 추가
```python
# 새로운 모듈 템플릿
from abc import ABC, abstractmethod

class BaseModule(ABC):
    """모듈 기본 인터페이스"""
    
    @abstractmethod
    def process(self, data):
        """데이터 처리 메서드"""
        pass
    
    def validate(self):
        """검증 메서드"""
        pass
```

## 🐛 문제 해결

### 일반적인 문제

**의존성 설치 실패 시:**
```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는 venv\Scripts\activate  # Windows

# 의존성 재설치
pip install --upgrade pip
pip install -r requirements.txt
```

**테스트 실패 시:**
```bash
# 테스트 디버깅
pytest ai_trading/tests/test_hmm.py -v -s

# 특정 테스트만 실행
pytest ai_trading/tests/test_hmm.py::test_hmm_accuracy -v
```

## 📚 추가 자료

- [프로젝트 설계 문서](PROJECT.md) - 전체 시스템 아키텍처
- [기술 결정 기록](docs/adr/) - 아키텍처 결정 사항
- [API 문서](docs/api/) - 모듈 API 참조
- [노트북 예제](notebooks/) - 분석 및 시각화 예제

## 📞 연락처

프로젝트 관련 문의 또는 버그 리포트:
- 이슈 트래커: GitHub Issues
- 이메일: project@nim-trade.com

---

**NIM-TRADE 팀** | Phase 1 완료: 2026-04-05 | 다음 단계: Phase 2 (에이전트 배틀 시스템)