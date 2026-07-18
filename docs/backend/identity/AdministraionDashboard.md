# MODULE DOCUMENTATION: CROSS-CONTEXT ADMINISTRATION DASHBOARD

**Version:** 2.0.0 

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
*   **Currency Bootstrap Invariant:** Every time a new Currency is created, the system **must** automatically generate a System Escrow Account. The account number is deterministically calculated as `9000000000 + currency_id`. This account has `user_id = NULL` and `merchant_id = NULL`.
*   **Automatic Card Provisioning:** When an Account is created for a User or Merchant, a 16-digit Luhn-valid Card Number is automatically generated and persisted in the `user_cards` table. This occurs synchronously within the same HTTP request.
*   **Zero-Balance Currency Change:** An account's currency can only be changed if its current balance is exactly `0.00`. The `Account.change_currency()` method enforces this domain invariant.
*   **Strict Identity Uniqueness:**
    *   `users.phone_email` must be globally unique (UNIQUE constraint in SQLite).
    *   `merchants.api_key` must be globally unique.
    *   `accounts.account_number` must be globally unique (10 digits, generated via `generators.py`).
    *   `user_cards.card_number` must be globally unique (16 digits, Luhn-valid).
*   **No Direct Data Manipulation:** The dashboard controller never imports SQLAlchemy, raw SQL, or repositories. All mutations are delegated to Application Handlers via the DI Container.

### 2. Rationale & Trade-offs (WHY)
*   **Why automatic System Escrow Account?** The Ledger implements double-entry bookkeeping. Every currency requires a system-owned escrow account to balance hold/complete/refund transactions. Automating this at currency creation time eliminates the risk of an admin forgetting to create it manually, which would cause `HoldFundsHandler` to fail at runtime.
*   **Why synchronous card provisioning?** The synchronous `InMemoryEventBus` ensures that when the dashboard redirects after account creation, the card number is already persisted and visible on the accounts list page. An async bus would cause a "flash of stale content" where the account appears without a card until the next page load.
*   **Why zero-balance currency change?** Changing the currency of an account with a non-zero balance would silently re-denominate existing funds (e.g., treating 100 USD as 100 EUR), violating financial integrity. The domain model rejects this at the aggregate level.
*   **Why in-house Luhn generation instead of a real issuer?** The entire module is a simulator for testing and internal sandbox use. Integrating with a real card issuer (Stripe Issuing, Marqeta) would introduce external dependencies, API costs, and latency that are unnecessary for an MVP simulator. The `OnAccountCreatedHandler` is designed behind an implicit port; when real card issuance is needed, it can be swapped to a `CardProvisioningPort` adapter.

### 3. Rejected Alternatives
*   **Rejected:** *Manual Escrow Account creation by the admin.*
    *   **Reason:** Error-prone. An admin could create a currency without its corresponding escrow account, breaking all subsequent transactions in that currency. Automating it in `CreateCurrencyHandler` guarantees consistency.
*   **Rejected:** *Using real card issuer APIs for card generation.*
    *   **Reason:** Over-engineering for a simulator. The generated card numbers are used only for internal OTP-based authorization flows; they never touch a real payment rail.

---

## 3. Backend Architecture

### 1. Technical Details & Structure (WHAT)

*   **Delivery Layer (Controller):**
    *   File: `src/identity/infrastructure/web/dashboard_controller.py`
    *   Flask Blueprint registered at URL prefix `/dashboard`.
    *   14 route functions (7 GET, 7 POST). Zero business logic. All handlers obtained from `current_app.di_container.get_..._handler(uow)`.
*   **Dependency Injection (Composite Container):**
    *   `src/app/di_container.py`: Central `DIContainer` class. Instantiates `InMemoryEventBus`, then delegates to context-specific registration modules.
    *   `src/app/di/identity_di.py`: Binds 6 handler factory methods + 7 event subscriptions.
    *   `src/app/di/ledger_di.py`: Binds 13 handler factory methods.
    *   Factory signature pattern: `def get_X_handler(uow: SqliteUnitOfWork) -> XHandler`
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
    *   Schema initialized by `Database.initialize()` in `src/common/infrastructure/database/__init__.py`.
    *   Key tables: `users`, `merchants`, `user_cards`, `user_summaries`, `merchant_summaries`, `currencies`, `accounts`, `transactions`.
*   **Cross-Context Coupling Point:**
    *   `src/identity/infrastructure/persistence/ledger_account_provisioning_adapter.py`: Directly inserts into `accounts` table (owned by Ledger). Isolated behind `AccountProvisioningPort` interface.

**Complete DDL (Identity + Ledger):**
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
*   **Why Composite DI Container?** A single monolithic DI file would become a God Object as bounded contexts grow. Delegating to `identity_di.py`, `ledger_di.py`, etc., keeps each context's wiring self-contained and testable in isolation.
*   **Why Nested UoW?** When `CreateAccountHandler` publishes `AccountCreatedEvent`, the subscriber `OnAccountCreatedHandler` opens its own `with uow:` block. Without nesting support, the inner block would commit/rollback independently, breaking transactional atomicity. The `_nesting_level` counter ensures only the outermost handler controls the final commit.
*   **Why raw SQL JOINs in Read Models (no ORM, no denormalized tables)?**
    *   *Team Skill & Simplicity:* Raw SQL is transparent; developers are comfortable writing it. No ORM mapping overhead for presentational queries.
    *   *CQRS Pragmatism:* A true denormalized read table would require event handlers to maintain it, introducing eventual consistency. The raw JOIN queries the source of truth directly, guaranteeing freshness.
    *   *Performance Context:* On SQLite with MVP-scale data, JOINs across 5 tables are sub-millisecond. The trade-off is accepted: faster initial development over long-term schema-change maintainability.
*   **Why Cross-Context DB Coupling via `LedgerAccountProvisioningAdapter`?** In an MVP monolith, writing directly to the shared database avoids building an inter-module command bus just for account provisioning. The debt is isolated behind the `AccountProvisioningPort` interface. If Ledger is extracted into a microservice, only this adapter needs replacement (swap direct SQL for HTTP/gRPC call). The probability of immediate extraction was low, making this acceptable technical debt.
*   **Why Optimistic Concurrency Control on Accounts?** `SqliteAccountRepository.update()` uses `WHERE version = ?` to detect concurrent modifications. This prevents lost updates when two handlers (e.g., Topup and Hold) modify the same account within overlapping transactions. On conflict, `ConcurrencyException` is raised.

### 3. Rejected Alternatives
*   **Rejected:** *Using Flask's MethodView (class-based views).*
    *   **Reason:** For the simplicity of the MVP, plain functions keep the codebase straightforward. Class-based views add a layer of indirection without significant benefit for a dashboard with 14 routes.
*   **Rejected:** *Denormalized Read-Model tables updated by event handlers.*
    *   **Reason:** Would introduce eventual consistency and require complex sync logic. Direct JOINs on SQLite provide instant consistency at acceptable performance for MVP load.
*   **Rejected:** *Strict Hexagonal boundary between Identity and Ledger (no shared DB writes).*
    *   **Reason:** Would require building an internal command bus or HTTP API for account provisioning. Unnecessary overhead for an MVP monolith where both contexts share the same deployable and database file.

---

## 4. API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)

**Contract Type:** Internal HTML SSR via Flask Blueprint. **No JSON API.**  
**Base URL:** `/dashboard`  
**Root Redirect:** `GET /` → `302` → `/dashboard/currencies` (defined in `flask_app.py`)

| # | Method | Endpoint | Form Inputs | Success Behavior | Error Behavior |
|---|--------|----------|-------------|-----------------|----------------|
| 1 | `GET` | `/dashboard/currencies` | — | Renders `currencies.html` with list of all currencies | — |
| 2 | `POST` | `/dashboard/currencies/add` | `name` (str), `code` (str, 3-letter ISO) | Creates Currency + System Escrow Account. Redirect to `/dashboard/currencies` | Flash error, redirect to `/dashboard/currencies` |
| 3 | `POST` | `/dashboard/currencies/toggle/<int:id>` | — (URL param) | Toggles `is_active`. Redirect to `/dashboard/currencies` | Flash error, redirect |
| 4 | `GET` | `/dashboard/users` | Query param: `?query=` (optional) | Renders `users.html`. If `query` present, searches by name/account_number/card_number | — |
| 5 | `POST` | `/dashboard/users/add` | `name` (str), `phone_email` (str, E.164 or email) | Registers user. Redirect to `/dashboard/users` | Flash error, redirect |
| 6 | `GET` | `/dashboard/merchants` | — | Renders `merchants.html` | — |
| 7 | `POST` | `/dashboard/merchants/add` | `name` (str) | Onboards merchant, generates `pay_` API key. Redirect to `/dashboard/merchants` | Flash error, redirect |
| 8 | `POST` | `/dashboard/merchants/toggle/<int:id>` | — (URL param) | Toggles `is_active`. Redirect to `/dashboard/merchants` | Flash error, redirect |
| 9 | `GET` | `/dashboard/accounts` | — | Renders `accounts.html` with accounts, currencies, users, merchants | — |
| 10 | `POST` | `/dashboard/accounts/create` | `owner_id` (str: `user_<id>` or `merchant_<id>`), `currency_code` (str) | Creates account, triggers card provisioning. Redirect to `/dashboard/accounts` | Flash error, redirect |
| 11 | `POST` | `/dashboard/accounts/topup` | `account_id` (int), `amount` (decimal string) | Adds funds. Redirect to `request.referrer` or `/dashboard/accounts` | Flash error, redirect |
| 12 | `POST` | `/dashboard/accounts/update-currency` | `account_id` (int), `currency_code` (str) | Changes currency (requires 0 balance). Redirect to `/dashboard/accounts` | Flash error, redirect |
| 13 | `GET` | `/dashboard/escrow` | — | Renders `escrow_accounts.html` with system escrow accounts | — |

**DTOs Returned to Templates:**
*   `UserSummaryDTO(user_id: int, name: str, phone_email: str, account_number: Optional[str], card_number: Optional[str], currency_code: Optional[str])`
*   `MerchantSummaryDTO(id: int, name: str, api_key: str, is_active: bool)`
*   `AccountSummary(id: int, user_id: int, user_name: str, currency_id: int, currency_code: str, account_number: str, balance: Decimal, card_number: Optional[str])`
*   `CurrencySummaryDTO(id: int, name: str, code: CurrencyCode, is_active: bool)`
*   `EscrowAccountSummary(id: int, currency_id: int, currency_code: str, account_number: str, balance: Decimal)`

### 2. Contract Choices (WHY)
*   **Why HTML-only (No JSON API)?** The dashboard is strictly a back-office tool for internal admin use. External actors (mobile apps, merchant integrators) interact with the `Checkout` and `Ledger` contexts via REST/JSON. Exposing Identity/Dashboard via JSON would unnecessarily expand the attack surface.
*   **Why no versioning in the URL?** The dashboard is a single internal consumer; no backward compatibility is required.
*   **Why redirect after POST (PRG Pattern)?** Prevents duplicate form submissions on page refresh. Combined with domain invariants (UNIQUE constraints), this provides sufficient double-submit protection without the complexity of the `@idempotent` decorator.
*   **Why `owner_id` format is `user_<id>` / `merchant_<id>`?** The controller parses this string to determine `user_id` vs `merchant_id` for the `CreateAccountCommand`. This avoids separate form fields and dropdowns for owner type selection.

### 3. Rejected Alternatives
*   **Rejected:** *Building a GraphQL or REST API for the Admin Dashboard.*
    *   **Reason:** Over-engineering for an internal tool. Flask's `render_template` provides sufficient UX without state management libraries (React/Vue) or API serialization layers.
*   **Rejected:** *Applying the `@idempotent` decorator to dashboard routes.*
    *   **Reason:** The decorator relies on an `Idempotency-Key` HTTP header, which HTML forms cannot send. The PRG pattern + domain invariants already handle double-submits for human-operated forms. The decorator is reserved for headless JSON APIs where external merchants retry payment initiation.

---

## 5. Execution Flows

### 1. Step-by-step Sequence (WHAT)

#### Flow A: Admin Creates a Currency (with System Escrow Bootstrap)
1. Admin navigates to `GET /dashboard/currencies`.
2. Submits form to `POST /dashboard/currencies/add` with `name="US Dollar"`, `code="USD"`.
3. Controller creates `SqliteUnitOfWork`, obtains `CreateCurrencyHandler` from DI container.
4. Handler validates `CurrencyCode("USD")` (3-letter ISO, uppercase).
5. Handler checks `CurrencyRepository.get_by_code()` for uniqueness.
6. Handler creates `Currency` aggregate via `Currency.create()`.
7. Handler persists currency, retrieves `currency_id`.
8. **Handler auto-generates System Escrow Account:** `account_number = "9000000000" + str(currency_id)`. Creates `Account` aggregate with `user_id=None, merchant_id=None, balance=Money('0.00', 'USD')`.
9. Handler persists escrow account via `AccountRepository.add()`.
10. Handler publishes `CurrencyCreatedEvent(currency_id, name, code)`.
11. Controller commits UoW. Redirects to `GET /dashboard/currencies`.

#### Flow B: Admin Creates a User Account (with Cross-Context Card Provisioning)
1. Admin navigates to `GET /dashboard/accounts`. Template loads users, merchants, and active currencies for dropdown.
2. Submits form to `POST /dashboard/accounts/create` with `owner_id="user_5"`, `currency_code="USD"`.
3. Controller parses `owner_id`: `owner_type="user"`, `owner_id=5`. Sets `user_id=5, merchant_id=None`.
4. Controller creates `SqliteUnitOfWork`, obtains `CreateAccountHandler` from DI container.
5. Handler generates unique 10-digit `AccountNumber` via `generate_account_number()`.
6. Handler creates `Account` aggregate with `balance=Money('0.00', 'USD')`.
7. Handler persists account, retrieves `account_id`.
8. Handler publishes `AccountCreatedEvent(account_id, user_id=5, merchant_id=None, account_number, currency_code)`.
9. **InMemoryEventBus synchronously triggers subscribers:**
    *   **Subscriber 1:** `AccountCreatedReadModelHandler` executes `UPDATE user_summaries SET account_id=..., account_number=..., currency_code=..., balance='0.00' WHERE user_id=5`.
    *   **Subscriber 2:** `OnAccountCreatedHandler` generates Luhn-valid 16-digit card number via `generate_card_number()`. Executes `INSERT INTO user_cards (user_id, merchant_id, account_id, card_number)`. Publishes `CardAssignedEvent`.
    *   **Subscriber 3:** `CardAssignedReadModelHandler` executes `UPDATE user_summaries SET card_number=... WHERE account_id=...`.
10. Controller commits UoW. Redirects to `GET /dashboard/accounts`. Dashboard loads with new account row including card number.

#### Flow C: Admin Adds a User
1. Admin submits `POST /dashboard/users/add` with `name="Alice"`, `phone_email="alice@example.com"`.
2. Controller obtains `RegisterUserHandler` from DI container.
3. Handler creates `PhoneEmail("alice@example.com")` → validates email regex → normalizes to lowercase.
4. Handler checks `UserRepository.exists_by_phone_email("alice@example.com")`.
5. Handler creates `User(id=None, name="Alice", phone_email=PhoneEmail)`.
6. Handler persists via `UserRepository.add()`, retrieves `user_id`.
7. Handler publishes `UserRegisteredEvent(user_id, name, phone_email)`.
8. **Subscriber:** `UserRegisteredReadModelHandler` executes `INSERT INTO user_summaries (user_id, name, phone_email)`.
9. Controller commits. Redirects to `GET /dashboard/users`.

#### Flow D: Admin Tops Up an Account
1. Admin submits `POST /dashboard/accounts/topup` with `account_id=3`, `amount="150.00"`.
2. Controller parses amount as `Decimal("150.00")`.
3. Controller obtains `TopupAccountHandler` from DI container.
4. Handler fetches `Account` aggregate via `AccountRepository.get_by_id(3)`.
5. Handler creates `Money(Decimal("150.00"), account.balance.currency)`.
6. Handler calls `account.topup(money)` → validates amount > 0, validates currency match, adds to balance.
7. Handler calls `AccountRepository.update(account)` → executes `UPDATE accounts SET balance=..., version=version+1 WHERE id=3 AND version=<current>`. If `rowcount == 0`, raises `ConcurrencyException`.
8. Controller commits. Redirects to `request.referrer` or `/dashboard/accounts`.

### 2. Sequence Justification (WHY)
*   **Why synchronous event processing in Flow B?** The `InMemoryEventBus.publish()` blocks until all subscribers complete. This guarantees that when the redirect happens in step 10, the `user_summaries` table already contains the account number AND the card number. If the bus were async, the redirect could occur before `OnAccountCreatedHandler` finishes, and the admin would see a "missing card" on the accounts page.
*   **Why generate card number in a subscriber, not in the handler?** Separation of concerns. `CreateAccountHandler` (Ledger) should not know about card provisioning (Identity). The event bus decouples these contexts. If card provisioning is later removed or moved to an external service, only the subscriber registration in `identity_di.py` changes; the Ledger handler remains untouched.
*   **Why parse `owner_id` string in the controller, not in a Value Object?** The `user_<id>` / `merchant_<id>` format is a UI convention specific to the dashboard's form dropdown. It has no domain meaning. Parsing it in the controller keeps the domain model clean from presentation concerns.
*   **Why does `TopupAccountHandler` not publish an event?** Top-ups are admin-initiated balance adjustments, not customer-facing transactions. No downstream system (Notifications, Checkout) needs to react to a top-up in the current MVP. If a "TopupCompleted" notification is needed later, an event can be added without changing the handler's signature.

### 3. Rejected Alternatives
*   **Rejected:** *Processing card provisioning asynchronously (background task or message queue).*
    *   **Reason:** Would break the admin's expectation of seeing the card number immediately after account creation. The synchronous bus provides a simpler, more predictable UX for an internal tool.
*   **Rejected:** *Controller directly inserting into `user_summaries` after handler returns.*
    *   **Reason:** Would bypass the event-driven architecture. Read model updates must be triggered by domain events to maintain consistency and allow multiple subscribers to react to the same event.

---

## 6. Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)

*   **Scenario 1: Double-Click Submit**
    *   Admin double-clicks "Add User" button. Two identical POST requests hit `/dashboard/users/add` within milliseconds.
    *   First request succeeds: user created, `user_summaries` updated, redirect issued.
    *   Second request fails: `SqliteUserRepository.add()` catches `sqlite3.IntegrityError` ("UNIQUE constraint failed: users.phone_email"), raises `UserAlreadyExistsError`. Controller catches exception, flashes error message, redirects.
    *   **Impact:** No data corruption. User sees an error flash message on the second redirect.

*   **Scenario 2: Concurrent Account Modification (Optimistic Lock Failure)**
    *   Two admins simultaneously top up the same account.
    *   First admin's `AccountRepository.update()` succeeds (version match), increments `version`.
    *   Second admin's `update()` finds `rowcount == 0` (version mismatch), raises `ConcurrencyException`.
    *   **Impact:** Second admin sees a flash error. Must reload the page and retry. No lost updates.

*   **Scenario 3: Currency Change on Non-Zero Balance**
    *   Admin attempts to change currency of an account with balance `150.00`.
    *   `Account.change_currency()` checks `self.balance.amount == 0` → `False` → raises `ValueError("Cannot change currency on an account with a balance > 0.")`.
    *   **Impact:** Controller catches exception, flashes error message.

*   **Scenario 4: Top-Up with Currency Mismatch**
    *   Admin tops up account with currency USD using a form that sends a different currency.
    *   `account.topup(money)` checks `self.balance.currency != amount.currency` → raises `CurrencyMismatchError`.
    *   **Impact:** Flash error. (Note: current dashboard form does not allow currency selection for top-up; it uses the account's existing currency. This edge case would only occur via API manipulation.)

*   **Scenario 5: No CSRF Protection**
    *   Forms lack `csrf_token`. A malicious external page could theoretically submit forms to the dashboard.
    *   **Impact:** Acceptable risk because the dashboard is bound to `127.0.0.1` or an internal network. If the dashboard is ever exposed to the internet, CSRF tokens must be added immediately.

### 2. Root Cause & Impact (WHY)
*   **Why no client-side double-submit prevention?** The dashboard uses no JavaScript. Adding JS disable-on-submit would increase maintenance without improving security. The domain's UNIQUE constraints are the ultimate guard against duplicates. The trade-off: slightly worse UX (flash error instead of silent prevention) for zero additional complexity.
*   **Why optimistic locking instead of pessimistic (SELECT FOR UPDATE)?** SQLite does not support row-level locks. The `version` column with `WHERE version = ?` is the standard pattern for SQLite concurrency control. The trade-off: occasional retry-required errors for admins under concurrent access, but zero risk of deadlocks.
*   **Why swallow exceptions with `try/except` + `flash()`?** The dashboard is an admin tool where errors should be informative, not fatal. Catching all exceptions prevents 500 errors and provides actionable feedback. The trade-off: potential masking of unexpected bugs (e.g., `TypeError` from bad code would appear as a flash message rather than a crash log).

### 3. Rejected Alternatives
*   **Rejected:** *Client-side validation only for form inputs.*
    *   **Reason:** Cannot be trusted. Server-side validation via Value Objects (`PhoneEmail`, `CurrencyCode`, `Money`) is always required. Adding JavaScript would duplicate logic and create a false sense of security.
*   **Rejected:** *Pessimistic locking for account updates.*
    *   **Reason:** SQLite does not support `SELECT ... FOR UPDATE`. Using `BEGIN EXCLUSIVE` would serialize all writes, killing throughput. Optimistic locking via `version` column is the correct pattern for SQLite.

---

## 7. Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Strict DI Container Factories:** `dashboard_controller.py` never instantiates handlers directly. It requests them from `current_app.di_container.get_..._handler(uow)`. This enforces DIP at the delivery layer.
*   **No ORM in Controllers:** The controller never imports SQLAlchemy or raw SQL. All data access goes through application handlers or read-model query ports.
*   **Single SQLite Database:** All bounded contexts share `paymenter.db`. Schema creation is orchestrated by `Database.initialize()` which concatenates `IDENTITY_SCHEMA + LEDGER_SCHEMA + CHECKOUT_SCHEMA + NOTIFICATIONS_SCHEMA`.
*   **Cross-Context Foreign Keys:** SQLite foreign keys cross bounded context boundaries (e.g., `user_cards.account_id → accounts.id`, `accounts.user_id → users.id`). This is enforced by `PRAGMA foreign_keys = ON`.
*   **Event Subscription Registration:** All cross-context event subscriptions are registered at startup in the DI modules. `identity_di.py` subscribes to `AccountCreatedEvent` (owned by Ledger). `notifications_di.py` subscribes to `TransactionCompletedEvent` (owned by Ledger).
*   **Idempotency Decorator:** Exists in `src/common/infrastructure/web/idempotency.py` but is **not** applied to the dashboard blueprint. Reserved for headless JSON API endpoints (Checkout).

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Using Flask-Admin or a similar CRUD generator.*
    *   **Reason:** Would couple the UI tightly to the database schema and bypass domain logic. Custom routes allow precise command and event handling.
*   **Rejected:** *Separating the dashboard into a Single Page Application (SPA).*
    *   **Reason:** Overkill for an internal tool. Would require a separate build chain, API layer, and authentication token management.
*   **Rejected:** *Separating the dashboard into its own microservice with a REST API.*
    *   **Reason:** For the MVP, co-location with the bounded contexts reduces network latency and deployment overhead.
*   **Rejected:** *Async event bus (RabbitMQ / Redis Streams / Kafka).*
    *   **Reason:** Would break UI consistency guarantees. The synchronous bus ensures all side effects complete before redirect. The accepted trade-off is limited throughput and blocking HTTP threads, which is acceptable for a low-traffic admin tool.
*   **Rejected:** *Strict Hexagonal boundary with no shared database writes.*
    *   **Reason:** Would require building inter-module communication infrastructure (internal command bus or HTTP API) just for account provisioning. Unnecessary overhead for MVP monolith. The debt is isolated behind `AccountProvisioningPort`.