# 🏟 Arena Mechanism: 경쟁 및 자산 배분

에이전트 간의 '약육강식' 경쟁을 통해 시장에 가장 적절한 전략을 선별하는 시스템입니다.

## 1. 에이전트 리더보드 (Leaderboard)
- **평가 지표**: 
    - **PnL (Profit & Loss)**: 절대 수익률.
    - **Sharpe Ratio**: 위험 대비 수익 효율성.
    - **Max Drawdown (MDD)**: 최대 낙폭 방어력.
- **평가 주기**: 단기(최근 50회 매매)와 장기(최근 500회 매매) 성과를 혼합하여 점수 산출.

## 2. 가변 자본 할당 (Dynamic Capital Allocation)
- **로직**: 순위가 높은 에이전트에게 더 많은 'Votitng Weight'와 'Asset Allocation' 부여.
- **배분 방식**:
    - **Tier 1 (우승)**: 가용한 자본의 60% 운용 권한.
    - **Tier 2 (우수)**: 가용한 자본의 30% 운용 권한.
    - **Tier 3 (그림자)**: 가상 매매(Shadow Trading)만 수행하며 실거래 배제.

## 3. 페르소나별 경쟁 전략 (Winning Persona)
- 시장 상황(Regime)에 따라 리더보드 상위권 페르소나가 자연스럽게 교체됨.
    - **Bull Market**: Flash(공격수)가 자본을 독식.
    - **Sideways/Volatility Market**: Delta(기술 분석가)나 Guardian(수비수)이 자산 통제권을 확보.

---
