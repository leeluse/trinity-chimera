"""전략 파라미터 최적화 엔진 (Grid, Random, Bayesian)"""
import logging
import random
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from server.modules.backtest.backtest_engine import BacktestEngine, PeriodResult

logger = logging.getLogger(__name__)

@dataclass
class ParamRange:
    name: str
    min_val: float
    max_val: float
    step: float
    is_int: bool = True

    def to_list(self) -> List[Any]:
        vals = []
        curr = self.min_val
        while curr <= self.max_val + 1e-9:
            vals.append(int(curr) if self.is_int else round(curr, 8))
            curr += self.step
        return vals

class StrategyOptimizer:
    def __init__(self, engine: BacktestEngine, strategy_fn: Callable):
        self.engine = engine
        self.strategy_fn = strategy_fn

    def grid_search(self, param_ranges: List[ParamRange], scoring_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """모든 조합을 탐색하는 그리드 서치"""
        keys = [p.name for p in param_ranges]
        value_lists = [p.to_list() for p in param_ranges]
        
        combinations = list(product(*value_lists))
        logger.info(f"[Optimizer] Starting Grid Search: {len(combinations)} combinations")
        
        results = []
        for combo in combinations:
            params = dict(zip(keys, combo))
            score, metrics = self._evaluate(params, scoring_fn)
            results.append({
                "params": params,
                "score": score,
                "metrics": metrics
            })
            
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def random_search(self, param_ranges: List[ParamRange], n_iter: int = 10, scoring_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """무작위 샘플링 기반 탐색"""
        results = []
        logger.info(f"[Optimizer] Starting Random Search: {n_iter} iterations")
        
        for _ in range(n_iter):
            params = {}
            for p in param_ranges:
                vals = p.to_list()
                params[p.name] = random.choice(vals)
            
            score, metrics = self._evaluate(params, scoring_fn)
            results.append({
                "params": params,
                "score": score,
                "metrics": metrics
            })
            
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def bayesian_search(self, param_ranges: List[ParamRange], n_iter: int = 20, scoring_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        심플 베이지안 최적화 (Hill-Climbing + Random Restart)
        외부 라이브러리(Optuna) 없이 구현된 경량화 버전
        """
        # TODO: 실제 Bayesian Optimization 라이브러리 도입 가능
        # 현재는 Random Search 결과 중 상위권을 바탕으로 주변부 재탐색하는 방식 사용
        initial_results = self.random_search(param_ranges, n_iter=max(5, n_iter // 4), scoring_fn=scoring_fn)
        best_params = initial_results[0]["params"]
        
        results = initial_results
        
        # Best 주변부 좁은 범위 재탐색
        for _ in range(n_iter - len(initial_results)):
            refined_params = {}
            for p in param_ranges:
                curr_val = best_params[p.name]
                offset = (p.max_val - p.min_val) * 0.1 # 10% 범위 내외
                new_min = max(p.min_val, curr_val - offset)
                new_max = min(p.max_val, curr_val + offset)
                
                if p.is_int:
                    refined_params[p.name] = random.randint(int(new_min), int(new_max))
                else:
                    refined_params[p.name] = random.uniform(new_min, new_max)
            
            score, metrics = self._evaluate(refined_params, scoring_fn)
            results.append({
                "params": refined_params,
                "score": score,
                "metrics": metrics
            })
            
            # 최적값 갱신
            current_best = max(results, key=lambda x: x["score"])
            best_params = current_best["params"]
            
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def _evaluate(self, params: Dict[str, Any], scoring_fn: Optional[Callable]) -> tuple[float, Any]:
        """단일 파라미터 세트 평가"""
        try:
            # 전략 함수에 파라미터 주입
            # strategy_fn(df, **params) 형태를 기대
            res: PeriodResult = self.engine.run_backtest(
                strategy_fn=lambda df: self.strategy_fn(df, **params)
            )
            
            if scoring_fn:
                score = scoring_fn(res)
            else:
                # 기본 스코어링: 샤프 지수 * (1 + 수익률)
                score = res.sharpe * (1 + max(0, res.total_return))
                
            return float(score), res
        except Exception as e:
            logger.error(f"[Optimizer] Eval failed for {params}: {e}")
            return -9999.0, None

def default_trinity_scorer(res: PeriodResult) -> float:
    """트리니티 표준 점수 계산기"""
    if not res or res.total_trades == 0:
        return -100.0
    
    # 수익률(%), 샤프, MDD(%)
    ret = res.total_return 
    sharpe = res.sharpe
    mdd = abs(res.max_drawdown)
    
    # 점수화 로직 (0 ~ 100)
    score = (ret * 0.4) + (sharpe * 30.0) - (mdd * 0.5)
    return float(score)
