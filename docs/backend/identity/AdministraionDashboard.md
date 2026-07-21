# MODULE DOCUMENTATION: CROSS-CONTEXT ADMINISTRATION DASHBOARD & FINANCIAL CORE

**Version:** 2.4.0

---

## Table of Contents
1. [Overview](#1-overview)
2. [Business Rules](#2-business-rules)
3. [Backend Architecture](#3-backend-architecture)
4. [API Contract / Integration](#4-api-contract--integration)
5. [Execution Flows](#5-execution-flows)
6. [Edge Cases & Known Issues](#6-edge-cases--known-issues)
7. [Architectural Notes & Rejected Decisions](#7-architectural-notes--rejected-decisions)

---

## 1. Overview

The Administration Dashboard is a **Server-Side Rendered (SSR) Cross-Context Administration UI** built with Flask Blueprints. It serves as the central back-office control plane for administrators to manage the entire state of the `Paymenter` Modular Monolith. The dashboard directly invokes Application Services across the **`Identity`**, **`Ledger`**, and **`Webhook`** bounded contexts.

*   **Delivery Mechanism:** Standard HTML forms, server-rendered via `render_template`, strictly utilizing the Post/Redirect/Get (PRG) pattern to prevent duplicate form submissions.
*   **Authentication:** None at the application layer. Security relies entirely on strict network perimeter controls (Internal VPN, WAF, reverse proxy).
*   **Nature:** This module operates as a **Closed-Loop Financial Ledger Emulator**. Card numbers are generated locally using the Luhn algorithm to maintain strict deterministic validation parity with external payment networks, without relying on external I/O. Fund movements occur entirely within the in-process Ledger context, guaranteeing absolute mathematical isolation and deterministic state verification.
*   **v2.4.0 Evolution:** The system now features a complete **Three-Party Escrow Transaction Engine** and a robust **Merchant Webhook Configuration Subsystem**. The infrastructure has been fully standardized around **Ambient Transaction Management** via Python's `contextvars`. Application Handlers no longer explicitly invoke database commits; instead, they rely entirely on the implicit commit boundary of the Unit of Work (UoW) context manager, allowing deep domain services and synchronous event subscribers to participate in strictly atomic transactions.

---

## 2. Business Rules

### 1. Specification (WHAT)

#### Financial Core (Ledger Context)
*   **Three-Party Escrow Mechanics:** All fund movements utilize a strict double-entry escrow model. 
    *   *Hold:* Payer's balance decreases, Payer's `pending_holds` increase, System Escrow balance increases.
    *   *Complete:* Payer's `pending_holds` decrease, System Escrow balance decreases, Payee's balance increases.
    *   *Fail/Refund:* Reverses the exact mathematical legs depending on whether the transaction was `Pending` or `Success`.
*   **Deterministic Currency Bootstrap Invariant:** Every time a new Currency is created, the system **must** automatically generate a System Escrow Account. The **Domain Account Number** is deterministically calculated using a **SHA-256 hash of the currency code** (modulo 10 billion, zero-padded to 10 digits) to guarantee absolute idempotency across network retries.
*   **Financial Precision & Currency Isolation:** The `Money` Value Object strictly enforces `Decimal` precision (quantized to `0.01`) and mathematically prohibits arithmetic operations (`__add__`, `__sub__`) between different `CurrencyCode` instances, raising `CurrencyMismatchError`.
*   **Zero-State Currency Change:** An account's currency can only be changed if its `balance`, `pending_holds`, and `open_authorizations` are all exactly zero. The `Account.change_currency()` method strictly enforces these domain invariants to prevent catastrophic silent ledger imbalances.
*   **Strict Transaction State Machine:** The `Transaction` entity enforces a strict lifecycle: `Pending` $\rightarrow$ `Success`/`Failed` $\rightarrow$ `Refunded`. Any attempt to mutate a transaction outside this state graph raises `InvalidTransactionStateError`.

#### Identity & Webhook Context
*   **Webhook Configuration Invariants:** 
    *   A webhook cannot be enabled without providing a valid, absolute URL (enforced by the `WebhookUrl` Value Object via `urllib.parse`).
    *   Webhook secrets must be cryptographically secure (`whsec_` prefix + 32 URL-safe bytes) and minimum 20 characters.
*   **Automatic Card Provisioning (Event-Driven Chain):** When an Account is created, `CreateAccountHandler` emits `AccountCreatedEvent`. The Identity context's `OnAccountCreatedHandler` intercepts this, generates a 16-digit Luhn-valid Card Number, persists it, and emits `CardAssignedEvent`. **System Escrow accounts are strictly excluded** from card provisioning.
*   **Strict Identity Uniqueness:**
    *   `users.phone_email` must be globally unique (E.164 or RFC-compliant email).
    *   `merchants.api_key` must be globally unique (`pay_` prefix + 43 URL-safe chars).
    *   `accounts.account_number` must be globally unique (10 digits).
    *   `user_cards.card_number` must be globally unique (16 digits, Luhn-valid).
*   **No Direct Data Manipulation:** The dashboard controller never imports SQLAlchemy, raw SQL, or repositories. All mutations are delegated to Application Handlers via the DI Container.

### 2. Rationale & Trade-offs (WHY)
*   **Why Three-Party Escrow?** Direct wallet-to-wallet transfers cannot safely handle asynchronous merchant fulfillment. Escrow ensures funds are mathematically secured before the merchant is notified, preventing double-spend and insufficient funds race conditions.
*   **Why purge `LedgerAccountProvisioningAdapter`?** It relied on auto-increment IDs and raw SQL, bypassing the `Money` VO. Removing it ensures 100% of account creation flows through the Ledger bounded context, maintaining the Single Source of Truth (SSOT).
*   **Why clamp `decrease_holds` at zero?** In an evolving system, legacy transactions might not have initialized holds. Clamping ensures backward compatibility and prevents pipeline crashes without corrupting the ledger.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)

*   **Delivery Layer (Controller):** Flask Blueprint registered at `/dashboard`. Catches `DomainException` subclasses and bubbles exact error messages to UI flash alerts.
*   **Implicit Ambient Transaction Management:** The `SqliteUnitOfWork` utilizes Python's `contextvars` to manage nested transactions and ambient connections. Application Handlers (e.g., `CreateCurrencyHandler`, `UpdateAccountCurrencyHandler`) **no longer explicitly invoke `commit()`**. They rely entirely on the `__exit__` method of the context manager to automatically commit or rollback the ambient transaction. This strictly enforces `PRAGMA foreign_keys = ON` and `journal_mode=WAL` at the connection boundary.
*   **Dependency Injection (Composite Container):** Central `DIContainer` instantiates `InMemoryEventBus`, then delegates to context-specific registration functions.
*   **Event Bus (Synchronous In-Memory Atomicity):** Subscribers instantiate their own `SqliteUnitOfWork`, but due to the Ambient Transaction pattern (`contextvars`), they seamlessly detect and **join the parent's active database transaction**. This guarantees strict atomic consistency for synchronous in-memory event chains; if a subscriber fails, the parent transaction rolls back.

**Complete DDL (Identity + Ledger + Webhook - v2.4.0 Verified):**
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
    is_active BOOLEAN NOT NULL DEFAULT 1,
    webhook_url TEXT,
    webhook_secret TEXT,
    webhook_enabled BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    merchant_id INTEGER,
    account_id TEXT NOT NULL, 
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

CREATE TABLE IF NOT EXISTS merchant_summaries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    webhook_url TEXT,
    webhook_enabled BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (id) REFERENCES merchants(id)
);

-- LEDGER SCHEMA
CREATE TABLE IF NOT EXISTS currencies (
    id TEXT PRIMARY KEY, 
    name TEXT NOT NULL, 
    code TEXT NOT NULL UNIQUE, 
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, 
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

-- WEBHOOK SCHEMA
CREATE TABLE IF NOT EXISTS webhook_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP,
    next_attempt_at TIMESTAMP,
    signature TEXT NOT NULL,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
CREATE INDEX IF NOT EXISTS idx_webhook_outbox_status ON webhook_outbox(status, next_attempt_at);
```

### 2. Architectural Decisions (WHY)
*   **Why `INTEGER` for `balance` and `pending_holds` in SQLite?** SQLite's dynamic typing causes affinity issues with `TEXT` decimals. Storing financial values as exact integer cents guarantees absolute precision. The Repository pattern strictly encapsulates `_to_cents()` and `_from_cents()`.
*   **Why Ambient Transactions for Event Subscribers?** By leveraging `contextvars`, newly instantiated `SqliteUnitOfWork` objects inside event handlers automatically detect and join the active ambient connection. This ensures that if a synchronous subscriber (like the Escrow Bootstrapper) fails, the exception propagates and the **entire parent transaction rolls back**. This prevents partial state mutations (Split Transactions) and guarantees strict ACID compliance for in-process event chains.

---

## 4. API Contract / Integration

**Contract Type:** Internal HTML SSR via Flask Blueprint. **No JSON API.**  
**Base URL:** `/dashboard`  

**DTOs Returned to Templates:**
*   `UserSummaryDTO(user_id, name, phone_email, account_number, card_number, currency_code)`
*   `MerchantSummaryDTO(id, name, api_key, is_active, webhook_url, webhook_enabled)`
*   `WebhookStatusDTO(webhook_url, webhook_enabled)`
*   `AccountSummary(id, user_id, user_name, currency_id, currency_code, account_number, balance, pending_holds, open_authorizations, card_number)`
*   `CurrencySummaryDTO(id, name, code, is_active)`
*   `EscrowAccountSummary(id, currency_id, currency_code, account_number, balance)`
*   `TransactionListItem(id, amount, currency_code, status, created_at, user_email, from_account_number, to_account_number)`

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)

#### Flow A: Three-Party Escrow Fund Hold & Completion
1.  **Hold:** `HoldFundsHandler` invokes `DoubleEntryLedger.hold_funds()`. Payer's balance decreases, Payer's `pending_holds` increase, and the System Escrow account balance increases. A `Pending` Transaction is persisted. The ambient UoW commits upon clean exit.
2.  **Complete:** `CompleteFundsHandler` invokes `DoubleEntryLedger.complete_funds()`. The Transaction transitions to `Success`. Payer's `pending_holds` decrease, Escrow balance decreases, and Payee's balance increases. `TransactionCompletedEvent` is published inside the UoW block. The ambient UoW commits atomically.

#### Flow B: Admin Configures Merchant Webhook (Event-Driven Projection)
1.  Admin submits form to `POST /dashboard/merchants/<id>/webhook/configure`.
2.  `ConfigureWebhookHandler` loads the `Merchant` aggregate, invokes `merchant.configure_webhook()` (which enforces URL validation via the `WebhookUrl` VO), and persists the state.
3.  Handler publishes `MerchantWebhookConfiguredEvent`.
4.  **`MerchantWebhookConfiguredReadModelHandler` intercepts the event:**
    *   Joins the ambient transaction and updates the `merchant_summaries` read model table with the new `webhook_url` and `webhook_enabled` state.
    *   The entire operation (Write Model + Read Model) commits atomically upon exiting the handler's UoW block.

#### Flow C: Admin Creates a Currency (Idempotent UUID + Deterministic VO)
1.  Admin submits form to `POST /dashboard/currencies/add`.
2.  `CreateCurrencyHandler` generates a random UUID, persists the `Currency`, and publishes `CurrencyCreatedEvent`. (Commit is deferred to the ambient boundary).
3.  **`EscrowBootstrapperEventHandler` intercepts the event:**
    *   Joins the ambient transaction.
    *   Generates the deterministic 10-digit `AccountNumber` using SHA-256.
    *   **Idempotency Guard:** If the account number exists, the handler safely aborts.
    *   If it doesn't exist, it creates the System Escrow Account and persists it.
4.  Upon exiting the outer UoW block, the entire chain (Currency + Escrow Account) is committed atomically.

#### Flow D: Admin Creates a User Account (Cross-Context UUID & Card Chain)
1.  `CreateAccountHandler` generates a UUID, persists the Account, and publishes `AccountCreatedEvent`.
2.  **InMemoryEventBus synchronously triggers Identity subscribers (all joining the ambient transaction):**
    *   **Link 1 (Read Model):** `AccountCreatedReadModelHandler` updates `user_summaries`.
    *   **Link 2 (Card Provisioning):** `OnAccountCreatedHandler` generates a Luhn-valid card number, inserts it into `user_cards`, and publishes `CardAssignedEvent`.
    *   **Link 3 (Card Read Model):** `CardAssignedReadModelHandler` updates the `card_number` in `user_summaries`.
3.  The ambient UoW commits all cross-context mutations atomically.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)

*   **Scenario 1: Strict Atomic Rollback on Subscriber Failure**
    *   Admin creates a Currency. The `CreateCurrencyHandler` publishes `CurrencyCreatedEvent`. The `EscrowBootstrapperEventHandler` encounters a database constraint violation or error.
    *   **Impact:** Because the event handler joins the ambient transaction via `contextvars`, the exception propagates to the outer `with self._uow:` block. The entire transaction is rolled back. The Currency is **not** created. This prevents "Split Transactions" and ensures the ledger never exists in a state where a Currency lacks its mandatory Escrow account.
*   **Scenario 2: Cross-Currency Arithmetic Prevention**
    *   A developer attempts to add `Money(10.00, 'USD')` to `Money(5.00, 'EUR')`.
    *   **Impact:** The `Money` VO's `__add__` method immediately raises `CurrencyMismatchError`, preventing catastrophic silent ledger imbalances.
*   **Scenario 3: Webhook Secret Flash Exposure**
    *   The `GenerateWebhookSecretHandler` returns the plain-text secret, which is flashed to the UI via the PRG pattern.
    *   **Impact:** In a production environment, secrets should be hashed and shown via a secure, one-time-view mechanism. For this closed-loop environment, flashing is an acceptable, deliberate trade-off for immediate UI verification.
*   **Scenario 4: Legacy Transaction Hold Settlement**
    *   `account.decrease_holds()` is called on an account where `pending_holds` is already `0`.
    *   **Impact:** The system gracefully clamps the holds at zero (`max(Decimal('0.00'), ...)`) instead of throwing negative holds.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Implicit Ambient Transactions (`contextvars`):** The `SqliteUnitOfWork` uses `contextvars` to track the active connection and nesting level. Application Handlers rely entirely on the `__exit__` context manager boundary for commits. This allows the `DoubleEntryLedger` domain service and synchronous event subscribers to mutate multiple aggregates atomically without requiring the UoW to be explicitly passed through every method signature or explicitly committed, preserving domain purity.
*   **Strict Aggregate Invariants:** The `Account` entity enforces currency matching on all mutations via the `Money` Value Object.
*   **Cents-based Persistence:** The Repository pattern strictly hides the `INTEGER` cents implementation detail from the Domain layer.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Direct Wallet-to-Wallet Transfers.* 
    *   **Reason:** Fails to handle asynchronous merchant fulfillment securely. The Three-Party Escrow model mathematically guarantees funds are secured before external state changes occur.
*   **Rejected:** *Explicit UoW Injection and Explicit Commits in Domain Services/Handlers.* 
    *   **Reason:** Pollutes domain method signatures with infrastructure concerns and risks premature commits before event subscribers finish their work. Ambient transactions via `contextvars` combined with implicit `__exit__` commits provide a cleaner, strictly atomic, and orthogonal architecture.
*   **Rejected:** *Using a global `try/except DomainException` block in a Flask error handler.*
    *   **Reason:** For an SSR dashboard using `flash()`, catching exceptions locally within the route functions allows for precise redirection logic (`redirect(request.referrer)`) that a global error handler would complicate.