# Ledger Infrastructure & Persistence Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Infrastructure Layer](#backend-architecture--infrastructure-layer)
   - [SQLite Repositories](#sqlite-repositories)
   - [Unit of Work](#unit-of-work)
3. [Database Schema Reference](#database-schema-reference)
   - [currencies](#currencies)
   - [users](#users)
   - [merchants](#merchants)
   - [accounts](#accounts)
   - [transactions](#transactions)
   - [gateway_sessions](#gateway_sessions)
4. [Edge Cases & Known Issues](#edge-cases--known-issues)
5. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Ledger Infrastructure & Persistence** module implements the repository ports defined in the Domain layer and provides the transactional Unit of Work. It handles all SQLite database access, entity mapping, and the underlying schema that supports the Ledger bounded context.

### Core Responsibilities
- **Account Persistence**: Mapping `Account` entities to/from the `accounts` table, including currency resolution via JOIN with `currencies`.
- **Transaction Persistence**: Mapping `Transaction` entities to/from the `transactions` table, including currency resolution.
- **Transactional Boundary**: `SqliteUnitOfWork` ensures atomic commits and rollbacks.
- **Schema Definition**: Full DDL for all tables used by the Ledger context.
- **Concurrency Control**: Enforcing optimistic locking to ensure data integrity under concurrent loads.
- **Concurrency & Locking**: Enables `PRAGMA journal_mode=WAL;` on connection initialization. This transitions SQLite from rollback journal mode to Write-Ahead Logging, allowing concurrent readers and writers. This is critical to prevent "database is locked" errors when the background Outbox Relay Worker processes events simultaneously with foreground HTTP requests.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Infrastructure implements Domain ports. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Currency is handled via domain `Money` value object and string codes, not DB IDs. |
| Rule 4: Aggregates Protect Invariants | ✅ Enforced. Currency changes routed strictly through `Account.change_currency()`. |
| Rule 6: Infrastructure as Plugin | ✅ Enforced. SQLite/Flask are infrastructure details. |

---

## Backend Architecture — Infrastructure Layer

### SQLite Repositories

**SqliteAccountRepository**
- Implements `AccountRepository` from Domain layer.
- Maps database rows to `Account` entities using `_map_row_to_account()`.
- **`get_by_id(account_id: int) -> Account`**:
  - JOINs with `currencies` table to resolve `currency_code`.
  - Returns fully hydrated `Account` entity (including `version` for optimistic locking).
- **`update(account: Account) -> None`**:
  - Updates `balance` and `currency_id` columns.
  - Converts `Money.amount` to `str` for precision.
  - **Implements Optimistic Locking**: `UPDATE ... SET version = version + 1 WHERE id = ? AND version = ?`.
  - Raises `ConcurrencyException` if `cursor.rowcount == 0` and synchronizes in-memory `account.version`.
- **`add(account: Account) -> int`**:
  - Looks up `currency_id` from `currencies` table by `Money.currency`.
  - Inserts full row.
  - Returns `cursor.lastrowid`.

**SqliteTransactionRepository**
- Implements `TransactionRepository` from Domain layer.
- Maps database rows to `Transaction` entities using `_map_row_to_txn()`.
- **`get_by_id(transaction_id: int) -> Transaction`**:
  - JOINs with `currencies` to resolve `currency_code`.
  - Returns fully hydrated `Transaction` entity (including `version`).
- **`add(transaction: Transaction) -> int`**:
  - Looks up `currency_id` dynamically from `currencies` table.
  - Inserts transaction row.
  - **Assigns Identity**: `transaction.id = cursor.lastrowid` to maintain aggregate integrity.
  - Returns `transaction.id`.
- **`update(transaction: Transaction) -> None`**:
  - Updates `status` column.
  - **Implements Optimistic Locking**: `UPDATE ... SET version = version + 1 WHERE id = ? AND version = ?`.
  - Raises `ConcurrencyException` if `cursor.rowcount == 0` and synchronizes in-memory `transaction.version`.

### Unit of Work

**SqliteUnitOfWork**
- Manages SQLite connection lifecycle with `__enter__` / `__exit__` (context manager).
- Supports nested context managers via `_nesting_level` counter.
- Enables `PRAGMA foreign_keys = ON` on connection init.
- Auto-commits on clean exit of outermost context.
- Auto-rollback on exception (Seamlessly catches `ConcurrencyException` raised by repositories, triggering rollback to prevent partial state updates).

---

## Database Schema Reference

### currencies
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `code` | TEXT | NOT NULL, UNIQUE |
| `is_active` | BOOLEAN | DEFAULT 1 |

### users
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `phone_email` | TEXT | NOT NULL, UNIQUE |

### merchants
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `api_key` | TEXT | NOT NULL, UNIQUE |
| `is_active` | BOOLEAN | DEFAULT 1 |
| `settlement_account_id` | INTEGER | FOREIGN KEY → `accounts(id)` |

### accounts
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `user_id` | INTEGER | NOT NULL, FOREIGN KEY → `users(id)` |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `account_number` | TEXT | NOT NULL, UNIQUE |
| `balance` | TEXT | NOT NULL, DEFAULT '0.00' |
| `version` | INTEGER | NOT NULL, DEFAULT 0 |

### transactions
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `merchant_id` | INTEGER | FOREIGN KEY → `merchants(id)` |
| `from_account_id` | INTEGER | NOT NULL, FOREIGN KEY → `accounts(id)` |
| `to_account_id` | INTEGER | NOT NULL, FOREIGN KEY → `accounts(id)` |
| `amount` | TEXT | NOT NULL |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `status` | TEXT | NOT NULL |
| `user_email` | TEXT | |
| `version` | INTEGER | NOT NULL, DEFAULT 0 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### gateway_sessions
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `token` | TEXT | NOT NULL, UNIQUE |
| `merchant_id` | INTEGER | NOT NULL, FOREIGN KEY → `merchants(id)` |
| `amount` | TEXT | NOT NULL |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `user_email` | TEXT | NOT NULL |
| `callback_url` | TEXT | NOT NULL |
| `otp_code` | TEXT | Nullable. Generated only upon explicit user request. |
| `otp_locked_card` | TEXT | Nullable. The specific card number the OTP is cryptographically bound to. |
| `otp_expires_at` | TIMESTAMP | Nullable. Expiration time for the OTP (e.g., 3 minutes). |
| `status` | TEXT | DEFAULT 'Initiated' |
| `transaction_id` | INTEGER | FOREIGN KEY → `transactions(id)` |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

## Edge Cases & Known Issues

*(No critical edge cases currently active. Concurrency controls are in place.)*

### EC-1: Concurrent Balance Modification (Lost Updates) - MITIGATED
**Previous Scenario**: Two simultaneous `HoldFunds` operations on the same account resulting in blind overwrites.
**Current Behavior**: Fully mitigated via Optimistic Locking (`version` column). If a race condition occurs, the second transaction to commit will fail the `WHERE version = ?` check, `cursor.rowcount` will be 0, a `ConcurrencyException` will be raised, and the `SqliteUnitOfWork` will automatically rollback the transaction.
**Status**: ✅ Resolved

---

## Notes & Technical Debt

### TD-2: Infrastructure Leakage into the Ledger Context - RESOLVED
**Previous Violation**: DDD Bounded Context Boundaries
**Previous Issue**: `SqliteAccountRepository.get_by_card_number()` resolved an account using a raw card number string, coupling the Ledger to Checkout/Identity concepts.
**Resolution**: Method removed. Card-to-account mapping is now handled outside the Ledger bounded context before invoking use cases.
**Status**: ✅ Resolved

### TD-3: Transaction ID Assignment Bug - RESOLVED
**Previous Violation**: DDD Aggregate Identity Integrity
**Previous Issue**: `cursor.lastrowid` was returned but never assigned back to the `Transaction` entity.
**Resolution**: Modified `SqliteTransactionRepository.add()`:
```python
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    transaction.id = cursor.lastrowid  # Identity correctly assigned
    return transaction.id
```
**Status**: ✅ Resolved

### TD-4: Missing Optimistic Locking - RESOLVED
**Previous Violation**: Constitution Performance & Scalability — "Aggregates use optimistic locking or SELECT FOR UPDATE"
**Previous Issue**: Repositories performed blind overwrites.
**Resolution**: 
1. Added `version INTEGER DEFAULT 0` to `accounts` and `transactions` tables.
2. Added `version: int` to `Account` and `Transaction` entities.
3. Modified `UPDATE` queries in both repositories:
   ```sql
   UPDATE accounts SET balance = ?, currency_id = ?, version = version + 1 WHERE id = ? AND version = ?
   ```
4. Implemented `ConcurrencyException` handling. UoW catches exception and triggers rollback.
**Status**: ✅ Resolved

### TD-5: Bypassing Aggregate Invariants / Primitive Obsession - RESOLVED
**Previous Violation**: Constitution Rule 3 & Rule 4
**Previous Issue**: `UpdateAccountCurrencyCommand` accepted `currency_id: int`, leaking infrastructure details into the Application layer. The handler used a Query Port to translate this back to a code, bypassing the aggregate.
**Resolution**: 
1. `UpdateAccountCurrencyCommand` now strictly accepts `currency_code: str`.
2. Handler simplified to pass the string directly to `Account.change_currency(currency_code)`.
3. Frontend (`accounts.html`) and Controller (`dashboard_controller.py`) updated to submit and route the 3-letter currency code directly.
**Status**: ✅ Resolved

### TD-10: Database Schema — Floating-Point Imprecision - RESOLVED
**Previous Violation**: Financial Data Integrity
**Previous Issue**: `accounts.balance` and `transactions.amount` were defined as `REAL` (IEEE 754 floating-point).
**Resolution**: Schema migrated to `TEXT NOT NULL DEFAULT '0.00'`. Money is stored as the exact string representation of `Decimal`. All repository read/write mappings utilize `str()` and `Decimal()` to guarantee precision.
**Status**: ✅ Resolved
### TD-11: Identity Leakage in Ledger Domain Events - RESOLVED
**Previous Violation**: Constitution Rule 1 (Dependency Inward) & Rule 5 (Cross-Context Boundaries).
**Previous Issue**: Ledger domain events (`TransactionCompletedEvent`, etc.) carried a `user_email` string. This leaked an Identity concept into the Ledger bounded context and caused receipts to be routed to the Laravel shopper rather than the actual Paymenter account owner.
**Resolution**: 
1. Removed `user_email` from all Ledger transaction events.
2. Replaced it with `payer_account_id: int` (derived from `transaction.from_account_id`).
3. Introduced an Anti-Corruption Layer (ACL) port (`AccountOwnerResolverPort`) in the Notifications context to dynamically resolve the registered Paymenter user email via the `account_id` at the moment of dispatch.
**Status**: ✅ Resolved

### TD-12: SQLite Write-Lock Contention & Double Dispatch - RESOLVED
**Previous Violation**: Infrastructure Reliability & Outbox Pattern Integrity.
**Previous Issue**: The Outbox Relay Worker held database connections open while executing slow SMTP handlers, causing strict exclusive write locks to collide with foreground HTTP requests. This resulted in "database is locked" errors, causing the worker to falsely assume dispatch failure and send duplicate emails on retry.
**Resolution**: 
1. Enabled `PRAGMA journal_mode=WAL;` globally across `SqliteUnitOfWork`, `OutboxEventBusDecorator`, and `OutboxRelayWorker`.
2. Refactored `OutboxRelayWorker` to strictly decouple the Fetch, Process, and Update phases. Messages are fetched and the read-lock is released *before* handlers execute, and a new transaction is opened *after* execution to update statuses.
**Status**: ✅ Resolved