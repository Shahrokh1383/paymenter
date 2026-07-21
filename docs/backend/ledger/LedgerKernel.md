# Account & Currency Module

**Version:** 2.4.0

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules & Invariants](#2-business-rules--invariants)
3. [Backend Architecture](#3-backend-architecture)
4. [Execution Flows](#4-execution-flows)
5. [Edge Cases & Known Issues](#5-edge-cases--known-issues)
6. [Architectural Notes & Trade-offs](#6-architectural-notes--trade-offs)

---

## 1. Overview
The Account & Currency module is responsible for the lifecycle of financial accounts and the currencies in which they operate. It is a self-contained part of the `ledger` Bounded Context, built on Domain-Driven Design (DDD) and Clean Architecture. 

This module enforces critical invariants such as the non-negative balance rule for standard withdrawals, the strict zero-balance/zero-holds/zero-authorizations prerequisite for currency mutation, and strict Bounded Context isolation on the read side. To guarantee deterministic execution and eliminate database-sequence coupling, all Aggregate Root identities are generated as **UUIDs (v4)** in the Application Layer prior to persistence. Financial quantities are strictly persisted as **INTEGER (cents)** to bypass SQLite's lack of native DECIMAL types, ensuring zero precision loss. Furthermore, Optimistic Concurrency Control (OCC) collisions are handled gracefully via **Application-Layer Exponential Backoff**. It utilizes an **Event-Driven Architecture** to deterministically bootstrap System Escrow accounts whenever a new currency is introduced. 

**v2.4.0 Evolution:** The infrastructure has been fully standardized around **Implicit Ambient Transaction Management** via Python's `contextvars`. Application Handlers and synchronous Event Subscribers no longer explicitly invoke database commits; instead, they rely entirely on the implicit commit boundary of the Unit of Work (UoW) context manager. This guarantees strict ACID compliance across in-process event chains, ensuring that domain purity is maintained without sacrificing atomic consistency.

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
  All financial quantities and identifiers crossing layer boundaries are expressed through strict, immutable Value Objects (`@dataclass(frozen=True)`). Balances and amounts use `Money(Decimal, CurrencyCode)`, and account identifiers are represented by `AccountNumber` (10‑digit format) and UUID strings for internal Aggregate routing. Raw primitives such as floats are forbidden in Domain and Application layers.

- **BR-8: Defensive Legacy Data Clamping**  
  The `Account.decrease_holds()` method clamps the resulting hold balance at `0.00`. This gracefully handles edge cases where legacy transactions (created before holds were tracked) are released, preventing the aggregate from entering an invalid negative-holds state.

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies. Pure Python.*

- **Aggregates**
  - `Account` – Controls balance mutations (`deposit`, `withdraw`, `topup`, `apply_system_reversal`), hold mutations (`increase_holds`, `decrease_holds`), currency mutation (`change_currency`), and identity via UUID `id` and `AccountNumber`.
  - `Currency` – Represents a tradable currency. Creation is strictly pure and side-effect free; it merely registers a `CurrencyCreatedEvent` to be handled by the application layer.
  - `Transaction` – Manages transaction lifecycle states (`Pending`, `Success`, `Failed`, `Refunded`). Uses UUID strings for `id`, `from_account_id`, and `to_account_id`.

- **Value Objects**
  - `AccountNumber` – Validates a 10‑digit string, rejecting any malformed input.
  - `Money` – Holds a `Decimal` amount (quantized to 2 decimal places) and a `CurrencyCode`. Enforces same‑currency checks on arithmetic operations.
  - `CurrencyCode` – Immutable three‑letter ISO code, normalized to uppercase.

- **Domain Events**
  - `AccountCreatedEvent`
  - `CurrencyCreatedEvent` (Triggers atomic escrow provisioning)
  - `CurrencyActivatedEvent` / `CurrencyDeactivatedEvent`

- **Exceptions**
  - Dedicated domain exceptions strictly inherit from a base `DomainException`: `InsufficientFundsError`, `CurrencyMismatchError`, `NonZeroBalanceCurrencyChangeError`, `PendingHoldsExistError`, `InvalidTopupAmountError`, `InvalidTransactionStateError`, `ConcurrencyException`, `CurrencyNotFoundError`, `CurrencyAlreadyExistsError`, `AccountNotFoundError`.

- **Ports**
  - `SystemAccountResolverPort` – Abstract interface for retrieving a system escrow account by currency code.
  - `UnitOfWork` – Abstract interface for managing atomic database transactions via context managers (`__enter__`, `__exit__`).
  - `EventBus` – Abstract interface for publishing and subscribing to domain events.

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, Event Handlers, and DTOs.*

- **Commands & Handlers**
  - `CreateCurrencyCommand` / `CreateCurrencyHandler` – Accepts currency attributes, generates a UUID, persists the pure `Currency` aggregate, and dispatches the `CurrencyCreatedEvent` strictly *inside* the UoW block. Relies on the implicit commit boundary of the context manager.
  - `UpdateAccountCurrencyCommand` / `UpdateAccountCurrencyHandler` – Loads the `Account` aggregate, invokes `change_currency`. **Implements a Retry Mechanism** with exponential backoff (Max 3 retries, base delay 0.1s) to automatically resolve transient `ConcurrencyException` collisions. Relies on implicit commits.

- **Event Handlers**
  - `EscrowBootstrapperEventHandler` – Subscribes to `CurrencyCreatedEvent`. Generates the deterministic 10-digit account number via SHA-256, executes an idempotency check (`get_by_account_number`), instantiates the system `Account` aggregate, and persists it. Due to Ambient Transaction Management, it seamlessly joins the parent's active database transaction, ensuring strict atomic consistency.

- **Queries & Handlers**
  - `GetAllAccountsHandler` / `GetAllEscrowAccountsHandler` – Return optimized DTOs for list views via dedicated Query Ports.

- **DTOs**
  - `AccountSummary` – Contains account metadata. `id` and `currency_id` are strictly typed as `str` (UUIDs). The `card_number` field is strictly hardcoded to `None` to enforce bounded context isolation.
  - `EscrowAccountSummary` – Focused strictly on escrow metadata (`id` and `currency_id` as `str`).

### 3.3. Infrastructure Layer (Adapters & Persistence)

*Implementation details. Pluggable.*

- **Write Repositories**
  - `SqliteAccountRepository` / `SqliteTransactionRepository` – Persists aggregates. Implements **Integer Cents Mapping** via `_to_cents()` and `_from_cents()` helper methods to ensure zero precision loss in SQLite. Implements Optimistic Concurrency Control (OCC) via a `version` column, raising `ConcurrencyException` if `rowcount == 0` during updates.
  - `SqliteCurrencyRepository` – Persists `Currency` aggregates.

- **Read Models**
  - `SqliteAccountReadModel` / `SqliteEscrowAccountReadModel` – Materialises summaries. Reconstructs `Decimal` financial quantities by dividing the stored integer cents by `100`. Strictly queries within the `ledger` context.

- **Adapters**
  - `SqliteSystemAccountResolver` – Implements `SystemAccountResolverPort` by querying for accounts where `user_id IS NULL AND merchant_id IS NULL`.

- **Unit of Work & DI**
  - `SqliteUnitOfWork` – Manages atomic transactions and nesting levels via `contextvars`. Configures SQLite PRAGMAs (`foreign_keys = ON`, `journal_mode=WAL`) and sets a `10.0s` connection timeout to gracefully handle physical write contention (`SQLITE_BUSY`). Automatically commits on a clean `__exit__` or rolls back if an exception propagates.
  - `ledger_di.py` – Wires the dependency injection container, registers handler factories, and subscribes the `EscrowBootstrapperEventHandler` to the `CurrencyCreatedEvent` on the event bus.

---

## 4. Execution Flows

### Flow 1: Currency Creation with Event-Driven Escrow Bootstrapping
1. **Command dispatch:** `CreateCurrencyCommand` is processed by `CreateCurrencyHandler`.
2. **Handler execution (Ambient UoW):**
   - A UUID is generated for the `currency_id`.
   - A pure `Currency` aggregate is instantiated and persisted.
   - The handler publishes a `CurrencyCreatedEvent` to the event bus *inside* the UoW block.
3. **Event Handling (Atomic & Idempotent via Ambient UoW):**
   - `EscrowBootstrapperEventHandler` catches the event synchronously.
   - Due to `contextvars`, it seamlessly joins the parent's active ambient transaction.
   - It generates a 10-digit account number using `SHA-256(currency_code) % 10^10`.
   - **Idempotency Check:** It queries `AccountRepository.get_by_account_number()`. If an account already exists, it exits early.
   - It generates a new UUID for the `account_id`, instantiates the system `Account`, and persists it.
4. **Atomic Commit:** Upon clean exit of the outermost `with self._uow:` block, the implicit commit finalizes both the Currency and the Escrow Account atomically. If the bootstrapper fails, the entire transaction rolls back, preventing orphaned currencies.

### Flow 2: Account Currency Change with OCC Retry
1. **Command dispatch:** `UpdateAccountCurrencyCommand` carrying the `account_id` (UUID string) and target `CurrencyCode`.
2. **Handler execution (Retry Loop & Ambient UoW):**
   - Enters a `while True` loop (max 3 attempts).
   - Opens UoW context manager. Loads the `Account` aggregate.
   - Invokes `Account.change_currency(new_currency_code)`. The aggregate strictly checks BR-3.
   - If valid, it updates the `Money` value objects with the new currency code.
   - `SqliteAccountRepository.update()` verifies the currency exists, increments the `version`, and executes the SQL update.
   - If a concurrent modification occurred, SQLite returns `rowcount == 0`, triggering a `ConcurrencyException`.
   - **Backoff:** The handler catches the exception, sleeps for `0.1 * (2 ^ (attempt - 1))` seconds, and retries.
3. **Implicit Persistence:** On success, the clean exit of the UoW context manager triggers the implicit commit, and the loop breaks. Historical transactions remain untouched.

---

## 5. Edge Cases & Known Issues

### Issue 1: Centralized Exception Mapping Required
**Description:** The domain and infrastructure layers raise strict, semantic exceptions (`ConcurrencyException`, `CurrencyNotFoundError`, `NonZeroBalanceCurrencyChangeError`, etc.) inheriting from `DomainException`. 
**Impact:** If not caught by a centralized Exception Mapper at the API/Presentation boundary, these will propagate as generic 500 Internal Server Errors.
**Action Required:** The API layer must implement a centralized exception handler to translate these domain exceptions into appropriate HTTP status codes (e.g., `ConcurrencyException` -> `409 Conflict`, `CurrencyNotFoundError` -> `404 Not Found`, `NonZeroBalance...` -> `422 Unprocessable Entity`).

### Issue 2: Theoretical Hash Collision in Escrow Numbering
**Description:** The deterministic escrow account number relies on `SHA-256 % 10,000,000,000`. By the birthday paradox, a 50% probability of a collision occurs after generating approximately $\sqrt{10^{10}} \approx 100,000$ currencies.
**Impact:** If a collision occurs, the idempotency check in `EscrowBootstrapperEventHandler` will silently skip creating the new escrow account.
**Mitigation:** In any realistic financial system, the number of supported currencies will never exceed a few hundred. The probability of a collision at $N < 1000$ is astronomically low. This is an acceptable theoretical trade-off for eliminating database sequence dependencies.

### Issue 3: SQLite Physical Write Contention & WAL
**Description:** While Optimistic Concurrency Control (OCC) handles *logical* conflicts at the application layer, SQLite uses database-level locking for *physical* writes. 
**Impact:** Under extreme write contention, SQLite may throw `SQLITE_BUSY` errors.
**Mitigation:** The `SqliteUnitOfWork` is configured with `PRAGMA journal_mode=WAL` and a `10.0s` connection timeout, allowing SQLite to queue physical writes gracefully. Combined with the Application-Layer Exponential Backoff on `ConcurrencyException`, the system is highly resilient. The architecture is designed such that migrating to a row-level locking RDBMS (like PostgreSQL) requires zero domain or application layer refactoring.

---

## 6. Architectural Notes & Trade-offs

### Application-Layer UUID Generation (Eliminating the Flush Paradox)
By generating `uuid.uuid4().hex` in the Application Layer *before* invoking the repository, we completely decoupled the Domain from database auto-increment sequences. This eliminated the "mid-transaction flush paradox," allowing the `CreateCurrencyHandler` to remain pure and strictly adhere to the Unit of Work pattern without requiring partial commits to retrieve generated IDs.

### Implicit Ambient Transactions & DDD Purity
Strict DDD purity dictates that Aggregates must remain free of side-effects. By publishing a `CurrencyCreatedEvent` and delegating the Escrow account provisioning to an Application-layer Event Handler, we decouple the lifecycle of the two aggregates at the domain level. Furthermore, by leveraging `contextvars` for Ambient Transaction Management, the event handler seamlessly joins the parent's active database transaction. This provides DDD purity at the domain layer while guaranteeing strict ACID compliance at the infrastructure layer, completely eliminating the risk of split transactions or orphaned entities.

### Integer Cents Persistence (Zero Precision Loss)
SQLite lacks a native `DECIMAL` type, often degrading `NUMERIC` to `REAL` (Float), which introduces catastrophic rounding errors in financial systems. By strictly storing `balance`, `pending_holds`, and `amount` as `INTEGER` (representing cents) in the schema, and utilizing `_to_cents()` / `_from_cents()` mapping in the repositories, we guarantee absolute mathematical precision while allowing the Domain Layer to operate purely on `Decimal` objects.

### Strict Bounded Context Isolation on the Read Side
The architectural exception allowing a `LEFT JOIN` on the `user_cards` table (from the `checkout`/`identity` context) has been **permanently revoked**. Direct cross-context data access creates tight coupling. The `SqliteAccountReadModel` strictly queries only within the `ledger` and core identity contexts. The `card_number` field in DTOs is hardcoded to `None`. Future integration requiring card data must rely on an Anti-Corruption Layer (ACL) or Integration Events.

### Dedicated Domain Exceptions
Generic host-language exceptions (e.g., Python's `ValueError`) have been entirely replaced with dedicated Domain Exceptions inheriting from `DomainException`. This ensures that the Domain layer remains pure, and higher layers can implement precise, semantic error handling and HTTP status code mapping.

### Immutable Audit Trail on Currency Mutation
When `UpdateAccountCurrencyCommand` changes an account’s operational currency, only the `Account` aggregate’s state is altered. Historical rows in the `transactions` table retain their original `currency_id`. This follows standard double-entry accounting principles, ensuring financial reports and reconciliation processes remain accurate for any point in time.

### Defensive Aggregate Mutations
The `Account` aggregate employs defensive programming patterns, such as clamping `pending_holds` at zero during a decrease operation (`max(Decimal('0.00'), ...)`). This ensures that eventual consistency issues, legacy data migrations, or out-of-order event processing cannot force the aggregate into an invalid negative-holds state, preserving the mathematical integrity of the ledger.