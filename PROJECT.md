{
  "TargetFile": "PROJECT.md",
  "Overwrite": true,
  "IsArtifact": true,
  "ArtifactMetadata": {
    "ArtifactType": "task",
    "Summary": "자율적 전략 탐색 및 도구 활용 기반 마스터 플랜",
    "RequestFeedback": true
  },
  "Description": "에이전트에게 HMM, Triple Barrier 등의 도구를 제공하되, 성과에 따라 스스로 전략을 수정하고 새로운 최적점을 찾는 '자율성' 중심의 설계를 반영합니다.",
  "ReplacementChunks": [
    {
      "StartLine": 1,
      "EndLine": 55,
      "TargetContent": "# 🚀 AI Multi-Agent Futures Trading System (NIM-Trade)\n\n## 1. 프로젝트 비전\n**무한 경쟁 기반의 에이전트 아레나(Agent Arena)**를 통해 시장 변화에 스스로 적응하는 고강건성 선물 매매 자동화 시스템 구축.\n\n## 2. 핵심 아키텍처 (3-Layer 모델)\n\n### Layer 1: 시그널 레이어 (Signal Layer - 기초 체력)\n- **Market Regime(HMM)**: 현재 시장 판도를 분석하여 각 에이전트에게 상황 데이터 제공.\n- **Triple Barrier Labeling**: 지능형 레이블링으로 고품질 학습 데이터 생산.\n- **ML Signal Generation**: 확률 기반 방향성 지표 산출.\n\n### Layer 2: 경쟁 레이어 (Competition Layer - Survival Arena)\n- **에이전트 리더보드**: 실시간 PnL, Sharpe Ratio 기반으로 각 에이전트 순위 산정.\n- **가변 자본 할당(Dynamic Allocation)**: 성적이 좋은 에이전트의 베팅 비중을 늘리고, 성적이 나쁜 에이전트의 권한을 축소.\n- **Competing Personas**:\n    - **Flash (Aggressive Scalper)**: 고레버리지, 단기 돌파 매매 중심.\n    - **Guardian (Defensive Conservative)**: 낮은 변동성, 자본 보존 매매 중심.\n    - **Quant (Statistical Neutral)**: 통계적 차익 거래 및 중립형 매매 중심.\n- **Evolutionary Logic**: 성과가 저조한 에이전트(모델)를 자동으로 퇴출하고 새로운 하이퍼파라미터 모델로 대체.",
      "ReplacementContent": "# 🚀 AI Multi-Agent Futures Trading System (NIM-Trade)\n\n## 1. 프로젝트 비전\n**자율적 전략 탐색(Autonomous Strategic Search)**과 **무한 아레나 경쟁**을 통해 도구를 스스로 익히고 진화하는 트레이딩 에이전트 에코시스템 구축.\n\n## 2. 핵심 아키텍처 (Toolbox & Autonomy)\n\n### Layer 1: 에이전트 무기고 (Agent Toolbox - 전술 도구)\n- **Regime Detector (HMM)**: 시장의 성격을 파악하는 도구.\n- **Outcome Labeler (Triple Barrier)**: 매매 결과의 질을 평가하는 도구.\n- **Predictive Engine (ML Signals)**: 확률적 미래를 예측하는 도구.\n- *에이전트는 이 도구들을 원재료로 활용하되, 어떤 도구의 가중치를 높일지는 스스로 결정함.*\n\n### Layer 2: 자율 의사결정 레이어 (Autonomous Decision & Arena)\n- **Self-Correction Loop**: 에이전트가 실시간 PnL 성과가 낮아질 경우, 스스로 하이퍼파라미터를 재조정하거나 강조하는 피처(Feature)를 변경하며 전략을 피봇함.\n- **Persona-driven Autonomy**:\n    - **Flash (Momentum focused)**: 돌파 시그널 무기를 선호하며 공격적 익절 전략 탐색.\n    - **Guardian (Risk-first)**: 변동성 및 손절 장벽 도구를 최우선시하며 생존 전략 탐색.\n    - **Explorer (Discovery)**: 무기고의 도구들을 새롭게 조합하여 시장에 없던 변칙 전략을 스스로 실험.\n- **Leaderboard-based Allocation**: 성과를 내는 '방식'이 시장에 통한 페르소나에게 실제 운용 자금을 동적으로 몰아줌.\n\n### Layer 3: 적응형 실행 레이어 (Refining Execution - Freqtrade)\n- **Multi-Agent Voting**: 각 에이전트의 자율적 판단을 종합하여 최종 주문 집행.\n- **Dynamic Backtesting**: 실시간으로 각 에이전트의 '실험적 전략' 성과를 그림자 매매(Shadow Trading)로 추적.",
      "AllowMultiple": false
    }
  ],
  "Instruction": "에이전트에게 제공되는 핵심 기술들을 '도구(Toolbox)'로 정의하고, 에이전트가 이를 자율적으로 조합하여 스스로 전략을 수정해 나가는 '자율성' 기반의 체계를 프로젝트 파일에 반영했습니다."
}
