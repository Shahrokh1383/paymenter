# Transaction & Settlement Module

**Version:** 2.2.0

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
The Transaction & Settlement module is the operational heart of the `ledger` Bounded Context. It orchestrates the complete lifecycle of a financial transaction using a strict double-entry ledger pattern enhanced with a **Dual-Tracking Hybrid Escrow** mechanism. Every fund movement follows a multi-step logic: funds are physically debited from the payer and credited to a system escrow account, while simultaneously incrementing a shadow `pending_holds` tracker on the payer's account for strict audit and lifecycle invariants.

The module operates with **application-generated UUIDs** for all aggregate identities, completely decoupling the domain model from database sequence generators. For optimal performance and precision, monetary values are persisted as **integer cents** at the infrastructure layer, while the domain layer strictly enforces `Decimal` precision via the `Money` value object. It exposes both HTML and JSON API endpoints, enforces idempotency via an in-memory caching decorator, and publishes domain events for downstream contexts strictly after successful database commits. Furthermore, system escrow accounts are auto-provisioned via an event-driven bootstrapper using deterministic SHA-256 hashing whenever a new currency is introduced.

---

## 2. Business Rules & Invariants
The following rules are enforced by the `Transaction`, `Account`, and `Currency` aggregates, and the `DoubleEntryLedger` domain service.

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

- **BR-6: Zero Primitive Obsession & Strict Typing**  
  Monetary values use the `Money` value object, guaranteeing decimal precision (`quantize('0.01')`) and currency matching. Internal aggregate identities utilize UUID strings, while routing and display identifiers use the `AccountNumber` value object (strictly validated 10-digit strings).

- **BR-7: Optimistic Concurrency Control (OCC) & Retry Resilience**  
  All mutable aggregates enforce OCC via a `version` column. High-contention operations (such as currency updates) implement application-layer exponential backoff retries to gracefully resolve `ConcurrencyException` conflicts without failing the user request.

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies.*

- **Aggregates**
  - `Transaction` – Holds a UUID `id`, payer/payee references, amount (`Money`), status, and timestamps. Exposes methods `mark_as_success()`, `mark_as_failed()`, `mark_as_refunded()`.
  - `Account` – Tracks `balance`, `pending_holds` (`Money`), and `open_authorizations` (`int`). Encapsulates logic for `withdraw`, `deposit`, `topup`, `increase_holds`, `decrease_holds` (with legacy clamping), `apply_system_reversal`, and `change_currency`.
  - `Currency` – Tracks `id` (UUID), `name`, `code` (`CurrencyCode`), and `is_active` state.

- **Value Objects**
  - `Money` – Immutable, enforces currency matching on arithmetic operations, and quantizes to 2 decimal places.
  - `CurrencyCode` – Normalized 3-letter ISO code.
  - `AccountNumber` – Strictly validated 10-digit string.
  - `EmailAddress` – RFC-compliant email validation.

- **Domain Service**
  - `DoubleEntryLedger` – Stateless orchestrator that manipulates `Account` aggregates and the `Transaction` aggregate to execute hold, complete, and fail/refund operations.

- **Domain Events**
  - `TransactionCompletedEvent`, `TransactionFailedEvent`, `TransactionRefundedEvent`
  - `AccountCreatedEvent`, `CurrencyCreatedEvent`, `CurrencyActivatedEvent`, `CurrencyDeactivatedEvent`

- **Ports**
  - `SystemAccountResolverPort` – Retrieves the system escrow account for a given currency.
  - `UnitOfWork` – Manages atomic database transactions.
  - `EventBus` – Publishes and subscribes to domain events.

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, DTOs.*

- **Commands & Handlers**
  - `HoldFundsHandler` – Validates accounts, resolves escrow, calls `DoubleEntryLedger.hold_funds()`, and persists a `Pending` transaction.
  - `CompleteFundsHandler` / `FailAndRefundHandler` – Settle or reverse transactions and dispatch events post-commit.
  - `UpdateAccountCurrencyHandler` – Enforces BR-3 and implements a robust exponential backoff retry mechanism for OCC conflicts.
  - `CreateCurrencyHandler` & `EscrowBootstrapperEventHandler` – Listens to `CurrencyCreatedEvent` to automatically provision system escrow accounts using deterministic SHA-256 hashing to generate the 10-digit `AccountNumber`.

- **Queries & Handlers**
  - `GetTransactionsHandler`, `GetAllAccountsHandler`, `GetAllCurrenciesHandler` – Return DTOs via strictly isolated read models.

### 3.3. Infrastructure Layer (Adapters & Persistence)
*Implementation details.*

- **Write Repositories**
  - `SqliteTransactionRepository`, `SqliteAccountRepository`, `SqliteCurrencyRepository` – Persist aggregates with strict Optimistic Concurrency Control (OCC) via a `version` column. They encapsulate monetary serialization via `_to_cents()` and `_from_cents()` methods, storing financial figures as `INTEGER` in SQLite to eliminate string-parsing overhead and guarantee exact integer arithmetic at the DB level.

- **Read Models**
  - `SqliteTransactionReadModel`, `SqliteAccountReadModel`, `SqliteEscrowAccountReadModel` – Execute highly optimised SQL JOINs strictly *intra-context*.

- **Unit of Work**
  - `SqliteUnitOfWork` – Context manager managing atomicity. Uses SQLite WAL mode and enforces foreign keys. Auto-commits on clean exit, auto-rollbacks on exceptions.

- **Web Controllers & Middleware**
  - `transaction_bp` (HTML) / `transaction_api_bp` (JSON).
  - `@idempotent` decorator intercepts POST requests, checking an in-memory dictionary for the `Idempotency-Key` header to prevent duplicate executions.

---

## 4. API Contract

### 4.1. HTML Endpoints (UI)
| Method | Endpoint | Description | Payload / Query Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/transactions/` | Renders transaction history, filterable. | `?status=Pending\|Success\|Failed` |
| `POST` | `/transactions/create` | Initiates a transaction hold. | `form-data`: `from_account_id` (UUID), `to_account_id` (UUID), `amount`, `merchant_id`, `user_email` |

### 4.2. JSON API Endpoints (Machine-to-Machine)
| Method | Endpoint | Description | Headers | Payload | Responses |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/transactions/<uuid:id>/complete` | Settles a Pending transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |
| `POST` | `/api/transactions/<uuid:id>/fail` | Fails or refunds a transaction. | `Idempotency-Key` (required) | None | `200 OK`, `400 Bad Request`, `409 Conflict`, `500 Error` |

Both API endpoints are protected by the `@idempotent` decorator. A repeated request with the same `Idempotency-Key` returns the cached 2xx response without re-executing the command.

---

## 5. Execution Flows

### Flow 1: Holding Funds (Checkout Integration)
1. **HTTP Request:** Client submits a `POST` to `/transactions/create`.
2. **Validation:** `HoldFundsRequestSchema` converts amount to `Decimal` and validates UUID strings.
3. **Orchestration (inside UoW):**
   - `from_acc` and `to_acc` aggregates are loaded. `escrow_acc` is resolved.
   - Identity resolution prevents duplicate UoW tracking (`if from_acc.id == escrow_acc.id: from_acc = escrow_acc`).
   - Application layer generates a new UUID (`uuid.uuid4().hex`) for the `Transaction` aggregate.
   - `DoubleEntryLedger.hold_funds()` physically debits the payer, increments `pending_holds`, and credits the escrow.
4. **Persistence:** Repositories convert `Money` decimals to integer cents via `_to_cents()` and persist the mutated aggregates (incrementing OCC versions). `UnitOfWork.commit()` atomically persists everything.

### Flow 2: Completing Funds (Settlement)
1. **HTTP Request:** External system sends `POST /api/transactions/<uuid:id>/complete` with `Idempotency-Key`.
2. **Orchestration (UoW):**
   - Loads `Transaction`, `from_acc`, `to_acc`, and `escrow_acc`.
   - `DoubleEntryLedger.complete_funds()` transitions transaction to `Success`, decrements `pending_holds` on payer, debits escrow, and credits payee.
3. **Persistence & Eventing:** Aggregates saved via integer-cents conversion. UoW commits. `TransactionCompletedEvent` is published to the `EventBus` **outside** the UoW block.

### Flow 3: Failing / Refunding (Chargeback)
1. **Orchestration (UoW):**
   - **Pending case:** Marks as `Failed`, decrements `pending_holds`, debits escrow, credits payer.
   - **Success case:** Marks as `Refunded`, credits payer, and forcefully debits payee via `apply_system_reversal()` (bypassing non-negative invariant). Escrow is untouched.
2. **Persistence & Eventing:** Aggregates saved. UoW commits. Appropriate failure/refund event is published outside the UoW block.

---

## 6. Edge Cases & Known Issues

### Issue 1: Partial Exception Mapping (OCC 500 Risk)
**Description:** Domain exceptions (`InsufficientFundsError`, `AccountNotFoundError`, `CurrencyMismatchError`) are correctly mapped to HTTP `409 Conflict` in the API controllers. However, `ConcurrencyException` thrown by OCC conflicts is not explicitly caught in the `try/except` blocks of `transaction_api_controller.py`.  
**Impact:** Race conditions result in a generic `500 Internal Server Error` instead of a retry-friendly 409.  
**Action Required:** Register a global `@app.errorhandler` or add explicit `except ConcurrencyException` blocks to map to a 409 response.

### Issue 2: At-Most-Once Event Delivery (No Outbox)
**Description:** Events are published synchronously via `EventBus` after `uow.commit()`. A crash between commit and publish loses the event.  
**Impact:** Downstream contexts may miss `TransactionCompletedEvent`.  
**Action Required:** Implement the Transactional Outbox Pattern for production message brokers.

### Issue 3: In-Memory Idempotency Store Limitations
**Description:** The `@idempotent` decorator relies on a Python dictionary (`_idempotency_store`) to cache responses.  
**Impact:** The cache is lost on application restart and cannot be shared across multiple horizontal instances (pods/containers). Retries hitting a different instance will re-execute the command.  
**Action Required:** Migrate the idempotency store to a shared, persistent datastore like Redis or a dedicated database table with TTLs.

---

## 7. Architectural Notes & Trade-offs

### Dual-Tracking Hybrid Escrow Model
The module implements a hybrid approach. Funds are physically moved to an Immediate Escrow account to prevent double-spending, while the payer's `pending_holds` field is simultaneously incremented. This provides the security of pre-funding with the auditability and lifecycle tracking of a shadow hold system. The `decrease_holds` method includes defensive clamping (`max(0, ...)`) to gracefully handle legacy data.

### Event-Driven Escrow Bootstrapping
System Escrow accounts are not hardcoded. When a new currency is created, a `CurrencyCreatedEvent` is published. The `EscrowBootstrapperEventHandler` subscribes to this event and automatically provisions a system account. It uses a deterministic SHA-256 hash of the currency code to generate a 10-digit `AccountNumber`, ensuring idempotency and preventing duplicate escrow accounts on event retries.

### Integer-Cents Persistence Strategy
To eliminate floating-point inaccuracies and string-parsing overhead at the database engine level, monetary values (`amount`, `balance`, `pending_holds`) are stored as `INTEGER` (cents) in SQLite. The conversion logic (`_to_cents` and `_from_cents`) is strictly encapsulated within the Infrastructure Repositories, ensuring the Domain `Money` value object remains pure and completely unaware of its serialization format.

### Application-Layer UUID Generation
By shifting Aggregate IDs from database-generated integers to application-generated UUIDs (`uuid.uuid4().hex`), the Domain Layer is completely decoupled from the infrastructure's sequence generator. Aggregates now possess valid, globally unique identities *before* persistence, which is critical for distributed systems and preventing ID collision during concurrent transaction processing.

### Strict Intra-Context Read Model Isolation
Query handlers never touch aggregates. The Read Models perform highly optimised SQL JOINs strictly within the ledger context (`transactions`, `accounts`, `currencies`). They refuse to join tables from external contexts, ensuring the ledger remains fully autonomous and deployable independently.

### Safe Event Publishing Timing
By instantiating domain events inside the Unit of Work block but invoking `event_bus.publish()` strictly **outside** the block, the handlers guarantee that events are only dispatched if the database commit succeeds. This prevents "phantom events" where downstream contexts react to transactions that were ultimately rolled back.

### Aggregate Identity Resolution in UoW
The application handlers implement a precise identity resolution pattern (`if from_acc.id == escrow_acc.id: from_acc = escrow_acc`). This prevents the Unit of Work from tracking the same database row under two different Python object references, which would otherwise cause state corruption or false Optimistic Concurrency Control (OCC) failures when `repo.update()` is called multiple times on the same underlying row.

### OCC Retry Mechanism with Exponential Backoff
To handle high-contention scenarios gracefully, specific handlers like `UpdateAccountCurrencyHandler` implement a retry loop with exponential backoff (`time.sleep(BASE_DELAY * (2 ** (attempt - 1)))`). This ensures that transient `ConcurrencyException` conflicts are resolved automatically at the application layer without surfacing unnecessary errors to the end user.