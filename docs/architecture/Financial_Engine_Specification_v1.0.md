# Financial Engine Specification v1.0 — RECONCILED DRAFT

> **P-001 — Honestidad documental**  
> Reconstruido a partir del historial de diseño del Sprint 2, del DRR v1.1 y de la reconciliación realizada durante el Sprint 3 antes de la implementación del Financial Engine.
>
> **Provenance:** RECONCILED  
> **Maturity:** DRAFT
>
> Este documento no debe considerarse Level A hasta completar la revisión cruzada contra `Variable_Dictionary_v1.2.md` y resolver los puntos abiertos indicados al final.

---

## 1. Definition

The Financial Engine is a **deterministic, stateless and auditable** component that transforms a mortgage scenario into objective financial indicators.

It does not:

- predict whether a bank will approve or reject an operation,
- recommend banks,
- recommend actions,
- use Machine Learning,
- consume EFF, INE or Banco de España data during calculation,
- classify financial risk.

It may be invoked repeatedly by the Simulation Engine with modified immutable scenarios.

---

## 2. Unit of work

The unit of work is a `FinancialScenario`.

A FinancialScenario represents one concrete mortgage structure, including:

- property price,
- client savings,
- desired cash buffer,
- planned down payment,
- requested loan amount,
- computable monthly income,
- current monthly debt,
- interest rate,
- term,
- purchase-cost assumptions,
- appraisal value when available.

The same client may generate multiple scenarios.

The Financial Engine must not preserve mutable state between scenarios.

---

## 3. Domain model

Financial Engine v1 is expected to expose at least the following domain structures:

### `FinancialScenario`

Immutable input structure.

Implementation requirement:

```python
@dataclass(frozen=True)
class FinancialScenario:
    ...

```

Simulation must create new scenarios through immutable replacement rather than modifying the original object.

Example:

    dataclasses.replace(
        base_scenario,
        property_price=new_property_price
    )

### `FinancialResult`

Contains calculated financial outputs.

It does not contain classification thresholds or bank approval decisions.

### `CalculationMetadata`

Contains calculation-quality and traceability information, including:

- missing inputs,
- assumptions,
- fallbacks applied,
- calculation completeness,
- technical confidence,
- engine version,
- variable dictionary version,
- defaults configuration version,
- calculation modes.

### `AssumptionType`

Controlled Enum used for machine-readable assumptions.

Free-text strings must not be the primary representation of assumptions.

### `CalculationMode`

Controlled Enum used to represent explicitly documented alternative calculation paths.

Alternative calculation paths are not assumptions and must not be recorded as `AssumptionType`.

### `RiskFlags`

Reserved for the Rules Engine.

Financial calculation metadata must not be represented as `RiskFlags`.

---

## 4. Inputs

The canonical input contract is defined in:

`Variable_Dictionary_v1.2.md`

The Financial Engine must not introduce additional business variables without first updating the Variable Dictionary.

Core Financial Engine v1 variables include:

- `property_price`
- `available_savings`
- `desired_cash_buffer`
- `planned_down_payment`
- `monthly_net_income`
- `current_monthly_debt`
- `requested_loan_amount`
- `interest_rate_annual`
- `term_years`
- `purchase_cost_rate`
- `appraisal_value`

Additional scenario metadata may include:

- `scenario_id`
- `num_borrowers`
- `age_oldest_borrower`

`monthly_variable_income` and `other_verified_income` are excluded from Financial Engine v1 calculation logic.

The engine receives one already-resolved value:

`monthly_net_income`

Any decision about how variable income, commissions, bonuses, rent or other income is considered computable belongs upstream or to a future business-rule component.

---

## 5. Missing-input semantics

The Financial Engine distinguishes between:

- missing input,
- explicit numeric zero,
- fallback-resolved value.

A missing value must never be silently converted to zero.

The Variable Dictionary defines:

- `user_required`
- `calculation_required`
- `fallback_available`

If `calculation_required = true` and `fallback_available = false`, the affected calculation cannot proceed when the value is missing.

If `calculation_required = true` and `fallback_available = true`, calculation may continue only if:

1. the fallback is explicitly defined,
2. the fallback source is traceable,
3. the assumption is recorded in `CalculationMetadata`.

If `calculation_required = false` and `fallback_available = false`, the input is optional. Its absence does not block calculation and may activate an explicitly documented alternative calculation path.

Examples:

- missing `interest_rate_annual` → use configured reference rate;
- missing `term_years` → use configured provisional term;
- missing `planned_down_payment` → derive the documented fallback;
- missing `appraisal_value` → do not substitute an appraisal value; calculate provisional LTV using `property_price` and record the alternative calculation mode.

`current_monthly_debt = 0` is valid only when explicitly declared.

`current_monthly_debt = None` means unknown and must never be treated as zero.

---

## 6. Financial calculation model

### 6.1 Estimated purchase costs

`purchase_costs = property_price × purchase_cost_rate`

`purchase_cost_rate` may be supplied by the scenario or resolved through configuration.

If a configured fallback is used, it must be recorded in `CalculationMetadata`.

### 6.2 Cash available for the operation

`available_cash_for_operation = available_savings - desired_cash_buffer`

This represents the amount the client can use without consuming the desired retained cash buffer.

If `desired_cash_buffer` is missing, Financial Engine v1 resolves it using the versioned `desired_cash_buffer_reference` from `financial_defaults.yaml`.

The engine must record:

`AssumptionType.DESIRED_CASH_BUFFER_REFERENCE`

The fallback value must not be hardcoded in calculation logic.

A negative value is possible if the desired cash buffer exceeds available savings and must not be silently converted to zero.

---

### 6.3 Planned down payment

`planned_down_payment` represents the amount the client intends to contribute specifically against the property purchase price.

It does not include purchase costs.

If it is provided explicitly, the declared value is used.

If it is missing, Financial Engine v1 may use:

`planned_down_payment = max(0, available_cash_for_operation - purchase_costs)`

When this fallback is used, the engine must record:

`AssumptionType.MAX_AVAILABLE_DOWN_PAYMENT`

### 6.4 Required mortgage amount

`required_loan = property_price - planned_down_payment`

This represents the mortgage capital required to finance the purchase price given the planned down payment.

Purchase costs are not automatically added to `required_loan`.

Validation rule:

`0 <= planned_down_payment <= property_price`

`planned_down_payment = property_price` is valid and produces `required_loan = 0`.

`planned_down_payment > property_price` is invalid input. The Financial Engine must not silently cap or correct the value.

---

### 6.5 Requested mortgage amount

`requested_loan_amount` represents the mortgage amount that the client or adviser intends to evaluate.

It may differ from `required_loan`.

Both values must be preserved.

### 6.6 Financed amount

If `requested_loan_amount` is provided:

`financed_amount = requested_loan_amount`

Otherwise:

`financed_amount = required_loan`

The following calculations use `financed_amount`:

- monthly payment,
- LTV,
- DSTI,
- total interest.

This ensures that the Financial Engine evaluates the mortgage amount actually represented by the scenario.

---

### 6.7 Loan gap

When `requested_loan_amount` is provided:

`loan_gap = required_loan - requested_loan_amount`

Interpretation:

- `loan_gap > 0`: the requested mortgage amount is insufficient to cover the property price given the planned down payment.
- `loan_gap = 0`: requested and required mortgage amounts match.
- `loan_gap < 0`: the requested mortgage amount exceeds the calculated required mortgage.

The Financial Engine reports the signed value but does not classify whether it is acceptable.

A negative `loan_gap` must be preserved as a negative value. Financial Engine v1 does not create a separate `loan_surplus` variable because that would duplicate the same information with inverted sign.

If `requested_loan_amount` is absent:

`loan_gap = None`

---

### 6.8 Total client cash required

`total_cash_required = planned_down_payment + purchase_costs`

This represents the total client cash required to execute the scenario as structured.

It replaces the ambiguous informal concept `required_cash`.

### 6.9 Cash gap

`cash_gap = max(0, total_cash_required - available_cash_for_operation)`

Interpretation:

- `cash_gap > 0`: available cash is insufficient to execute the planned structure while preserving the desired cash buffer.
- `cash_gap = 0`: available cash is sufficient.

The Financial Engine reports the shortfall but does not classify the financial risk.

---

### 6.10 Residual savings

`residual_savings = available_savings - planned_down_payment - purchase_costs`

This represents the savings remaining after the planned down payment and estimated purchase costs are covered.

Unlike the earlier reconstructed design, `residual_savings` is not automatically equal to `desired_cash_buffer`.

This allows the engine to show whether the planned structure preserves, exceeds or falls below the desired retained cash buffer.

---

### 6.11 Monthly mortgage payment

The monthly payment uses the French amortization formula.

`P = financed_amount`

`r = interest_rate_annual / 12`

`n = term_years × 12`

`monthly_payment = P × r × (1+r)^n / ((1+r)^n - 1)`

All monetary and rate calculations must use `Decimal`.

No intermediate rounding is permitted.

If `interest_rate_annual = 0`, the standard formula is not used.

Instead:

`monthly_payment = financed_amount / number_of_months`

This zero-interest case must be included in the golden test cases.

---

### 6.12 LTV

When `appraisal_value` is available:

`ltv = financed_amount / min(property_price, appraisal_value)`

When `appraisal_value` is missing:

`ltv_provisional = financed_amount / property_price`

In that case, no appraisal value is assumed or substituted.

The engine must record:

`CalculationMode.LTV_PROVISIONAL_WITHOUT_APPRAISAL`

The Financial Engine reports the ratio only.

Interpretation against LTV thresholds belongs to the Rules Engine.

---

### 6.13 DSTI

`dsti = (monthly_payment + current_monthly_debt) / monthly_net_income`

If `current_monthly_debt` is unknown, DSTI must not silently assume debt = 0.

If `monthly_net_income <= 0`, DSTI cannot be calculated normally and must return a controlled failure or partial result according to the implementation contract.

The Financial Engine reports the ratio only.

Interpretation against DSTI thresholds belongs to the Rules Engine.

---

### 6.14 Monthly margin

`monthly_margin = monthly_net_income - current_monthly_debt - monthly_payment`

This is an objective monthly cash-flow indicator.

The Financial Engine reports the value but does not classify it.

---

### 6.15 Total interest

`total_interest = (monthly_payment × number_of_months) - financed_amount`

This is an approximate scheduled interest cost assuming:

- fixed payment structure,
- no early repayment,
- no fees,
- no rate changes,
- no insurance or ancillary products.

It must not be presented as the complete legal or contractual cost of the mortgage.

---

## 7. Outputs

### 7.1 Scenario identification and traceability

Expected output metadata includes:

- `scenario_id`
- calculation timestamp
- `engine_version`
- `variable_dictionary_version`
- `defaults_config_version`

The Financial Engine does not expose `threshold_config_version`.

That belongs to the Rules Engine.

### 7.2 Financial outputs

Financial Engine v1 outputs include:

- `purchase_costs`
- `available_cash_for_operation`
- `planned_down_payment`
- `required_loan`
- `requested_loan_amount`
- `financed_amount`
- `loan_gap`
- `total_cash_required`
- `cash_gap`
- `residual_savings`
- `monthly_payment`
- `ltv` or `ltv_provisional`
- `dsti`
- `monthly_margin`
- `total_interest`

No variable called `required_cash` is part of the v1 contract.

### 7.3 Calculation quality

Calculation quality must be returned through `CalculationMetadata`, including:

- `missing_inputs`
- `assumptions`
- `fallbacks_applied`
- `calculation_completeness`
- `technical_confidence`
- `engine_version`
- `variable_dictionary_version`
- `defaults_config_version`
- `calculation_modes`

The exact controlled values for completeness and confidence remain open before Level A.

---

## 8. Configuration ownership

Financial calculation defaults and financial classification thresholds are separated.

### 8.1 `config/financial_defaults.yaml`

Owned by the Financial Engine.

Expected responsibilities include:

- reference interest rate,
- provisional mortgage term,
- purchase-cost assumptions where applicable,
- configuration version,
- source/reference metadata,
- validation-for-production status.

The provisional 3% reference rate is a development assumption only and must not be presented as current market truth.

### 8.2 `config/financial_thresholds.yaml`

Owned by the Rules Engine.

Expected responsibilities include:

- DSTI classification thresholds,
- LTV classification thresholds,
- other interpretation thresholds.

These thresholds must not modify the arithmetic produced by the Financial Engine.

---

## 9. Rules Engine separation

The Rules Engine is independent from the Financial Engine.

It receives Financial Engine outputs and may generate:

- `RiskFlags`
- risk categories
- interpretive messages
- threshold-based classifications

Example conceptual risk flags may include:

- `HIGH_LTV`
- `HIGH_DSTI`
- `INSUFFICIENT_CASH`
- `REQUESTED_LOAN_INSUFFICIENT`
- `COST_FINANCING_REQUIRED`

These flags must not change the arithmetic outputs produced by the Financial Engine.

The Rules Engine records `threshold_config_version` independently from Financial Engine versioning.

---

## 10. Simulation Engine

The Simulation Engine reuses the Financial Engine.

It must:

1. receive an immutable base `FinancialScenario`,
2. create a new scenario,
3. modify one or more explicit levers,
4. invoke the same Financial Engine,
5. compare the resulting `FinancialResult` objects.

The Financial Engine must not know whether a scenario is the original case or a simulation.

MVP simulation levers:

- reduce property price,
- increase planned down payment,
- cancel monthly debt,
- add a second borrower or modify computable income.

`planned_down_payment` is the preferred explicit lever for simulating additional client contribution.

---

## 11. Stress tests v1

Initial stress scenarios:

| Scenario | Modification |
|---|---|
| Base | Declared or resolved interest rate |
| Rate Stress 1 | Annual rate +1 percentage point |
| Rate Stress 2 | Annual rate +2 percentage points |
| Income Stress | Monthly computable income -10% |

Expected comparison outputs include:

- monthly payment
- DSTI
- monthly margin
- difference versus the base scenario

Stress tests are analytical scenarios.

They do not represent bank-specific approval criteria.

---

## 12. Precision and rounding

All monetary values, ratios and rates must use `Decimal`.

Binary floating-point arithmetic must not be used for financial calculations.

Rules:

- no intermediate rounding unless mathematically necessary;
- threshold comparisons use unrounded values;
- presentation rounding is separate from calculation;
- EUR display uses 2 decimal places;
- LTV and DSTI may be displayed with 2 decimal places;
- interest rates may require 3 or more decimal places;
- tests should compare exact Decimal values where feasible.

---

## 13. Expected Python functions

Initial Financial Engine v1 functions:

- `calculate_purchase_costs()`
- `calculate_available_cash_for_operation()`
- `resolve_planned_down_payment()`
- `calculate_required_loan()`
- `resolve_financed_amount()`
- `calculate_loan_gap()`
- `calculate_total_cash_required()`
- `calculate_cash_gap()`
- `calculate_residual_savings()`
- `calculate_monthly_payment()`
- `calculate_ltv()`
- `calculate_dsti()`
- `calculate_monthly_margin()`
- `calculate_total_interest()`
- `evaluate_financial_scenario()`

Stress-test orchestration may be implemented separately through:

- `run_stress_tests()`

Simulation-specific functions belong to the Simulation Engine rather than the Financial Engine.

---

## 14. Predefined test-case families

Golden test values must be calculated independently from the Python implementation.

The final golden table must include at least the following test families:

| Test case | Purpose |
|---|---|
| Standard operation | Full normal calculation |
| LTV exactly 80% | Boundary precision |
| LTV exactly 100% | Highly financed structure |
| DSTI near threshold | Ratio precision |
| Insufficient client cash | Positive `cash_gap` |
| Requested loan insufficient | Positive `loan_gap` |
| Requested loan exceeds required loan | Negative `loan_gap` |
| Explicit current debt = 0 | Valid zero handling |
| Current debt unknown | Ensure `None` is not converted to zero |
| Interest rate missing | FE-002 fallback + assumption metadata |
| Term missing | Fallback + metadata |
| Planned down payment missing | `MAX_AVAILABLE_DOWN_PAYMENT` fallback |
| Appraisal missing | Provisional LTV + assumption metadata |
| Interest rate = 0 | Zero-interest amortization branch |
| Property price = 0 | Controlled invalid-input behaviour |
| Monthly income = 0 | Controlled DSTI failure |
| Planned down payment > property price | Validation policy |
| Desired cash buffer > available savings | Negative available cash / cash-gap behaviour |
| Rate +2pp stress | Stress-test behaviour |
| Income -10% stress | Stress-test behaviour |

Expected values must be produced through an independent spreadsheet or equivalent independent calculation artifact before Python financial functions are implemented.

---

## 15. Decisions closed during reconciliation

The following decisions are considered closed for the reconciled draft:

1. `FinancialScenario` is the unit of calculation.
2. `FinancialScenario` is immutable.
3. The Financial Engine is pure, deterministic and stateless.
4. Calculation and Rules Engine interpretation remain separate.
5. Simulation reuses the same Financial Engine.
6. The Financial Engine outputs indicators, not approval/rejection.
7. Machine Learning is excluded from Financial Engine calculations.
8. Monetary calculations use `Decimal`.
9. Golden cases precede calculation implementation.
10. `RiskFlags` belongs to the Rules Engine.
11. Financial Engine quality metadata uses `CalculationMetadata`.
12. `planned_down_payment` is separate from total available savings.
13. `planned_down_payment` applies against property price, not purchase costs.
14. `required_loan = property_price - planned_down_payment`.
15. `requested_loan_amount` and `required_loan` remain separate.
16. `financed_amount` uses requested amount when supplied; otherwise required amount.
17. Payment, LTV, DSTI and total interest use `financed_amount`.
18. `loan_gap` and `cash_gap` represent different structural deficits.
19. `required_cash` is removed.
20. Financial defaults and Rules Engine thresholds live in separate configuration files.
21. `monthly_variable_income` and `other_verified_income` are excluded from Financial Engine v1 formulas.

---

## 16. Financial Engine decision register

| ID | Decision | Status |
|---|---|---|
| FE-001 | Handling of `requested_loan_amount` versus `required_loan` | ✅ Reconciled — preserve both, derive `financed_amount`, calculate `loan_gap` |
| FE-002 | Source of `interest_rate_reference` | 🟡 Partially resolved — provisional value in `financial_defaults.yaml`; formal update/source policy pending |
| FE-003 | Ownership of `threshold_config_version` | ✅ Reconciled — belongs to Rules Engine, not Financial Engine |

---

## 17. Open items before Level A

### O-01 – Negative `loan_gap`

**CLOSED** — The Financial Engine reports the signed `loan_gap` value only.

Negative values are preserved as negative values. No separate `loan_surplus` field is introduced because it would duplicate the same information with inverted sign.

### O-02 – Signed cash balance

**CLOSED** — `cash_gap` remains a non-negative shortfall indicator:

`cash_gap = max(0, total_cash_required - available_cash_for_operation)`

Financial Engine v1 does not introduce an additional signed cash-balance variable.

`residual_savings` and `desired_cash_buffer` already preserve the information needed to evaluate whether the scenario leaves liquidity above or below the desired retained buffer.

### O-03 – Planned down payment greater than property price

**CLOSED** — `planned_down_payment` must satisfy:

`0 <= planned_down_payment <= property_price`

A value equal to `property_price` is valid and produces `required_loan = 0`.

A value above `property_price` is invalid input and must not be silently capped or corrected.

### O-04 – Desired cash buffer fallback

**CLOSED** — Missing `desired_cash_buffer` is resolved using the versioned `desired_cash_buffer_reference` from `financial_defaults.yaml`.

The applied fallback must be recorded as:

`AssumptionType.DESIRED_CASH_BUFFER_REFERENCE`

The numeric fallback value belongs to configuration and must not be hardcoded in Financial Engine logic.

### O-05 — Term fallback

Confirm the provisional `term_years_reference` and its source/status.

### O-06 — Purchase-cost configuration hierarchy

Define how purchase-cost assumptions are selected based on:

- territory,
- property type,
- transaction type,
- or a generic development fallback.

No current configuration value should be represented as legal or tax truth until validated.


### O-07 — `num_borrowers`

Confirm whether `num_borrowers` belongs inside `FinancialScenario` v1 metadata or should be consumed only by Simulation/Rules layers.

### O-08 — Technical confidence

Define controlled values and derivation logic for `technical_confidence`.

Possible values may be:

- `HIGH`
- `MEDIUM`
- `LOW`

These labels must represent input/fallback quality only and must not imply a probability of mortgage approval.

### O-09 — Partial results

Define which outputs may still be returned when one calculation is blocked.

Example:

- unknown `current_monthly_debt` may block DSTI and monthly margin,
- while purchase costs, cash structure, required loan, financed amount and LTV may still remain valid.


### O-10 — Zero financed amount

Define monthly-payment and ratio behaviour when:

`financed_amount = 0`

The implementation must avoid invalid amortization or ratio calculations and return a controlled result.

### O-11 — Negative available cash

Confirm whether:

`available_cash_for_operation < 0`

is retained as signed financial information or handled through a validation state.

---

Until these items are reconciled:

**Provenance: RECONCILED**  
**Maturity: DRAFT**
