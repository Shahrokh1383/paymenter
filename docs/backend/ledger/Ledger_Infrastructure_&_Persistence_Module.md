# Ledger Infrastructure & Persistence Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Infrastructure Layer](#backend-architecture--infrastructure-layer)
   - [Database Orchestrator (Rule 7 Compliance)](#database-orchestrator-rule-7-compliance)
   - [SQLite Repositories](#sqlite-repositories)
   - [Unit of Work](#unit-of-work)
   - [Event Bus & Outbox Pattern](#event-bus--outbox-pattern)
3. [Database Schema Reference](#database-schema-reference)
   - [users](#users)
   - [merchants](#merchants)
   - [user_cards](#user_cards)
   - [currencies](#currencies)
   - [accounts](#accounts)
   - [transactions](#transactions)
   - [gateway_sessions](#gateway_sessions)
   - [outbox_messages](#outbox_messages)
4. [Edge Cases & Known Issues](#edge-cases--known-issues)
5. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Ledger Infrastructure & Persistence** module implements the repository ports defined in the Domain layer, provides the transactional Unit of Work, and orchestrates the database schema. It handles all SQLite database access, entity mapping, and the underlying schema that supports the Ledger, Identity, and Checkout bounded contexts.

### Core Responsibilities
- **Schema Orchestration**: Aggregating isolated bounded-context schemas and executing them atomically (Strict adherence to Constitution Rule 7).
- **Entity Persistence & Hydration**: Mapping database rows to Domain Aggregates (`Account`, `Transaction`) while strictly extracting primitives from Value Objects (like `CurrencyCode`) at the SQL boundary.
- **Transactional Boundary**: `SqliteUnitOfWork` ensures atomic commits, rollbacks, and nested transaction support.
- **Outbox Pattern Implementation**: Intercepting domain events and persisting them atomically to prevent phantom events and HTTP blocking.
- **Concurrency Control**: Enforcing optimistic locking and Write-Ahead Logging (WAL) to ensure data integrity under concurrent loads.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Infrastructure implements Domain ports. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Repositories extract `.value` from `CurrencyCode` VOs strictly at the SQL execution boundary. |
| Rule 6: Infrastructure as Plugin | ✅ Enforced. SQLite/Flask are infrastructure details hidden behind ports. |
| Rule 7: Schema Isolation | ✅ Enforced. `database.py` acts purely as an orchestrator; raw SQL is isolated in context-specific subfolders. |

---

## Backend Architecture — Infrastructure Layer

### Database Orchestrator (Rule 7 Compliance)
**File**: `src/common/infrastructure/database.py`

To prevent monolithic schema files and merge conflicts, the database initialization strictly follows **Constitution Rule 7**. 
- **Aggregation**: The `Database.initialize()` method imports isolated schema constants (`IDENTITY_SCHEMA`, `LEDGER_SCHEMA`, `CHECKOUT_SCHEMA`, `EVENTING_SCHEMA`) from their respective bounded context subfolders.
- **Atomic Execution**: It concatenates these strings and executes them via `cursor.executescript()`.
- **System Seeding**: It securely seeds a "System" user (`id=0`) to maintain foreign key integrity for system-level operations without violating domain boundaries.

### SQLite Repositories

**SqliteAccountRepository** & **SqliteTransactionRepository**
- **Hydration**: Maps database rows to Domain entities. Crucially, it wraps raw string currency codes into the strict `CurrencyCode` Value Object during instantiation (e.g., `Money(amount, CurrencyCode(row['currency_code']))`).
- **Persistence**: When saving, it extracts the primitive string at the exact boundary of the SQL query (e.g., `account.balance.currency.value`) to satisfy the SQLite C-driver.
- **Optimistic Locking**: Both repositories enforce concurrency control via the `version` column. 
  ```sql
  UPDATE accounts SET balance = ?, currency_id = ?, version = version + 1 WHERE id = ? AND version = ?
  ```
  If `cursor.rowcount == 0`, a `ConcurrencyException` is raised, triggering an automatic rollback by the Unit of Work.
- **Identity Assignment**: `SqliteTransactionRepository.add()` explicitly assigns `transaction.id = cursor.lastrowid` to synchronize the in-memory aggregate identity with the database before the UoW commits.

### Unit of Work

**SqliteUnitOfWork**
- Manages SQLite connection lifecycle via context managers (`__enter__` / `__exit__`).
- Supports nested context managers via a `_nesting_level` counter.
- Enables `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode=WAL;` on connection initialization. WAL mode is critical to prevent "database is locked" errors when the background Outbox Relay Worker processes events simultaneously with foreground HTTP requests.
- Auto-commits on clean exit; auto-rollbacks on any exception (seamlessly catching `ConcurrencyException`).

### Event Bus & Outbox Pattern

**OutboxEventBusDecorator**
- Implements the **Approximate ACID Outbox Pattern** to solve the dual-write problem and prevent HTTP blocking.
- **Interception**: Wraps the inner `EventBus`. When `publish(event)` is called, it serializes the event into JSON.
- **Custom Serialization**: Uses a custom `_DomainEventEncoder` to safely convert Domain Value Objects (like `Decimal` amounts) into strings before JSON serialization.
- **Atomic Persistence**: Opens a short-lived SQLite connection, inserts the payload into the `outbox_messages` table, and commits.
- **Asynchronous Dispatch**: Triggers the `OutboxRelayWorker` background thread to process the message, ensuring the HTTP response is returned to the client immediately without waiting for slow I/O (like SMTP).

---

## Database Schema Reference

### users
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `phone_email` | TEXT | NOT NULL, UNIQUE |
*Note: ID `0` is reserved and seeded for the 'System' user to support internal ledger operations.*

### merchants
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `api_key` | TEXT | NOT NULL, UNIQUE |
| `is_active` | BOOLEAN | DEFAULT 1 |
| `settlement_account_id` | INTEGER | FOREIGN KEY → `accounts(id)` |

### user_cards
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `user_id` | INTEGER | NOT NULL, FOREIGN KEY → `users(id)` |
| `account_id` | INTEGER | NOT NULL, FOREIGN KEY → `accounts(id)` |
| `card_number` | TEXT | NOT NULL, UNIQUE |

### currencies
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `code` | TEXT | NOT NULL, UNIQUE |
| `is_active` | BOOLEAN | DEFAULT 1 |

### accounts
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `user_id` | INTEGER | **Nullable**, FOREIGN KEY → `users(id)` *(Nullable to support System Escrow accounts)* |
| `currency_id` | INTEGER | NOT NULL, FOREIGN KEY → `currencies(id)` |
| `account_number` | TEXT | NOT NULL, UNIQUE |
| `balance` | TEXT | NOT NULL, DEFAULT '0.00' *(Stored as string to preserve Decimal precision)* |
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
| `user_email` | TEXT | Nullable |
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
| `otp_code` | TEXT | Nullable |
| `otp_locked_card` | TEXT | Nullable |
| `otp_expires_at` | TIMESTAMP | Nullable |
| `status` | TEXT | DEFAULT 'Initiated' |
| `transaction_id` | INTEGER | FOREIGN KEY → `transactions(id)` |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

### outbox_messages
| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `event_type` | TEXT | NOT NULL *(e.g., 'TransactionCompletedEvent')* |
| `payload` | TEXT | NOT NULL *(JSON serialized domain event)* |
| `status` | TEXT | DEFAULT 'Pending' |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

## Edge Cases & Known Issues

### EC-1: Concurrent Balance Modification (Lost Updates) - MITIGATED
**Previous Scenario**: Two simultaneous `HoldFunds` operations on the same account resulting in blind overwrites.
**Current Behavior**: Fully mitigated via Optimistic Locking (`version` column). If a race condition occurs, the second transaction to commit will fail the `WHERE version = ?` check, `cursor.rowcount` will be 0, a `ConcurrencyException` will be raised, and the `SqliteUnitOfWork` will automatically rollback the transaction.
**Status**: ✅ Resolved

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-2: Infrastructure Leakage into the Ledger Context*
**Resolution**: `get_by_card_number()` removed. Card-to-account mapping is handled outside the Ledger bounded context via Anti-Corruption Layers.

*(Resolved) TD-3: Transaction ID Assignment Bug*
**Resolution**: `SqliteTransactionRepository.add()` now explicitly assigns `transaction.id = cursor.lastrowid` before returning, ensuring Domain Events capture the correct ID.

*(Resolved) TD-4: Missing Optimistic Locking*
**Resolution**: Added `version` columns to `accounts` and `transactions`. Repositories enforce `WHERE version = ?` checks and raise `ConcurrencyException` on conflicts.

*(Resolved) TD-10: Database Schema — Floating-Point Imprecision*
**Resolution**: Schema migrated to `TEXT NOT NULL DEFAULT '0.00'` for all financial columns. Repositories utilize `str()` and `Decimal()` to guarantee IEEE 754 precision safety.

*(Resolved) TD-12: SQLite Write-Lock Contention & Double Dispatch*
**Resolution**: Enabled `PRAGMA journal_mode=WAL;` globally. Refactored `OutboxRelayWorker` to strictly decouple Fetch, Process, and Update phases, releasing read-locks before executing slow I/O handlers.

*(Resolved) TD-14: Synchronous HTTP Blocking via Email Dispatch*
**Resolution**: Implemented the Approximate ACID Outbox Pattern via `OutboxEventBusDecorator`. HTTP requests now only perform a fast local SQLite insert into `outbox_messages`. A background daemon thread guarantees eventual delivery.

***