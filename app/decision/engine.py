"""
Decision Engine.

PRD section 16: the final analytical gate between an identified
opportunity and a potential betting decision.

PRD section 25 is explicit that a positive EV alone must NOT be
enough to call an opportunity attractive — classification considers
edge, EV, confidence, and strategy fit together, and always explains
its reasoning (section 24).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.models.entities import Strategy
from app.strategies.engine import StrategyEvaluation, engine as strategy_engine


class Classification(str, Enum):
    STRONG_CANDIDATE = "Strong Candidate"
    CANDIDATE = "Candidate"
    WEAK_CANDIDATE = "Weak Candidate"
    PASS = "Pass"
    INSUFFICIENT_DATA = "Insufficient Data"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class DecisionInput:
    market_probability: Optional[float]
    model_probability: Optional[float]
    edge: Optional[float]
    expected_value: Optional[float]
    confidence: Optional[float]
    strategy: Strategy
    sport_id: Optional[str] = None
    market_type: Optional[str] = None
    historical_sample_size: Optional[int] = None


@dataclass
class Decision:
    classification: Classification
    risk: Optional[RiskLevel]
    reasons: list[str] = field(default_factory=list)
    failed_criteria: list[str] = field(default_factory=list)
    supporting_metrics: dict = field(default_factory=dict)
    strategy_evaluation: Optional[StrategyEvaluation] = None


MIN_HISTORICAL_SAMPLE = 8


class DecisionEngine:
    def decide(self, inputs: DecisionInput) -> Decision:
        reasons: list[str] = []
        failed: list[str] = []
        metrics = {
            "market_probability": inputs.market_probability,
            "model_probability": inputs.model_probability,
            "edge": inputs.edge,
            "expected_value": inputs.expected_value,
            "confidence": inputs.confidence,
        }

        # --- Sufficiency gate -------------------------------------------------
        if inputs.market_probability is None:
            failed.append("Market price is not available.")
        if inputs.model_probability is None:
            failed.append("Model probability is not available.")
        if inputs.edge is None:
            failed.append("Edge could not be estimated.")

        if failed:
            reasons.append("The system does not have enough reliable information to assess this opportunity.")
            return Decision(
                classification=Classification.INSUFFICIENT_DATA,
                risk=None,
                reasons=reasons,
                failed_criteria=failed,
                supporting_metrics=metrics,
                strategy_evaluation=None,
            )

        # --- Strategy fit -------------------------------------------------
        strategy_eval = strategy_engine.evaluate(
            inputs.strategy,
            edge=inputs.edge,
            expected_value=inputs.expected_value,
            confidence=inputs.confidence,
            sport_id=inputs.sport_id,
            market_type=inputs.market_type,
        )
        failed.extend(strategy_eval.failed_criteria)

        # --- Historical evidence -------------------------------------------------
        historical_sufficient = True
        if inputs.historical_sample_size is not None and inputs.historical_sample_size < MIN_HISTORICAL_SAMPLE:
            historical_sufficient = False
            reasons.append(
                f"Only {inputs.historical_sample_size} comparable historical samples were found "
                f"(minimum {MIN_HISTORICAL_SAMPLE} recommended); treat this signal with caution."
            )

        # --- Risk tier -------------------------------------------------
        confidence = inputs.confidence or 0.0
        if confidence >= 0.70:
            risk = RiskLevel.LOW
        elif confidence >= 0.55:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.HIGH
        metrics["risk"] = risk.value

        ev_positive = (inputs.expected_value or 0) > 0
        edge_positive = (inputs.edge or 0) > 0

        # --- Classification -------------------------------------------------
        # A positive EV alone is never sufficient (PRD section 25) — strategy
        # fit, confidence, and risk are always weighed together.
        if strategy_eval.meets_strategy and historical_sufficient and risk == RiskLevel.LOW:
            classification = Classification.STRONG_CANDIDATE
            reasons.insert(0, "Meets all strategy criteria with high model confidence and low assessed risk.")
        elif strategy_eval.meets_strategy:
            classification = Classification.CANDIDATE
            reasons.insert(0, "Meets the strategy's criteria, though confidence, risk, or historical sample size are limited.")
        elif edge_positive and ev_positive:
            classification = Classification.WEAK_CANDIDATE
            reasons.insert(0, "Some positive signal exists (edge and expected value are positive), but the opportunity falls short of the strategy's thresholds.")
        else:
            classification = Classification.PASS
            reasons.insert(0, "The opportunity does not meet the decision criteria.")

        if not failed and classification == Classification.PASS:
            failed.append("Edge or expected value is not positive.")

        return Decision(
            classification=classification,
            risk=risk,
            reasons=reasons,
            failed_criteria=failed,
            supporting_metrics=metrics,
            strategy_evaluation=strategy_eval,
        )


engine = DecisionEngine()
