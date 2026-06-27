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

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Infrastructure implements Domain ports. |
| Rule 6: Infrastructure as Plugin | ✅ Enforced. SQLite/Flask are infrastructure details. |
| Rule 4: Aggregates Protect Invariants | ⚠️ Violated via `update_currency()` (see TD-5). |

---

## Backend Architecture — Infrastructure Layer

### SQLite Repositories

**SqliteAccountRepository**
- Implements `AccountRepository` from Domain layer.
- Maps database rows to `Account` entities using `_map_row_to_account()`.
- **`get_by_id(account_id: int) -> Account`**:
  - JOINs with `currencies` table to resolve `currency_code`.
  - Returns fully hydrated `Account` entity.
- **`get_by_card_number(card_number: CardNumber) -> Account`**:
  - Lookup by raw card number string.
  - ⚠️ Should be removed when TD-2 (CardNumber in Ledger) is addressed.
- **`update(account: Account) -> None`**:
  - Updates only `balance` column.
  - Converts `Money.amount` to `str` for precision.
  - ⚠️ No version check for optimistic locking (see TD-4).
  - Query: `UPDATE accounts SET balance = ? WHERE id = ?`
- **`add(account: Account) -> int`**:
  - Looks up `currency_id` from `currencies` table by `Money.currency`.
  - Inserts full row.
  - Returns `cursor.lastrowid`.
- **`update_currency(account_id: int, currency_id: int) -> None`**:
  - Raw SQL update on `currency_id` column.
  - ⚠️ Does not touch entity state (see TD-5).
  - Must be eliminated when `Account.change_currency()` is implemented.

**SqliteTransactionRepository**
- Implements `TransactionRepository` from Domain layer.
- Maps database rows to `Transaction` entities using `_map_row_to_txn()`.
- **`get_by_id(transaction_id: int) -> Transaction`**:
  - JOINs with `currencies` to resolve `currency_code`.
  - Returns fully hydrated `Transaction` entity.
- **`add(transaction: Transaction) -> int`**:
  - Looks up `currency_id` dynamically from `currencies` table.
  - Inserts transaction row.
  - Returns `cursor.lastrowid`.
  - ⚠️ **Critical Bug**: `lastrowid` is never assigned to `transaction.id`. The aggregate remains with `id=0` (see TD-3).
- **`update(transaction: Transaction) -> None`**:
  - Updates only `status` column.
  - ⚠️ No version check for optimistic locking (see TD-4).
  - Query: `UPDATE transactions SET status = ? WHERE id = ?`

### Unit of Work

**SqliteUnitOfWork**
- Manages SQLite connection lifecycle with `__enter__` / `__exit__` (context manager).
- Supports nested context managers via `_nesting_level` counter.
- Enables `PRAGMA foreign_keys = ON` on connection init.
- Auto-commits on clean exit of outermost context.
- Auto-rollback on exception.
- ⚠️ **No Optimistic Locking**: `commit()` does not verify `version` columns (see TD-4).

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
| `card_number` | TEXT | NOT NULL, UNIQUE |
| `balance` | REAL | NOT NULL, DEFAULT 0.0 |

### transactions
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `merchant_id` | INTEGER | FOREIGN KEY → `merchants(id)` |
| `from_account_id` | INTEGER | NOT NULL, FOREIGN KEY → `accounts(id)` |
| `to_account_id` | INTEGER | NOT NULL, FOREIGN KEY → `accounts(id)` |
| `amount` | REAL | NOT NULL |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `status` | TEXT | NOT NULL |
| `user_email` | TEXT | |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### gateway_sessions
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `token` | TEXT | NOT NULL, UNIQUE |
| `merchant_id` | INTEGER | NOT NULL, FOREIGN KEY → `merchants(id)` |
| `amount` | REAL | NOT NULL |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `user_email` | TEXT | NOT NULL |
| `callback_url` | TEXT | NOT NULL |
| `otp_code` | TEXT | NOT NULL |
| `status` | TEXT | DEFAULT 'Initiated' |
| `transaction_id` | INTEGER | FOREIGN KEY → `transactions(id)` |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

## Edge Cases & Known Issues

### EC-1: Concurrent Balance Modification (Lost Updates)
**Scenario**: Two simultaneous `HoldFunds` operations on the same account.
**Current Behavior**: SQLite writes are serialized at the database level, but there is no application-level optimistic locking. If two requests read the same balance simultaneously, the second write overwrites the first without awareness.
**Impact**: **CRITICAL**. Double-spending or balance drift.
**Status**: Unhandled. See TD-4.

---

## Notes & Technical Debt

### TD-3: Transaction ID Assignment Bug
**Violation**: DDD Aggregate Identity Integrity
**Location**: `src/ledger/infrastructure/persistence/sqlite_transaction_repository.py` → `add()`
**Current**:
```python
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    return cursor.lastrowid  # Never assigned back
```
**Required Fix**:
```python
def add(self, transaction: Transaction) -> int:
    cursor = ... # INSERT
    transaction.id = cursor.lastrowid  # Assign identity to aggregate
    return transaction.id
```
Without this fix, `TransactionCompletedEvent` and similar events carry `transaction_id=0` for newly created transactions.

### TD-4: Missing Optimistic Locking
**Violation**: Constitution Performance & Scalability — "Aggregates use optimistic locking or SELECT FOR UPDATE"
**Location**: All SQLite repositories (`SqliteAccountRepository.update()`, `SqliteTransactionRepository.update()`).
**Current**: `UPDATE accounts SET balance = ? WHERE id = ?` has no version check.
**Required Fix**:
1. Add `version INTEGER DEFAULT 0` to `accounts` and `transactions` tables.
2. Add `version: int` to `Account` and `Transaction` entities.
3. Modify `UPDATE` queries:
   ```sql
   UPDATE accounts SET balance = ?, version = version + 1 WHERE id = ? AND version = ?
   ```
4. Check `cursor.rowcount`. If `0`, raise `ConcurrencyException`.

### TD-10: Database Schema — `balance REAL`
**Location**: `src/common/infrastructure/database.py` (accounts table definition).
**Current**: `accounts.balance REAL NOT NULL DEFAULT 0.0`
**Issue**: `REAL` in SQLite is IEEE 754 floating point. Although repositories convert to `str` before INSERT, the column type itself is imprecise. If any raw SQL or external tool writes to this column, precision is lost.
**Required Fix**: Change schema to `balance TEXT NOT NULL DEFAULT '0.00'`. Store `Money` as string representation of `Decimal`. This affects all repository `update()` and `add()` methods that write to the `balance` column, as well as the `amount` column in `transactions` table.