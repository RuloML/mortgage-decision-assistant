# Mortgage Decision Assistant

> **Decision support for mortgage operation structuring**
>
> A tool designed to help real-estate and mortgage advisers identify
> structural constraints, explore feasible alternatives and standardize
> mortgage pre-analysis before specialist financial review.

---

## 🎯 The Problem

The initial assessment of a mortgage operation often requires advisers
to combine multiple financial factors:

- available savings and required liquidity
- mortgage amount and down payment
- monthly affordability
- LTV and debt-service ratios
- appraisal assumptions
- alternative ways of restructuring the operation

These assessments may rely on spreadsheets, isolated calculators and
professional judgement.

The challenge is not only calculating a mortgage payment, but answering:

**What is preventing this operation from working, and what could be
changed to improve its structure?**

---

## ✨ The Solution

Mortgage Decision Assistant combines deterministic financial calculation
with decision-support logic.

It helps the adviser:

1. **Diagnose** the main structural constraint
2. **Understand** why the current operation requires adjustment
3. **Explore** changes in price, down payment, term, appraisal or financing
4. **Compare** feasible and non-feasible restructuring strategies
5. **Escalate** the case with a more structured initial assessment

### Two modes, one decision engine

**Lite**  
Fast pre-analysis for real-estate advisers.

**Pro**  
Deeper mortgage structuring and scenario exploration for financial advisers.

## 💡 Example Scenario

A client is considering a €300,000 property:

- Savings: €100,000
- Planned down payment: €60,000
- Monthly income: €4,000
- Current monthly debt: €300
- Mortgage term: 30 years
- Interest rate: 3%

### Initial assessment

The system detects a **liquidity constraint**.

Although the monthly affordability remains within the configured
reference threshold, the operation does not preserve the desired
post-purchase liquidity buffer once acquisition costs are considered.

### Recommended restructuring

The Decision Engine identifies a feasible structure around:

- Property price: €265,000
- Down payment: €53,000
- Estimated monthly payment: €894
- Resulting DSTI: 29.8%
- Liquidity gap: €0

### Alternative strategies

The system also evaluates different restructuring paths:

- **Lower price while maintaining the down payment** → viable
- **Maintain price while increasing the down payment** → does not solve all constraints simultaneously
- **Extend the mortgage term** → not relevant when monthly affordability is not the main constraint

The result is a structured decision map rather than a single mortgage calculation.

## 📚 Academic Research Context

As part of the Master's Final Project, a separate statistical research
layer was developed to investigate how household-level benchmarking
could complement deterministic mortgage analysis.

This research environment is intentionally separated from the deployed
application and is not part of the commercial product implementation.

## 🔮 Roadmap

### Current prototype

- Lite and Pro user experiences
- Deterministic financial analysis
- Constraint diagnosis
- Restructuring recommendations
- Alternative strategy evaluation
- Appraisal and financing scenarios
- Technical traceability

### Future product evolution

- Mortgage policy rules by lender/profile
- Strategy ranking and prioritization
- Case management and audit trail
- Adviser reports
- Outcome tracking
- Commercially compatible statistical benchmarking
- Learning from proprietary real-world cases
