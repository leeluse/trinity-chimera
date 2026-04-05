### 2-3. Signal Layer — FreqAI + LightGBM

**LightGBMRegimeModel** (`freqai/lgbm_model.py`)
- `BaseClassifierModel` 상속
- Sample weight 지원 (`&-weight` 컬럼 자동 인식)
- Isotonic regression으로 확률 캘리브레이션
- Early stopping + Feature importance 자동 출력
- 출력: `p_long`, `p_short`, `p_flat`, `confidence`