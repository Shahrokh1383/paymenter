# MODULE DOCUMENTATION: CROSS-CONTEXT ADMINISTRATION DASHBOARD

**Version:** 2.1.0 

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

The Administration Dashboard is a **Server-Side Rendered (SSR) Cross-Context Administration UI** built with Flask Blueprints. It is the central back-office tool for administrators to manage the entire state of the `Paymenter` Modular Monolith. Contrary to its original MVP scoping (Identity-only), the dashboard directly invokes Application Services across **both `Identity` and `Ledger`** bounded contexts.

*   **Delivery Mechanism:** Standard HTML forms, server-rendered via `render_template`, using the Post/Redirect/Get (PRG) pattern.
*   **Authentication:** None at the application layer. Security relies entirely on network perimeter controls (Internal VPN, WAF, reverse proxy).
*   **Nature:** This module is a **Simulator**. Card numbers are generated locally using the Luhn algorithm and are not linked to any real payment network. Fund movements occur entirely within the in-process Ledger context.

---

## 2. Business Rules

### 1. Specification (WHAT)
*   **Deterministic Currency Bootstrap Invariant:** Every time a new Currency is created, the system **must** automatically generate a System Escrow Account. To guarantee idempotency across network retries, the account number is deterministically calculated using a **SHA-256 hash of the currency code** (modulo 10 billion, zero-padded to 10 digits). This account has `user_id = NULL` and `merchant_id = NULL`.
*   **Automatic Card Provisioning (With Escrow Exclusion):** When an Account is created for a User or Merchant, a 16-digit Luhn-valid Card Number is automatically generated and persisted in the `user_cards` table. **System Escrow accounts (`user_id=None`, `merchant_id=None`) are strictly excluded** from this process to prevent assigning payment cards to system-owned buckets.
*   **Zero-State Currency Change:** An account's currency can only be changed if its `balance`, `pending_holds`, and `open_authorizations` are all exactly zero. The `Account.change_currency()` method enforces these domain invariants, raising `NonZeroBalanceCurrencyChangeError` or `PendingHoldsExistError` if violated.
*   **Pre-Authorization & Holds Tracking:** Accounts now track `pending_holds` (Money) and `open_authorizations` (int) to support pre-auth flows. The `decrease_holds()` method mathematically clamps at `0.00` to gracefully handle legacy transactions created before holds were tracked.
*   **Strict Identity Uniqueness:**
    *   `users.phone_email` must be globally unique (UNIQUE constraint in SQLite).
    *   `merchants.api_key` must be globally unique.
    *   `accounts.account_number` must be globally unique (10 digits).
    *   `user_cards.card_number` must be globally unique (16 digits, Luhn-valid).
*   **No Direct Data Manipulation:** The dashboard controller never imports SQLAlchemy, raw SQL, or repositories. All mutations are delegated to Application Handlers via the DI Container.

### 2. Rationale & Trade-offs (WHY)
*   **Why deterministic SHA-256 Escrow generation?** The original DB-sequence approach (`9000000000 + currency_id`) was vulnerable to race conditions and retry-duplication. Hashing the `currency_code` ensures the exact same Escrow account number is generated every time, allowing the handler to safely abort if the account already exists (Idempotency).
*   **Why exclude Escrow from card provisioning?** System Escrow accounts act as counter-parties for holds and settlements. Assigning a 16-digit Luhn card to a system bucket violates the conceptual model of a payment instrument and could cause routing errors in downstream authorization flows.
*   **Why clamp `decrease_holds` at zero?** In an evolving system, legacy transactions might not have initialized holds. If a settlement process attempts to decrease holds on an account where `pending_holds` is already `0.00`, throwing an exception would crash the settlement. Clamping ensures backward compatibility and system resilience.
*   **Why zero-state (balance + holds + auths) for currency change?** Changing the currency of an account with active holds would silently re-denominate the held funds (e.g., holding 100 USD, changing to EUR, and suddenly holding 100 EUR without exchange rate logic). The aggregate strictly prevents this catastrophic state corruption.

### 3. Rejected Alternatives
*   **Rejected:** *Using DB Auto-Increment sequences for Escrow Account Numbers.*
    *   **Reason:** Sequences are not idempotent. If a `CreateCurrency` command times out but succeeds in the DB, a retry would generate a second, orphaned Escrow account. SHA-256 hashing guarantees deterministic state.
*   **Rejected:** *Throwing exceptions when decreasing holds below zero.*
    *   **Reason:** Would break backward compatibility with legacy ledger entries. Clamping at `0.00` using `max(Decimal('0.00'), ...)` is a pragmatic, defensive approach that prevents pipeline crashes.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)

*   **Delivery Layer (Controller):**
    *   File: `src/identity/infrastructure/web/dashboard_controller.py`
    *   Flask Blueprint registered at URL prefix `/dashboard`.
    *   14 route functions (7 GET, 7 POST). Zero business logic. Catches `DomainException` and bubbles exact error messages to UI flash alerts.
*   **Dependency Injection (Composite Container):**
    *   `src/app/di_container.py`: Central `DIContainer` class. Instantiates `InMemoryEventBus`, then delegates to context-specific registration modules.
    *   `src/app/di/identity_di.py`: Binds 6 handler factory methods + 7 event subscriptions (includes Escrow exclusion guards).
    *   `src/app/di/ledger_di.py`: Binds 13 handler factory methods.
*   **Unit of Work (Nested Transactions):**
    *   `src/common/infrastructure/persistence/sqlite_unit_of_work.py`
    *   Tracks `_nesting_level` to support nested `with uow:` blocks.
    *   Commits only when outermost block exits without exception.
    *   PRAGMA settings: `foreign_keys = ON`, `journal_mode = WAL`.
*   **Event Bus (Synchronous In-Memory):**
    *   `src/common/infrastructure/event_bus.py`
    *   `Dict[type, List[Callable]]` subscriber registry.
    *   `publish()` iterates subscribers synchronously on the calling thread.
*   **Database Schema (Shared SQLite):**
    *   Single file: `src/common/infrastructure/database/storage/paymenter.db`
    *   Schema initialized by `Database.initialize()` orchestrating `IDENTITY + LEDGER + CHECKOUT + NOTIFICATIONS`.

**Complete DDL (Identity + Ledger - Updated):**
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
    account_id INTEGER NOT NULL,
    card_number TEXT NOT NULL UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS user_summaries (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone_email TEXT NOT NULL,
    account_id INTEGER,
    account_number TEXT,
    card_number TEXT,
    balance TEXT DEFAULT '0.00',
    currency_code TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS merchant_summaries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

-- LEDGER SCHEMA
CREATE TABLE IF NOT EXISTS currencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    merchant_id INTEGER,
    currency_id INTEGER NOT NULL,
    account_number TEXT NOT NULL UNIQUE,
    balance TEXT NOT NULL DEFAULT '0.00',
    pending_holds TEXT NOT NULL DEFAULT '0.00',
    open_authorizations INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (currency_id) REFERENCES currencies(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER,
    from_account_id INTEGER NOT NULL,
    to_account_id INTEGER NOT NULL,
    amount TEXT NOT NULL,
    currency_id INTEGER NOT NULL,
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
*   **Why `TEXT` for `balance` and `pending_holds` in SQLite?** SQLite lacks a native `DECIMAL` type. Storing exact string representations of `Decimal` objects prevents floating-point precision loss during financial calculations. The application layer strictly hydrates these into `Money` Value Objects.
*   **Why Broad Exception Catching in Controller?** The controller uses `except Exception as e: flash(str(e), 'error')`. Because domain exceptions (`PendingHoldsExistError`, `NonZeroBalanceCurrencyChangeError`) inherit from `DomainException` and contain user-friendly messages, this allows the UI to display exact invariant violations without cluttering the controller with domain-specific `if/else` mapping logic.

### 3. Rejected Alternatives
*   **Rejected:** *Using `REAL` (Float) for financial columns in SQLite.*
    *   **Reason:** IEEE 754 floating-point math introduces rounding errors that are unacceptable in double-entry bookkeeping. `TEXT` mapped to Python `Decimal` guarantees exact precision.

---

## 4. API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)

**Contract Type:** Internal HTML SSR via Flask Blueprint. **No JSON API.**  
**Base URL:** `/dashboard`  

*(Endpoints 1 through 13 remain structurally identical to v2.0.0, but the underlying DTOs and error messages have evolved).*

**DTOs Returned to Templates (Updated):**
*   `UserSummaryDTO(user_id: int, name: str, phone_email: str, account_number: Optional[str], card_number: Optional[str], currency_code: Optional[str])`
*   `MerchantSummaryDTO(id: int, name: str, api_key: str, is_active: bool)`
*   `AccountSummary(id: int, user_id: int, user_name: str, currency_id: int, currency_code: str, account_number: str, balance: Decimal, pending_holds: Decimal, open_authorizations: int, card_number: Optional[str])`
*   `CurrencySummaryDTO(id: int, name: str, code: CurrencyCode, is_active: bool)`
*   `EscrowAccountSummary(id: int, currency_id: int, currency_code: str, account_number: str, balance: Decimal)`

### 2. Contract Choices (WHY)
*   **Why expose `pending_holds` in the Read Model?** As the system evolves to support pre-authorizations (e.g., hotel bookings, rental holds), the admin dashboard must reflect the true state of the aggregate. Exposing `pending_holds` ensures the CQRS read side remains strictly consistent with the write side.

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)

#### Flow A: Admin Creates a Currency (Idempotent Escrow Bootstrap)
1. Admin submits form to `POST /dashboard/currencies/add` with `name="US Dollar"`, `code="USD"`.
2. Controller creates `SqliteUnitOfWork`, obtains `CreateCurrencyHandler`.
3. Handler validates `CurrencyCode("USD")` and checks `CurrencyRepository` for uniqueness.
4. Handler creates `Currency` aggregate and persists it.
5. **Handler auto-generates System Escrow Account:** Calculates SHA-256 hash of `"USD"`, modulo 10 billion, zero-padded to 10 digits (e.g., `"8493028471"`).
6. **Idempotency Check:** Handler queries `AccountRepository.get_by_account_number("8493028471")`. If it exists (due to a previous retry), the handler safely aborts the Escrow creation step.
7. If it doesn't exist, Handler creates `Account` aggregate with `user_id=None, merchant_id=None, balance=Money('0.00', 'USD'), pending_holds=Money('0.00', 'USD'), open_authorizations=0`.
8. Handler persists escrow account and publishes `CurrencyCreatedEvent`.
9. Controller commits UoW. Redirects to `GET /dashboard/currencies`.

#### Flow B: Admin Creates a User Account (Escrow Exclusion in Subscribers)
1. Admin submits form to `POST /dashboard/accounts/create` with `owner_id="user_5"`, `currency_code="USD"`.
2. Controller obtains `CreateAccountHandler`, which creates the `Account`, persists it, and publishes `AccountCreatedEvent`.
3. **InMemoryEventBus synchronously triggers subscribers:**
    *   **Subscriber 1 (`AccountCreatedReadModelHandler`):** Checks `if event.user_id is None: return`. Since `user_id=5`, it proceeds to update `user_summaries`. *(If this were an Escrow account, it would abort here).*
    *   **Subscriber 2 (`OnAccountCreatedHandler`):** Checks `if event.user_id is None and event.merchant_id is None: return`. Since it's a user account, it proceeds to generate a Luhn card and insert into `user_cards`. *(Escrow accounts are strictly blocked from receiving cards).*
    *   **Subscriber 3 (`CardAssignedReadModelHandler`):** Updates `user_summaries` with the new card number.
4. Controller commits UoW. Redirects to `GET /dashboard/accounts`.

#### Flow C: Admin Attempts Currency Change on Account with Holds
1. Admin submits `POST /dashboard/accounts/update-currency` for an account that has `balance='0.00'` but `pending_holds='50.00'`.
2. Controller obtains `UpdateAccountCurrencyHandler`.
3. Handler fetches `Account` aggregate.
4. Handler calls `account.change_currency("EUR")`.
5. Aggregate evaluates `can_change_currency()`. `balance` is 0, but `pending_holds` > 0.
6. Aggregate raises `PendingHoldsExistError("Cannot change currency on an account with pending holds or authorizations.")`.
7. Controller catches exception, flashes the exact string message to the UI, and redirects. No state mutation occurs.

### 2. Sequence Justification (WHY)
*   **Why check `user_id is None` in Read Model handlers?** The `user_summaries` table is strictly an Identity context read model designed to map Users to their Accounts. System Escrow accounts do not belong to users. Attempting to update `user_summaries` with an Escrow account ID would result in SQL errors or logical corruption. The guard clause ensures cross-context events only mutate relevant read models.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)

*   **Scenario 1: Idempotent Currency Creation (Network Retry)**
    *   Admin clicks "Add Currency". The request hits the server, creates the Currency and the SHA-256 Escrow account, but the HTTP response times out before reaching the browser.
    *   The browser automatically retries the POST request.
    *   The second request hits `CreateCurrencyHandler`. It generates the exact same SHA-256 Escrow account number, queries the DB, finds the existing account, and safely skips the insertion.
    *   **Impact:** Zero duplicate Escrow accounts. Data integrity is preserved despite network instability.

*   **Scenario 2: Currency Change on Active Holds**
    *   Admin attempts to change the currency of a merchant account that currently has a pre-authorization hold pending.
    *   `Account.change_currency()` detects `pending_holds.amount != 0`.
    *   Raises `PendingHoldsExistError`.
    *   **Impact:** Controller flashes "Cannot change currency on an account with pending holds or authorizations." Prevents silent re-denomination of held funds.

*   **Scenario 3: Legacy Transaction Hold Settlement**
    *   A background settlement process attempts to decrease holds on an account created before the `pending_holds` column was introduced (where holds were implicitly zero but not tracked).
    *   `account.decrease_holds(Money('50.00', 'USD'))` is called.
    *   `max(Decimal('0.00'), 0.00 - 50.00)` evaluates to `0.00`.
    *   **Impact:** The system gracefully clamps the holds at zero instead of throwing a `NegativeHoldsError` or crashing the settlement pipeline.

*   **Scenario 4: Concurrent Account Modification (Optimistic Lock Failure)**
    *   Two admins simultaneously top up the same account.
    *   First admin's `AccountRepository.update()` succeeds (version match), increments `version`.
    *   Second admin's `update()` finds `rowcount == 0` (version mismatch), raises `ConcurrencyException`.
    *   **Impact:** Second admin sees a flash error. Must reload the page and retry. No lost updates.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Strict Aggregate Invariants:** The `Account` entity is now a robust payment instrument. It enforces currency matching on all mutations (`withdraw`, `deposit`, `topup`, `increase_holds`, `decrease_holds`) via the `CurrencyMismatchError`.
*   **Cross-Context Event Guards:** Subscribers in the Identity context (`OnAccountCreatedHandler`, `AccountCreatedReadModelHandler`) explicitly filter out Ledger events originating from System Escrow accounts (`user_id is None`). This prevents Identity read-models and card-provisioning logic from polluting system-level buckets.
*   **Exact Exception Bubbling:** Domain exceptions are designed with user-facing strings. The Flask controller's broad `except Exception` block safely surfaces these exact strings to the admin UI, maintaining a strict separation of concerns while providing excellent UX feedback.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Using a global `try/except DomainException` block in a Flask error handler.*
    *   **Reason:** While cleaner for APIs, for an SSR dashboard using `flash()`, catching exceptions locally within the route functions allows for precise redirection logic (e.g., `redirect(request.referrer or url_for(...))`) that a global error handler would complicate.
*   **Rejected:** *Adding `pending_holds` to the `user_summaries` read model.*
    *   **Reason:** `user_summaries` is designed for quick Identity lookups (Name, Email, Card Number). Financial hold states are volatile and belong strictly in the Ledger's `AccountSummary` DTO. Mixing them would violate bounded context read-model boundaries.
