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
