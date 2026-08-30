from decimal import Decimal

from mortgage_decision_assistant.config import (
    load_financial_defaults,
)


def test_development_financial_defaults():

    defaults = load_financial_defaults()

    assert defaults.version == "dev-1"
    assert defaults.validation_status == "development_only"

    assert defaults.interest_rate_reference == Decimal("0.03")
    assert defaults.term_years_reference == 30
    assert defaults.desired_cash_buffer_reference == Decimal("20000")
    assert defaults.purchase_cost_rate_global_default == Decimal("0.10")
