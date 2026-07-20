# MODULE DOCUMENTATION: CROSS-CONTEXT ADMINISTRATION DASHBOARD

**Version:** 2.2.1

---

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules](#2-business-rules)
3. [Backend Architecture](#3-backend-architecture)
4. [API Contract / Integration](#4-api-contract--integration)
5. [Execution Flows](#5-execution-flows)
6. [Edge Cases & Known Issues](#6-edge-cases--known-issues)
7. [Architectural Notes & Rejected Decisions](#7-architectural-notes--rejected-decisions)
8. [Complete File Index (100% Coverage)](#8-complete-file-index)

---

## 1. Overview

The Administration Dashboard is a **Server-Side Rendered (SSR) Cross-Context Administration UI** built with Flask Blueprints. It is the central back-office tool for administrators to manage the entire state of the `Paymenter` Modular Monolith. The dashboard directly invokes Application Services across **both `Identity` and `Ledger`** bounded contexts.

*   **Delivery Mechanism:** Standard HTML forms, server-rendered via `render_template`, using the Post/Redirect/Get (PRG) pattern.
*   **Authentication:** None at the application layer. Security relies entirely on network perimeter controls (Internal VPN, WAF, reverse proxy).
*   **Nature:** This module is a **Simulator**. Card numbers are generated locally using the Luhn algorithm and are not linked to any real payment network. Fund movements occur entirely within the in-process Ledger context.
*   **v2.2.1 Evolution:** The system has achieved strict cross-context event chaining. The legacy `AccountProvisioningPort` has been entirely purged to eliminate architectural contradictions. All account creation now strictly flows through the Ledger's `CreateAccountHandler`, triggering a deterministic, multi-step event chain that provisions Luhn-valid cards and updates read models with absolute referential integrity.

---

## 2. Business Rules

### 1. Specification (WHAT)
*   **Deterministic Currency Bootstrap Invariant:** Every time a new Currency is created, the system **must** automatically generate a System Escrow Account. To guarantee idempotency across network retries, the **Domain Account Number** is deterministically calculated using a **SHA-256 hash of the currency code** (modulo 10 billion, zero-padded to 10 digits). The database Primary Key is a random UUID.
*   **Automatic Card Provisioning (Event-Driven Chain):** When an Account is created, `CreateAccountHandler` emits `AccountCreatedEvent`. The Identity context's `OnAccountCreatedHandler` intercepts this, generates a 16-digit Luhn-valid Card Number, persists it in `user_cards` using the exact Ledger UUID, and emits `CardAssignedEvent`. **System Escrow accounts (`user_id=None`, `merchant_id=None`) are strictly excluded** from card provisioning.
*   **Financial Precision & Currency Isolation:** The `Money` Value Object strictly enforces `Decimal` precision (quantized to `0.01`) and mathematically prohibits arithmetic operations (`__add__`, `__sub__`) between different `CurrencyCode` instances, raising `CurrencyMismatchError`.
*   **Zero-State Currency Change:** An account's currency can only be changed if its `balance`, `pending_holds`, and `open_authorizations` are all exactly zero. The `Account.change_currency()` method enforces these domain invariants.
*   **Optimistic Concurrency with Exponential Backoff:** The `Account` aggregate uses version-based optimistic locking. The `UpdateAccountCurrencyHandler` implements a retry loop (max 3 attempts) with exponential backoff to gracefully handle transient `ConcurrencyException` collisions.
*   **Strict Transaction State Machine:** The `Transaction` entity enforces a strict lifecycle: `Pending` $\rightarrow$ `Success`/`Failed` $\rightarrow$ `Refunded`. Any attempt to mutate a transaction outside this state graph raises `InvalidTransactionStateError`.
*   **Strict Identity Uniqueness:**
    *   `users.phone_email` must be globally unique.
    *   `merchants.api_key` must be globally unique (`pay_` prefix + 43 URL-safe chars).
    *   `accounts.account_number` must be globally unique (10 digits).
    *   `user_cards.card_number` must be globally unique (16 digits, Luhn-valid).
*   **No Direct Data Manipulation:** The dashboard controller never imports SQLAlchemy, raw SQL, or repositories. All mutations are delegated to Application Handlers via the DI Container.

### 2. Rationale & Trade-offs (WHY)
*   **Why purge `LedgerAccountProvisioningAdapter`?** It relied on auto-increment IDs and raw SQL, bypassing the `Money` VO and UUID generation. Removing it eliminates a critical architectural contradiction, ensuring 100% of account creation flows through the Ledger bounded context.
*   **Why clamp `decrease_holds` at zero?** In an evolving system, legacy transactions might not have initialized holds. Clamping ensures backward compatibility and prevents pipeline crashes.
*   **Why zero-state for currency change?** Changing the currency of an account with active holds would silently re-denominate the held funds. The aggregate strictly prevents this catastrophic state corruption.

### 3. Rejected Alternatives
*   **Rejected:** *Using DB Auto-Increment sequences for Ledger Primary Keys.* (Reason: Tightly couples domain to SQLite; UUIDs prepare for microservice extraction).
*   **Rejected:** *Keeping the `AccountProvisioningPort` for backward compatibility.* (Reason: Dead code creates ambiguity. Strict purging enforces SSOT purity).

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)

*   **Delivery Layer (Controller):**
    *   File: `src/identity/infrastructure/web/dashboard_controller.py`
    *   Flask Blueprint registered at `/dashboard`. Catches `Exception` (which maps to `DomainException` subclasses) and bubbles exact error messages to UI flash alerts.
*   **Dependency Injection (Composite Container):**
    *   `src/app/di_container.py`: Central `DIContainer`. Instantiates `InMemoryEventBus`, then delegates to `register_identity` and `register_ledger`.
    *   **Crucial Wiring:** Event subscribers are wired with their own independent `SqliteUnitOfWork` instances to prevent cross-context read-model failures from rolling back core domain transactions.
*   **Unit of Work (Nested Transactions & PRAGMAs):**
    *   `src/common/infrastructure/persistence/sqlite_unit_of_work.py`
    *   Tracks `_nesting_level` to support nested `with uow:` blocks.
    *   Enforces `PRAGMA foreign_keys = ON;` and `PRAGMA journal_mode=WAL;` on connection initialization to guarantee referential integrity and concurrent read performance.
*   **Event Bus (Synchronous In-Memory):**
    *   `src/common/infrastructure/event_bus.py`: `Dict[type, List[Callable]]` subscriber registry.

**Complete DDL (Identity + Ledger - v2.2.1 Verified):**
```sql
-- IDENTITY SCHEMA
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    name TEXT NOT NULL, 
    phone_email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    merchant_id INTEGER,
    account_id TEXT NOT NULL,  -- UUID from Ledger Context
    card_number TEXT NOT NULL UNIQUE, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS user_summaries (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone_email TEXT NOT NULL,
    account_id TEXT,
    account_number TEXT,
    card_number TEXT,
    balance TEXT DEFAULT '0.00',
    currency_code TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- LEDGER SCHEMA
CREATE TABLE IF NOT EXISTS currencies (
    id TEXT PRIMARY KEY,  -- Application-generated UUID
    name TEXT NOT NULL, 
    code TEXT NOT NULL UNIQUE, 
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,  -- Application-generated UUID
    user_id INTEGER,  
    merchant_id INTEGER,
    currency_id TEXT NOT NULL, 
    account_number TEXT NOT NULL UNIQUE, 
    balance INTEGER NOT NULL DEFAULT 0,  -- Stored as exact cents
    pending_holds INTEGER NOT NULL DEFAULT 0,
    open_authorizations INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 0, 
    FOREIGN KEY (user_id) REFERENCES users(id), 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id), 
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, 
    merchant_id INTEGER, 
    from_account_id TEXT NOT NULL, 
    to_account_id TEXT NOT NULL, 
    amount INTEGER NOT NULL, 
    currency_id TEXT NOT NULL, 
    status TEXT NOT NULL, 
    user_email TEXT, 
    version INTEGER NOT NULL DEFAULT 0, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (merchant_id) REFERENCES merchants(id), 
    FOREIGN KEY (from_account_id) REFERENCES accounts(id), 
    FOREIGN KEY (to_account_id) REFERENCES accounts(id), 
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);
```

### 2. Architectural Decisions (WHY)
*   **Why `INTEGER` for `balance` and `pending_holds` in SQLite?** SQLite's dynamic typing causes affinity issues with `TEXT` decimals. Storing financial values as exact integer cents guarantees absolute precision. The `SqliteAccountRepository` strictly encapsulates `_to_cents()` and `_from_cents()`, ensuring the Domain layer only ever interacts with `Decimal` via the `Money` VO.
*   **Why Independent UoW in Event Subscribers?** Subscribers instantiate their own `SqliteUnitOfWork()`. This ensures that if an Identity Read Model update fails, it does not roll back the critical Ledger account creation. This enforces eventual consistency boundaries.

### 3. Rejected Alternatives
*   **Rejected:** *Using `REAL` (Float) for financial columns.* (Reason: IEEE 754 rounding errors).
*   **Rejected:** *Sharing the exact same UoW instance across the Event Bus.* (Reason: Read-model failures would destroy core domain data).

---

## 4. API Contract / Integration

**Contract Type:** Internal HTML SSR via Flask Blueprint. **No JSON API.**  
**Base URL:** `/dashboard`  

**DTOs Returned to Templates:**
*   `UserSummaryDTO(user_id: int, name: str, phone_email: str, account_number: Optional[str], card_number: Optional[str], currency_code: Optional[str])`
*   `MerchantSummaryDTO(id: int, name: str, api_key: str, is_active: bool)`
*   `AccountSummary(id: str, user_id: int, user_name: str, currency_id: str, currency_code: str, account_number: str, balance: Decimal, pending_holds: Decimal, open_authorizations: int, card_number: Optional[str])`
*   `CurrencySummaryDTO(id: str, name: str, code: CurrencyCode, is_active: bool)`
*   `EscrowAccountSummary(id: str, currency_id: str, currency_code: str, account_number: str, balance: Decimal)`

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)

#### Flow A: Admin Creates a Currency (Idempotent UUID + Deterministic VO)
1. Admin submits form to `POST /dashboard/currencies/add`.
2. `CreateCurrencyHandler` generates a random UUID for the `Currency` aggregate ID, persists it, and commits.
3. Handler publishes `CurrencyCreatedEvent`.
4. **`EscrowBootstrapperEventHandler` intercepts the event with its own UoW:**
    * Generates the deterministic 10-digit `AccountNumber` using SHA-256.
    * Queries `AccountRepository.get_by_account_number()`.
    * **Idempotency Guard:** If the account number exists, the handler safely aborts.
    * If it doesn't exist, it generates a new UUID for the Escrow Account's Primary Key, creates the aggregate, and persists it.

#### Flow B: Admin Creates a User Account (Cross-Context UUID & Card Chain)
1. Admin submits form to `POST /dashboard/accounts/create`.
2. `CreateAccountHandler` generates a UUID (`uuid.uuid4().hex`) for the Account, persists it via `SqliteAccountRepository` (converting `Money` to cents), and publishes `AccountCreatedEvent(account_id: str, user_id: int, account_number: AccountNumber, currency_code: CurrencyCode)`.
3. **InMemoryEventBus synchronously triggers Identity subscribers:**
    * **Link 1 (Read Model):** `AccountCreatedReadModelHandler` updates `user_summaries` with the UUID `account_id`, `account_number`, and `currency_code`.
    * **Link 2 (Card Provisioning):** `OnAccountCreatedHandler` checks `if event.user_id is None`. Since it's a user, it generates a Luhn-valid card number via `generate_card_number()`, inserts it into `user_cards` using the exact Ledger UUID, and publishes `CardAssignedEvent(account_id: str, user_id: int, card_number: str)`.
4. **Link 3 (Card Read Model):** `CardAssignedReadModelHandler` catches `CardAssignedEvent` and updates the `card_number` in `user_summaries` matched precisely by `account_id`.

#### Flow C: Admin Attempts Currency Change with Concurrency Collision
1. Two admins attempt to change the currency of the same account simultaneously.
2. Admin A's `UpdateAccountCurrencyHandler` succeeds, incrementing the `version` column.
3. Admin B's handler attempts to `UPDATE ... WHERE version = ?`. SQLite returns `rowcount == 0`.
4. `SqliteAccountRepository` raises `ConcurrencyException`.
5. The `while True` loop in the handler catches the exception, increments `attempt`, sleeps for `0.1s * (2^attempt)`, and retries.
6. On retry, Admin B's handler fetches the fresh aggregate, validates invariants, and successfully commits.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)

*   **Scenario 1: Event Bus Partial Failure (Split Transaction)**
    *   Admin creates a Currency. The `CreateCurrencyHandler` commits the Currency to the DB.
    *   The `CurrencyCreatedEvent` fires, but the `EscrowBootstrapperEventHandler` encounters a database lock and fails.
    *   **Impact:** The system now has a Currency without an Escrow account. Because Event Subscribers use independent UoWs, this is an accepted trade-off. Manual admin intervention or a background reconciliation job is required.
*   **Scenario 2: Cross-Currency Arithmetic Prevention**
    *   A developer attempts to add `Money(10.00, 'USD')` to `Money(5.00, 'EUR')` inside an application handler.
    *   **Impact:** The `Money` VO's `__add__` method immediately raises `CurrencyMismatchError`, preventing catastrophic silent ledger imbalances.
*   **Scenario 3: Legacy Transaction Hold Settlement**
    *   `account.decrease_holds()` is called on an account where `pending_holds` is already `0`.
    *   `max(Decimal('0.00'), 0.00 - 50.00)` evaluates to `0.00`.
    *   **Impact:** The system gracefully clamps the holds at zero instead of crashing or throwing negative holds.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Strict Aggregate Invariants:** The `Account` entity enforces currency matching on all mutations via the `Money` Value Object.
*   **Cents-based Persistence:** The Repository pattern strictly hides the `INTEGER` cents implementation detail from the Domain layer.
*   **UUID Propagation:** The transition to Application-layer UUIDs in the Ledger context is fully isolated. The Identity context retains `INTEGER` auto-increment IDs for Users and Merchants.
*   **Transaction State Machine:** The `Transaction` entity strictly guards its lifecycle via factory methods (`create_pending`) and state-transition methods (`mark_as_success`, `mark_as_failed`), raising `InvalidTransactionStateError` on illegal transitions.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Using a global `try/except DomainException` block in a Flask error handler.*
    *   **Reason:** For an SSR dashboard using `flash()`, catching exceptions locally within the route functions allows for precise redirection logic (`redirect(request.referrer)`) that a global error handler would complicate.
*   **Rejected:** *Retaining `LedgerAccountProvisioningAdapter` for legacy support.*
    *   **Reason:** It bypassed the `Money` VO, used auto-increment IDs, and lacked event publishing. Keeping it would violate the SSOT principle and introduce severe architectural contradictions. It has been entirely purged.