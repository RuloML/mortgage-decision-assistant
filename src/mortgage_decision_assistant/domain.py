from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4


class AssumptionType(str, Enum):
    INTEREST_RATE_REFERENCE = "INTEREST_RATE_REFERENCE"
    TERM_REFERENCE = "TERM_REFERENCE"
    PURCHASE_COST_RATE_REFERENCE = "PURCHASE_COST_RATE_REFERENCE"
    MAX_AVAILABLE_DOWN_PAYMENT = "MAX_AVAILABLE_DOWN_PAYMENT"
    DESIRED_CASH_BUFFER_REFERENCE = "DESIRED_CASH_BUFFER_REFERENCE"


class CalculationMode(str, Enum):
    LTV_PROVISIONAL_WITHOUT_APPRAISAL = "LTV_PROVISIONAL_WITHOUT_APPRAISAL"


class CalculationCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class TechnicalConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class FinancialScenario:
    property_price: Decimal
    available_savings: Decimal
    monthly_net_income: Decimal
    current_monthly_debt: Optional[Decimal]

    desired_cash_buffer: Optional[Decimal] = None
    planned_down_payment: Optional[Decimal] = None
    requested_loan_amount: Optional[Decimal] = None
    interest_rate_annual: Optional[Decimal] = None
    term_years: Optional[int] = None
    purchase_cost_rate: Optional[Decimal] = None
    appraisal_value: Optional[Decimal] = None

    territory: Optional[str] = None
    property_type: Optional[str] = None

    scenario_id: str = field(default_factory=lambda: str(uuid4()))
    num_borrowers: int = 1
    age_oldest_borrower: Optional[int] = None


@dataclass(frozen=True)
class CalculationMetadata:
    missing_inputs: tuple[str, ...] = ()
    assumptions: tuple[AssumptionType, ...] = ()
    fallbacks_applied: tuple[str, ...] = ()
    calculation_completeness: CalculationCompleteness = (
        CalculationCompleteness.COMPLETE
    )
    technical_confidence: TechnicalConfidence = TechnicalConfidence.HIGH

    engine_version: str = "1.0"
    variable_dictionary_version: str = "1.2"
    defaults_config_version: Optional[str] = None

    calculation_modes: tuple[CalculationMode, ...] = ()
    validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinancialResult:
    scenario_id: str

    purchase_costs: Optional[Decimal]
    available_cash_for_operation: Optional[Decimal]
    planned_down_payment: Optional[Decimal]
    required_loan: Optional[Decimal]
    requested_loan_amount: Optional[Decimal]
    financed_amount: Optional[Decimal]
    loan_gap: Optional[Decimal]

    total_cash_required: Optional[Decimal]
    cash_gap: Optional[Decimal]
    residual_savings: Optional[Decimal]

    monthly_payment: Optional[Decimal]
    ltv: Optional[Decimal]
    ltv_provisional: Optional[Decimal]
    dsti: Optional[Decimal]
    monthly_margin: Optional[Decimal]
    total_interest: Optional[Decimal]

    metadata: CalculationMetadata
