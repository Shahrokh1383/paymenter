# Account Domain Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture — Domain Layer](#backend-architecture--domain-layer)
   - [Account Entity](#account-entity)
   - [Value Objects](#value-objects)
   - [Repository Port](#repository-port)
4. [Edge Cases & Known Issues](#edge-cases--known-issues)
5. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Account Domain** module defines the core financial account model within the Ledger bounded context. It encapsulates the `Account` aggregate, its associated value objects, and the abstract repository port. This module is pure domain logic with no external dependencies, enforcing all invariants on balance, currency, and identity.

### Core Responsibilities
- **Balance Invariant**: Ensuring accounts never go negative during normal withdrawals.
- **Currency Safety**: All deposit, withdraw, and topup operations enforce currency homogeneity.
- **Identity**: Every account is uniquely identified by an `AccountNumber` value object.
- **Currency Change Guard**: Currency can only be changed when balance is exactly zero, encapsulated within the aggregate.
- **Minimum Topup Rule**: Topup amounts must be positive and are strictly enforced at the domain layer.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Enforced. Domain has zero external imports. |
| Rule 3: No Primitive Obsession | ✅ Enforced. `topup()` accepts `Money` Value Object. |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced. Currency update logic encapsulated within the aggregate. |

---

## Business Rules

### BR-1: Non-Negative Balance Invariant
An account balance must never drop below zero during normal operations. `Account.withdraw()` enforces this by raising `InsufficientFundsError` if `balance.amount < amount.amount`.

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its balance is exactly zero. `Account.change_currency()` enforces this internally before mutating state.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. This rule is defined and strictly enforced within the Domain layer inside `Account.topup()`, ensuring the invariant cannot be bypassed by any Application layer caller.

### (Implicit) Currency Homogeneity in Account Operations
All `deposit`, `withdraw`, and `topup` methods verify that the provided `Money` object has the same currency as the account, raising `CurrencyMismatchError` otherwise. This prevents mixed-currency operations on a single account.

---

## Backend Architecture — Domain Layer

### Directory
```
src/ledger/domain/
├── entities/
│   └── account.py          # Account aggregate
└── value_objects/
    └── account_number.py   # AccountNumber
```

### Account Entity
```python
@dataclass
class Account:
    id: int
    user_id: int
    account_number: AccountNumber
    balance: Money
```
**Methods:**
- `withdraw(amount: Money)`: Validates currency match and sufficient funds. Subtracts from balance.
- `deposit(amount: Money)`: Validates currency match. Adds to balance.
- `topup(amount: Money)`: Validates currency match and positive amount rule (BR-6). Adds to balance.
- `can_change_currency() -> bool`: Returns `True` only if `balance.amount == 0`.
- `change_currency(new_currency_code: str)`: Enforces zero-balance invariant, reconstructs internal `Money` object with the new currency code.

### Value Objects
- **AccountNumber**: Immutable. Exactly 10 digits. Zero-padded or stripped whitespace.
- **Money** (from `src.common`): Immutable. `Decimal` amount + 3-letter ISO currency code. Safe arithmetic (`__add__`, `__sub__`) with currency mismatch protection.

### Repository Port (Abstract)
```python
class AccountRepository(ABC):
    def get_by_id(self, account_id: int) -> Account
    def update(self, account: Account) -> None
    def add(self, account: Account) -> int
```
**Note**: The repository interface is strictly limited to standard aggregate persistence. Direct state mutation methods (e.g., `update_currency`) and cross-context data lookups (e.g., `get_by_card_number`) have been purged to respect Domain boundaries.

---

## Edge Cases & Known Issues

*No active edge cases.*

*(Resolved) EC-6: Stale Aggregate After Currency Change*
**Previous Scenario**: After an account’s currency was changed via the application handler, the in‑memory `Account` entity retained the old currency code.
**Resolution**: The handler now invokes `account.change_currency(new_code)` directly on the aggregate. The aggregate updates its own state in memory, and the handler calls `repo.update(account)` to persist the fully synchronized state. Memory inconsistency eliminated.

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-2: CardNumber in Ledger Context*
**Previous Violation**: Constitution Security & Compliance — “Ledger context never sees card data”.
**Resolution**: `CardNumber` value object, `card_number` entity attribute, and `get_by_card_number` repository method have been completely removed from the Ledger bounded context. The database schema dropped the `card_number` column. Card data is now strictly isolated to the `Identity` context (`user_cards` table) and mapped to accounts via an Anti-Corruption Layer in the `Checkout` context.

*(Resolved) TD-5: Update Currency Bypasses Aggregate*
**Previous Violation**: Constitution Rule 4 (Aggregates Protect Their Own Invariants).
**Resolution**: 
1. The `update_currency()` bypass method was deleted from both the repository port and SQLite implementation.
2. A `change_currency(new_currency_code: str)` method was added to the `Account` entity, enforcing `can_change_currency()` and updating `self.balance`.
3. The Application handler was refactored to orchestrate the domain method followed by `repo.update(account)`.