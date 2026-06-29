# Ledger HTTP API Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Infrastructure Layer (Web)](#backend-architecture--infrastructure-layer-web)
   - [SSR Controller (HTML/Forms)](#ssr-controller-htmlforms)
   - [REST API Controller (JSON)](#rest-api-controller-json)
   - [DI Container Integration](#di-container-integration)
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

The **Ledger HTTP API** module exposes the transaction lifecycle and query operations via Flask web controllers. To maintain architectural purity and adhere to the Single Responsibility Principle (SRP), this module is strictly divided into two distinct paradigms: Server-Side Rendering (SSR) for HTML views and a pure RESTful JSON API for programmatic clients. All endpoints strictly enforce input validation, secure error handling, and support idempotency for state-mutating actions.

### Core Responsibilities
- **Routing**: Mapping URLs to application handlers via separated Blueprints.
- **Request Parsing & Validation**: Extracting form/JSON data, validating schemas (Fail-Fast), and creating commands/queries.
- **Response Rendering**: Returning HTML templates (SSR) or JSON responses (REST).
- **Error Handling**: Catching domain exceptions and mapping them to precise HTTP status codes; securely logging system exceptions without leaking data.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 6: Infrastructure as Plugin | ✅ Flask, validation schemas, and idempotency decorators are infrastructure details. |
| Rule 5: Cross-Context via Events | N/A for web layer. |
| Rule 2: New Feature = New File | ✅ API controller, validation schema, and idempotency wrapper isolated in new files. |
| DI Container Integration | ✅ Handlers are fully resolved via `DIContainer`. Local factories removed. |
| Security & Compliance | ✅ No stack traces leaked to clients. Internal logging used for 500s. |

---

## Backend Architecture — Infrastructure Layer (Web)

### SSR Controller (HTML/Forms)
**File**: `src/ledger/infrastructure/web/transaction_controller.py`
**Blueprint**: `transactions` (url_prefix `/transactions`)

Used exclusively for the traditional web UI. Implements the PRG (Post-Redirect-Get) pattern.

| Route | Method | Handler | Response |
|---|---|---|---|
| `/` | GET | `GetTransactionsHandler` | Render `transactions.html` with `transactions` list and `current_filter` |
| `/create` | POST | `HoldFundsHandler` (via `HoldFundsRequestSchema`) | Flash message + Redirect to `/transactions/` |

### REST API Controller (JSON)
**File**: `src/ledger/infrastructure/web/transaction_api_controller.py`
**Blueprint**: `transactions_api` (url_prefix `/api/transactions`)

Used by programmatic clients (SPAs, mobile, external services). Enforces strict HTTP semantics and supports the `Idempotency-Key` header.

| Route | Method | Handler | Response |
|---|---|---|---|
| `/<int:id>/complete` | POST | `CompleteFundsHandler` | JSON `{success, new_status}` |
| `/<int:id>/fail` | POST | `FailAndRefundHandler` | JSON `{success, new_status}` |

### DI Container Integration
Controller layers no longer instantiate infrastructure dependencies (like repositories or unit of work) directly for handler creation. The `DIContainer` handles all handler wiring. The controller only instantiates the `SqliteUnitOfWork` context to pass into the handler, maintaining the lifecycle boundary of the request.

---

## API Contract

### Hold Funds (Create Transaction)
```
POST /transactions/create
Content-Type: application/x-www-form-urlencoded

from_account_id=1&to_account_id=2&amount=100.00&merchant_id=5&user_email=user@example.com
```
**Validation**: Fails fast via `HoldFundsRequestSchema` if IDs are not integers or amount is not a positive decimal.
**Success**: Flash message "Funds held successfully." + Redirect to `/transactions/`

**Errors** (Flash message):
- `ValueError` (Validation): Malformed inputs (e.g., missing/invalid amount).
- `InsufficientFundsError`: Source account lacks funds.
- `AccountNotFoundError`: One or both accounts do not exist.
- `CurrencyMismatchError`: Accounts have different currencies.

### Complete Funds
```
POST /api/transactions/<id>/complete
Headers: 
  Idempotency-Key: <optional-uuid>
```
**Success Response** (200):
```json
{ "success": true, "new_status": "Success" }
```
**Error Responses**:
- `400 Bad Request`: `InvalidTransactionStateError` (e.g., already failed).
- `409 Conflict`: `InsufficientFundsError`, `AccountNotFoundError`, `CurrencyMismatchError`.
- `500 Internal Server Error`: Generic catch-all. Logs full trace internally; returns `{"message": "An internal server error occurred."}` to client.

### Fail & Refund
```
POST /api/transactions/<id>/fail
Headers: 
  Idempotency-Key: <optional-uuid>
```
**Success Response** (200):
```json
{ "success": true, "new_status": "Refunded" }
```
**Error Responses**:
- `400 Bad Request`: `InvalidTransactionStateError`.
- `409 Conflict`: `InsufficientFundsError` (e.g., destination account insolvent during refund), `AccountNotFoundError`.
- `500 Internal Server Error`: Secure generic message, internal logging applied.

### List Transactions
```
GET /transactions/?status=Pending
```
**Response**: Rendered HTML (`transactions.html`) with `transactions` list and `current_filter`.

---

## Flows

### 1. Hold Funds
```
[User/Checkout UI] → POST /transactions/create
  → Validate form data via HoldFundsRequestSchema (Fail-Fast)
  → Map to HoldFundsCommand(...)
  → HoldFundsHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: Flash message + Redirect to /transactions/
  → On error: Flash specific error message + Redirect to /transactions/
```

### 2. Complete Funds
```
[Merchant/SPA] → POST /api/transactions/complete/<id>
  → Check Idempotency-Key (if provided)
  → Map to CompleteFundsCommand(transaction_id=id)
  → CompleteFundsHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: JSON {success: true, new_status: "Success"}
  → On Domain Error: JSON {success: false, message: "..."}, HTTP 400 or 409
  → On System Error: Log stack trace, JSON {success: false, message: "Internal..."}, HTTP 500
```

### 3. Fail & Refund
```
[Merchant/SPA] → POST /api/transactions/fail/<id>
  → Check Idempotency-Key (if provided)
  → Map to FailAndRefundCommand(transaction_id=id)
  → FailAndRefundHandler
    → (See Transaction Application (Commands) module for domain flow)
  → On success: JSON {success: true, new_status: "Refunded"}
  → On Domain Error: JSON {success: false, message: "..."}, HTTP 400 or 409
  → On System Error: Log stack trace, JSON {success: false, message: "Internal..."}, HTTP 500
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
**Status**: RESOLVED / Outdated.
**Historical Context**: Previously documented as a bug where `create_pending` used `id=0` and events would capture this before the DB updated it. 
**Current State**: The repository (`sqlite_transaction_repository.py`) correctly assigns `transaction.id = cursor.lastrowid` atomically before the UoW commits. Furthermore, no events are emitted during the Hold phase, rendering this edge case dormant. If a `TransactionHeldEvent` is added in the future, it must be constructed *after* the repository `add()` method returns, not inside the entity factory.

*(Note: Other edge cases like EC-2, EC-3 are handled safely at domain/application layers and explicitly mapped to 4xx HTTP codes by the controllers).*

---

## Notes & Technical Debt

### TD-9: Incomplete DI Container Integration
**Status**: RESOLVED.
**Previous State**: Controller manually instantiated `SqliteUnitOfWork`, `SqliteAccountRepository`, and `SqliteTransactionRepository` using local factory functions.
**Current State**: Local factory functions (`_get_uow`, `_get_account_repo`, etc.) have been completely removed. The controller strictly requests handlers from `current_app.di_container`.

### Architecture & Security Debt (Resolved in v1.1.0)
The following technical debts were completely resolved in the latest iteration:
- **Schizophrenic Architecture (TD-2)**: Resolved by separating `/transactions` (SSR) and `/api/transactions` (REST) into distinct infrastructure files.
- **Lack of Validation (TD-3)**: Resolved by implementing `HoldFundsRequestSchema` to intercept bad data before it reaches the Application layer.
- **Information Leakage & 500 Leaks**: Resolved by explicitly catching Domain exceptions (returning 4xx) and masking generic `Exception` traces from the client (returning secure 500 + internal `app.logger.error`).
- **Missing Idempotency**: Resolved by implementing the `@idempotent` decorator on state-mutating API endpoints.