"""Core perception layer for AI Trading System.

This module provides market regime classification and labeling capabilities
that form the perception layer of the trading system.
"""

from ai_trading.core.triple_barrier import (
    BarrierConfig,
    BarrierType,
    LabelOutput,
    RegimeAwareBarrierLabeler,
    TripleBarrierLabeler,
    TripleBarrierResult,
    create_labeler,
)

# HMM Regime Classifier is optional - requires hmmlearn
try:
    from ai_trading.core.hmm_regime import (
        HMMConfig,
        HMMRegimeClassifier,
        RegimePrediction,
        create_regime_classifier,
    )
    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    HMMConfig = None  # type: ignore
    HMMRegimeClassifier = None  # type: ignore
    RegimePrediction = None  # type: ignore
    create_regime_classifier = None  # type: ignore

__all__ = [
    # Triple Barrier Labeler (always available)
    "BarrierConfig",
    "BarrierType",
    "LabelOutput",
    "RegimeAwareBarrierLabeler",
    "TripleBarrierLabeler",
    "TripleBarrierResult",
    "create_labeler",
]

if _HMM_AVAILABLE:
    __all__ += [
        # HMM Regime Classifier
        "HMMConfig",
        "HMMRegimeClassifier",
        "RegimePrediction",
        "create_regime_classifier",
    ]
