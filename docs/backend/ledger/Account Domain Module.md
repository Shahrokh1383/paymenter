# Account Domain Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

## Overview

The **Account Domain** module defines the core financial account model within the Ledger bounded context. It encapsulates the `Account` aggregate, its associated value objects, and the abstract repository port. This module is pure domain logic with zero external framework dependencies, strictly enforcing all financial invariants.

### Core Responsibilities
- **Balance Invariant Protection**: Ensuring accounts never drop below a zero balance during standard user withdrawals.
- **System Reversals (Chargebacks)**: Safely allowing negative balances strictly for system-initiated refunds on spent funds, bypassing standard user-facing withdrawal invariants.
- **Universal Ledger Representation**: Acting as the single source of truth for both **User Accounts** and **System Escrow Accounts** (where `user_id` is absent/null) to guarantee perfect double-entry accounting.
- **Currency Safety & Normalization**: Enforcing currency homogeneity across all fund movements using strict Value Objects.
- **Identity & Concurrency**: Managing unique identities via `AccountNumber` and optimistic concurrency via aggregate versioning.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Enforced. Domain has zero external/framework imports. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Operations accept `Money`. Currencies are strictly typed via the `CurrencyCode` Value Object. |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced. Currency updates and overdraft protections are encapsulated exclusively within the aggregate. |

---

## Business Rules

### BR-1: Non-Negative Balance Invariant
A user account balance must never drop below zero during normal operations. `Account.withdraw()` enforces this by raising `InsufficientFundsError` if `balance.amount < amount.amount`.

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its current balance is exactly zero. `Account.change_currency()` enforces this internally before mutating state, preventing complex multi-currency balance reconciliation.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. Defined and enforced within `Account.topup()`, ensuring this invariant cannot be bypassed by any Application layer caller.

### BR-8: System Reversal / Chargeback Override
Standard withdrawals are blocked if funds are insufficient. However, system-initiated chargebacks (refunding a completed transaction where the receiver has already spent the funds) require forcing a debit. `Account.apply_system_reversal()` strictly bypasses BR-1, allowing the account balance to drop below zero. This ensures the global double-entry ledger balances without crashing on overdraft exceptions.

### (Implicit) Currency Homogeneity in Account Operations
All `deposit`, `withdraw`, `topup`, and `apply_system_reversal` methods verify that the provided `Money` object holds the exact same `CurrencyCode` Value Object instance/value as the account. If they differ, a `CurrencyMismatchError` is raised.

---

## Backend Architecture — Domain Layer

### Directory
```text
src/ledger/domain/
├── entities/
│   └── account.py          # Account aggregate (User & System Escrow)
├── ports/
│   └── system_account_resolver_port.py  # Port to dynamically resolve Escrow accounts by currency
└── value_objects/
    └── account_number.py   # AccountNumber
```

### Account Entity
```python
@dataclass
class Account:
    id: int
    user_id: Optional[int]     # Optional to support System Escrow Accounts (where user_id is NULL)
    account_number: AccountNumber
    balance: Money             # Money encapsulates Decimal amount + CurrencyCode VO
    version: int = 0           # Used for Optimistic Concurrency Control (OCC)
```
**Domain Methods:**
- `withdraw(amount: Money)`: Validates currency match and sufficient funds (Enforces BR-1). Subtracts from balance.
- `deposit(amount: Money)`: Validates currency match. Adds to balance.
- `topup(amount: Money)`: Validates currency match and positive amount rule (BR-6). Adds to balance.
- `apply_system_reversal(amount: Money)`: Validates currency match. Forces subtraction from balance, explicitly bypassing the non-negative check (BR-8) for system chargebacks.
- `can_change_currency() -> bool`: Returns `True` only if `balance.amount == 0`.
- `change_currency(new_currency_code: str)`: Instantiates a new `CurrencyCode` Value Object, enforces the zero-balance invariant, and mutates internal state safely.

### Value Objects
- **AccountNumber** (Local to Ledger): Immutable. Exactly 10 digits. Strips whitespace and validates digit-only constraints.
- **Money** (from `src/common`): Immutable. Encapsulates a `Decimal` amount and a strictly typed **`CurrencyCode`** Value Object. Provides safe arithmetic (`__add__`, `__sub__`) with automatic currency mismatch protection.
- **CurrencyCode** (from `src/common`): Immutable 3-letter ISO code. Enforces uppercase normalization (e.g., `"usd "` becomes `"USD"`) in `__post_init__` to eliminate string-matching fragility across system boundaries.

### Repository Port (Abstract)
```python
class AccountRepository(ABC):
    def get_by_id(self, account_id: int) -> Account
    def update(self, account: Account) -> None
    def add(self, account: Account) -> int
```
**Note**: The repository interface is strictly limited to aggregate persistence. Infrastructure implementations (like `SqliteAccountRepository`) must extract primitives (like `.value` from Value Objects) strictly at the SQL execution boundary, and are responsible for incrementing/synchronizing the `version` attribute to enforce Optimistic Locking.

---

## Edge Cases & Known Issues

*No active edge cases.*

*(Resolved) EC-6: Stale Aggregate After Currency Change*
**Previous Scenario**: After an account’s currency was changed, the in‑memory `Account` entity retained the old currency state.
**Resolution**: The Application handler invokes `account.change_currency(new_code)` directly on the aggregate. The aggregate updates its own state in memory using the normalized `CurrencyCode` VO, and the handler subsequently calls `repo.update(account)`.

*(Resolved) EC-7: String Normalization Failures in Currency Checks*
**Previous Scenario**: Domain comparisons using raw string primitives (e.g., `"USD" != "USD "`) triggered false-positive `CurrencyMismatchError` exceptions during fund holds.
**Resolution**: Introduction of the `CurrencyCode` Value Object ensures all currency strings are strictly normalized (`strip().upper()`) upon instantiation. Domain equality checks now reliably compare normalized immutable objects.

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-2: CardNumber in Ledger Context*
**Previous Violation**: Constitution Security & Compliance — “Ledger context never sees card data”.
**Resolution**: `CardNumber` logic completely removed from Ledger. Card data is strictly isolated to the `Identity` context.

*(Resolved) TD-8: Unrecoverable Refund State on Spent Funds*
**Previous Violation**: Refunding a successful transaction called `withdraw()` on the destination account. If the receiver spent the funds, it threw `InsufficientFundsError`, halting the system.
**Resolution**: Introduced `Account.apply_system_reversal(amount)`. This dedicated domain method forces a debit (allowing negative balances) strictly for system chargebacks, ensuring the ledger balances globally without crashing.

*(Resolved) TD-12: Primitive Obsession in Currency Representation*
**Previous Violation**: Constitution Rule 3. The `Money` Value Object relied on a primitive `str` for the currency code, leading to brittle comparisons and lack of central validation.
**Resolution**: Refactored `Money` to require the `CurrencyCode` Value Object. The Domain layer now speaks exclusively in normalized, strictly-typed Ubiquitous Language rather than fragile primitives. Infrastructure adapters are explicitly responsible for translating DB rows into these Value Objects.

***