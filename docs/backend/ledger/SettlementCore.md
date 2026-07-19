# Transaction & Settlement Module

**Version:** 2.0.0

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules & Invariants](#2-business-rules--invariants)
3. [Backend Architecture](#3-backend-architecture)
4. [API Contract](#4-api-contract)
5. [Execution Flows](#5-execution-flows)
6. [Edge Cases & Known Issues](#6-edge-cases--known-issues)
7. [Architectural Notes & Trade-offs](#7-architectural-notes--trade-offs)

---

## 1. Overview
The Transaction & Settlement module is the operational heart of the `ledger` Bounded Context. It orchestrates the complete lifecycle of a financial transaction using a strict double-entry ledger pattern with an **Immediate Escrow** mechanism. Every fund movement follows a three-step logic: hold funds by moving them from the payer to a system escrow account, then either complete (escrow to payee) or fail/refund (escrow back to payer, or system reversal). This module exposes both HTML and JSON API endpoints, enforces idempotency to guard against duplicate processing, and publishes domain events for downstream contexts after successful persistence. It adheres fully to CQRS, separating write commands that mutate aggregates from read queries that fetch pre-built DTOs via strictly isolated intra-context read models.

---

## 2. Business Rules & Invariants
The following rules are enforced by the Transaction aggregate and the `DoubleEntryLedger` domain service.

- **BR-1: Non-Negative Balance Invariant (Standard Withdrawals)**  
  Any debit operation performed during the hold phase calls `Account.withdraw()`, which refuses to bring the account balance below zero. This invariant, defined in the Account & Currency module, is an absolute prerequisite for transaction processing.

- **BR-2: System Reversals & Permanent Negative Balances (Chargebacks)**  
  When a completed transaction is refunded, the receiver’s account may already have spent the funds. To prevent system crashes during chargeback processing, `Account.apply_system_reversal()` intentionally bypasses the non-negative balance invariant. This results in a permanently negative balance for the receiving account. No automated debt-collection or overdraft facility is provided; the negative balance is an accepted audit state.

- **BR-4: Double-Entry Ledger & Escrow Isolation**  
  Funds are never transferred directly from payer to payee. The `DoubleEntryLedger` domain service enforces a two-step escrow flow:
  1. **Hold:** Debit Payer -> Credit System Escrow Account.
  2. **Complete/Fail:** Debit Escrow -> Credit Payee (Success) OR Debit Escrow -> Credit Payer (Fail). *Note: Refunding a Success transaction bypasses the escrow account entirely, executing a direct system reversal on the payee.*

- **BR-5: Strict Transaction State Machine**  
  A transaction progresses through a predefined, immutable lifecycle:
  `Pending` -> `Success` OR `Failed` -> `Refunded` (only from `Success`).
  Any attempt to transition from an invalid state raises `InvalidTransactionStateError`.

- **BR-7: Zero Primitive Obsession**  
  Monetary values inside transactions use the `Money` value object, guaranteeing decimal precision and currency matching. Transaction identifiers, where modelled, avoid bare primitives.

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies.*

- **Aggregate**
  - `Transaction` – Holds a unique ID, payer and payee account references, amount (`Money`), status, and timestamps. Exposes methods `mark_as_success()`, `mark_as_failed()`, `mark_as_refunded()` that enforce BR-5.

- **Domain Service**
  - `DoubleEntryLedger` – Stateless orchestrator that manipulates `Account` aggregates and the `Transaction` aggregate to execute hold, complete, and fail/refund operations. It never persists data itself; all persistence is delegated to repositories through the Unit of Work.

- **Domain Events**
  - `TransactionCompletedEvent`
  - `TransactionFailedEvent`
  - `TransactionRefundedEvent`
  These events are fired strictly **after** the database transaction commits, enabling loose coupling with other contexts such as notifications.

- **Ports**
  - `SystemAccountResolverPort` – Retrieves the system escrow account for a given currency. Implementation is provided by the Account & Currency module’s infrastructure (`SqliteSystemAccountResolver`).

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, DTOs.*

- **Commands & Handlers**
  - `HoldFundsCommand` / `HoldFundsHandler` – Validates accounts, resolves escrow, calls `DoubleEntryLedger.hold_funds()`, and persists a `Pending` transaction.
  - `CompleteFundsCommand` / `CompleteFundsHandler` – Settles a pending transaction, marks it `Success`, moves funds from escrow to payee.
  - `FailAndRefundCommand` / `FailAndRefundHandler` – Fails a pending transaction or refunds a successful one. In refund scenarios, invokes the system reversal path on the payee account.
  - All state-modifying handlers publish domain events **outside** the Unit of Work block to ensure events are only dispatched upon successful commit.

- **Queries & Handlers**
  - `GetTransactionsHandler` – Accepts optional `status` filter, returns a list of `TransactionListItem` DTOs.

- **DTOs**
  - `TransactionListItem` – Flat representation optimised for list views, avoiding N+1 problems.

### 3.3. Infrastructure Layer (Adapters & Persistence)
*Implementation details.*

- **Write Repositories**
  - `SqliteTransactionRepository` – Persists `Transaction` aggregates with OCC via a `version` column. Concurrency conflicts raise `ConcurrencyException`.

- **Read Models**
  - `SqliteTransactionReadModel` – Executes highly optimised SQL JOINs across `transactions`, `accounts`, and `currencies` to produce DTOs directly. **Architectural Note:** These are strictly *intra-context* joins. The module enforces strict Bounded Context isolation on the read side and does not join tables from external contexts (e.g., `user_cards`).

- **Unit of Work**
  - `SqliteUnitOfWork` – Shared instance managing atomicity. All write operations within a single command handler run inside the same UoW block.

- **Web Controllers**
  - `transaction_bp` – Flask Blueprint for HTML endpoints (UI rendering).
  - `transaction_api_bp` – Flask Blueprint for JSON API endpoints.
  - Both utilise schema validation and the idempotency decorator from `src.common.infrastructure.web.idempotency`.

---

## 4. API Contract

### 4.1. HTML Endpoints (UI)
| Method | Endpoint | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/transactions/` | Renders transaction history, filterable. | `?status=Pending\|Success\|Failed` |
| `POST` | `/transactions/create` | Initiates a transaction hold. | `form-data`: `from_account_id`, `to_account_id`, `amount`, `merchant_id` (optional), `user_email` (optional) |

### 4.2. JSON API Endpoints (Machine-to-Machine)
| Method | Endpoint | Description | Headers | Payload | Responses |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/transactions/<id>/complete` | Settles a Pending transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |
| `POST` | `/api/transactions/<id>/fail` | Fails or refunds a transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |

Both API endpoints are protected by the `@idempotent` decorator. A repeated request with the same `Idempotency-Key` returns the original response without re-executing the command.

---

## 5. Execution Flows

### Flow 1: Holding Funds (Checkout Integration)
1. **HTTP Request:** Client submits a `POST` to `/transactions/create` with payer, payee, and amount.
2. **Validation:** `HoldFundsRequestSchema` converts the amount to `Decimal` and validates account identifiers.
3. **Command:** `HoldFundsCommand` is built and passed to `HoldFundsHandler`.
4. **Orchestration (inside UoW):**
   - `from_acc` and `to_acc` aggregates are loaded.
   - Currency matching is verified.
   - `SystemAccountResolverPort` returns the escrow account for the currency.
   - `DoubleEntryLedger.hold_funds()` debits the payer and credits the escrow.
   - A new `Transaction` in `Pending` status is created and staged.
5. **Persistence:** Repositories save the mutated aggregates and the transaction. `UnitOfWork.commit()` atomically persists everything.
6. **Result:** A redirect to the transaction UI with a success flash message. No domain event is published at this stage; events are reserved for settlement or failure.

### Flow 2: Completing Funds (Settlement)
1. **HTTP Request:** An external system sends `POST /api/transactions/<id>/complete` with an `Idempotency-Key`.
2. **Command:** `CompleteFundsCommand` dispatched to `CompleteFundsHandler`.
3. **Orchestration (UoW):**
   - Loads `Transaction`; verifies status is `Pending`.
   - Loads `to_acc` (payee) and `escrow_acc`.
   - `DoubleEntryLedger.complete_funds()` transitions the transaction to `Success`, debits the escrow, and credits the payee.
4. **Persistence:** All aggregates are saved with incremented version numbers. UoW commits.
5. **Eventing:** `TransactionCompletedEvent` is instantiated inside the UoW but published to the `InMemoryEventBus` **outside** the UoW block.
6. **Cross-Context:** Subscribers in other bounded contexts react by sending receipts.

### Flow 3: Failing / Refunding (Chargeback)
1. **Command:** `FailAndRefundCommand` dispatched.
2. **Orchestration (UoW):**
   - **Pending case:** Marks transaction as `Failed`, debits escrow, credits payer.
   - **Success case:** Marks as `Refunded`, credits payer, and forcefully debits the original payee via `Account.apply_system_reversal()` (bypassing the non-negative invariant, per BR-2). The escrow account is untouched as it was zeroed out during completion.
3. **Persistence:** Aggregates and transaction saved; UoW commits.
4. **Eventing:** Publishes `TransactionFailedEvent` or `TransactionRefundedEvent` outside the UoW block.

---

## 6. Edge Cases & Known Issues

### Issue 1: Partial Exception Mapping (OCC 500 Risk)
**Description:** The API controllers (`transaction_api_controller.py`) correctly map Domain Exceptions (like `InsufficientFundsError`, `AccountNotFoundError`, and `CurrencyMismatchError`) to HTTP `409 Conflict`, preventing generic 500 errors during expected business rule violations. However, the `ConcurrencyException` thrown by the SQLite write repositories during Optimistic Concurrency Control (OCC) conflicts is **not explicitly caught** in the controller `try/except` blocks.  
**Impact:** If a race condition occurs (e.g., two concurrent requests attempting to complete the same transaction), the unhandled `ConcurrencyException` will fall through to the generic `Exception` handler, resulting in a **500 Internal Server Error** instead of the semantically appropriate `409 Conflict`.  
**Action Required:** A global `@app.errorhandler` must be registered in the Flask application setup to map `ConcurrencyException` to a 409 response, ensuring total coverage of all distributed system conflicts.

### Issue 2: At-Most-Once Event Delivery (No Outbox)
**Description:** Domain events are published synchronously via `InMemoryEventBus` after the database transaction commits. If the application process crashes in the narrow window between `uow.commit()` and `event_bus.publish()`, the event is permanently lost.  
**Impact:** Downstream contexts may never receive `TransactionCompletedEvent`, causing missing receipts or audit gaps.  
**Action Required:** This is acceptable for the in-memory simulation. In a production environment backed by a message broker (Kafka, RabbitMQ), the Transactional Outbox Pattern must be introduced to guarantee at-least-once delivery.

---

## 7. Architectural Notes & Trade-offs

### Immediate Escrow vs. Shadow Hold
The module implements an **Immediate Escrow (Pre-Funding)** model rather than a "Shadow Hold" model. When funds are held, they are physically debited from the payer's available balance and credited to the System Escrow account. This guarantees that the payer cannot double-spend the held funds and simplifies the settlement logic, as the funds are already secured in a system-controlled aggregate.

### Strict Intra-Context Read Model Isolation
The module strictly separates write-side aggregate persistence from read-side projections. Query handlers never touch aggregates; they delegate directly to `SqliteTransactionReadModel`. This read model performs highly optimised SQL JOINs across `transactions`, `accounts`, and `currencies`. **Crucially, these are strictly intra-context joins.** The module enforces rigorous Bounded Context isolation on the read side, refusing to join tables from external contexts (such as `user_cards` from the checkout context). This prevents tight coupling and schema fragility, ensuring the ledger remains autonomous.

### Idempotency Enforcement
All mutating JSON API endpoints (`/complete`, `/fail`) are wrapped in the `@idempotent` decorator. This decorator persists the `Idempotency-Key` and the original response for a configurable duration. Network retries from external gateways will receive the cached response without re-executing the underlying command. This protects the ledger from duplicate settlements and double refunds, preserving financial integrity without requiring distributed transactions.

### Safe Event Publishing Timing
By instantiating domain events inside the Unit of Work block but invoking `event_bus.publish()` strictly **outside** the block (after the `with self._uow:` context manager exits), the handlers guarantee that events are only dispatched if the database commit succeeds. This prevents "phantom events" where downstream contexts react to transactions that were ultimately rolled back due to database errors or OCC conflicts.