# Backtest UI

## 엔트리
`client/app/backtest/BacktestClientPage.tsx`

## 주요 기능
- 전략 목록 조회/선택
- 전략 코드 로드/수정
- 백테스트 실행
- 채팅 생성 코드 즉시 반영
- 전략 배포(`/api/chat/deploy`)

## 시각화
- 캔들 차트: `lightweight-charts`
- 매매 마커: 진입/청산 포인트
- 결과 카드: 수익률, MDD, Win, PF, Sharpe 등
- Trade Analysis: 평균 손익, 연속 승패, 롱/숏 비중

## 탭
- 지표
- 백테스트
- 코드
