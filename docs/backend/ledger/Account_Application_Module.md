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

The **Account Application** module orchestrates write and read operations on the `Account` aggregate. It defines commands, queries, handlers, and the CQRS read-side projection for account summaries. All operations go through the Domain layer for invariant validation, except where noted as technical debt.

### Core Responsibilities
- **Topup**: Adding funds to an account with minimum amount enforcement.
- **Currency Update**: Changing an account’s currency when zero‑balance invariant holds.
- **Account Queries**: Serving optimized, joined read models for UI list views without N+1 problems.
- **CQRS Separation**: Commands use the domain model; queries use a dedicated read model port.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command/handler/query is isolated. |
| Rule 3: No Primitive Obsession | ⚠️ Violated in Topup (see TD-6). |
| Rule 4: Aggregates Protect Invariants | ⚠️ Violated in Currency Update (see TD-5). |
| Rule 5: Cross-Context via Events | N/A for these operations. |

---

## Business Rules

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its balance is exactly zero. Validated by `Account.can_change_currency()` in the handler before proceeding.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. Enforced in `TopupAccountHandler`.

---

## Backend Architecture — Application Layer

### Commands (Immutable Dataclasses)

| Command | Fields | Purpose |
|---|---|---|
| `TopupAccountCommand` | `account_id: int`, `amount: float` | Add funds to an account |
| `UpdateAccountCurrencyCommand` | `account_id: int`, `currency_id: int` | Change account currency |

### Queries (Immutable Dataclasses)

| Query | Fields | Purpose |
|---|---|---|
| `GetAllAccountsQuery` | *(none)* | Retrieve all account summaries |

### Handlers

**TopupAccountHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`
- Flow:
  1. Load `Account` by `command.account_id`.
  2. Validate `command.amount > 0` (BR-6).
  3. Call `account.topup(command.amount)` — ⚠️ Accepts primitive `float` (see TD-6).
  4. Call `AccountRepository.update(account)`.
  5. Commit Unit of Work.
- **No domain events emitted** for topup operations currently.

**UpdateAccountCurrencyHandler**
- Dependencies: `UnitOfWork`, `AccountRepository`
- Flow:
  1. Load `Account` by `command.account_id`.
  2. Call `account.can_change_currency()` → raises error if balance ≠ 0 (BR-5).
  3. Call `repo.update_currency(account_id, currency_id)` — ⚠️ **Bypasses aggregate** (see TD-5).
  4. Commit Unit of Work.
- **Post-condition**: The in‑memory `Account` entity still has the old currency code (stale state — see EC-6).

**GetAllAccountsHandler**
- Dependencies: `AccountQueryPort` (CQRS Read Model)
- Flow: Delegates directly to `query_port.get_all_summaries()`.

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
| `card_number` | `str` | `accounts.card_number` (⚠️ Should be removed — see TD-2 in Account Domain module) |
| `balance` | `Decimal` | `accounts.balance` (converted from REAL) |

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
         c.code AS currency_code, a.account_number, a.card_number, a.balance
  FROM accounts a
  JOIN currencies c ON a.currency_id = c.id
  JOIN users u ON a.user_id = u.id
  ```

---

## Flows

### 1. Topup Account
```
[Internal/Admin] → TopupAccountCommand(account_id, amount: float)
  → TopupAccountHandler
    → UoW.begin()
    → AccountRepository.get_by_id(account_id)
    → Validate amount > 0.0
    → account.topup(amount)                    [⚠️ primitive float → Decimal(str(amount))]
    → AccountRepository.update(account)
    → UoW.commit()
```

### 2. Update Account Currency
```
[Internal/Admin] → UpdateAccountCurrencyCommand(account_id, currency_id)
  → UpdateAccountCurrencyHandler
    → UoW.begin()
    → AccountRepository.get_by_id(account_id)
    → account.can_change_currency()            [Invariant Check — must be zero balance]
    → repo.update_currency(account_id, currency_id)  [⚠️ Bypasses aggregate]
    → UoW.commit()
    → ⚠️ account.balance.currency remains stale in memory
```

### 3. Query All Accounts
```
  → GetAllAccountsQuery()
    → GetAllAccountsHandler
      → SqliteAccountReadModel.get_all_summaries()
        → JOIN query (accounts + users + currencies)
        → Returns List[AccountSummary]
```

---

## Edge Cases & Known Issues

### EC-5: Currency Mismatch on Topup (Precision Risk)
**Scenario**: Topup is called with a `float` amount but no currency is specified. The `topup()` method uses the account’s existing currency.
**Current Behavior**: Works correctly for existing accounts, but the `float` input risks precision loss before `Decimal(str(amount))` conversion.
**Impact**: Potential micro‑precision errors in financial records.
**Status**: Works but violates Constitution Rule 3. See TD-6.

### EC-6: Stale Aggregate After Currency Change
**Scenario**: `UpdateAccountCurrencyHandler` commits successfully.
**Current Behavior**: The `Account` entity loaded into memory still has the old `balance.currency`. If the same entity instance is reused in the same request (e.g., for a subsequent topup), currency mismatch errors may occur.
**Impact**: Logic errors in compound operations.
**Status**: **BUG**. Caused by the repository’s `update_currency()` method that does not update the aggregate. See TD-5.

---

## Notes & Technical Debt

### TD-5: Update Currency Bypasses Aggregate
**Violation**: Constitution Rule 4 (Aggregates Protect Their Own Invariants)
**Location**: `src/ledger/application/handlers/update_account_currency_handler.py`, `src/ledger/infrastructure/persistence/sqlite_account_repository.py` → `update_currency()`
**Current**: Handler calls `repo.update_currency(account_id, currency_id)` directly. The `Account` entity’s `balance.currency` remains unchanged.
**Required Fix**:
1. Add `change_currency(new_currency: str)` method to `Account` entity (see Account Domain module).
2. Inside the method, enforce `can_change_currency()`, update `self.balance = Money(self.balance.amount, new_currency)`, and increment version.
3. Handler must call `account.change_currency(new_code)` followed by `repo.update(account)`.
4. Delete `AccountRepository.update_currency()` method.

### TD-6: Topup Uses Primitive Float
**Violation**: Constitution Rule 3 (Primitive Obsession) + Financial Precision Risk
**Location**: `src/ledger/application/commands/topup_account_command.py`, `src/ledger/domain/entities/account.py` → `topup()`
**Current**: `amount: float` in command → `topup(amount: float)`.
**Required Fix**:
1. Change `TopupAccountCommand` to accept `amount: Decimal` and `currency_code: str`.
2. Change `Account.topup()` to accept `amount: Money`.
3. Validate currency match inside `topup()`.

### TD-10: Database Schema — `balance REAL`
**Location**: `src/common/infrastructure/database.py` (accounts table definition)
**Current**: `accounts.balance REAL NOT NULL DEFAULT 0.0`
**Issue**: `REAL` in SQLite is IEEE 754 floating point. Although repositories convert to `str` before INSERT, the column type itself is imprecise. If any raw SQL or external tool writes to this column, precision is lost.
**Required Fix**: Change schema to `balance TEXT NOT NULL DEFAULT '0.00'`. Store `Money` as string representation of `Decimal`. This affects the `AccountSummary` read model and the `SqliteAccountRepository.update()` method.

### TD-9 (Partial): Incomplete DI Container Integration
**Location**: Controller layer, but affects handler instantiation.
**Current**: `GetAllAccountsHandler` is likely manually instantiated in the controller alongside other handlers. The global `DIContainer` is only accessed for `EventBus`.
**Required Fix**: All handlers (including `GetAllAccountsHandler`, `TopupAccountHandler`, `UpdateAccountCurrencyHandler`) should be registered in and requested from the `DIContainer`.