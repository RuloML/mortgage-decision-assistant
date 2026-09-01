# Boundary Solver Contract v1.0

## 1. Purpose
Deterministic decision-support component for identifying restructuring boundaries.

It does not predict bank approval, issue denials, or modify client facts silently.

## 2. Scope v1
Supports:
- 1 adjustable variable (1D boundary)
- maximum 2 adjustable variables simultaneously (2D boundary)
- deterministic constraints
- analytical solutions where appropriate
- discrete evaluation where explicitly defined
- mandatory verification through the Financial Engine

Does not support:
- 3+ adjustable variables
- unrestricted nonlinear optimization
- lender-specific approval logic

## 3. Simulation Policy
LOCKED / ADJUSTABLE belongs to each simulation execution and is independent from user_required.

Default Pro policy:
- property_price: ADJUSTABLE
- planned_down_payment: ADJUSTABLE
- current_monthly_debt: ADJUSTABLE
- term_years: ADJUSTABLE
- monthly_net_income: LOCKED
- available_savings: LOCKED
- desired_cash_buffer: LOCKED
- interest_rate_annual: LOCKED
- purchase_cost_rate: LOCKED
- appraisal_value: LOCKED

The adviser may explicitly lock an adjustable variable.

## 4. Supported constraints
- Liquidity: cash_gap == 0
- LTV: LTV <= configured_ltv_limit
- Debt capacity: DSTI <= configured_dsti_limit
- Financing consistency: loan_gap <= 0

Final verification must always use Financial Engine outputs.

## 5. Boundary 1D
When exactly one variable is adjustable:

1. calculate the limit imposed by each applicable constraint,
2. discard non-applicable limits,
3. select the most restrictive valid limit,
4. create the candidate scenario,
5. recalculate it through Financial Engine,
6. verify every configured constraint.

The result identifies its dominant constraint.

## 6. Boundary 2D
When exactly two variables are adjustable:

1. generate every pair of candidate constraints,
2. solve each pair at equality,
3. reject invalid or out-of-domain solutions,
4. recalculate every candidate through Financial Engine,
5. verify all remaining constraints,
6. retain feasible candidates only,
7. rank candidates according to the declared optimization objective.

With LTV, liquidity and DSTI, the solver must evaluate:
- LTV + liquidity
- LTV + DSTI
- liquidity + DSTI

The dominant pair is discovered, never hardcoded.

Maximum simultaneous adjustable variables in v1: 2.

## 7. Optimization objectives
Supported in v1:

MAXIMIZE_PROPERTY_PRICE
- highest property price satisfying all configured constraints.

MINIMIZE_REQUIRED_CHANGE
- feasible scenario closest to the base scenario.

The objective must always be explicit.

## 8. Lever treatment

| Variable | v1 treatment |
|---|---|
| property_price | analytical where supported |
| planned_down_payment | analytical where supported |
| current_monthly_debt | analytical boundary + discrete actionable values |
| term_years | discrete allowed terms |
| interest_rate_annual | LOCKED |
| monthly_net_income | LOCKED |
| available_savings | LOCKED |
| desired_cash_buffer | LOCKED by default |
| purchase_cost_rate | LOCKED config/assumption |
| appraisal_value | LOCKED |

## 9. Candidate verification
No analytical candidate is accepted directly.

Every candidate must pass through:

calculate_financial_scenario(...)

and then through the configured Rules constraints.

Financial Engine remains the calculation authority.

## 10. Diagnostic terminology

primary_bottleneck:
- property of the base scenario
- answers: what is the main issue now?

dominant_constraint:
- property of a particular boundary solve
- answers: what determines this frontier?

They must not be conflated.

## 11. Conservative presentation boundary

Internal technical boundaries retain full Decimal precision.

For 1D boundaries, directional conservative rounding may be applied directly:

- maximum allowed values -> round DOWN
- minimum required values -> round UP

For 2D boundaries, adjustable variables must NOT be rounded independently.

A pair that is individually rounded in the conservative direction can still
violate another configured constraint.

Therefore v1 uses a feasible presentation boundary:

1. preserve the exact technical boundary,
2. project candidate values onto the configured presentation grid,
3. evaluate the variables jointly,
4. recalculate every candidate through the Financial Engine,
5. verify all configured constraints,
6. select the highest-ranked feasible presentation pair according to the
   declared optimization objective.

Default presentation grid step v1:
- 1000 EUR

Example B01:

Technical boundary:
- property_price = 266666.67 EUR
- planned_down_payment = 53333.33 EUR

Independent rounding to:
- property_price = 266000 EUR
- planned_down_payment = 54000 EUR

is NOT feasible because it exceeds available operation cash.

The feasible presentation boundary is:
- property_price = 265000 EUR
- planned_down_payment = 53000 EUR

The technical boundary and the feasible presentation boundary must both remain
available in traceability.

## 12. Target profiles

Boundary solves must use an explicit target profile.

A target profile resolves to versioned configuration thresholds used by the
Rules and Boundary Solver layers.

Example:

`target_profile = STANDARD`

may resolve in development configuration to:

`DSTI target = 0.40`

Target profiles are structuring objectives, not bank approval categories.

The solver must expose both:

- target_profile
- resolved threshold values

in technical traceability.

The product must not describe development target profiles as universal lender
risk bands or approval criteria.

---

## 13. Traceability
Every solver result must expose:
- base scenario id
- adjustable variables
- locked variables
- simulation policy
- optimization objective
- constraints evaluated
- 2D candidate intersections evaluated
- rejected candidate reasons
- raw boundary
- conservative rounded boundary
- dominant constraint(s)
- Financial Engine version
- Rules config version
- defaults config version
- assumptions
- fallbacks
- calculation modes
- technical confidence

## 14. B01 — LTV + Liquidity boundary

Inputs:
- initial property price: 300000
- available savings: 100000
- desired cash buffer: 20000
- monthly net income: 4000
- current monthly debt: 300
- interest rate: 3%
- term: 30 years
- purchase cost rate: 10%
- LTV limit: 80%
- DSTI limit: 40%

Adjustable:
- property_price
- planned_down_payment

Available cash:
100000 - 20000 = 80000

At the joint boundary:

down_payment = 0.20 * property_price

down_payment + 0.10 * property_price = 80000

Therefore:

property_price = 266666.666...

Expected down payment:
53333.333...

Expected financed amount:
213333.333...

DSTI is approximately 30%, therefore non-binding.

Expected dominant constraints:
- LTV
- LIQUIDITY

Expected conservative displayed maximum with 1000 EUR step:
266000 EUR

## 15. B02 — DSTI dominant

### Purpose

Validate a 1D boundary solve where DSTI determines the maximum property price,
while liquidity and LTV remain non-binding.

### Simulation policy

ADJUSTABLE:
- property_price

LOCKED:
- planned_down_payment
- available_savings
- desired_cash_buffer
- monthly_net_income
- current_monthly_debt
- interest_rate_annual
- term_years
- purchase_cost_rate
- appraisal_value

### Target profile

`target_profile = STANDARD`

Resolved development threshold:

`resolved_dsti_target = 0.40`

This threshold is a development configuration value for structuring tests.

It must not be interpreted or presented as:
- a universal banking threshold,
- an approval criterion,
- a lender-specific underwriting rule.

### Inputs

- initial property price: 400000
- planned down payment: 100000
- available savings: 200000
- desired cash buffer: 20000
- monthly net income: 3500
- current monthly debt: 500
- interest rate: 3% annual
- term: 30 years
- purchase cost rate: 10%
- LTV target: 80%
- DSTI target: 40%

### Independent calculation

Available cash for operation:

`200000 - 20000 = 180000`

#### Liquidity boundary

With down payment locked at 100000:

`100000 + 0.10 * property_price <= 180000`

Therefore:

`property_price <= 800000`

Liquidity is non-binding.

#### LTV boundary

Financed amount:

`property_price - 100000`

Constraint:

`(property_price - 100000) / property_price <= 0.80`

Therefore:

`property_price <= 500000`

LTV is non-binding at the final boundary.

#### DSTI boundary

Maximum total monthly debt service:

`3500 * 0.40 = 1400`

Existing monthly debt:

`500`

Maximum mortgage payment:

`1400 - 500 = 900`

For 3% annual interest and 30 years, the French amortization payment factor is
approximately:

`0.004216040337...`

Therefore:

`maximum_financed_amount = 900 / 0.004216040337...`

Expected financed amount:

`≈ 213470.44`

With planned down payment locked at 100000:

Expected technical property-price boundary:

`≈ 313470.44`

### Cross-check

At the technical boundary:

- DSTI ≈ 40.00%
- LTV ≈ 68.10%
- required client cash ≈ 131347
- available cash for operation = 180000
- cash gap = 0

Therefore DSTI is the binding constraint.

Expected dominant constraint:

`DEBT_CAPACITY / DSTI`

### Conservative presentation

Technical price boundaries use:

`round_conservatively(value, step=1000, direction=DOWN)`

Therefore:

`313470.44 -> 313000`

Expected conservative displayed maximum:

`313000 EUR`

The raw technical boundary remains available in traceability.

### Validation status

B02 expected values were calculated independently before Boundary Solver
implementation.

Status:

`FROZEN_REFERENCE_CASE`

## 16. B03 — Non-obvious 2D intersection

### Purpose

Validate the 2D candidate-intersection algorithm with two adjustable variables
and three competing constraints.

The solver must not assume that LTV + liquidity determine the final boundary.

### Simulation policy

ADJUSTABLE:
- property_price
- planned_down_payment

LOCKED:
- available_savings
- desired_cash_buffer
- monthly_net_income
- current_monthly_debt
- interest_rate_annual
- term_years
- purchase_cost_rate
- appraisal_value

### Target profile

`target_profile = STANDARD`

Resolved development thresholds:

- LTV target = 0.80
- DSTI target = 0.40

These are development structuring objectives, not universal banking criteria.

### Inputs

- initial property price: 300000
- available savings: 100000
- desired cash buffer: 20000
- monthly net income: 2800
- current monthly debt: 300
- interest rate: 3% annual
- term: 30 years
- purchase cost rate: 10%
- LTV target: 80%
- DSTI target: 40%

Available cash for operation:

`100000 - 20000 = 80000`

---

### Candidate 1 — LTV + Liquidity

At the LTV boundary:

`down_payment = 0.20 * property_price`

At the liquidity boundary:

`down_payment + 0.10 * property_price = 80000`

Therefore:

`property_price = 266666.666...`

`planned_down_payment = 53333.333...`

`financed_amount = 213333.333...`

This pairwise intersection is mathematically valid.

However, verifying DSTI:

Monthly mortgage payment is approximately:

`899.42`

Total monthly debt service:

`899.42 + 300 = 1199.42`

DSTI:

`1199.42 / 2800 ≈ 0.4284`

Therefore:

`DSTI ≈ 42.84% > 40%`

Candidate 1 must be rejected because it violates the remaining DSTI constraint.

Expected rejection reason:

`VIOLATES_DSTI_TARGET`

---

### Candidate 2 — DSTI + Liquidity

Maximum total monthly debt service:

`2800 * 0.40 = 1120`

Existing monthly debt:

`300`

Maximum mortgage payment:

`1120 - 300 = 820`

For 3% annual interest and 30 years, the French payment factor is approximately:

`0.004216040337...`

Therefore:

Expected maximum financed amount:

`≈ 194495.29`

DSTI boundary:

`property_price - planned_down_payment = 194495.29`

Liquidity boundary:

`planned_down_payment + 0.10 * property_price = 80000`

Solving the two equations:

Expected technical property price:

`≈ 249541.18`

Expected planned down payment:

`≈ 55045.88`

Expected financed amount:

`≈ 194495.29`

### Verification against remaining LTV constraint

`194495.29 / 249541.18 ≈ 0.7794`

Therefore:

`LTV ≈ 77.94% <= 80%`

Candidate 2 is feasible.

At this boundary:

- DSTI = 40%
- cash gap = 0
- LTV ≈ 77.94%

Expected dominant constraints:

- DEBT_CAPACITY / DSTI
- LIQUIDITY

Expected selected technical property-price boundary:

`≈ 249541.18`

### Conservative presentation

For a maximum price boundary:

`round_conservatively(value, step=1000, direction=DOWN)`

Therefore:

`249541.18 -> 249000`

Expected conservative displayed maximum:

`249000 EUR`

### Expected algorithm behaviour

The solver must:

1. generate LTV + LIQUIDITY,
2. generate LTV + DSTI,
3. generate LIQUIDITY + DSTI,
4. verify every candidate against the remaining constraint,
5. reject LTV + LIQUIDITY because DSTI is violated,
6. retain the feasible DSTI + LIQUIDITY candidate,
7. select the feasible boundary according to MAXIMIZE_PROPERTY_PRICE.

### Validation status

B03 expected values were calculated independently before Boundary Solver
implementation.

Status:

`FROZEN_REFERENCE_CASE`

## 17. Implementation Gate
Implementation starts only when:
- contract reviewed
- B01 independently verified
- B02 expected values frozen independently
- B03 expected values frozen independently

This document defines design intent only.
