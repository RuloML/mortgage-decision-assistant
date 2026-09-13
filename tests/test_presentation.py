from decimal import Decimal

from mortgage_decision_assistant.presentation import (
    PresentationState,
    classify_cash_gap,
    classify_upper_bound,
)


D = Decimal


def test_ltv_threshold_is_inclusive_below_at_and_above():
    target = D("0.80")

    assert classify_upper_bound(D("0.7999"), target) == PresentationState.WITHIN_TARGET
    assert classify_upper_bound(D("0.8000"), target) == PresentationState.WITHIN_TARGET
    assert classify_upper_bound(D("0.8001"), target) == PresentationState.REQUIRES_ADJUSTMENT


def test_dsti_threshold_is_inclusive_below_at_and_above():
    target = D("0.40")

    assert classify_upper_bound(D("0.3999"), target) == PresentationState.WITHIN_TARGET
    assert classify_upper_bound(D("0.4000"), target) == PresentationState.WITHIN_TARGET
    assert classify_upper_bound(D("0.4001"), target) == PresentationState.REQUIRES_ADJUSTMENT


def test_liquidity_has_no_deficit_at_zero_or_below():
    assert classify_cash_gap(D("-0.01")) == PresentationState.WITHIN_TARGET
    assert classify_cash_gap(D("0.00")) == PresentationState.WITHIN_TARGET
    assert classify_cash_gap(D("0.01")) == PresentationState.REQUIRES_ADJUSTMENT
