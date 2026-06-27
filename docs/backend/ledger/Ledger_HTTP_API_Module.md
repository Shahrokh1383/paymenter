# Ledger HTTP API Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Infrastructure Layer (Web)](#backend-architecture--infrastructure-layer-web)
   - [Flask Controller](#flask-controller)
   - [DI Factory (Temporary)](#di-factory-temporary)
3. [API Contract](#api-contract)
   - [Hold Funds (Create Transaction)](#hold-funds-create-transaction)
   - [Complete Funds](#complete-funds)
   - [Fail & Refund](#fail--refund)
   - [List Transactions](#list-transactions)
4. [Flows](#flows)
   - [Hold Funds](#1-hold-funds)
   - [Complete Funds](#2-complete-funds)
   - [Fail & Refund](#3-fail--refund)
   - [Query Transactions](#4-query-transactions)
5. [Edge Cases & Known Issues](#edge-cases--known-issues)
6. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Ledger HTTP API** module exposes the transaction lifecycle and query operations via a Flask web controller. It handles incoming HTTP requests for creating, completing, failing/refunding, and listing transactions. Responses are either HTML (for list view) or JSON (for action endpoints). This module currently uses temporary manual dependency injection.

### Core Responsibilities
- **Routing**: Mapping URLs to application handlers.
- **Request Parsing**: Extracting form/JSON data and creating commands/queries.
- **Response Rendering**: Returning HTML templates or JSON responses.
- **Error Handling**: Catching domain exceptions and returning appropriate HTTP status codes and messages.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 6: Infrastructure as Plugin | ✅ Flask is an infrastructure detail. |
| Rule 5: Cross-Context via Events | N/A for web layer. |
| DI Container Integration | ⚠️ Incomplete (see TD-9). |

---

## Backend Architecture — Infrastructure Layer (Web)

### Flask Controller
**File**: `src/ledger/infrastructure/web/transaction_controller.py`

**Blueprint**: `transactions` (url_prefix `/transactions`)

| Route | Method | Handler | Response |
|---|---|---|---|
| `/` | GET | `GetTransactionsHandler` | Render `transactions.html` with `transactions` list and `current_filter` |
| `/create` | POST | `HoldFundsHandler` | Flash message + Redirect to `/transactions/` |
| `/complete/<int:id>` | POST | `CompleteFundsHandler` | JSON `{success, new_status}` |
| `/fail/<int:id>` | POST | `FailAndRefundHandler` | JSON `{success, new_status}` |

### DI Factory (Temporary)
Inside `transaction_controller.py`, dependencies are manually constructed using local factory functions:
```python
def _get_uow(): return SqliteUnitOfWork()
def _get_account_repo(uow): return SqliteAccountRepository(uow)
def _get_txn_repo(uow): return SqliteTransactionRepository(uow)
```
⚠️ This is manual wiring. The DI Container (`app/di_container.py`) exists but is only used for `EventBus` access (`current_app.di_container.event_bus`). Full DI container integration for handlers is incomplete (see TD-9).

---

## API Contract

### Hold Funds (Create Transaction)
```
POST /transactions/create
Content-Type: application/x-www-form-urlencoded

from_account_id=1&to_account_id=2&amount=100.00&merchant_id=5&user_email=user@example.com
```
**Success**: Flash message "Funds held successfully." + Redirect to `/transactions/`

**Errors** (Flash message):
- `InsufficientFundsError`: Source account lacks funds.
- `AccountNotFoundError`: One or both accounts do not exist.
- `CurrencyMismatchError`: Accounts have different currencies.
- `InvalidOperation`: Malformed Decimal amount.

### Complete Funds
```
POST /transactions/complete/<id>
```
**Success Response**:
```json
{ "success": true, "new_status": "Success" }
```
**Error Response** (400):
```json
{ "success": false, "message": "Transaction cannot be completed. Current status: Failed" }
```
**Error Response** (500): Generic catch-all.

### Fail & Refund
```
POST /transactions/fail/<id>
```
**Success Response**:
```json
{ "success": true, "new_status": "Refunded/Failed" }
```
**Error Response** (400): `InvalidTransactionStateError`
**Error Response** (500): Generic catch-all, including `InsufficientFundsError` from insolvent destination account during refund.

### List Transactions
```
GET /transactions/?status=Pending
```
**Response**: Rendered HTML (`transactions.html`) with `transactions` list and `current_filter`.

---

## Flows

### 1. Hold Funds
```
[User/Checkout] → POST /transactions/create
  → Parse form data → HoldFundsCommand(...)
  → HoldFundsHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: Flash message + Redirect to /transactions/
  → On error: Flash error message + Redirect to /transactions/
```

### 2. Complete Funds
```
[User/Merchant] → POST /transactions/complete/<id>
  → CompleteFundsCommand(transaction_id=id)
  → CompleteFundsHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: JSON {success: true, new_status: "Success"}
  → On error: JSON {success: false, message: "..."}, HTTP 400 or 500
```

### 3. Fail & Refund
```
[User/Merchant] → POST /transactions/fail/<id>
  → FailAndRefundCommand(transaction_id=id)
  → FailAndRefundHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: JSON {success: true, new_status: "Refunded" or "Failed"}
  → On error: JSON {success: false, message: "..."}, HTTP 400 or 500
```

### 4. Query Transactions
```
GET /transactions/?status=Pending
  → GetTransactionsQuery(status_filter='Pending')
  → GetTransactionsHandler
    → (See Transaction Application (Queries) module for read model flow)
  → Render transactions.html with transactions list and current_filter
```

---

## Edge Cases & Known Issues

### EC-4: Transaction ID Zero in Events
**Scenario**: A newly created transaction (via Hold Funds) does not have its `id` updated from `lastrowid`. If any event were emitted downstream after completion, it would carry `transaction_id=0`.
**Impact**: Correlation issues in notification systems.
**Status**: Bug. Root cause in repository (see TD-3 in Infrastructure module). The API itself only handles the redirect/flash; the ID problem affects downstream event consumers.

*(Note: Other edge cases like EC-2, EC-3 are handled at domain/application layers, but the controller catches them as 500 errors.)*

---

## Notes & Technical Debt

### TD-9: Incomplete DI Container Integration
**Location**: `src/ledger/infrastructure/web/transaction_controller.py`
**Current**: Controller manually instantiates `SqliteUnitOfWork`, `SqliteAccountRepository`, and `SqliteTransactionRepository` using local factory functions. The global `DIContainer` is only accessed for `EventBus`.
**Required Fix**: Controller should request handlers from the `DIContainer` (e.g., `current_app.di_container.hold_funds_handler`). This ensures all dependencies (including EventBus) are injected consistently and testable. The local factory functions (`_get_uow`, etc.) should be removed after handlers are registered in the container.