# MODULE DOCUMENTATION: USER MANAGEMENT & DASHBOARD ORCHESTRATION

**Version:** 2.1.0  

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture](#backend-architecture)
4. [API Contract / Integration](#api-contract--integration)
5. [Execution Flows](#execution-flows)
6. [Edge Cases & Known Issues](#edge-cases--known-issues)
7. [Architectural Notes & Rejected Decisions](#architectural-notes--rejected-decisions)

---

## Overview
The User Management module manages the lifecycle of `User` entities within the Identity bounded context. It operates on a strict Hexagonal/DDD architecture with a multi-stage CQRS-lite read-model projection. The write-side handles registration, enforcing domain invariants via the `PhoneEmail` Value Object. The read-side maintains a denormalized `user_summaries` table that incrementally aggregates data from the Identity, Ledger, and Card contexts to serve the internal Administration Dashboard. Furthermore, the module's web layer acts as a monolithic orchestration point (BFF), dispatching commands across multiple bounded contexts. The system is designed as a zero-ops local simulator, prioritizing immediate consistency, nested transaction safety, and simplicity over production-grade fault isolation.

## Business Rules

### 1. Specification (WHAT)
*   **User Uniqueness & Normalization:** Users are uniquely identified by a `PhoneEmail` Value Object. Emails are normalized to lowercase; phones are validated against E.164. A user cannot be registered if the `PhoneEmail` exists in the `users` table.
*   **Temporal Decoupling of Accounts:** A `User` can exist independently of an `Account`. The read-model (`user_summaries`) accepts a nullable `account_id`, allowing the user record to be created first, and subsequently updated when an account is provisioned via the Ledger context.
*   **Domain Events:** Successful registration emits a `UserRegisteredEvent` containing the `user_id`, `name`, and normalized `PhoneEmail`.

### 2. Rationale (WHY)
*   **Single String Value Object:** Combining phone and email into a single `PhoneEmail` string simplifies the UI and allows a single `UNIQUE` constraint in SQLite to prevent duplicate accounts across both mediums. Normalization prevents casing-based duplicates.
*   **Surrogate Key:** Using an auto-incrementing integer ID decouples the user's internal identity from their mutable contact information, allowing future contact updates without breaking foreign keys.
*   **Nullable Foreign Keys in Read Model:** Making `account_id` nullable in `user_summaries` reflects the real-world business flow where user onboarding and financial account creation are distinct, sequential steps rather than a single atomic transaction.

### 3. Rejected Alternatives
*   **Rejected:** *Separate `Phone` and `Email` Value Objects / Two Nullable Columns.*
    *   **Reason:** Discarded because it complicates the database schema and makes the SQLite `UNIQUE` constraint implementation significantly harder. We sacrificed downstream type-ambiguity to achieve write-side simplicity.
*   **Rejected:** *Forcing Atomic User+Account Creation.*
    *   **Reason:** Discarded to allow independent lifecycles. We sacrificed short-term UI simplicity (requiring two steps to fully onboard a user) to maintain strict separation between Identity (who the user is) and Ledger (what the user owns).

## Backend Architecture

### 1. Technical Details (WHAT)
*   **Domain & Application:** Pure Python dataclasses (`User`, `PhoneEmail`, `RegisterUserCommand`). Handlers rely strictly on the `UnitOfWork` and `EventBus` ports.
*   **Persistence & Nested Transactions:** `SqliteUserRepository` persists to SQLite. The `SqliteUnitOfWork` creates a fresh `sqlite3` connection per request but utilizes a `_nesting_level` counter. This allows multiple handlers or nested `with uow:` blocks to share the same connection without prematurely committing or closing the file handle.
*   **Multi-Stage CQRS Read Model:** The `user_summaries` table is populated synchronously via three distinct event listeners:
    1.  `UserRegisteredReadModelHandler` (Listens to Identity `UserRegisteredEvent` -> Inserts base user data).
    2.  `AccountCreatedReadModelHandler` (Listens to Ledger `AccountCreatedEvent` -> Updates account/balance fields).
    3.  `CardAssignedReadModelHandler` (Listens to Identity `CardAssignedEvent` -> Updates card fields).

### 2. Decisions (WHY)
*   **Cross-Context Event Listening:** The Identity context explicitly imports and listens to `src.ledger.domain.events.account_events.AccountCreatedEvent`. This ensures the dashboard's unified view remains consistent without requiring a dedicated aggregation service.
*   **SQLite with WAL Mode & Nested UoW:** Chosen for the "zero-ops" mandate. The nested transaction support prevents `sqlite3.ProgrammingError` when the DI container or controller inadvertently wraps multiple command executions in overlapping UoW contexts.
*   **Denormalized Read Model:** Pre-joins user, account, and card data to prepare the Identity context for a future microservice split, strictly adhering to the rule that contexts must not perform cross-context SQL JOINs at query time.

### 3. Rejected Alternatives
*   **Rejected:** *Dedicated Read-Model / Aggregator Bounded Context.*
    *   **Reason:** Discarded to avoid microservice overhead. We sacrificed strict bounded-context purity (Identity importing Ledger events) to maintain a unified dashboard view in a single local process.
*   **Rejected:** *PostgreSQL / MySQL with Connection Pooling.*
    *   **Reason:** Discarded to maintain the zero-ops simulator mandate.

## API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **Delivery Mechanism:** Server-Side Rendered (SSR) HTML via Flask/Jinja2.
*   **Monolithic Orchestration:** The `dashboard_controller.py` acts as a Backend-For-Frontend (BFF), importing and dispatching commands for both Identity and Ledger contexts.
*   **Internal Routes:**
    *   `GET /dashboard/users` -> Executes `GetAllUsersQuery` or `SearchUsersQuery`.
    *   `POST /dashboard/users/add` -> Maps to `RegisterUserCommand`.
    *   `POST /dashboard/accounts/update-currency` -> Dispatches `UpdateAccountCurrencyCommand` (Ledger).
    *   `POST /dashboard/accounts/topup` -> Dispatches `TopupAccountCommand` (Ledger).

### 2. Contract Choices (WHY)
*   **Monolithic Dashboard Controller:** Chosen for rapid MVP delivery. It eliminates the need for an API Gateway or complex frontend state management, allowing a single developer to ship a fully functional admin UI that directly manipulates multiple domains.
*   **SSR via Flask:** Eliminates the need for a frontend build pipeline.

### 3. Rejected Alternatives
*   **Rejected:** *Decoupled SPA (React/Next.js) consuming a JSON API via API Gateway.*
    *   **Reason:** Discarded to accelerate MVP delivery. We sacrificed API-first design and strict context isolation at the delivery layer to deliver a functional local UI in the shortest possible time.

## Execution Flows

### 1. Step-by-step Sequence: User Registration (WHAT)
1.  **Input:** Admin submits form to `POST /dashboard/users/add`.
2.  **Translation:** `dashboard_controller` maps form data to `RegisterUserCommand`.
3.  **Validation:** `RegisterUserHandler` instantiates `PhoneEmail` (validates regex, normalizes).
4.  **Transaction Start:** `SqliteUnitOfWork` opens a connection (`_nesting_level` = 1).
5.  **Invariant Check:** Handler calls `exists_by_phone_email`.
6.  **Persistence:** Handler calls `repo.add(user)`, SQLite assigns `lastrowid`.
7.  **Commit:** `uow.commit()` is called. The `users` row is permanently written.
8.  **Event Emission:** Handler publishes `UserRegisteredEvent`.
9.  **Read-Model Projection (Stage 1):** `UserRegisteredReadModelHandler` catches the event, opens a *nested* UoW (`_nesting_level` = 2), inserts base data into `user_summaries`, and commits.
10. **Response:** Controller redirects to `GET /dashboard/users`.

### 2. Step-by-step Sequence: Account Creation & Read-Model Sync (WHAT)
1.  **Input:** Admin creates an account via the Dashboard.
2.  **Ledger Execution:** Ledger context processes `CreateAccountCommand` and emits `AccountCreatedEvent`.
3.  **Cross-Context Projection (Stage 2):** `AccountCreatedReadModelHandler` (residing in Identity) catches the Ledger event.
4.  **Update:** It opens a UoW and executes an `UPDATE` on `user_summaries`, populating the previously NULL `account_id`, `account_number`, `currency_code`, and `balance`.

### 3. Sequence Justification (WHY)
*   **Commit before Publish:** Ensures downstream handlers don't attempt to read uncommitted data.
*   **Nested UoW in Read-Model Handlers:** The `_nesting_level` logic in `SqliteUnitOfWork` ensures that if the event bus triggers a handler that opens its own `with uow:` block, it reuses the existing connection and only decrements the level, preventing the "database is locked" or "closed connection" errors common in SQLite.

## Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **The "Phantom User" Anomaly:** If the write-side commits but the synchronous `UserRegisteredReadModelHandler` fails, the user exists in the domain but is invisible to the dashboard.
*   **Cross-Context Compile-Time Coupling:** The Identity context explicitly imports `src.ledger.domain.events.account_events`. If the Ledger context changes the schema of `AccountCreatedEvent`, the Identity context will crash at runtime or fail to import, violating the Dependency Inversion Principle.
*   **Downstream Ambiguity:** The `Notifications` context receives the `UserRegisteredEvent` containing a raw `PhoneEmail` string and must re-implement regex parsing to route SMS vs. Email.

### 2. Root Cause & Impact (WHY)
*   **Root Cause (Phantom User):** Synchronous in-process event bus without a distributed transaction (Outbox pattern).
*   **Root Cause (Coupling):** Prioritizing a unified local dashboard over strict bounded-context isolation and dependency rules.
*   **Impact:** Low for a local simulator, but catastrophic for a production microservice ecosystem.

### 3. Rejected Alternatives
*   **Rejected:** *Implementing the Transactional Outbox Pattern or Anti-Corruption Layers (ACL).*
    *   **Reason:** Discarded as massive over-engineering for a local simulator. We accepted the risk of phantom users and tight compile-time coupling to maintain absolute architectural simplicity.

## Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Monolithic Controller:** `dashboard_controller.py` imports commands from `src.identity` and `src.ledger`, acting as a centralized orchestration layer.
*   **Nested Unit of Work:** `SqliteUnitOfWork` tracks `_nesting_level` to allow safe composition of multiple operations without prematurely closing the SQLite connection.
*   **Centralized Generators:** Utility functions like `generate_card_number` are housed in `src/common/infrastructure/generators.py`.

### 2. Discarded Alternatives (WHY)
*   **Centralized Generators:** Kept in `common` for DRY convenience across the simulator, even though card generation technically belongs to the Checkout/Card domain.
*   **Nested UoW:** Implemented to prevent SQLite locking exceptions when the DI container or event bus inadvertently nests transaction boundaries.

### 3. Rejected Alternatives
*   **Rejected:** *Context-Specific Domain Factories & Strict Dependency Inversion.*
    *   **Reason:** Discarded to prioritize developer speed. We sacrificed strict bounded-context purity (making Identity aware of Ledger events, and generic infrastructure aware of Luhn algorithms) to maintain a single, easily accessible codebase.
*   **Rejected:** *SQLAlchemy or an ORM for the Unit of Work.*
    *   **Reason:** Discarded to maintain raw SQL transparency and avoid the heavy dependency footprint of an ORM, keeping the CQRS projections explicitly visible in the codebase.
