import pytest

from app.decision.engine import Classification, DecisionEngine, DecisionInput, RiskLevel
from app.models.entities import Strategy
from app.strategies.engine import StrategyEngine


@pytest.fixture
def strategy():
    return Strategy(
        id="test-strategy",
        name="Test Strategy",
        min_edge=0.05,
        min_ev=0.0,
        min_confidence=0.70,
        max_stake_units=2,
    )


@pytest.fixture
def decision_engine():
    return DecisionEngine()


class TestDecisionEngineSufficiency:
    def test_insufficient_data_when_market_probability_missing(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=None,
            model_probability=0.55,
            edge=None,
            expected_value=None,
            confidence=0.7,
            strategy=strategy,
        ))
        assert decision.classification == Classification.INSUFFICIENT_DATA
        assert decision.risk is None
        assert "Market price is not available." in decision.failed_criteria

    def test_insufficient_data_when_model_probability_missing(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.5,
            model_probability=None,
            edge=None,
            expected_value=None,
            confidence=None,
            strategy=strategy,
        ))
        assert decision.classification == Classification.INSUFFICIENT_DATA


class TestDecisionEngineClassification:
    def test_strong_candidate_when_all_criteria_exceeded(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.60,
            edge=0.10,
            expected_value=0.15,
            confidence=0.80,
            strategy=strategy,
            historical_sample_size=20,
        ))
        assert decision.classification == Classification.STRONG_CANDIDATE
        assert decision.risk == RiskLevel.LOW
        assert len(decision.reasons) > 0

    def test_candidate_when_meets_strategy_but_medium_risk(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.58,
            edge=0.08,
            expected_value=0.10,
            confidence=0.60,  # below 0.70 LOW threshold but strategy min is lower in this test
            strategy=Strategy(id="s2", name="s2", min_edge=0.05, min_ev=0.0, min_confidence=0.55),
        ))
        assert decision.classification == Classification.CANDIDATE
        assert decision.risk == RiskLevel.MEDIUM

    def test_pass_below_min_edge(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.51,
            edge=0.01,
            expected_value=-0.02,
            confidence=0.6,
            strategy=strategy,
        ))
        assert decision.classification == Classification.PASS
        assert any("Edge" in reason for reason in decision.failed_criteria)

    def test_weak_candidate_positive_but_below_threshold(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.53,
            edge=0.03,
            expected_value=0.02,
            confidence=0.60,
            strategy=strategy,  # requires min_edge 0.05, min_confidence 0.70
        ))
        assert decision.classification == Classification.WEAK_CANDIDATE

    def test_positive_ev_alone_is_not_sufficient(self, decision_engine, strategy):
        """PRD section 25: a positive EV alone must not classify a bet as attractive."""
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.505,
            edge=0.005,
            expected_value=0.30,  # deliberately large positive EV, tiny edge/confidence
            confidence=0.30,
            strategy=strategy,
        ))
        assert decision.classification in (Classification.PASS, Classification.WEAK_CANDIDATE)
        assert decision.classification != Classification.STRONG_CANDIDATE

    def test_low_historical_sample_prevents_strong_candidate(self, decision_engine, strategy):
        decision = decision_engine.decide(DecisionInput(
            market_probability=0.50,
            model_probability=0.62,
            edge=0.12,
            expected_value=0.18,
            confidence=0.85,
            strategy=strategy,
            historical_sample_size=2,  # below MIN_HISTORICAL_SAMPLE
        ))
        assert decision.classification != Classification.STRONG_CANDIDATE
        assert decision.classification == Classification.CANDIDATE


class TestStrategyEngine:
    def test_meets_strategy_true(self, strategy):
        result = StrategyEngine().evaluate(
            strategy, edge=0.10, expected_value=0.10, confidence=0.9
        )
        assert result.meets_strategy is True
        assert result.failed_criteria == []

    def test_meets_strategy_false_reports_reasons(self, strategy):
        result = StrategyEngine().evaluate(
            strategy, edge=0.01, expected_value=-0.5, confidence=0.1
        )
        assert result.meets_strategy is False
        assert len(result.failed_criteria) >= 2

    def test_sport_scope_mismatch(self):
        strat = Strategy(id="nba-only", name="NBA Only", sport="nba", min_edge=0.0, min_ev=0.0, min_confidence=0.0)
        result = StrategyEngine().evaluate(
            strat, edge=0.1, expected_value=0.1, confidence=0.9, sport_id="nfl"
        )
        assert result.meets_strategy is False
