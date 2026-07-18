# Account & Currency Module

**Version:** 1.0.0 (SSOT)  

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules & Invariants](#2-business-rules--invariants)
3. [Backend Architecture](#3-backend-architecture)
4. [Execution Flows](#4-execution-flows)
5. [Edge Cases & Known Issues](#5-edge-cases--known-issues)
6. [Architectural Notes & Trade-offs](#6-architectural-notes--trade-offs)

---

## 1. Overview
The Account & Currency module is responsible for the lifecycle of financial accounts and the currencies in which they operate. It is a self-contained part of the `ledger` Bounded Context, built on Domain-Driven Design and Clean Architecture. This module enforces critical invariants such as the non-negative balance rule for standard withdrawals and the zero-balance prerequisite for currency mutation. It also owns the deterministic bootstrapping of System Escrow accounts whenever a new currency is introduced, ensuring that every currency has an operational escrow facility from the moment of creation. The module exposes no HTTP endpoints directly; its capabilities are consumed by the Transaction & Settlement module and internal administrative processes through Application-layer use cases.

---

## 2. Business Rules & Invariants
All rules listed here are non-negotiable and enforced at the aggregate level.

- **BR-1: Non-Negative Balance Invariant (Standard Withdrawals)**  
  The `Account.withdraw()` method guarantees that an account's balance can never fall below zero. Any attempt to withdraw more than the available balance results in an `InsufficientFundsError`. This invariant is essential for all standard operations and must be respected by any flow that debits an account, including transaction holds.

- **BR-3: Currency Mutation Invariant**  
  An account's currency may only be changed if its current balance is exactly `0.00`. The `Account.change_currency()` method enforces this rule. A non-zero balance triggers a `ValueError`, preventing inconsistent historical records.

- **BR-6: Deterministic Escrow Bootstrapping**  
  The moment a new `Currency` aggregate is persisted, the system automatically creates a corresponding System Escrow account. The escrow account number is deterministically derived using the formula `9000000000 + currency_id`. This guarantees a one-to-one mapping between currencies and their escrow containers, and it removes the need for manual escrow account setup.

- **BR-7: Zero Primitive Obsession**  
  All financial quantities and identifiers crossing layer boundaries are expressed through strict Value Objects. Balances and amounts use `Money(Decimal, CurrencyCode)`, and account identifiers are represented by `AccountNumber`, which enforces a rigid 10‑digit format. Raw primitives such as strings or floats are forbidden in Domain and Application layers.

---

## 3. Backend Architecture

### 3.1. Domain Layer (Core)
*Zero external dependencies. Pure Python.*

- **Aggregates**
  - `Account` – Controls balance mutations (`deposit`, `withdraw`, `apply_system_reversal`), currency mutation (`change_currency`), and identity via `AccountNumber`.
  - `Currency` – Represents a tradable currency with `code`, `name`, and active status. Creation triggers the escrow bootstrapping side effect via a domain service.

- **Value Objects**
  - `AccountNumber` – Validates a 10‑digit string, rejecting any malformed input.
  - `Money` – Holds a `Decimal` amount and a `CurrencyCode`. Enforces same‑currency checks on arithmetic operations.
  - `CurrencyCode` – Immutable three‑letter ISO code.

- **Domain Services**
  - `EscrowBootstrapper` – Generates the escrow account number from a currency’s ID, instantiates the escrow `Account` aggregate, and marks it as a system account. This service is called during currency creation to satisfy BR-6.

- **Domain Events**
  - `AccountCreatedEvent`
  - `CurrencyActivatedEvent`
  - `CurrencyDeactivatedEvent`

- **Ports**
  - `SystemAccountResolverPort` – Abstract interface for retrieving a system escrow account by currency. While primarily consumed by the Transaction & Settlement module, its contract is defined here to allow the domain service to verify that a bootstrapped account can later be resolved.

### 3.2. Application Layer (Orchestration)
*Use Cases, CQRS, and DTOs.*

- **Commands & Handlers**
  - `CreateCurrencyCommand` / `CreateCurrencyHandler` – Accepts currency attributes, invokes `EscrowBootstrapper`, persists the new `Currency` and the escrow `Account` within a single atomic transaction.
  - `UpdateAccountCurrencyCommand` / `UpdateAccountCurrencyHandler` – Loads the `Account` aggregate, verifies BR-3, applies the currency change, and persists.

- **Queries & Handlers**
  - `GetAccountSummariesHandler` – Returns a collection of `AccountSummary` DTOs, optimized for list views.
  - `GetEscrowAccountSummaryHandler` – Returns `EscrowAccountSummary` for a given currency.

- **DTOs**
  - `AccountSummary` – Contains account ID, account number, balance, currency code, and a flag indicating escrow status.
  - `EscrowAccountSummary` – Similar to `AccountSummary` but focused on escrow metadata.

### 3.3. Infrastructure Layer (Adapters & Persistence)

Infrastructure details not explicitly defined here (exact column names, specific SQLite isolation levels) are considered Implementation Details to be determined at implementation time, provided they satisfy the Aggregate invariants defined in Section 2.

*Implementation details. Pluggable.*

- **Write Repositories**
  - `SqliteAccountRepository` – Persists `Account` aggregates. Implements Optimistic Concurrency Control (OCC) via a `version` column to prevent lost updates.
  - `SqliteCurrencyRepository` – Persists `Currency` aggregates with OCC.

- **Read Models**
  - `SqliteAccountReadModel` – Executes raw SQL queries, including cross-context JOINs (see Architectural Notes), to materialise `AccountSummary` and `EscrowAccountSummary` DTOs directly.

- **Unit of Work**
  - `SqliteUnitOfWork` – Shared across the entire `ledger` context. Manages atomic transactions (`commit`, `rollback`), enables `PRAGMA foreign_keys = ON`, and uses WAL journal mode.

- **Web Controllers**
  - None. Account and currency management is performed exclusively through internal command/query dispatch. No HTTP endpoints are exposed by this module.

---

## 4. Execution Flows

### Flow 1: Currency Creation with Escrow Bootstrapping
1. **Command dispatch:** `CreateCurrencyCommand` is built with the currency code and name.
2. **Handler execution (UoW):**
   - A new `Currency` aggregate is instantiated and added to the repository.
   - `EscrowBootstrapper` is called with the currency’s ID; it creates an `Account` marked as system escrow and inserts it via `AccountRepository`.
   - Both aggregates are persisted within the same unit of work.
3. **Commit:** `UnitOfWork.commit()` flushes both the currency and the escrow account.
4. **Event:** `CurrencyActivatedEvent` (if immediate activation is requested) is published after the commit.

### Flow 2: Account Currency Change
1. **Command dispatch:** `UpdateAccountCurrencyCommand` carrying the account ID and the target `CurrencyCode`.
2. **Handler execution:**
   - Loads the `Account` aggregate.
   - Invokes `Account.change_currency(new_currency)`. Internally, the aggregate checks BR-3 (balance must be zero) and raises `ValueError` if violated.
3. **Persistence:** The aggregate’s `version` is incremented; `SqliteAccountRepository.save()` updates the row.
4. **Commit:** `UnitOfWork.commit()` persists the change. The historical `transactions` table remains untouched, preserving the original currency of past entries (see Architectural Notes).

---

## 5. Edge Cases & Known Issues

### Issue 1: Unhandled ConcurrencyException on Account Mutations
**Description:** Both `SqliteAccountRepository` and `SqliteCurrencyRepository` enforce Optimistic Concurrency Control. Any concurrent modification of the same aggregate row results in a `ConcurrencyException`. While this module does not expose HTTP endpoints, internal processes (e.g., an admin tool or future API) that invoke commands like `UpdateAccountCurrencyCommand` could trigger this exception. There is no global exception handler registered in the Flask application for `ConcurrencyException`.  
**Impact:** The exception propagates as an unhandled error, leading to a generic 500 Internal Server Error in any HTTP context, or a crash in scripted environments.  
**Action Required:** A centralised error handler should translate `ConcurrencyException` into a 409 Conflict response where applicable. For non-HTTP invocations, the calling code must implement retry logic or surface the conflict appropriately.

### Issue 2: Hard Cap on Supported Currencies
**Description:** The escrow account number formula `9000000000 + currency_id` relies on the `currency_id` auto-increment value staying within 9 digits. The `AccountNumber` value object strictly enforces exactly 10 digits. If the `currencies` table ever assigns an ID of `1,000,000,000` (10 digits), the resulting string becomes 11 digits, causing `AccountNumber` instantiation to fail with a `ValueError`.  
**Impact:** Currency creation becomes impossible beyond 999,999,999 entries.  
**Limitation:** This is a theoretical ceiling. In the current simulation, currency creation is a deliberate, low-volume operation, making the cap acceptable. The limitation must be documented and revisited if the system moves to a production environment with automated currency seeding.

---

## 6. Architectural Notes & Trade-offs

### Cross-Context Read Model Exception (CQRS Read-Side JOINs)
Strict Bounded Context isolation (Constitution Rule #5) normally forbids direct cross-context data access. However, an explicit exception has been granted for CQRS Read Models. The `SqliteAccountReadModel.get_all_summaries()` performs a `LEFT JOIN` against the `user_cards` table, which resides in the `checkout`/`identity` context.  
**Rationale:** This trade-off eliminates N+1 queries when rendering UI views that combine account data with card ownership. The Read Model treats the entire SQLite database as a shared read-only data lake, enabling performant materialised views without corrupting the Write side’s transactional integrity.

### Immutable Audit Trail on Currency Mutation
When `UpdateAccountCurrencyCommand` changes an account’s operational currency, only the `Account` aggregate’s state is altered. Historical rows in the `transactions` table retain their original `currency_id`.  
**Rationale:** This follows standard double-entry accounting principles. The ledger must faithfully record the exact currency in which each transaction was settled, regardless of later configuration changes. The immutable audit trail ensures financial reports and reconciliation processes remain accurate for any point in time.