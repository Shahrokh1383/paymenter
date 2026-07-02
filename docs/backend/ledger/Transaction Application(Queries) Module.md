# Transaction Application (Queries) Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

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

The **Transaction Application (Queries)** module provides optimized read‑side projections for transaction lists. It implements the CQRS query path, completely separated from the write‑side domain model, to serve UI views and API clients without N+1 query problems or business logic coupling.

### Core Responsibilities
- **Transaction List Retrieval**: Fetching transaction summaries with optional status filtering.
- **CQRS Read Model**: Using a dedicated query port and SQLite implementation that safely joins related tables using `LEFT JOIN` to ensure data resilience.
- **DTO Projection**: Returning flat, strictly-typed `TransactionListItem` objects suitable for direct rendering, completely eliminating primitive obsession (e.g., parsing ISO strings into `datetime` objects and TEXT into `Decimal`).

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Query handlers depend only on abstraction (`TransactionQueryPort`). |
| Rule 2: New Feature = New File | ✅ Query, handler, DTO, port, and read model are strictly isolated. |
| Rule 3: No Primitive Obsession | ✅ Enforced. Amounts are cast to `Decimal`, timestamps to `datetime`. |
| Rule 6: Infrastructure as Plugin | ✅ SQLite read model implements the port; can be replaced by Postgres/Redis without touching the handler. |

---

## Backend Architecture — Application Layer

### Query (Immutable Dataclass)
```python
@dataclass(frozen=True)
class GetTransactionsQuery:
    status_filter: Optional[str] = None
```
**Purpose**: Retrieve all transactions, optionally filtered by status (e.g., `'Pending'`, `'Success'`, `'Failed'`, `'Refunded'`).

### Handler

**GetTransactionsHandler**
- Dependencies: `TransactionQueryPort` (CQRS Read Model)
- Flow: Delegates directly to `query_port.get_all_summaries(status_filter)`.
- Contains zero business logic and does not require a Unit of Work, as it is a pure read operation.

### DTO

**TransactionListItem**
| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | `int` | `transactions.id` | Primary Key |
| `amount` | `Decimal` | `transactions.amount` | Strictly cast from DB `TEXT` to prevent IEEE 754 float precision loss. |
| `currency_code` | `str` | `currencies.code` | Resolved via `LEFT JOIN`. |
| `status` | `str` | `transactions.status` | State machine value. |
| `created_at` | `datetime` | `transactions.created_at` | Parsed from ISO string via `datetime.fromisoformat()`. |
| `user_email` | `Optional[str]` | `transactions.user_email` | Nullable audit field. |
| `from_account_number` | `str` | `from_acc.account_number` | Resolved via `LEFT JOIN` (supports User & Escrow accounts). |
| `to_account_number` | `str` | `to_acc.account_number` | Resolved via `LEFT JOIN` (supports User & Escrow accounts). |

---

## Backend Architecture — Infrastructure Layer (Read Side)

### CQRS Read Model Port
```python
class TransactionQueryPort(ABC):
    @abstractmethod
    def get_all_summaries(self, status: Optional[str] = None) -> List[TransactionListItem]:
        pass
```

### SQLite Read Model Implementation

**SqliteTransactionReadModel** (`src/ledger/infrastructure/persistence/sqlite_transaction_read_model.py`)
- Implements `TransactionQueryPort`.
- Performs a highly optimized 4‑way `LEFT JOIN` across `transactions`, `accounts` (aliased twice for source and destination), and `currencies`.
- **Architectural Benefit**: Using `LEFT JOIN` ensures that the read model remains resilient and continues to return transaction history even if an associated account record is ever soft-deleted or archived in the future.
- Dynamically appends the `WHERE` clause only if a `status` filter is provided, preventing unnecessary database index scans.
- Orders results by `created_at DESC` to show the most recent transactions first.

**Query Pattern:**
```sql
SELECT t.id, t.amount, t.status, t.created_at, t.user_email,
       from_acc.account_number as from_account,
       to_acc.account_number as to_account,
       c.code as currency_code
FROM transactions t
LEFT JOIN accounts from_acc ON t.from_account_id = from_acc.id
LEFT JOIN accounts to_acc ON t.to_account_id = to_acc.id
LEFT JOIN currencies c ON t.currency_id = c.id
-- Dynamic clause appended in Python if status is provided:
-- WHERE t.status = ?
ORDER BY t.created_at DESC
```

---

## Flows

### Query Transactions
```text
[Browser/SPA] → GET /transactions/?status=Pending
  → TransactionController
    → Instantiates SqliteUnitOfWork
    → Resolves GetTransactionsHandler via DIContainer
  → GetTransactionsQuery(status_filter='Pending')
    → GetTransactionsHandler.handle(query)
      → SqliteTransactionReadModel.get_all_summaries('Pending')
        → Executes LEFT JOIN query
        → Maps rows to List[TransactionListItem] (casting Decimal/datetime)
  → Renders transactions.html with the DTO list
```

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-9: Incomplete DI Container Integration*
**Previous Violation**: Constitution Rule 6 & SRP. `GetTransactionsHandler` was manually instantiated inside the `transaction_controller.py`, tightly coupling the delivery layer to infrastructure implementations.
**Resolution**: 
1. Registered the handler factory in `src/app/di/ledger_di.py` as `get_transactions_handler(uow)`, injecting the `SqliteTransactionReadModel`.
2. Refactored `transaction_controller.py` to strictly resolve the handler via `current_app.di_container.get_transactions_handler(uow)`.
**Status**: ✅ Resolved

***