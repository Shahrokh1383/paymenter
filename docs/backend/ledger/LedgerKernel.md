# Account & Currency Module

**Version:** 2.1.0

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules & Invariants](#2-business-rules--invariants)
3. [Backend Architecture](#3-backend-architecture)
4. [Execution Flows](#4-execution-flows)
5. [Edge Cases & Known Issues](#5-edge-cases--known-issues)
6. [Architectural Notes & Trade-offs](#6-architectural-notes--trade-offs)

---

## 1. Overview
The Account & Currency module is responsible for the lifecycle of financial accounts and the currencies in which they operate. It is a self-contained part of the `ledger` Bounded Context, built on Domain-Driven Design (DDD) and Clean Architecture. This module enforces critical invariants such as the non-negative balance rule for standard withdrawals, the strict zero-balance/zero-holds/zero-authorizations prerequisite for currency mutation, and strict Bounded Context isolation on the read side. It utilizes an **Event-Driven Architecture** to deterministically bootstrap System Escrow accounts whenever a new currency is introduced, ensuring Aggregate purity and idempotency. The module exposes no HTTP endpoints directly; its capabilities are consumed by the Transaction & Settlement module and internal administrative processes through Application-layer use cases.

---

## 2. Business Rules & Invariants
All rules listed here are non-negotiable and enforced at the aggregate level.

- **BR-1: Non-Negative Balance Invariant (Standard Withdrawals)**  
  The `Account.withdraw()` method guarantees that an account's balance can never fall below zero. Any attempt to withdraw more than the available balance results in an `InsufficientFundsError`. *Note: System-initiated chargebacks (`apply_system_reversal`) intentionally bypass this invariant to prevent system crashes when a receiver has already spent held funds.*

- **BR-3: Currency Mutation Invariant (Enhanced)**  
  An account's currency may only be changed if its current balance, pending holds, and open authorizations are all exactly zero. The `Account.change_currency()` method enforces this rule. A non-zero balance triggers a `NonZeroBalanceCurrencyChangeError`, and active holds/authorizations trigger a `PendingHoldsExistError`. This prevents inconsistent historical records, orphaned holds, and settlement mismatches.

- **BR-6: Deterministic & Idempotent Escrow Bootstrapping**  
  The moment a new `Currency` aggregate is persisted, a `CurrencyCreatedEvent` is published. An application-layer event handler provisions the System Escrow account. The escrow account number is generated using a **cryptographically deterministic algorithm**: a SHA-256 hash of the currency code, converted to an integer, modulo 10 billion, and zero-padded to exactly 10 digits. The handler explicitly checks for the existence of this account number before creation, ensuring strict **idempotency** and preventing duplicate accounts on event retries or network failures.

- **BR-7: Zero Primitive Obsession**  
  All financial quantities and identifiers crossing layer boundaries are expressed through strict, immutable Value Objects (`@dataclass(frozen=True)`). Balances and amounts use `Money(Decimal, CurrencyCode)`, and account identifiers are represented by `AccountNumber`, which enforces a rigid 10‑digit format. Raw primitives such as strings or floats are forbidden in Domain and Application layers.

- **BR-8: Defensive Legacy Data Clamping**  
  The `Account.decrease_holds()` method clamps the resulting hold balance at `0.00`. This gracefully handles edge cases where legacy transactions (created before holds were tracked) are released, preventing the aggregate from entering an invalid negative-holds state.

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies. Pure Python.*

- **Aggregates**
  - `Account` – Controls balance mutations (`deposit`, `withdraw`, `topup`, `apply_system_reversal`), hold mutations (`increase_holds`, `decrease_holds`), currency mutation (`change_currency`), and identity via `AccountNumber`.
  - `Currency` – Represents a tradable currency. Creation is strictly pure and side-effect free; it merely registers a `CurrencyCreatedEvent` to be handled by the application layer.
  - `Transaction` – Manages transaction lifecycle states (`Pending`, `Success`, `Failed`, `Refunded`).

- **Value Objects**
  - `AccountNumber` – Validates a 10‑digit string, rejecting any malformed input.
  - `Money` – Holds a `Decimal` amount (quantized to 2 decimal places) and a `CurrencyCode`. Enforces same‑currency checks on arithmetic operations.
  - `CurrencyCode` – Immutable three‑letter ISO code, normalized to uppercase.

- **Domain Events**
  - `AccountCreatedEvent`
  - `CurrencyCreatedEvent` (Triggers asynchronous escrow provisioning)
  - `CurrencyActivatedEvent` / `CurrencyDeactivatedEvent`

- **Exceptions**
  - Dedicated domain exceptions inherit from `DomainException`: `InsufficientFundsError`, `CurrencyMismatchError`, `NonZeroBalanceCurrencyChangeError`, `PendingHoldsExistError`, `InvalidTopupAmountError`, `InvalidTransactionStateError`, `ConcurrencyException`, `CurrencyNotFoundError`, `CurrencyAlreadyExistsError`, `AccountNotFoundError`.

- **Ports**
  - `SystemAccountResolverPort` – Abstract interface for retrieving a system escrow account by currency code.
  - `UnitOfWork` – Abstract interface for managing atomic database transactions.
  - `EventBus` – Abstract interface for publishing and subscribing to domain events.

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, Event Handlers, and DTOs.*

- **Commands & Handlers**
  - `CreateCurrencyCommand` / `CreateCurrencyHandler` – Accepts currency attributes, persists the pure `Currency` aggregate, and dispatches the `CurrencyCreatedEvent`. It strictly adheres to the Single Responsibility Principle by not instantiating other aggregates.
  - `UpdateAccountCurrencyCommand` / `UpdateAccountCurrencyHandler` – Loads the `Account` aggregate, invokes `change_currency` (which enforces BR-3 via domain exceptions), and persists the state.

- **Event Handlers**
  - `EscrowBootstrapperEventHandler` – Subscribes to `CurrencyCreatedEvent`. It generates the deterministic 10-digit account number via SHA-256, executes an idempotency check (`get_by_account_number`), instantiates the system `Account` aggregate (with zero balance, holds, and auths), and persists it within a new UoW transaction.

- **Queries & Handlers**
  - `GetAllAccountsHandler` / `GetAllEscrowAccountsHandler` – Return optimized DTOs for list views via dedicated Query Ports.

- **DTOs**
  - `AccountSummary` – Contains account metadata including `pending_holds` and `open_authorizations`. The `card_number` field is retained in the DTO signature for backward compatibility but is strictly hardcoded to `None` to enforce bounded context isolation.
  - `EscrowAccountSummary` – Focused strictly on escrow metadata.

### 3.3. Infrastructure Layer (Adapters & Persistence)

*Implementation details. Pluggable.*

- **Write Repositories**
  - `SqliteAccountRepository` – Persists `Account` aggregates. Implements Optimistic Concurrency Control (OCC) via a `version` column. Explicitly queries the `currencies` table during `add` and `update` operations; raises `CurrencyNotFoundError` if the referenced currency code is missing, eliminating silent fallbacks.
  - `SqliteCurrencyRepository` – Persists `Currency` aggregates.
  - `SqliteTransactionRepository` – Persists `Transaction` aggregates with OCC.

- **Read Models**
  - `SqliteAccountReadModel` – **Isolation Fix:** Strictly queries within the `ledger` context (joining `accounts`, `currencies`, `users`, and `merchants`). The cross-context `LEFT JOIN` on `user_cards` has been entirely removed.
  - `SqliteEscrowAccountReadModel` – Materialises escrow summaries.

- **Adapters**
  - `SqliteSystemAccountResolver` – Implements `SystemAccountResolverPort` by querying for accounts where `user_id IS NULL AND merchant_id IS NULL`.

- **Unit of Work & DI**
  - `SqliteUnitOfWork` – Manages atomic transactions, nesting levels, and SQLite PRAGMAs (`foreign_keys = ON`, `journal_mode=WAL`).
  - `ledger_di.py` – Wires the dependency injection container, registers handler factories, and subscribes the `EscrowBootstrapperEventHandler` to the `CurrencyCreatedEvent` on the event bus.

---

## 4. Execution Flows

### Flow 1: Currency Creation with Event-Driven Escrow Bootstrapping
1. **Command dispatch:** `CreateCurrencyCommand` is processed by `CreateCurrencyHandler`.
2. **Handler execution (UoW):**
   - A pure `Currency` aggregate is instantiated and persisted.
   - The UoW commits the transaction.
   - The handler publishes a `CurrencyCreatedEvent` to the event bus.
3. **Event Handling (Asynchronous/Decoupled & Idempotent):**
   - `EscrowBootstrapperEventHandler` catches the event.
   - It generates a 10-digit account number using `SHA-256(currency_code) % 10^10`.
   - **Idempotency Check:** It queries `AccountRepository.get_by_account_number()`. If an account already exists, it exits early (preventing duplicates on retry).
   - It instantiates the system `Account` (with `user_id=None`, `merchant_id=None`, `pending_holds=0`, `open_authorizations=0`) and persists it within a new UoW transaction.

### Flow 2: Account Currency Change
1. **Command dispatch:** `UpdateAccountCurrencyCommand` carrying the account ID and target `CurrencyCode`.
2. **Handler execution:**
   - Loads the `Account` aggregate.
   - Invokes `Account.change_currency(new_currency_code)`.
   - The aggregate strictly checks BR-3. If balance > 0, it raises `NonZeroBalanceCurrencyChangeError`. If holds/auths > 0, it raises `PendingHoldsExistError`.
   - If valid, it updates the `Money` value objects with the new currency code.
3. **Persistence:** `SqliteAccountRepository.update()` verifies the currency exists, increments the `version`, and commits via OCC. Historical transactions remain untouched.

---

## 5. Edge Cases & Known Issues

### Issue 1: Unhandled Domain & Concurrency Exceptions
**Description:** The repositories enforce Optimistic Concurrency Control (`ConcurrencyException`) and strict referential integrity (`CurrencyNotFoundError`, `AccountNotFoundError`). The domain layer raises strict business rule violations (`NonZeroBalanceCurrencyChangeError`, `PendingHoldsExistError`). 
**Impact:** If not caught by a centralized Exception Mapper at the API/Presentation boundary, these will propagate as generic 500 Internal Server Errors.
**Action Required:** The API layer must implement a centralized exception handler to translate these domain exceptions into appropriate HTTP status codes (e.g., `ConcurrencyException` -> `409 Conflict`, `CurrencyNotFoundError` -> `404 Not Found`, `NonZeroBalance...` -> `422 Unprocessable Entity`).

### Issue 2: Theoretical Hash Collision in Escrow Numbering
**Description:** The deterministic escrow account number relies on `SHA-256 % 10,000,000,000`. By the birthday paradox, a 50% probability of a collision occurs after generating approximately $\sqrt{10^{10}} \approx 100,000$ currencies.
**Impact:** If a collision occurs, the idempotency check in `EscrowBootstrapperEventHandler` will silently skip creating the new escrow account, resulting in two currencies sharing the same escrow account.
**Mitigation:** In any realistic financial system, the number of supported currencies will never exceed a few hundred. The probability of a collision at $N < 1000$ is astronomically low ($< 0.00005\%$). This is an acceptable theoretical trade-off for eliminating database sequence dependencies.

### Issue 3: SQLite Physical Write Contention
**Description:** While Optimistic Concurrency Control (OCC) handles *logical* conflicts at the application layer, SQLite uses database-level locking for *physical* writes (even in WAL mode). 
**Impact:** Under extreme write contention on the same aggregate or table, SQLite may throw `SQLITE_BUSY` errors.
**Mitigation:** Application-layer retry mechanisms with exponential backoff must be implemented for database operational errors. The architecture is designed such that migrating to a row-level locking RDBMS (like PostgreSQL) requires zero domain or application layer refactoring.

---

## 6. Architectural Notes & Trade-offs

### Event-Driven Aggregate Provisioning (DDD Purity)
Strict DDD purity dictates that Aggregates must remain pure and free of side-effects (such as instantiating other Aggregates or accessing external repositories) during their creation. By publishing a `CurrencyCreatedEvent` and delegating the Escrow account provisioning to an Application-layer Event Handler, we decouple the lifecycle of the two aggregates. This prevents the `Currency` aggregate from becoming a "God object" and ensures clean domain boundaries.

### Cryptographic Deterministic Numbering & Idempotency
The previous reliance on `9000000000 + currency_id` created a hard ceiling and tightly coupled the domain to infrastructure auto-increment sequences. The new SHA-256 modulo approach guarantees that the escrow account number is derived entirely from the domain identity (the currency code). Combined with a read-before-write idempotency check, this makes the system highly resilient to database migrations, sharding, sequence resets, and transient network failures during event processing.

### Strict Bounded Context Isolation on the Read Side
The architectural exception allowing a `LEFT JOIN` on the `user_cards` table (from the `checkout`/`identity` context) has been **permanently revoked**. Direct cross-context data access on the read side creates tight coupling and schema fragility. The `SqliteAccountReadModel` now strictly queries only within the `ledger` and core identity contexts. The `card_number` field in the UI and DTOs has been deprecated/hardcoded to `None` to reflect this strict decoupling. Future integration requiring card data must rely on an Anti-Corruption Layer (ACL) or Integration Events.

### Dedicated Domain Exceptions
Generic host-language exceptions (e.g., Python's `ValueError`) have been entirely replaced with dedicated Domain Exceptions inheriting from `DomainException`. This ensures that the Domain layer remains pure, and higher layers can implement precise, semantic error handling and HTTP status code mapping without relying on string matching or generic exception types.

### Immutable Audit Trail on Currency Mutation
When `UpdateAccountCurrencyCommand` changes an account’s operational currency, only the `Account` aggregate’s state is altered. Historical rows in the `transactions` table retain their original `currency_id`. This follows standard double-entry accounting principles, ensuring financial reports and reconciliation processes remain accurate for any point in time.

### Defensive Aggregate Mutations
The `Account` aggregate employs defensive programming patterns, such as clamping `pending_holds` at zero during a decrease operation. This ensures that eventual consistency issues, legacy data migrations, or out-of-order event processing cannot force the aggregate into an invalid negative-holds state, preserving the mathematical integrity of the ledger.