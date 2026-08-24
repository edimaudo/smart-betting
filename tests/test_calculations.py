import math

import pytest

from app.calculations import edge as edge_mod
from app.calculations import odds as odds_mod
from app.calculations import stake as stake_mod
from app.calculations import vig as vig_mod


class TestOddsConversion:
    def test_decimal_implied_probability(self):
        assert odds_mod.decimal_implied_probability(2.0) == pytest.approx(0.5)
        assert odds_mod.decimal_implied_probability(1.5) == pytest.approx(2 / 3)

    def test_decimal_implied_probability_rejects_invalid(self):
        with pytest.raises(ValueError):
            odds_mod.decimal_implied_probability(1.0)
        with pytest.raises(ValueError):
            odds_mod.decimal_implied_probability(0.5)

    def test_american_implied_probability_positive(self):
        # +150 -> 100 / 250 = 0.4
        assert odds_mod.american_implied_probability(150) == pytest.approx(0.4)

    def test_american_implied_probability_negative(self):
        # -110 -> 110 / 210
        assert odds_mod.american_implied_probability(-110) == pytest.approx(110 / 210)

    def test_american_implied_probability_rejects_zero(self):
        with pytest.raises(ValueError):
            odds_mod.american_implied_probability(0)

    def test_american_to_decimal_roundtrip_positive(self):
        decimal = odds_mod.american_to_decimal(150)
        assert decimal == pytest.approx(2.5)
        assert odds_mod.decimal_to_american(decimal) == pytest.approx(150)

    def test_american_to_decimal_roundtrip_negative(self):
        decimal = odds_mod.american_to_decimal(-200)
        assert decimal == pytest.approx(1.5)
        assert odds_mod.decimal_to_american(decimal) == pytest.approx(-200)

    def test_potential_return_and_profit(self):
        assert odds_mod.potential_return(10, 2.5) == pytest.approx(25)
        assert odds_mod.potential_profit(10, 2.5) == pytest.approx(15)

    def test_potential_return_rejects_negative_stake(self):
        with pytest.raises(ValueError):
            odds_mod.potential_return(-5, 2.0)

    def test_implied_probability_dispatch(self):
        assert odds_mod.implied_probability(2.0, "decimal") == pytest.approx(0.5)
        assert odds_mod.implied_probability(-110, "american") == pytest.approx(110 / 210)
        with pytest.raises(ValueError):
            odds_mod.implied_probability(2.0, "fractional")

    def test_to_decimal_dispatch(self):
        assert odds_mod.to_decimal(2.5, "decimal") == pytest.approx(2.5)
        assert odds_mod.to_decimal(150, "american") == pytest.approx(2.5)


class TestVig:
    def test_market_overround(self):
        # Two-sided market, both sides priced at -110 (implied ~0.5238 each)
        p = odds_mod.american_implied_probability(-110)
        assert vig_mod.market_overround([p, p]) == pytest.approx(2 * p)

    def test_market_overround_requires_values(self):
        with pytest.raises(ValueError):
            vig_mod.market_overround([])

    def test_vig_percentage(self):
        assert vig_mod.vig_percentage([0.55, 0.55]) == pytest.approx(0.10)

    def test_normalize_probabilities_sums_to_one(self):
        raw = [0.55, 0.55]
        normalized = vig_mod.normalize_probabilities(raw)
        assert sum(normalized) == pytest.approx(1.0)
        assert normalized[0] == pytest.approx(normalized[1])

    def test_normalize_probabilities_uneven_market(self):
        raw = [0.6, 0.5]  # 110% book
        normalized = vig_mod.normalize_probabilities(raw)
        assert sum(normalized) == pytest.approx(1.0)
        assert normalized[0] > normalized[1]

    def test_has_sufficient_market_info(self):
        assert vig_mod.has_sufficient_market_info(2, 2) is True
        assert vig_mod.has_sufficient_market_info(1, 2) is False
        assert vig_mod.has_sufficient_market_info(0, 2) is False


class TestEdgeAndEV:
    def test_edge_positive(self):
        assert edge_mod.edge(0.55, 0.50) == pytest.approx(0.05)

    def test_edge_negative(self):
        assert edge_mod.edge(0.45, 0.50) == pytest.approx(-0.05)

    def test_expected_value_positive_edge(self):
        # 60% true win probability at even money (decimal 2.0), $10 stake
        result = edge_mod.expected_value(0.6, 2.0, 10)
        # EV = 0.6*10 - 0.4*10 = 2.0
        assert result.expected_profit == pytest.approx(2.0)
        assert result.payout_if_win == pytest.approx(20.0)
        assert result.profit_if_win == pytest.approx(10.0)
        assert result.stake == pytest.approx(10.0)
        assert result.ev_per_unit_staked == pytest.approx(0.2)

    def test_expected_value_negative_edge(self):
        result = edge_mod.expected_value(0.4, 2.0, 10)
        assert result.expected_profit == pytest.approx(-2.0)

    def test_expected_value_rejects_invalid_probability(self):
        with pytest.raises(ValueError):
            edge_mod.expected_value(1.5, 2.0, 10)

    def test_expected_value_rejects_negative_stake(self):
        with pytest.raises(ValueError):
            edge_mod.expected_value(0.5, 2.0, -10)

    def test_expected_value_zero_stake_ev_per_unit(self):
        result = edge_mod.expected_value(0.5, 2.0, 0)
        assert result.ev_per_unit_staked == 0.0


class TestStake:
    def test_fixed_unit_stake(self):
        assert stake_mod.fixed_unit_stake(10, 2) == pytest.approx(20)

    def test_fixed_unit_stake_rejects_negative(self):
        with pytest.raises(ValueError):
            stake_mod.fixed_unit_stake(-10, 1)

    def test_percentage_bankroll_stake(self):
        assert stake_mod.percentage_bankroll_stake(1000, 0.02) == pytest.approx(20)

    def test_percentage_bankroll_stake_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            stake_mod.percentage_bankroll_stake(1000, 1.5)

    def test_kelly_fraction_positive_edge(self):
        # 60% win prob, decimal odds 2.0 (b=1): f* = (1*0.6 - 0.4)/1 = 0.2
        assert stake_mod.kelly_fraction(0.6, 2.0) == pytest.approx(0.2)

    def test_kelly_fraction_no_edge_clips_to_zero(self):
        # 40% win prob at even money has negative Kelly -> clipped to 0
        assert stake_mod.kelly_fraction(0.4, 2.0) == pytest.approx(0.0)

    def test_kelly_stake_scales_with_fraction(self):
        full = stake_mod.kelly_stake(1000, 0.6, 2.0, fraction=1.0)
        half = stake_mod.kelly_stake(1000, 0.6, 2.0, fraction=0.5)
        assert half == pytest.approx(full / 2)

    def test_kelly_stake_rejects_negative_bankroll(self):
        with pytest.raises(ValueError):
            stake_mod.kelly_stake(-100, 0.6, 2.0)
