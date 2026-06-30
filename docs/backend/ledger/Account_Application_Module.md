# Account Application Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture — Application Layer](#backend-architecture--application-layer)
   - [Commands](#commands)
   - [Queries](#queries)
   - [Handlers](#handlers)
   - [DTOs](#dtos)
4. [Backend Architecture — Infrastructure Layer (Read Side)](#backend-architecture--infrastructure-layer-read-side)
   - [CQRS Read Model Port](#cqrs-read-model-port)
   - [SQLite Read Model Implementation](#sqlite-read-model-implementation)
5. [Flows](#flows)
   - [Topup Account](#1-topup-account)
   - [Update Account Currency](#2-update-account-currency)
   - [Query All Accounts](#3-query-all-accounts)
6. [Edge Cases & Known Issues](#edge-cases--known-issues)
7. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Account Application** module orchestrates write and read operations on the `Account` aggregate. It defines commands, queries, handlers, and the CQRS read-side projection for account summaries. All operations strictly go through the Domain layer for invariant validation.

### Core Responsibilities
- **Topup**: Adding funds to an account with minimum amount enforcement and strict type safety.
- **Currency Update**: Changing an account’s currency when zero‑balance invariant holds, fully encapsulated within the aggregate.
- **Account Queries**: Serving optimized, joined read models for UI list views without N+1 problems.
- **CQRS Separation**: Commands use the domain model; queries use a dedicated read model port.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command/handler/query/port is isolated. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Topup uses `Decimal` and `Money` Value Objects. |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced. Currency update delegated to `Account` aggregate. |
| Rule 5: Cross-Context via Events | N/A for these operations. |

---

## Business Rules

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its balance is exactly zero. Validated internally by `Account.change_currency()` which throws an error if the invariant does not hold.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. Enforced inside the Domain layer by `Account.topup()`.

---

## Backend Architecture — Application Layer

### Commands (Immutable Dataclasses)

| Command | Fields | Purpose |
|---|---|---|
| `TopupAccountCommand` | `account_id: int`, `amount: Decimal` | Add funds to an account |
| `UpdateAccountCurrencyCommand` | `account_id: int`, `currency_code: str` | Change account currency |

### Queries (Immutable Dataclasses)

| Query | Fields | Purpose |
|---|---|---|
| `GetAllAccountsQuery` | *(none)* | Retrieve all account summaries |

### Handlers

**TopupAccountHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`
- Flow:
  1. Load `Account` by `command.account_id`.
  2. Construct `Money` Value Object from `command.amount` and the account's existing currency.
  3. Call `account.topup(money)` — Domain enforces BR-6 and currency homogeneity.
  4. Call `AccountRepository.update(account)`.
  5. Commit Unit of Work.
- **No domain events emitted** for topup operations currently.

**UpdateAccountCurrencyHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`
- Flow:
  1. Load `Account` by `command.account_id`.
  2. Call `account.change_currency(command.currency_code)` — Aggregate enforces BR-5 and mutates its own state.
  3. Call `AccountRepository.update(account)` — Persists fully synchronized aggregate state.
  4. Commit Unit of Work.

**GetAllAccountsHandler**
- Dependencies: `AccountQueryPort` (CQRS Read Model)
- Flow: Delegates directly to `query_port.get_all_summaries()`. Instantiated via `DIContainer`.

### DTOs

**AccountSummary**
| Field | Type | Source |
|---|---|---|
| `id` | `int` | `accounts.id` |
| `user_id` | `int` | `accounts.user_id` |
| `user_name` | `str` | `users.name` (JOIN) |
| `currency_id` | `int` | `accounts.currency_id` |
| `currency_code` | `str` | `currencies.code` (JOIN) |
| `account_number` | `str` | `accounts.account_number` |
| `balance` | `Decimal` | `accounts.balance` (stored as TEXT) |

---

## Backend Architecture — Infrastructure Layer (Read Side)

### CQRS Read Model Port
```python
class AccountQueryPort(ABC):
    def get_all_summaries(self) -> List[AccountSummary]
```

### SQLite Read Model Implementation

**SqliteAccountReadModel** (`src/ledger/infrastructure/persistence/...`)
- Implements `AccountQueryPort`.
- Performs a 3‑way JOIN: `accounts` → `currencies` → `users`.
- Returns `List[AccountSummary]` with `Decimal` balance (no primitive floats).
- Query pattern:
  ```sql
  SELECT a.id, a.user_id, u.name AS user_name, a.currency_id,
         c.code AS currency_code, a.account_number, a.balance
  FROM accounts a
  JOIN currencies c ON a.currency_id = c.id
  JOIN users u ON a.user_id = u.id
  ```

---

## Flows

### 1. Topup Account
```
[Internal/Admin] → TopupAccountCommand(account_id, amount: Decimal)
  → TopupAccountHandler (Resolved via DIContainer)
    → UoW.begin()
    → AccountRepository.get_by_id(account_id)
    → Money(amount, account.balance.currency)
    → account.topup(money)                    [Domain enforces > 0 and currency match]
    → AccountRepository.update(account)
    → UoW.commit()
```

### 2. Update Account Currency
```
[Internal/Admin] → UpdateAccountCurrencyCommand(account_id, currency_code: str)
  → UpdateAccountCurrencyHandler (Resolved via DIContainer)
    → UoW.begin()
    → AccountRepository.get_by_id(account_id)
    → account.change_currency(currency_code)                 [Aggregate enforces zero-balance & updates state]
    → AccountRepository.update(account)
    → UoW.commit()
```

### 3. Query All Accounts
```
  → GetAllAccountsQuery()
    → GetAllAccountsHandler (Resolved via DIContainer)
      → SqliteAccountReadModel.get_all_summaries()
        → JOIN query (accounts + users + currencies)
        → Returns List[AccountSummary]
```

---

## Edge Cases & Known Issues

*No active edge cases.*

*(Resolved) EC-5: Currency Mismatch on Topup (Precision Risk)*
**Previous Scenario**: Topup was called with a `float` amount, risking precision loss before conversion.
**Resolution**: Command now strictly accepts `Decimal`. Handler constructs a `Money` Value Object ensuring type safety and currency matching before crossing the domain boundary.

*(Resolved) EC-6: Stale Aggregate After Currency Change*
**Previous Scenario**: `UpdateAccountCurrencyHandler` committed via a repository bypass, leaving the in-memory `Account` entity with a stale `balance.currency`.
**Resolution**: Handler now explicitly calls `account.change_currency()`. The aggregate mutates its own state in memory, and `repo.update(account)` persists the synchronized state. Memory inconsistency eliminated.

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-2: PII Leakage in Read Model*
**Previous Violation**: `card_number` was exposed in `AccountSummary` DTO and SQL projection.
**Resolution**: `card_number` completely purged from the DTO and the `SqliteAccountReadModel` JOIN query. Ledger context adheres to Principle of Least Privilege.

*(Resolved) TD-5: Update Currency Bypasses Aggregate*
**Previous Violation**: Constitution Rule 4. Handler called `repo.update_currency(account_id, currency_id)` directly.
**Resolution**: 
1. Added `CurrencyQueryPort` (Application) and `SqliteCurrencyResolver` (Infrastructure) to translate `int` ID to `str` code without breaking Dependency Rule.
2. Added `change_currency()` to `Account` entity.
3. Handler calls domain method, then `repo.update(account)`.
4. Deleted `update_currency()` from repository port and implementation.

*(Resolved) TD-6: Topup Uses Primitive Float*
**Previous Violation**: Constitution Rule 3. `amount: float` in command → `topup(amount: float)`.
**Resolution**: 
1. `TopupAccountCommand.amount` changed to `Decimal`.
2. `Account.topup()` changed to accept `Money`.
3. Currency homogeneity enforced inside the aggregate.

*(Resolved) TD-10: Database Schema — `balance REAL`*
**Previous Violation**: `accounts.balance REAL NOT NULL DEFAULT 0.0` risked IEEE 754 precision loss.
**Resolution**: Schema migrated to `balance TEXT NOT NULL DEFAULT '0.00'`. Applied to `accounts.balance`, `transactions.amount`, and `gateway_sessions.amount`.

*(Resolved) TD-9: Incomplete DI Container Integration*
**Previous Violation**: Handlers manually instantiated in Controllers (tight coupling).
**Resolution**: Factory methods added to `DIContainer` for all handlers. Controllers refactored to resolve handlers via `current_app.di_container`.