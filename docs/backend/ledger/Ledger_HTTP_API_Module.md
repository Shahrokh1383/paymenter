# Ledger HTTP API Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Backend Architecture — Infrastructure Layer (Web)](#backend-architecture--infrastructure-layer-web)
   - [SSR Controller (HTML/Forms)](#ssr-controller-htmlforms)
   - [REST API Controller (JSON)](#rest-api-controller-json)
   - [Transaction Read Model (CQRS)](#transaction-read-model-cqrs)
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
- **Error Handling**: Catching domain exceptions and mapping them to precise HTTP status codes; securely logging system exceptions without leaking internal stack traces.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Controllers depend on Application Commands/Handlers, never the Domain directly. |
| Rule 2: New Feature = New File | ✅ API controller, validation schema, and idempotency wrapper isolated in new files. |
| Rule 3: No Primitive Obsession | ✅ Read Models strictly use `Decimal` for amounts and `datetime` for timestamps. |
| Rule 6: Infrastructure as Plugin | ✅ Flask, validation schemas, and idempotency decorators are infrastructure details. |
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

Used by programmatic clients (SPAs, mobile, external services). Enforces strict HTTP semantics and supports the `Idempotency-Key` header via the `@idempotent` decorator.

| Route | Method | Handler | Response |
|---|---|---|---|
| `/<int:id>/complete` | POST | `CompleteFundsHandler` | JSON `{success, new_status}` |
| `/<int:id>/fail` | POST | `FailAndRefundHandler` | JSON `{success, new_status}` |

**Exception-to-HTTP Status Mapping (REST):**
- `InvalidTransactionStateError` → **400 Bad Request** (e.g., attempting to complete an already failed transaction).
- `InsufficientFundsError`, `AccountNotFoundError`, `CurrencyMismatchError` → **409 Conflict** (Domain invariant violations or resource conflicts).
- Unhandled `Exception` → **500 Internal Server Error** (Logged internally with `exc_info=True`, returns secure generic message to client).

### Transaction Read Model (CQRS)
**File**: `src/ledger/infrastructure/persistence/sqlite_transaction_read_model.py`
**Port**: `TransactionQueryPort`

The read model executes a highly optimized `LEFT JOIN` query across `transactions`, `accounts` (aliased for both source and destination), and `currencies`. 
- **Architectural Benefit**: By joining the `accounts` table twice (`from_acc` and `to_acc`), the read model seamlessly resolves the `account_number` for both standard User Accounts and System Escrow Accounts without requiring complex conditional logic or violating bounded context boundaries.
- **Data Integrity**: Raw database strings for amounts are strictly cast to `Decimal`, and timestamps are parsed into `datetime` objects before crossing into the Application layer DTO (`TransactionListItem`), completely eliminating primitive obsession in the read pipeline.

### DI Container Integration
Controller layers no longer instantiate infrastructure dependencies (like repositories or unit of work) directly for handler creation. The `DIContainer` handles all handler wiring. The controller only instantiates the `SqliteUnitOfWork` context to pass into the handler, maintaining the strict lifecycle boundary of the HTTP request.

---

## API Contract

### Hold Funds (Create Transaction)
```http
POST /transactions/create
Content-Type: application/x-www-form-urlencoded

from_account_id=1&to_account_id=2&amount=100.00&merchant_id=5&user_email=user@example.com
```
**Architectural Note on `user_email`**: 
While the payload accepts `user_email`, this field is retained **strictly for legacy audit and transaction history purposes**. It is decoupled from notification routing. Transaction receipts are routed asynchronously via the `payer_account_id` using an Anti-Corruption Layer in the Notifications context.

**Validation**: Fails fast via `HoldFundsRequestSchema` if IDs are not integers or amount is not a positive decimal.
**Success**: Flash message "Funds held successfully." + Redirect to `/transactions/`
**Errors** (Flash message): `ValueError`, `InsufficientFundsError`, `AccountNotFoundError`, `CurrencyMismatchError`.

### Complete Funds
```http
POST /api/transactions/<id>/complete
Headers: 
  Idempotency-Key: <optional-uuid>
```
**Success Response** (200 OK):
```json
{ "success": true, "new_status": "Success" }
```

### Fail & Refund
```http
POST /api/transactions/<id>/fail
Headers: 
  Idempotency-Key: <optional-uuid>
```
**Success Response** (200 OK):
```json
{ "success": true, "new_status": "Refunded/Failed" }
```

### List Transactions
```http
GET /transactions/?status=Pending
```
**Response**: Rendered HTML (`transactions.html`).
**DTO Structure (`TransactionListItem`)**:
| Field | Type | Description |
|---|---|---|
| `id` | `int` | Transaction DB ID |
| `amount` | `Decimal` | Strict decimal precision (No floats) |
| `currency_code` | `str` | ISO 4217 Code (e.g., "USD") |
| `status` | `str` | "Pending", "Success", "Failed", "Refunded" |
| `created_at` | `datetime` | Parsed datetime object |
| `user_email` | `Optional[str]` | Audit email |
| `from_account_number`| `str` | 10-digit account number (User or Escrow) |
| `to_account_number` | `str` | 10-digit account number (User or Escrow) |

---

## Flows

### 1. Hold Funds
```text
[User/Checkout UI] → POST /transactions/create
  → Validate form data via HoldFundsRequestSchema (Fail-Fast)
  → Map to HoldFundsCommand(...)
  → HoldFundsHandler
    → (See Transaction Application Commands module for domain flow)
  → On success: Flash message + Redirect to /transactions/
  → On error: Flash specific error message + Redirect to /transactions/
```

### 2. Complete Funds
```text
[Merchant/SPA] → POST /api/transactions/<id>/complete
  → Check Idempotency-Key (if provided)
  → Map to CompleteFundsCommand(transaction_id=id)
  → CompleteFundsHandler
    → Mutates Aggregate & Persists State
    → Writes Domain Event to Outbox table (Synchronous DB Write)
  → On success: JSON {success: true, new_status: "Success"} (HTTP Response returns immediately)
  → Background Outbox Worker asynchronously picks up the event and dispatches it.
```

### 3. Fail & Refund
```text
[Merchant/SPA] → POST /api/transactions/<id>/fail
  → Check Idempotency-Key (if provided)
  → Map to FailAndRefundCommand(transaction_id=id)
  → FailAndRefundHandler
    → Mutates Aggregates & Persists State
    → Writes Domain Event to Outbox table (Synchronous DB Write)
  → On success: JSON {success: true, new_status: "Refunded/Failed"}
  → Background Outbox Worker asynchronously picks up the event.
```

### 4. Query Transactions
```text
GET /transactions/?status=Pending
  → GetTransactionsQuery(status_filter='Pending')
  → GetTransactionsHandler
    → SqliteTransactionReadModel.get_all_summaries(status)
      → LEFT JOIN accounts (resolves User & Escrow account numbers safely)
      → Maps to List[TransactionListItem]
  → Render transactions.html
```

---

## Edge Cases & Known Issues

### EC-4: Transaction ID Zero in Events
**Status**: RESOLVED / Outdated.
**Historical Context**: Previously documented as a bug where `create_pending` used `id=0` and events would capture this before the DB updated it. 
**Current State**: The repository (`sqlite_transaction_repository.py`) correctly assigns `transaction.id = cursor.lastrowid` atomically before the UoW commits. Furthermore, no events are emitted during the Hold phase, rendering this edge case dormant.

---

## Notes & Technical Debt

*No active technical debt in this module.*

*(Resolved) TD-9: Incomplete DI Container Integration*
**Previous State**: Controller manually instantiated infrastructure dependencies using local factory functions.
**Resolution**: Local factory functions completely removed. The controller strictly requests handlers from `current_app.di_container`.

*(Resolved) TD-14: Synchronous HTTP Blocking via Email Dispatch*
**Previous Issue**: State-mutating API endpoints were blocked from returning HTTP responses until the SMTP adapter finished sending the receipt email.
**Resolution**: Implemented the Approximate ACID Outbox Pattern. The HTTP request only performs a fast, local SQLite insert into the `outbox_messages` table. A background daemon thread (`OutboxRelayWorker`) guarantees eventual delivery.

*(Resolved) TD-15: Information Leakage on 500 Errors*
**Previous Issue**: Unhandled exceptions leaked Python stack traces to the API client.
**Resolution**: The REST controller now explicitly catches generic `Exception`, logs the full trace internally via `current_app.logger.error(..., exc_info=True)`, and returns a secure, generic `{"message": "An internal server error occurred."}` with a 500 status code.