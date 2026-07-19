# Transaction & Settlement Module

**Version:** 3.0.0

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
The Transaction & Settlement module is the operational heart of the `ledger` Bounded Context. It orchestrates the complete lifecycle of a financial transaction using a strict double-entry ledger pattern enhanced with a **Dual-Tracking Hybrid Escrow** mechanism. Every fund movement follows a multi-step logic: funds are physically debited from the payer and credited to a system escrow account, while simultaneously incrementing a shadow `pending_holds` tracker on the payer's account for strict audit and lifecycle invariants. Settlement or failure reverses these physical movements and decrements the shadow holds. 

The module exposes both HTML and JSON API endpoints, enforces idempotency via an in-memory caching decorator to guard against duplicate processing, and publishes domain events for downstream contexts strictly after successful database commits. It adheres fully to CQRS, separating write commands that mutate aggregates from read queries that fetch pre-built DTOs via strictly isolated intra-context read models. Furthermore, system escrow accounts are auto-provisioned via an event-driven bootstrapper whenever a new currency is introduced to the system.

---

## 2. Business Rules & Invariants
The following rules are enforced by the `Transaction` and `Account` aggregates, and the `DoubleEntryLedger` domain service.

- **BR-1: Non-Negative Balance Invariant (Standard Withdrawals)**  
  Any debit operation performed during the hold phase calls `Account.withdraw()`, which refuses to bring the available account balance below zero. This is an absolute prerequisite for transaction processing.

- **BR-2: System Reversals & Permanent Negative Balances (Chargebacks)**  
  When a completed transaction is refunded, the receiver’s account may already have spent the funds. To prevent system crashes during chargeback processing, `Account.apply_system_reversal()` intentionally bypasses the non-negative balance invariant. This results in a permanently negative balance for the receiving account. No automated debt-collection is provided; the negative balance is an accepted audit state.

- **BR-3: Strict Zero-State Currency Change**  
  An account can only change its base currency if its `balance`, `pending_holds`, and `open_authorizations` are all exactly zero. Any attempt to change currency while holds or authorizations exist raises `PendingHoldsExistError` or `NonZeroBalanceCurrencyChangeError`.

- **BR-4: Double-Entry Ledger & Dual-Tracking Escrow**  
  Funds are never transferred directly from payer to payee. The `DoubleEntryLedger` domain service enforces a hybrid flow:
  1. **Hold:** Physically Debit Payer -> Credit System Escrow Account. *Simultaneously*, increment Payer's `pending_holds`.
  2. **Complete:** Physically Debit Escrow -> Credit Payee. *Simultaneously*, decrement Payer's `pending_holds`.
  3. **Fail:** Physically Debit Escrow -> Credit Payer. *Simultaneously*, decrement Payer's `pending_holds`.
  *Note: Refunding a Success transaction bypasses the escrow account entirely, executing a direct system reversal on the payee.*

- **BR-5: Strict Transaction State Machine**  
  A transaction progresses through a predefined, immutable lifecycle:
  `Pending` -> `Success` OR `Failed` -> `Refunded` (only from `Success`).
  Any attempt to transition from an invalid state raises `InvalidTransactionStateError`.

- **BR-6: Zero Primitive Obsession**  
  Monetary values use the `Money` value object, guaranteeing decimal precision (`quantize('0.01')`) and currency matching. Account identifiers use the `AccountNumber` value object (strictly 10 digits).

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies.*

- **Aggregates**
  - `Transaction` – Holds a unique ID, payer/payee references, amount (`Money`), status, and timestamps. Exposes methods `mark_as_success()`, `mark_as_failed()`, `mark_as_refunded()`.
  - `Account` – Tracks `balance`, `pending_holds` (`Money`), and `open_authorizations` (`int`). Encapsulates logic for `withdraw`, `deposit`, `increase_holds`, `decrease_holds` (with legacy clamping), and `change_currency`.

- **Value Objects**
  - `Money` – Immutable, enforces currency matching on arithmetic operations.
  - `CurrencyCode` – Normalized 3-letter ISO code.
  - `AccountNumber` – Strictly validated 10-digit string.

- **Domain Service**
  - `DoubleEntryLedger` – Stateless orchestrator that manipulates `Account` aggregates and the `Transaction` aggregate to execute hold, complete, and fail/refund operations. It never persists data itself.

- **Domain Events**
  - `TransactionCompletedEvent`, `TransactionFailedEvent`, `TransactionRefundedEvent`
  - `AccountCreatedEvent`, `CurrencyCreatedEvent`
  These events are fired strictly **after** the database transaction commits.

- **Ports**
  - `SystemAccountResolverPort` – Retrieves the system escrow account for a given currency.

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, DTOs.*

- **Commands & Handlers**
  - `HoldFundsHandler` – Validates accounts, resolves escrow, calls `DoubleEntryLedger.hold_funds()`, and persists a `Pending` transaction.
  - `CompleteFundsHandler` – Settles a pending transaction, marks it `Success`, moves funds from escrow to payee, and decreases holds.
  - `FailAndRefundHandler` – Fails a pending transaction or refunds a successful one.
  - `UpdateAccountCurrencyHandler` – Enforces BR-3 before mutating the account's currency.
  - `TopupAccountHandler` / `CreateAccountHandler` – Manage account lifecycle.
  - *Event Handlers:* `EscrowBootstrapperEventHandler` listens to `CurrencyCreatedEvent` to automatically provision system escrow accounts using deterministic SHA-256 hashing for account numbers.

- **Queries & Handlers**
  - `GetTransactionsHandler` – Returns `TransactionListItem` DTOs via the read model.

### 3.3. Infrastructure Layer (Adapters & Persistence)
*Implementation details.*

- **Write Repositories**
  - `SqliteTransactionRepository` & `SqliteAccountRepository` – Persist aggregates with strict Optimistic Concurrency Control (OCC) via a `version` column. Concurrency conflicts raise `ConcurrencyException`.

- **Read Models**
  - `SqliteTransactionReadModel` – Executes highly optimised SQL JOINs across `transactions`, `accounts`, and `currencies`. Strictly *intra-context* joins only.

- **Unit of Work**
  - `SqliteUnitOfWork` – Context manager managing atomicity. Uses SQLite WAL mode. Auto-commits on clean exit, auto-rollbacks on exceptions.

- **Web Controllers & Middleware**
  - `transaction_bp` (HTML) / `transaction_api_bp` (JSON).
  - `@idempotent` decorator intercepts POST requests, checking an in-memory dictionary for the `Idempotency-Key` header to prevent duplicate executions.

---

## 4. API Contract

### 4.1. HTML Endpoints (UI)
| Method | Endpoint | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/transactions/` | Renders transaction history, filterable. | `?status=Pending\|Success\|Failed` |
| `POST` | `/transactions/create` | Initiates a transaction hold. | `form-data`: `from_account_id`, `to_account_id`, `amount`, `merchant_id`, `user_email` |

### 4.2. JSON API Endpoints (Machine-to-Machine)
| Method | Endpoint | Description | Headers | Payload | Responses |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/transactions/<id>/complete` | Settles a Pending transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |
| `POST` | `/api/transactions/<id>/fail` | Fails or refunds a transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |

Both API endpoints are protected by the `@idempotent` decorator. A repeated request with the same `Idempotency-Key` returns the cached 2xx response without re-executing the command.

---

## 5. Execution Flows

### Flow 1: Holding Funds (Checkout Integration)
1. **HTTP Request:** Client submits a `POST` to `/transactions/create`.
2. **Validation:** `HoldFundsRequestSchema` converts amount to `Decimal` and validates IDs.
3. **Orchestration (inside UoW):**
   - `from_acc` and `to_acc` aggregates are loaded. `escrow_acc` is resolved.
   - Identity resolution prevents duplicate UoW tracking (`if from_acc.id == escrow_acc.id: from_acc = escrow_acc`).
   - `DoubleEntryLedger.hold_funds()` physically debits the payer, increments `pending_holds`, and credits the escrow.
   - A new `Transaction` in `Pending` status is created.
4. **Persistence:** Repositories save mutated aggregates (incrementing OCC versions). `UnitOfWork.commit()` atomically persists everything.

### Flow 2: Completing Funds (Settlement)
1. **HTTP Request:** External system sends `POST /api/transactions/<id>/complete` with `Idempotency-Key`.
2. **Orchestration (UoW):**
   - Loads `Transaction`, `from_acc`, `to_acc`, and `escrow_acc`.
   - `DoubleEntryLedger.complete_funds()` transitions transaction to `Success`, decrements `pending_holds` on payer, debits escrow, and credits payee.
3. **Persistence & Eventing:** Aggregates saved. UoW commits. `TransactionCompletedEvent` is published to the `EventBus` **outside** the UoW block.

### Flow 3: Failing / Refunding (Chargeback)
1. **Orchestration (UoW):**
   - **Pending case:** Marks as `Failed`, decrements `pending_holds`, debits escrow, credits payer.
   - **Success case:** Marks as `Refunded`, credits payer, and forcefully debits payee via `apply_system_reversal()` (bypassing non-negative invariant). Escrow is untouched.
2. **Persistence & Eventing:** Aggregates saved. UoW commits. Appropriate failure/refund event is published outside the UoW block.

---

## 6. Edge Cases & Known Issues

### Issue 1: Partial Exception Mapping (OCC 500 Risk)
**Description:** Domain exceptions (`InsufficientFundsError`, `AccountNotFoundError`, `CurrencyMismatchError`) are correctly mapped to HTTP `409 Conflict`. However, `ConcurrencyException` thrown by OCC conflicts is not explicitly caught in the controller `try/except` blocks.  
**Impact:** Race conditions result in a generic `500 Internal Server Error`.  
**Action Required:** Register a global `@app.errorhandler` to map `ConcurrencyException` to a 409 response.

### Issue 2: At-Most-Once Event Delivery (No Outbox)
**Description:** Events are published synchronously via `EventBus` after `uow.commit()`. A crash between commit and publish loses the event.  
**Impact:** Downstream contexts may miss `TransactionCompletedEvent`.  
**Action Required:** Implement the Transactional Outbox Pattern for production message brokers.

### Issue 3: In-Memory Idempotency Store Limitations
**Description:** The `@idempotent` decorator relies on a Python dictionary (`_idempotency_store`) to cache responses.  
**Impact:** The cache is lost on application restart and cannot be shared across multiple horizontal instances (pods/containers). Retries hitting a different instance will re-execute the command, potentially causing OCC conflicts or double-processing if not guarded by database constraints.  
**Action Required:** Migrate the idempotency store to a shared, persistent datastore like Redis or a dedicated database table with TTLs.

---

## 7. Architectural Notes & Trade-offs

### Dual-Tracking Hybrid Escrow Model
The module implements a hybrid approach. Funds are physically moved to an Immediate Escrow account to prevent double-spending, while the payer's `pending_holds` field is simultaneously incremented. This provides the security of pre-funding with the auditability and lifecycle tracking of a shadow hold system. The `decrease_holds` method includes defensive clamping (`max(0, ...)`) to gracefully handle legacy data.

### Event-Driven Escrow Bootstrapping
System Escrow accounts are not hardcoded. When a new currency is created, a `CurrencyCreatedEvent` is published. The `EscrowBootstrapperEventHandler` subscribes to this event and automatically provisions a system account. It uses a deterministic SHA-256 hash of the currency code to generate a 10-digit `AccountNumber`, ensuring idempotency and preventing duplicate escrow accounts on event retries.

### Strict Intra-Context Read Model Isolation
Query handlers never touch aggregates. The `SqliteTransactionReadModel` performs highly optimised SQL JOINs strictly within the ledger context (`transactions`, `accounts`, `currencies`). It refuses to join tables from external contexts (e.g., `user_cards`), ensuring the ledger remains fully autonomous and deployable independently.

### Safe Event Publishing Timing
By instantiating domain events inside the Unit of Work block but invoking `event_bus.publish()` strictly **outside** the block, the handlers guarantee that events are only dispatched if the database commit succeeds. This prevents "phantom events" where downstream contexts react to transactions that were ultimately rolled back.

### Aggregate Identity Resolution in UoW
The application handlers implement a precise identity resolution pattern (`if from_acc.id == escrow_acc.id: from_acc = escrow_acc`). This prevents the Unit of Work from tracking the same database row under two different Python object references, which would otherwise cause state corruption or false Optimistic Concurrency Control (OCC) failures when `repo.update()` is called multiple times on the same underlying row.