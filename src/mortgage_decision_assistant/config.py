from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class FinancialDefaults:
    version: str
    validation_status: str
    interest_rate_reference: Decimal
    term_years_reference: int
    desired_cash_buffer_reference: Decimal
    purchase_cost_rate_global_default: Decimal


def load_financial_defaults(
    path: Optional[Path] = None,
) -> FinancialDefaults:

    if path is None:
        path = Path("config/financial_defaults.yaml")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return FinancialDefaults(
        version=str(data["version"]),
        validation_status=str(data["validation_status"]),
        interest_rate_reference=Decimal(
            str(data["interest_rate_reference"])
        ),
        term_years_reference=int(
            data["term_years_reference"]
        ),
        desired_cash_buffer_reference=Decimal(
            str(data["desired_cash_buffer_reference"])
        ),
        purchase_cost_rate_global_default=Decimal(
            str(data["purchase_cost_rate"]["global_default"])
        ),
    )
