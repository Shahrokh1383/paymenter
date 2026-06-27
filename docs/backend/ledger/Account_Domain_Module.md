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
- **Currency Safety**: All deposit/withdraw operations enforce currency homogeneity.
- **Identity**: Every account is uniquely identified by an `AccountNumber` value object.
- **Currency Change Guard**: Currency can only be changed when balance is exactly zero.
- **Minimum Topup Rule**: Topup amounts must be positive (business rule, enforced at application level but defined here).

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Enforced. Domain has zero external imports. |
| Rule 3: No Primitive Obsession | ⚠️ Violated — `topup()` accepts primitive `float` (see TD-6 in Account Application module). |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced for balance/currency; ⚠️ Currency update bypasses aggregate (see TD-5). |

---

## Business Rules

### BR-1: Non-Negative Balance Invariant
An account balance must never drop below zero during normal operations. `Account.withdraw()` enforces this by raising `InsufficientFundsError` if `balance.amount < amount.amount`.

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its balance is exactly zero. `Account.can_change_currency()` enforces this.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. This rule is defined here and enforced in the application layer (TopupAccountHandler).

### (Implicit) Currency Homogeneity in Account Operations
All `deposit` and `withdraw` methods verify that the provided `Money` object has the same currency as the account, raising `CurrencyMismatchError` otherwise. This prevents mixed-currency operations on a single account.

---

## Backend Architecture — Domain Layer

### Directory
```
src/ledger/domain/
├── entities/
│   └── account.py          # Account aggregate
├── value_objects/
│   ├── account_number.py   # AccountNumber
│   └── card_number.py      # CardNumber (⚠️ should be removed — see TD-2)
└── repositories.py         # AccountRepository abstract port
```

### Account Entity
```python
@dataclass
class Account:
    id: int
    user_id: int
    account_number: AccountNumber
    card_number: CardNumber          # ⚠️ SECURITY VIOLATION (see TD-2)
    balance: Money
```
**Methods:**
- `withdraw(amount: Money)`: Validates currency match and sufficient funds. Subtracts from balance.
- `deposit(amount: Money)`: Validates currency match. Adds to balance.
- `topup(amount: float)`: ⚠️ Accepts primitive `float` (see TD-6 in Account Application module). Adds to balance using `Decimal(str(amount))`.
- `can_change_currency() -> bool`: Returns `True` only if `balance.amount == 0`.
- *(Missing)* `change_currency(new_currency: str)` — should be added (see TD-5).

### Value Objects
- **AccountNumber**: Immutable. Exactly 10 digits. Zero-padded or stripped whitespace.
- **CardNumber**: Immutable. Exactly 16 digits. Luhn algorithm validation. String representation masks as `****-****-****-XXXX`. ⚠️ This should be removed from Ledger context entirely (see TD-2).
- **Money** (from `src.common`): Immutable. `Decimal` amount + 3-letter ISO currency code. Safe arithmetic (`__add__`, `__sub__`) with currency mismatch protection.

### Repository Port (Abstract)
```python
class AccountRepository(ABC):
    def get_by_id(self, account_id: int) -> Account
    def get_by_card_number(self, card_number: CardNumber) -> Account
    def update(self, account: Account) -> None
    def add(self, account: Account) -> int
    def update_currency(self, account_id: int, currency_id: int) -> None  # ⚠️ See TD-5
```
**Note**: `update_currency` bypasses the aggregate and will be eliminated.

---

## Edge Cases & Known Issues

### EC-6: Stale Aggregate After Currency Change
**Scenario**: After an account’s currency is changed via the application handler (UpdateAccountCurrencyHandler), the in‑memory `Account` entity still holds the old currency code.
**Impact**: If that same entity instance is reused in the same request (e.g., a subsequent topup), a `CurrencyMismatchError` may occur even though the database is correct.
**Status**: **BUG**. Caused by the repository's `update_currency()` method that does not update the aggregate. See TD-5.

---

## Notes & Technical Debt

### TD-2: CardNumber in Ledger Context
**Violation**: Constitution Security & Compliance — “Ledger context never sees card data”
**Location**: `src/ledger/domain/entities/account.py`, `src/ledger/domain/value_objects/card_number.py`
**Current**: `Account` entity holds `card_number: CardNumber`. Repository maps it from DB.
**Required Fix**: Remove `CardNumber` entirely from the Ledger bounded context. The `Account` entity should only contain `account_number: AccountNumber`. Card data must remain in `checkout` or `identity` contexts. If lookup by card is needed, it should be a tokenized reference or handled by an anti‑corruption layer in Checkout. Also delete the `get_by_card_number` method from the repository port.

### TD-5: Update Currency Bypasses Aggregate
**Violation**: Constitution Rule 4 (Aggregates Protect Their Own Invariants)
**Location**: Repository method `update_currency()` and handler `UpdateAccountCurrencyHandler` (see Account Application module).
**Current**: Handler calls `repo.update_currency(account_id, currency_id)` directly. The `Account` entity’s `balance.currency` is never updated in memory.
**Required Fix**:
1. Add `change_currency(new_currency: str)` method to `Account` entity.
2. Inside the method, enforce `can_change_currency()`, update `self.balance = Money(self.balance.amount, new_currency)`, and increment version (when optimistic locking is added).
3. Handler must call `repo.update(account)` after calling `account.change_currency(new_code)`.
4. Delete `AccountRepository.update_currency()` method.