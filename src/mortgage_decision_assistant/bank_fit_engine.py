from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

from .domain import FinancialResult, FinancialScenario


ZERO = Decimal("0")


class CriterionStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ProductStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE_PRODUCT = "INELIGIBLE_PRODUCT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class EvidenceType(str, Enum):
    HARD_PUBLIC_CRITERION = "HARD_PUBLIC_CRITERION"
    PUBLIC_GUIDANCE = "PUBLIC_GUIDANCE"


@dataclass(frozen=True)
class BorrowerProfile:
    borrower_ages: tuple[int, ...] = ()
    property_use: Optional[str] = None
    residency_status: Optional[str] = None


@dataclass(frozen=True)
class CriterionEvaluation:
    criterion_id: str
    status: CriterionStatus
    evidence_type: EvidenceType
    actual_value: Optional[Decimal]
    criterion_value: Optional[Decimal]
    source_status: str
    source_url: Optional[str]
    explanation: str


@dataclass(frozen=True)
class BankFitResult:
    bank_id: str
    bank_name: str
    product_id: str
    product_name: str
    product_status: ProductStatus
    criteria: tuple[CriterionEvaluation, ...]
    hard_matches: int
    hard_mismatches: int
    guidance_matches: int
    guidance_mismatches: int
    unknown_count: int
    core_coverage: Decimal
    verified_at: str


def load_bank_criteria(
    path: Optional[Path] = None,
) -> dict[str, Any]:
    if path is None:
        path = Path("config/bank_criteria_v0_1.yaml")

    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value))


def _eligibility_status(
    eligibility: dict[str, Any],
    profile: BorrowerProfile,
) -> ProductStatus:
    mapping = {
        "property_use": profile.property_use,
        "residency_status": profile.residency_status,
    }

    for key, expected in eligibility.items():
        actual = mapping.get(key)

        if actual is None:
            return ProductStatus.INSUFFICIENT_INFORMATION

        if str(actual) != str(expected):
            return ProductStatus.INELIGIBLE_PRODUCT

    return ProductStatus.ELIGIBLE


def _unknown_evaluation(
    criterion: dict[str, Any],
    explanation: str,
) -> CriterionEvaluation:
    evidence = EvidenceType(
        criterion.get(
            "evidence_type",
            EvidenceType.HARD_PUBLIC_CRITERION.value,
        )
    )

    return CriterionEvaluation(
        criterion_id=str(criterion["criterion_id"]),
        status=CriterionStatus.UNKNOWN,
        evidence_type=evidence,
        actual_value=None,
        criterion_value=_decimal(criterion.get("value")),
        source_status=str(criterion.get("source_status", "UNKNOWN")),
        source_url=criterion.get("source_url"),
        explanation=explanation,
    )


def _evaluate_maximum(
    *,
    criterion: dict[str, Any],
    actual_value: Optional[Decimal],
    explanation_label: str,
) -> CriterionEvaluation:
    if actual_value is None:
        return _unknown_evaluation(
            criterion,
            f"No hay información suficiente para evaluar {explanation_label}.",
        )

    limit = _decimal(criterion.get("value"))
    if limit is None:
        return _unknown_evaluation(
            criterion,
            f"El criterio publicado para {explanation_label} no tiene valor utilizable.",
        )

    status = (
        CriterionStatus.MATCH
        if actual_value <= limit
        else CriterionStatus.MISMATCH
    )

    return CriterionEvaluation(
        criterion_id=str(criterion["criterion_id"]),
        status=status,
        evidence_type=EvidenceType(criterion["evidence_type"]),
        actual_value=actual_value,
        criterion_value=limit,
        source_status=str(criterion.get("source_status", "UNKNOWN")),
        source_url=criterion.get("source_url"),
        explanation=(
            f"{explanation_label}: valor observado {actual_value} "
            f"frente a máximo publicado {limit}."
        ),
    )


def _evaluate_minimum(
    *,
    criterion: dict[str, Any],
    actual_value: Optional[Decimal],
    explanation_label: str,
) -> CriterionEvaluation:
    if actual_value is None:
        return _unknown_evaluation(
            criterion,
            f"No hay información suficiente para evaluar {explanation_label}.",
        )

    minimum = _decimal(criterion.get("value"))
    if minimum is None:
        return _unknown_evaluation(
            criterion,
            f"El criterio publicado para {explanation_label} no tiene valor utilizable.",
        )

    operator = str(criterion.get("operator", "GE"))
    if operator == "GT":
        matches = actual_value > minimum
    else:
        matches = actual_value >= minimum

    return CriterionEvaluation(
        criterion_id=str(criterion["criterion_id"]),
        status=(
            CriterionStatus.MATCH
            if matches
            else CriterionStatus.MISMATCH
        ),
        evidence_type=EvidenceType(criterion["evidence_type"]),
        actual_value=actual_value,
        criterion_value=minimum,
        source_status=str(criterion.get("source_status", "UNKNOWN")),
        source_url=criterion.get("source_url"),
        explanation=(
            f"{explanation_label}: valor observado {actual_value} "
            f"frente a mínimo publicado {minimum}."
        ),
    )


def _ltv_for_basis(
    scenario: FinancialScenario,
    result: FinancialResult,
    basis: Optional[str],
) -> Optional[Decimal]:
    if result.financed_amount is None:
        return None

    if basis == "APPRAISAL_VALUE":
        if scenario.appraisal_value is None or scenario.appraisal_value <= ZERO:
            return None
        return result.financed_amount / scenario.appraisal_value

    if basis == "LOWER_OF_PURCHASE_PRICE_AND_APPRAISAL":
        if scenario.appraisal_value is None or scenario.appraisal_value <= ZERO:
            return None
        denominator = min(
            scenario.property_price,
            scenario.appraisal_value,
        )
        if denominator <= ZERO:
            return None
        return result.financed_amount / denominator

    return None


def _age_at_maturity(
    profile: BorrowerProfile,
    term_years: Optional[int],
    rule: Optional[str],
) -> Optional[Decimal]:
    if not profile.borrower_ages or term_years is None:
        return None

    ages = profile.borrower_ages

    if rule == "YOUNGEST_BORROWER":
        selected = min(ages)
    elif rule in {"OLDEST_BORROWER", "ALL_BORROWERS"}:
        selected = max(ages)
    else:
        return None

    return Decimal(selected + term_years)


def _evaluate_criterion(
    criterion: dict[str, Any],
    scenario: FinancialScenario,
    result: FinancialResult,
    profile: BorrowerProfile,
) -> CriterionEvaluation:
    if criterion.get("source_status") != "VERIFIED_OFFICIAL":
        return _unknown_evaluation(
            criterion,
            "La fuente no está en estado VERIFIED_OFFICIAL.",
        )

    criterion_id = str(criterion["criterion_id"])

    if criterion_id == "MAX_LTV":
        actual = _ltv_for_basis(
            scenario,
            result,
            criterion.get("criterion_basis"),
        )
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=actual,
            explanation_label="LTV según la base publicada por la entidad",
        )

    if criterion_id == "MAX_TERM_YEARS":
        actual = (
            Decimal(scenario.term_years)
            if scenario.term_years is not None
            else None
        )
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=actual,
            explanation_label="plazo",
        )

    if criterion_id == "MAX_AGE_AT_MATURITY":
        actual = _age_at_maturity(
            profile,
            scenario.term_years,
            criterion.get("borrower_selection_rule"),
        )
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=actual,
            explanation_label="edad al vencimiento",
        )

    if criterion_id == "MIN_TOTAL_MONTHLY_INCOME":
        return _evaluate_minimum(
            criterion=criterion,
            actual_value=scenario.monthly_net_income,
            explanation_label="ingresos netos mensuales totales",
        )

    if criterion_id == "MAX_DSTI":
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=result.dsti,
            explanation_label="DSTI",
        )

    if criterion_id == "MAX_TOTAL_DEBT_RATIO":
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=result.dsti,
            explanation_label="ratio total de deuda",
        )

    if criterion_id == "MAX_MORTGAGE_PAYMENT_RATIO":
        ratio = None
        if (
            result.monthly_payment is not None
            and scenario.monthly_net_income > ZERO
        ):
            ratio = result.monthly_payment / scenario.monthly_net_income

        return _evaluate_maximum(
            criterion=criterion,
            actual_value=ratio,
            explanation_label="cuota hipotecaria sobre ingresos",
        )

    if criterion_id == "MAX_FINANCING_AMOUNT":
        return _evaluate_maximum(
            criterion=criterion,
            actual_value=result.financed_amount,
            explanation_label="importe financiado",
        )

    return _unknown_evaluation(
        criterion,
        f"El criterio {criterion_id} todavía no tiene evaluador implementado.",
    )


def evaluate_bank_product(
    *,
    scenario: FinancialScenario,
    result: FinancialResult,
    profile: BorrowerProfile,
    product: dict[str, Any],
    dataset: dict[str, Any],
) -> BankFitResult:
    eligibility = _eligibility_status(
        product.get("eligibility", {}),
        profile,
    )

    if eligibility != ProductStatus.ELIGIBLE:
        return BankFitResult(
            bank_id=str(product["bank_id"]),
            bank_name=str(product["bank_name"]),
            product_id=str(product["product_id"]),
            product_name=str(product["product_name"]),
            product_status=eligibility,
            criteria=(),
            hard_matches=0,
            hard_mismatches=0,
            guidance_matches=0,
            guidance_mismatches=0,
            unknown_count=0,
            core_coverage=ZERO,
            verified_at=str(dataset.get("verified_at", "")),
        )

    evaluations = tuple(
        _evaluate_criterion(
            criterion,
            scenario,
            result,
            profile,
        )
        for criterion in product.get("criteria", [])
    )

    hard_matches = sum(
        item.evidence_type == EvidenceType.HARD_PUBLIC_CRITERION
        and item.status == CriterionStatus.MATCH
        for item in evaluations
    )
    hard_mismatches = sum(
        item.evidence_type == EvidenceType.HARD_PUBLIC_CRITERION
        and item.status == CriterionStatus.MISMATCH
        for item in evaluations
    )
    guidance_matches = sum(
        item.evidence_type == EvidenceType.PUBLIC_GUIDANCE
        and item.status == CriterionStatus.MATCH
        for item in evaluations
    )
    guidance_mismatches = sum(
        item.evidence_type == EvidenceType.PUBLIC_GUIDANCE
        and item.status == CriterionStatus.MISMATCH
        for item in evaluations
    )
    unknown_count = sum(
        item.status == CriterionStatus.UNKNOWN
        for item in evaluations
    )

    core_ids = tuple(
        dataset.get("coverage_policy", {}).get("core_criteria", ())
    )
    by_id = {item.criterion_id: item for item in evaluations}

    evaluable_core = sum(
        by_id.get(core_id) is not None
        and by_id[core_id].status
        not in {
            CriterionStatus.UNKNOWN,
            CriterionStatus.NOT_APPLICABLE,
        }
        for core_id in core_ids
    )

    core_coverage = (
        Decimal(evaluable_core) / Decimal(len(core_ids))
        if core_ids
        else Decimal("1")
    )

    minimum_coverage = Decimal(
        str(
            dataset.get("coverage_policy", {}).get(
                "minimum_comparable_coverage",
                "0",
            )
        )
    )

    product_status = (
        ProductStatus.INSUFFICIENT_INFORMATION
        if core_coverage < minimum_coverage
        else ProductStatus.ELIGIBLE
    )

    return BankFitResult(
        bank_id=str(product["bank_id"]),
        bank_name=str(product["bank_name"]),
        product_id=str(product["product_id"]),
        product_name=str(product["product_name"]),
        product_status=product_status,
        criteria=evaluations,
        hard_matches=hard_matches,
        hard_mismatches=hard_mismatches,
        guidance_matches=guidance_matches,
        guidance_mismatches=guidance_mismatches,
        unknown_count=unknown_count,
        core_coverage=core_coverage,
        verified_at=str(dataset.get("verified_at", "")),
    )


def evaluate_bank_fit(
    *,
    scenario: FinancialScenario,
    result: FinancialResult,
    profile: BorrowerProfile,
    dataset: Optional[dict[str, Any]] = None,
) -> tuple[BankFitResult, ...]:
    if dataset is None:
        dataset = load_bank_criteria()

    return tuple(
        evaluate_bank_product(
            scenario=scenario,
            result=result,
            profile=profile,
            product=product,
            dataset=dataset,
        )
        for product in dataset.get("products", [])
    )
