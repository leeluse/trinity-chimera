# Triple Barrier 결과 데이터 인터페이스

## 데이터 구조

### TripleBarrierResult 객체

```typescript
interface TripleBarrierResult {
  // 핵심 결과 시리즈
  labels: Series<number>;          // -1, 0, 1 (SELL, HOLD, BUY)
  returns: Series<number>;        // 실제 수익률 (예: 0.025 = 2.5%)
  weights: Series<number>;        // 샘플 가중치 (1.0 또는 0.3)
  barrier_types: Series<string>;   // "TAKE_PROFIT" | "STOP_LOSS" | "TIME_EXPIRY"
  hold_times: Series<number>;     // 보유 기간 (봉 수)
  events: LabelOutput[];         // 상세 이벤트 목록
}

interface LabelOutput {
  label: -1 | 0 | 1;
  return_value: number;           // (end_price - start_price) / start_price
  barrier_type: BarrierType;      // TP, SL, TIME
  hold_bars: number;              // 실제 보유 기간
  weight: number;                 // 1.0 (명확) 또는 0.3 (불확실)
  start_price: number;            // 진입 가격
  end_price: number;              // 청산 가격
}

interface BarrierType {
  TAKE_PROFIT = 1,
  STOP_LOSS = -1,
  TIME_EXPIRY = 0
}

interface LabelStats {
  total_events: number;
  tp_rate: number;               // TP 비율 (0.0 ~ 1.0)
  sl_rate: number;               // SL 비율
  time_rate: number;             // 시간 만료 비율
  avg_return: number;            // 평균 수익률
  avg_hold_time: number;         // 평균 보유 기간
  avg_weight: number;            // 평균 샘플 가중치
  label_distribution: {
    positive: number;            // +1 레이블 수
    neutral: number;             // 0 레이블 수
    negative: number;            // -1 레이블 수
  };
}
```

## JSON 샘플 데이터

```json
[
  {
    "timestamp": "2024-01-01T10:00:00",
    "close_price": 102.45,
    "label": 1,
    "label_name": "BUY",
    "barrier_type": "TAKE_PROFIT",
    "sample_weight": 1.0,
    "return_value": 0.0253,
    "hold_bars": 5,
    "atr": 1.23,
    "tp_level": 104.89,
    "sl_level": 101.22
  },
  {
    "timestamp": "2024-01-01T14:00:00",
    "close_price": 101.80,
    "label": -1,
    "label_name": "SELL",
    "barrier_type": "STOP_LOSS",
    "sample_weight": 1.0,
    "return_value": -0.0185,
    "hold_bars": 3,
    "atr": 1.15,
    "tp_level": 104.10,
    "sl_level": 100.78
  },
  {
    "timestamp": "2024-01-01T18:00:00",
    "close_price": 102.10,
    "label": 0,
    "label_name": "HOLD",
    "barrier_type": "TIME_EXPIRY",
    "sample_weight": 0.3,
    "return_value": 0.0042,
    "hold_bars": 20,
    "atr": 1.30,
    "tp_level": 104.70,
    "sl_level": 100.81
  }
]
```

## 시각화 요구사항

### 1. 레이블 분포 차트
- **차트 유형**: Pie 또는 Donut Chart, 또는 Stacked Bar
- **데이터**: label_name 분류 (BUY, SELL, HOLD)
- **색상**: BUY (녹색), SELL (빨간색), HOLD (회색)
- **표시값**: 비율(%) 및 개수

### 2. 샘플 가중치 히스토그램
- **차트 유형**: Histogram 또는 Bar Chart
- **데이터**: weights 분포
- **구간**: 0.3 (Time expiry), 1.0 (Clear signal)
- **색상 구분**: 빈도수별 색상 강도

### 3. 레이블 타임라인 차트
- **차트 유형**: Candlestick Chart + Scatter Markers
- **X축**: timestamp
- **Y축**: close_price
- **마커**:
  - 🟢 삼각형 (위): BUY (TP hit)
  - 🔴 삼각형 (아래): SELL (SL hit)
  - ⚪ 원: HOLD (Time expiry)
- **오버레이**: TP/SL 장벽 수준 (점선)

### 4. 수익률 분포 차트
- **차트 유형**: Box Plot 또는 Violin Plot
- **데이터**: return_value by label_name
- **인사이트**: 레이블별 수익률 분포 비교

### 5. 보유 기간 분석
- **차트 유형**: Bar Chart 또는 Heatmap
- **데이터**: hold_bars by barrier_type
- **색상**: 보유 기간 길이에 따른 색상 변화

### 6. 메트릭 카드
```
┌─────────────┬─────────────┬─────────────┐
│ 총 이벤트   │ 평균 수익률 │ Sharpe 비율 │
│    127     │   +2.3%    │    1.42     │
└─────────────┴─────────────┴─────────────┘
┌─────────────┬─────────────┬─────────────┐
│ TP 비율     │ SL 비율     │ Time 비율   │
│   35.4%    │   42.5%    │   22.1%     │
└─────────────┴─────────────┴─────────────┘
```

## API 인터페이스

### 데이터 내보보내기

```python
from ai_trading.core import TripleBarrierLabeler

# 라벨링 실행
labeler = TripleBarrierLabeler(config)
result = labeler.label_events(ohlcv_data)

# 1. JSON export
result_df = pd.DataFrame({
    'timestamp': result.labels.index,
    'label': result.labels.values,
    'return': result.returns.values,
    'weight': result.weights.values,
    'barrier_type': [bt.name for bt in result.barrier_types.values]
})
result_df.to_json('triple_barrier_result.json', orient='records')

# 2. 통계 추출
stats = labeler.get_barrier_stats(result)
# Returns: {total_events, tp_rate, sl_rate, time_rate, avg_return, ...}
```

### 프론트엔드 Props

```typescript
interface TripleBarrierDashboardProps {
  // 필수 데이터
  events: TripleBarrierEvent[];

  // 선택적 데이터 (OHLCV 차트용)
  priceData?: {
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];

  // 설정
  config?: {
    showCandlestick?: boolean;      // 캔들스틱 차트 표시
    showBarriers?: boolean;         // 장벽 수준 표시
    showTimeline?: boolean;         // 타임라인 표시
    theme?: 'light' | 'dark';        // 테마
  };

  // 콜백
  onEventClick?: (event: TripleBarrierEvent) => void;
  onTimeRangeChange?: (start: Date, end: Date) => void;
}
```

## 품질 검증 인터페이스

### 데이터 품질 체크리스트

| 검항 | 기준 | 통과 조건 |
|------|------|----------|
| 레이블 유효성 | label in [-1, 0, 1] | 100% 일치 |
| 가중치 유효성 | weight in [0.3, 1.0] | 100% 일치 |
| 수익률 범위 | return_value | 상식적 범위 내 |
| 시간 연속성 | timestamp | 정렬 및 누락 없음 |
| 장벽 타입 | barrier_type | 3개 값만 존재 |

### 품질 메트릭 시각화
- 데이터 품질 스코어 (게이지 차트)
- 이상값 리스트 (테이블)
- 시간대별 레이블링 활동 (히트맵)

## 통합 예시

```python
# Python 백엔드에서 프론트엔드로 데이터 전달
@app.get("/api/triple-barrier")
def get_triple_barrier_data(symbol: str, period: str):
    # 데이터 로드
    ohlcv = load_ohlcv(symbol, period)

    # 라벨링
    labeler = TripleBarrierLabeler()
    result = labeler.label_events(ohlcv)

    # JSON 변환
    return {
        "events": [
            {
                "timestamp": str(idx),
                "close_price": float(ohlcv.loc[idx, "close"]),
                "label": int(result.labels.loc[idx]),
                "label_name": "BUY" if result.labels.loc[idx] == 1 else "SELL" if result.labels.loc[idx] == -1 else "HOLD",
                "barrier_type": result.barrier_types.loc[idx].name,
                "sample_weight": float(result.weights.loc[idx]),
                "return_value": float(result.returns.loc[idx]),
                "hold_bars": int(result.hold_times.loc[idx])
            }
            for idx in result.labels.index
        ],
        "stats": labeler.get_barrier_stats(result),
        "price_data": ohlcv.to_dict(orient="records")
    }
```

## 참고사항

1. **타임스탬프**: ISO 8601 형식 권장
2. **가격 데이터**: 캔들스틱 차트를 위해 OHLCV 필요
3. **지연 로딩**: 대용량 데이터를 위한 페이지네이션 고려
4. **실시간**: WebSocket 연동 시 이벤트 스트리밍 지원
