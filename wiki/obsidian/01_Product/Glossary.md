# Glossary

## Trinity Score
전략 품질을 통합한 점수. 코드베이스에 v1/v2 공식을 함께 보유.

## IS / OOS
- IS(In-Sample): 학습/튜닝 구간
- OOS(Out-of-Sample): 일반화 검증 구간

## WFO (Walk-Forward Optimization)
시간축을 따라 train/test를 반복 분할해 과적합 가능성을 점검하는 방식.

## Monte Carlo
수익률 경로를 재샘플링해 파산 확률/분포 리스크를 점검하는 방식.

## Evolution Trigger
진화 사이클을 시작하는 조건. 현재 구현은 heartbeat 중심.

## Strategy Loader
LLM 생성 코드를 AST 검증 후 안전한 네임스페이스에서 동적 로딩.
