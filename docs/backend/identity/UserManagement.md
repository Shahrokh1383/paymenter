# MODULE DOCUMENTATION: IDENTITY & DASHBOARD ORCHESTRATION

**Version:** 3.0.0  

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture](#backend-architecture)
4. [API Contract / Integration](#api-contract--integration)
5. [Execution Flows](#execution-flows)
6. [Edge Cases & Architectural Trade-offs](#edge-cases--architectural-trade-offs)
7. [Architectural Notes & Rejected Decisions](#architectural-notes--rejected-decisions)
---

## Overview
The Identity module manages the lifecycle of `User` and `Merchant` entities within the Identity bounded context. It operates on a strict Hexagonal/DDD architecture with a multi-stage CQRS-lite read-model projection. The write-side handles registration, onboarding, and outbound integration configurations (Webhooks), enforcing domain invariants via specialized Value Objects (`PhoneEmail`, `ApiKey`, `WebhookUrl`). 

The read-side maintains denormalized `user_summaries` and `merchant_summaries` tables that incrementally aggregate data from the Identity and Ledger contexts to serve the internal Administration Dashboard. Furthermore, the module's web layer acts as a monolithic Backend-For-Frontend (BFF), dispatching commands across multiple bounded contexts. The architecture prioritizes immediate consistency, ambient nested transaction safety, and strict server-side orchestration.

## Business Rules

### 1. Specification (WHAT)
*   **User Uniqueness & Normalization:** Users are uniquely identified by a `PhoneEmail` Value Object. Emails are normalized to lowercase; phones are validated against E.164. A user cannot be registered if the `PhoneEmail` exists in the `users` table.
*   **Merchant API Key Issuance:** Upon onboarding, a `Merchant` is issued a strict `ApiKey` Value Object (prefix `pay_` + 43 URL-safe characters). This key serves as the immutable credential for external integrations.
*   **Webhook Invariants:** A Merchant's webhook configuration is governed by strict domain rules. A webhook cannot be enabled without providing a valid, absolute HTTP/HTTPS URL (`WebhookUrl` VO). Webhook secrets are generated as cryptographically secure strings (prefix `whsec_` + 32 URL-safe chars) and must meet minimum length constraints.
*   **Temporal Decoupling & Cross-Context Provisioning:** `User` and `Merchant` entities exist independently of `Account` entities (managed by the Ledger context). When an account is provisioned in the Ledger context, the Identity context reacts by generating a PAN (Card Number) and linking it to the owner, subsequently updating the read models.
*   **Domain Events:** State changes emit deterministic events: `UserRegisteredEvent`, `MerchantOnboardedEvent`, `MerchantActivatedEvent`/`MerchantDeactivatedEvent`, `MerchantWebhookConfiguredEvent`, and `MerchantWebhookSecretGeneratedEvent`.

### 2. Rationale (WHY)
*   **Single String Value Object (`PhoneEmail`):** Combining phone and email into a single string simplifies the UI and allows a single `UNIQUE` constraint in SQLite to prevent duplicate accounts across both mediums. Normalization prevents casing-based duplicates.
*   **Surrogate Keys:** Using auto-incrementing integer IDs decouples internal identity from mutable contact information and external API credentials, protecting foreign key relationships from volatility.
*   **Nullable Foreign Keys in Read Models:** Making `account_id` nullable in `user_summaries` reflects the real-world business flow where onboarding and financial account creation are distinct, sequential operations rather than a single atomic transaction.

### 3. Rejected Alternatives
*   **Rejected:** *Separate `Phone` and `Email` Value Objects.*
    *   **Reason:** Discarded because it complicates the database schema and makes the SQLite `UNIQUE` constraint implementation significantly harder. Downstream type-ambiguity was accepted to achieve write-side simplicity and strict database-level uniqueness.
*   **Rejected:** *Forcing Atomic User+Account Creation.*
    *   **Reason:** Discarded to allow independent lifecycles and maintain strict separation between Identity (who the user is) and Ledger (what the user owns).

## Backend Architecture

### 1. Technical Details (WHAT)
*   **Domain & Application:** Pure Python dataclasses. Handlers rely strictly on the `UnitOfWork` and `EventBus` ports.
*   **Ambient Nested Transactions:** `SqliteUnitOfWork` utilizes `contextvars` to manage ambient connections and a `_nesting_level` counter. This allows multiple handlers or nested `with uow:` blocks (e.g., event handlers opening their own UoW) to share the same connection without prematurely committing, rolling back, or causing SQLite locking exceptions.
*   **Multi-Stage CQRS Read Model:** The summary tables are populated synchronously via distinct event listeners:
    1.  **Identity Projections:** `UserRegisteredReadModelHandler`, `MerchantOnboardedReadModelHandler`, `MerchantToggledReadModelHandler`, `MerchantWebhookConfiguredReadModelHandler`.
    2.  **Cross-Context Projections:** `AccountCreatedReadModelHandler` (Listens to Ledger `AccountCreatedEvent` -> Updates account/balance fields in `user_summaries`).
    3.  **Cross-Context Projections:** `CardAssignedReadModelHandler` (Listens to Identity `CardAssignedEvent` -> Updates card fields in `user_summaries`).

### 2. Decisions (WHY)
*   **Cross-Context Event Listening:** The Identity context explicitly imports and listens to `src.ledger.domain.events.account_events.AccountCreatedEvent`. This ensures the dashboard's unified view remains consistent without requiring a dedicated aggregation service or cross-context SQL JOINs at query time.
*   **SQLite with WAL Mode & Ambient UoW:** The nested transaction support via `contextvars` prevents `sqlite3.ProgrammingError` when the DI container or controller inadvertently wraps multiple command executions in overlapping UoW contexts.
*   **Denormalized Read Models:** Pre-joins user, merchant, account, and card data to prepare the Identity context for a future microservice split, strictly adhering to the rule that contexts must not perform cross-context SQL JOINs at query time.

### 3. Rejected Alternatives
*   **Rejected:** *Dedicated Read-Model / Aggregator Bounded Context.*
    *   **Reason:** Discarded to avoid distributed system overhead. Strict bounded-context purity (Identity importing Ledger events) was sacrificed to maintain a unified dashboard view within a single process space.
*   **Rejected:** *Relational Database Connection Pooling (PostgreSQL/MySQL).*
    *   **Reason:** Discarded in favor of SQLite's zero-configuration file-based persistence, relying on WAL mode and ambient UoW to handle concurrency safely.

## API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **Delivery Mechanism:** Server-Side Rendered (SSR) HTML via Flask/Jinja2.
*   **Monolithic Orchestration:** The `dashboard_controller.py` acts as a Backend-For-Frontend (BFF), importing and dispatching commands for both Identity and Ledger contexts.
*   **Internal Routes:**
    *   `GET /dashboard/users` -> Executes `GetAllUsersQuery` or `SearchUsersQuery`.
    *   `POST /dashboard/users/add` -> Maps to `RegisterUserCommand`.
    *   `GET /dashboard/merchants` -> Executes `GetAllMerchantsQuery`.
    *   `POST /dashboard/merchants/add` -> Maps to `OnboardMerchantCommand`.
    *   `POST /dashboard/merchants/toggle/<id>` -> Maps to `ToggleMerchantCommand`.
    *   `POST /dashboard/merchants/<id>/webhook/configure` -> Maps to `ConfigureWebhookCommand`.
    *   `POST /dashboard/merchants/<id>/webhook/generate-secret` -> Maps to `GenerateWebhookSecretCommand`.
    *   `POST /dashboard/accounts/create` -> Dispatches `CreateAccountCommand` (Ledger).
    *   `POST /dashboard/accounts/topup` -> Dispatches `TopupAccountCommand` (Ledger).

### 2. Contract Choices (WHY)
*   **Monolithic Dashboard Controller:** Eliminates the need for an API Gateway or complex frontend state management, allowing a single execution context to manipulate multiple domains atomically via the BFF pattern.
*   **SSR via Flask:** Eliminates the need for a frontend build pipeline, ensuring the UI is strictly a reflection of the server-side read models.

### 3. Rejected Alternatives
*   **Rejected:** *Decoupled SPA consuming a JSON API via API Gateway.*
    *   **Reason:** Discarded in favor of server-side orchestration to enforce strict context boundaries at the delivery layer and eliminate client-side state synchronization complexities.

## Execution Flows

### 1. Step-by-step Sequence: User Registration (WHAT)
1.  **Input:** Admin submits form to `POST /dashboard/users/add`.
2.  **Translation:** `dashboard_controller` maps form data to `RegisterUserCommand`.
3.  **Validation:** `RegisterUserHandler` instantiates `PhoneEmail` (validates regex, normalizes).
4.  **Transaction Start:** `SqliteUnitOfWork` opens an ambient connection (`_nesting_level` = 1).
5.  **Invariant Check:** Handler calls `exists_by_phone_email`.
6.  **Persistence:** Handler calls `repo.add(user)`, SQLite assigns `lastrowid`.
7.  **Commit:** `uow.commit()` is called. The `users` row is permanently written.
8.  **Event Emission:** Handler publishes `UserRegisteredEvent`.
9.  **Read-Model Projection (Stage 1):** `UserRegisteredReadModelHandler` catches the event, re-enters the ambient UoW (`_nesting_level` = 2), inserts base data into `user_summaries`, and decrements the level.
10. **Response:** Controller redirects to `GET /dashboard/users`.

### 2. Step-by-step Sequence: Cross-Context Account & Card Provisioning (WHAT)
1.  **Input:** Admin creates an account via the Dashboard.
2.  **Ledger Execution:** Ledger context processes `CreateAccountCommand` and emits `AccountCreatedEvent`.
3.  **Cross-Context Reaction:** `OnAccountCreatedHandler` (residing in Identity) catches the Ledger event.
4.  **Card Generation:** Handler generates a PAN and inserts a record into `user_cards`.
5.  **Commit & Secondary Event:** Handler commits the UoW and emits `CardAssignedEvent`.
6.  **Read-Model Sync (Stage 2 & 3):** `AccountCreatedReadModelHandler` and `CardAssignedReadModelHandler` catch their respective events, opening nested UoW blocks to execute `UPDATE` statements on `user_summaries`, populating account balances and card numbers.

### 3. Sequence Justification (WHY)
*   **Commit before Publish:** Ensures downstream handlers don't attempt to read uncommitted data from the database.
*   **Ambient UoW via ContextVars:** The `_nesting_level` logic ensures that if the event bus triggers a handler that opens its own `with uow:` block, it reuses the existing connection and only decrements the level, preventing "database is locked" or "closed connection" errors.

## Edge Cases & Architectural Trade-offs

### 1. Specific Scenario (WHAT)
*   **The "Phantom Entity" Anomaly:** If the write-side commits but the synchronous Read-Model Handler fails (e.g., database constraint violation on the summary table), the entity exists in the domain but is invisible to the dashboard.
*   **Cross-Context Compile-Time Coupling:** The Identity context explicitly imports `src.ledger.domain.events.account_events`. If the Ledger context changes the schema of `AccountCreatedEvent`, the Identity context will fail to import, violating the Dependency Inversion Principle.
*   **Downstream Ambiguity:** The `Notifications` context receives the `UserRegisteredEvent` containing a raw `PhoneEmail` string and must re-implement regex parsing to route SMS vs. Email.

### 2. Root Cause & Impact (WHY)
*   **Root Cause (Phantom Entity):** Synchronous in-process event bus without a distributed transaction (Outbox pattern).
*   **Root Cause (Coupling):** Prioritizing a unified local dashboard view over strict bounded-context isolation and dependency rules.
*   **Impact:** Requires strict schema versioning and monitoring. Read-model repair scripts must be available to reconcile domain state with dashboard state in the event of projection failures.

### 3. Rejected Alternatives
*   **Rejected:** *Implementing the Transactional Outbox Pattern or Anti-Corruption Layers (ACL).*
    *   **Reason:** Discarded as excessive infrastructure overhead for the current scale. The risk of phantom entities and tight compile-time coupling is accepted to maintain absolute architectural simplicity and synchronous execution guarantees.

## Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Monolithic Controller:** `dashboard_controller.py` imports commands from `src.identity` and `src.ledger`, acting as a centralized orchestration layer.
*   **Ambient Unit of Work:** `SqliteUnitOfWork` tracks `_nesting_level` via `contextvars` to allow safe composition of multiple operations without prematurely closing the SQLite connection.
*   **Centralized Generators:** Utility functions like `generate_card_number` and `generate_api_key` are housed in `src.common.infrastructure.generators`.

### 2. Discarded Alternatives (WHY)
*   **Centralized Generators:** Kept in `common` for DRY convenience across the system, even though card generation technically belongs to the Card/Checkout domain and API key generation belongs to Identity.
*   **Nested UoW:** Implemented specifically to prevent SQLite locking exceptions when the DI container or event bus inadvertently nests transaction boundaries.

### 3. Rejected Alternatives
*   **Rejected:** *Context-Specific Domain Factories & Strict Dependency Inversion.*
    *   **Reason:** Discarded to prioritize developer velocity. Strict bounded-context purity (making Identity aware of Ledger events, and generic infrastructure aware of Luhn algorithms) was sacrificed to maintain a single, easily accessible codebase.
*   **Rejected:** *SQLAlchemy or an ORM for the Unit of Work.*
    *   **Reason:** Discarded to maintain raw SQL transparency and avoid the heavy dependency footprint of an ORM, keeping the CQRS projections and nested transaction mechanics explicitly visible and deterministic in the codebase.