# Transaction Application (Queries) Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Application Layer](#backend-architecture--application-layer)
   - [Query](#query)
   - [Handler](#handler)
   - [DTO](#dto)
3. [Backend Architecture — Infrastructure Layer (Read Side)](#backend-architecture--infrastructure-layer-read-side)
   - [CQRS Read Model Port](#cqrs-read-model-port)
   - [SQLite Read Model Implementation](#sqlite-read-model-implementation)
4. [Flows](#flows)
   - [Query Transactions](#query-transactions)
5. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Transaction Application (Queries)** module provides optimized read‑side projections for transaction lists. It implements the CQRS query path, completely separated from the write‑side domain model, to serve UI views without N+1 query problems or business logic coupling.

### Core Responsibilities
- **Transaction List Retrieval**: Fetching transaction summaries with optional status filtering.
- **CQRS Read Model**: Using a dedicated query port and SQLite implementation that joins related tables.
- **DTO Projection**: Returning flat `TransactionListItem` objects suitable for direct rendering.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Query handlers depend only on abstraction (`TransactionQueryPort`). |
| Rule 2: New Feature = New File | ✅ Query, handler, DTO, and read model are isolated. |
| Rule 6: Infrastructure as Plugin | ✅ SQLite read model implements the port; can be replaced. |

---

## Backend Architecture — Application Layer

### Query (Immutable Dataclass)
```python
class GetTransactionsQuery:
    status_filter: Optional[str]
```
**Purpose**: Retrieve all transactions, optionally filtered by status (e.g., `'Pending'`, `'Success'`).

### Handler

**GetTransactionsHandler**
- Dependencies: `TransactionQueryPort` (CQRS Read Model)
- Flow: Delegates directly to `query_port.get_all_summaries(status_filter)`.
- No business logic, no Unit of Work.

### DTO

**TransactionListItem**
| Field | Type | Source |
|---|---|---|
| `id` | `int` | `transactions.id` |
| `amount` | `Decimal` | `transactions.amount` (converted from REAL) |
| `currency_code` | `str` | `currencies.code` (JOIN) |
| `status` | `str` | `transactions.status` |
| `created_at` | `datetime` | `transactions.created_at` |
| `user_email` | `str` | `transactions.user_email` |
| `from_account_number` | `str` | `from_acc.account_number` (JOIN) |
| `to_account_number` | `str` | `to_acc.account_number` (JOIN) |

---

## Backend Architecture — Infrastructure Layer (Read Side)

### CQRS Read Model Port
```python
class TransactionQueryPort(ABC):
    def get_all_summaries(self, status: Optional[str]) -> List[TransactionListItem]
```

### SQLite Read Model Implementation

**SqliteTransactionReadModel** (`src/ledger/infrastructure/persistence/...`)
- Implements `TransactionQueryPort`.
- Performs a 3‑way LEFT JOIN:
  - `transactions` → `accounts` (as `from_acc`) → `accounts` (as `to_acc`) → `currencies`
- Supports optional `status` filter via parameterized query.
- Orders results by `created_at DESC`.
- Returns `List[TransactionListItem]` with proper `Decimal` conversion for amounts.
- Query pattern:
  ```sql
  SELECT t.id, t.amount, c.code AS currency_code, t.status, t.created_at,
         t.user_email, fa.account_number AS from_account_number,
         ta.account_number AS to_account_number
  FROM transactions t
  JOIN currencies c ON t.currency_id = c.id
  JOIN accounts fa ON t.from_account_id = fa.id
  JOIN accounts ta ON t.to_account_id = ta.id
  WHERE (? IS NULL OR t.status = ?)
  ORDER BY t.created_at DESC
  ```

---

## Flows

### Query Transactions
```
GET /transactions/?status=Pending
  → GetTransactionsQuery(status_filter='Pending')
    → GetTransactionsHandler
      → SqliteTransactionReadModel.get_all_summaries('Pending')
        → JOIN query (transactions + accounts + currencies)
        → Returns List[TransactionListItem]
```

---

## Notes & Technical Debt

### TD-9 (Partial): Incomplete DI Container Integration
**Location**: Controller layer (see Ledger HTTP API module) but affects handler instantiation.
**Current**: `GetTransactionsHandler` is likely manually instantiated in the controller alongside other handlers. The global `DIContainer` is only accessed for `EventBus`.
**Required Fix**: Register `GetTransactionsHandler` and its `TransactionQueryPort` dependency in the `DIContainer`. The controller should request the handler from the container instead of manually wiring.