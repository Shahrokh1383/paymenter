# Account Application Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.2.0 (Strict Escrow Isolation & Merchant Support)

---

## Overview

The **Account Application** module orchestrates write and read operations on the `Account` aggregate. It defines commands, queries, handlers, and strictly separated CQRS read-side projections. All write operations strictly go through the Domain layer for invariant validation.

### Core Responsibilities
- **Account Creation:** Provisioning accounts for both **Users** and **Merchants** via a unified, explicit dashboard flow.
- **Topup & Currency Update:** Adding funds and changing currencies with strict domain invariant enforcement.
- **Strict CQRS Isolation:** Enforcing absolute separation between User/Merchant accounts and System Escrow accounts at the database query level to maintain the Single Responsibility Principle (SRP).

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Application depends on Domain, never the reverse. |
| Rule 2: New Feature = New File | ✅ Every command/handler/query/port is isolated. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Topup uses `Decimal` and `Money` VOs. |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced. Currency update delegated to `Account` aggregate. |
| Rule 5: Cross-Context via Events | ✅ Account creation emits events to update Identity read models. |

---

## Business Rules

### BR-5: Zero-Balance Currency Change
An account's currency may only be changed if its balance is exactly zero. Validated internally by `Account.change_currency()`.

### BR-6: Topup Minimum
Topup amounts must be strictly greater than zero. Enforced inside the Domain layer by `Account.topup()`.

### BR-7: Account Ownership (User vs. Merchant vs. System)
An account must belong to either a User (`user_id IS NOT NULL`), a Merchant (`merchant_id IS NOT NULL`), or the System Escrow (`user_id IS NULL AND merchant_id IS NULL`). This tri-state ownership is strictly enforced at the schema and read-model levels.

---

## Backend Architecture — Application Layer

### Commands (Immutable Dataclasses)

| Command | Fields | Purpose |
|---|---|---|
| `CreateAccountCommand` | `user_id: Optional[int]`, `merchant_id: Optional[int]`, `currency_code: str` | Provision a new account for a User or Merchant |
| `TopupAccountCommand` | `account_id: int`, `amount: Decimal` | Add funds to an account |
| `UpdateAccountCurrencyCommand` | `account_id: int`, `currency_code: str` | Change account currency |

### Handlers

**CreateAccountHandler**
- **Dependencies:** `UnitOfWork`, `AccountRepository`, `EventBus`
- **Flow:**
  1. Generate unique `AccountNumber`.
  2. Instantiate `Account` with `user_id`, `merchant_id`, and zero `Money` balance.
  3. Persist via `AccountRepository.add()`.
  4. Commit UOW.
  5. Publish `AccountCreatedEvent` (carrying both `user_id` and `merchant_id` for cross-context read model updates).

**GetAllAccountsHandler** & **GetAllEscrowAccountsHandler**
- Delegate to their respective CQRS Read Model ports.

### DTOs

**AccountSummary** (User & Merchant Accounts)
| Field | Type | Source |
|---|---|---|
| `id` | `int` | `accounts.id` |
| `user_id` | `int` | `accounts.user_id` (0 if merchant) |
| `user_name` | `str` | `users.name` OR `merchants.name` (via COALESCE) |
| `currency_code` | `str` | `currencies.code` |
| `account_number` | `str` | `accounts.account_number` |
| `balance` | `Decimal` | `accounts.balance` |

**EscrowAccountSummary** (System Accounts)
| Field | Type | Source |
|---|---|---|
| `id` | `int` | `accounts.id` |
| `currency_code` | `str` | `currencies.code` |
| `account_number` | `str` | `accounts.account_number` |
| `balance` | `Decimal` | `accounts.balance` |

---

## Backend Architecture — Infrastructure Layer (Read Side)

### SQLite Read Model Implementations

**SqliteAccountReadModel** (`src/ledger/infrastructure/persistence/sqlite_account_read_model.py`)
- Implements `AccountQueryPort`.
- **Strictly isolates USER and MERCHANT accounts.**
- Query pattern enforces SRP by explicitly filtering out System Escrow accounts:
  ```sql
  SELECT a.id, a.user_id, 
         COALESCE(u.name, m.name, 'System') AS user_name,
         c.code AS currency_code, a.account_number, uc.card_number, a.balance
  FROM accounts a
  JOIN currencies c ON a.currency_id = c.id
  LEFT JOIN users u ON a.user_id = u.id
  LEFT JOIN merchants m ON a.merchant_id = m.id
  LEFT JOIN user_cards uc ON a.id = uc.account_id
  WHERE a.user_id IS NOT NULL OR a.merchant_id IS NOT NULL
  ```

**SqliteEscrowAccountReadModel** (`src/ledger/infrastructure/persistence/sqlite_escrow_account_read_model.py`)
- Implements `EscrowAccountQueryPort`.
- **Strictly isolates SYSTEM ESCROW accounts.**
- Query pattern enforces SRP by explicitly filtering out User and Merchant accounts:
  ```sql
  SELECT a.id, c.code AS currency_code, a.account_number, a.balance
  FROM accounts a
  JOIN currencies c ON a.currency_id = c.id
  WHERE a.user_id IS NULL AND a.merchant_id IS NULL
  ```

---

## Flows

### 1. Create Account (User or Merchant)
```
[Dashboard UI] -> POST /dashboard/accounts/create (owner_id: "user_123" or "merchant_456")
  -> Controller parses owner_id into user_id and merchant_id
  -> CreateAccountCommand(user_id, merchant_id, currency_code)
    -> CreateAccountHandler
      -> Account(id=None, user_id, merchant_id, account_number, balance=0)
      -> AccountRepository.add(account)
      -> EventBus.publish(AccountCreatedEvent)
```

### 2. Query All User/Merchant Accounts
```
  -> GetAllAccountsQuery()
    -> GetAllAccountsHandler
      -> SqliteAccountReadModel.get_all_summaries()
        -> JOIN query with strict WHERE clause (Excludes Escrow)
        -> Returns List[AccountSummary]
```

---

## Edge Cases & Known Issues

*No active edge cases.*

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved in v1.2.0) TD-12: Conflation of User, Merchant, and Escrow Accounts in Read Models*
**Previous Violation**: Single Responsibility Principle (SRP). System Escrow accounts were leaking into the `/dashboard/accounts` UI because the read model lacked a strict filtering `WHERE` clause. Furthermore, Merchant accounts were being auto-provisioned, causing them to be misclassified as Escrow accounts.
**Resolution**: 
1. Added `merchant_id` to the `Account` aggregate and `accounts` schema.
2. Updated `SqliteAccountReadModel` to strictly filter `WHERE a.user_id IS NOT NULL OR a.merchant_id IS NOT NULL`.
3. Updated `SqliteEscrowAccountReadModel` to strictly filter `WHERE a.user_id IS NULL AND a.merchant_id IS NULL`.
4. Refactored the Accounts UI to use a grouped `<optgroup>` dropdown, allowing explicit account creation for both Users and Merchants.
```