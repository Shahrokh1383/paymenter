# MODULE DOCUMENTATION: MERCHANT MANAGEMENT

**Version:** 2.0.0 (SSOT)  

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
The Merchant Management module governs the lifecycle of `Merchant` entities within the Identity bounded context. It handles onboarding, secure API key generation, and state transitions (active/inactive). Operating as an internal service for the Administration Dashboard, it utilizes a CQRS-lite architecture with event-driven read-model projections and exposes no external HTTP APIs.

---

## Business Rules

### 1. Specification (WHAT)
*   **API Key Format:** Strictly `pay_` followed by exactly 43 URL-safe characters (Base64URL). Validated by the regex `^pay_[A-Za-z0-9\-_]{43}$`.
*   **State Machine:** A boolean `is_active` flag. State transitions are encapsulated within the `Merchant.toggle()` method to prevent an Anemic Domain Model.
*   **Write Model DDL:** The `merchants` table schema is:
    ```sql
    CREATE TABLE IF NOT EXISTS merchants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        api_key TEXT NOT NULL UNIQUE,
        is_active BOOLEAN NOT NULL DEFAULT 1
    );
    ```

### 2. Rationale & Trade-offs (WHY)
*   **API Key Entropy & Prefix:** The `pay_` prefix ensures immediate visual identification in logs and UI. 43 URL-safe characters provide ~256 bits of entropy, which is sufficient for secure server-to-server integrations without the overhead of asymmetric cryptography.
*   **Toggle over Explicit States:** A single toggle mechanism was chosen for MVP pragmatism and frontend simplicity. Because this is an internal admin tool, the blast radius of an accidental double-toggle is low (temporary service disruption, easily reversible by the admin). There is no irreversible financial loss or data corruption.

### 3. Rejected Alternatives
*   **Rejected:** *Explicit `Activate` and `Deactivate` commands.* 
    *   **Reason:** Adds unnecessary UI complexity and route maintenance for the MVP. A single toggle button drastically speeds up dashboard delivery.
*   **Rejected:** *JWTs or OAuth2 tokens for API keys.* 
    *   **Reason:** Over-engineering. API keys in this context act as long-lived, stateless identifiers; JWT rotation and expiration logic are currently out of scope.

---

## Backend Architecture

### 1. Technical Details & Structure (WHAT)
*   **Domain Layer:** `Merchant` entity, `ApiKey` Value Object (immutable, validates regex in `__post_init__`), and `MerchantRepository` port.
*   **Events:** `MerchantOnboardedEvent`, `MerchantActivatedEvent`, `MerchantDeactivatedEvent`.
*   **Application Layer:** Commands (`OnboardMerchantCommand`, `ToggleMerchantCommand`), Queries (`GetAllMerchantsQuery`), and Read Model Projections (`MerchantOnboardedReadModelHandler`, `MerchantToggledReadModelHandler`).
*   **Infrastructure:** `SqliteMerchantRepository`, `SqliteUnitOfWork`, `InMemoryEventBus`.
*   **Read Model DDL:** The `merchant_summaries` table schema is:
    ```sql
    CREATE TABLE IF NOT EXISTS merchant_summaries (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        api_key TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1
    );
    ```
    *Note: This table intentionally lacks a `FOREIGN KEY` constraint to the `merchants` table.*

### 2. Architectural Decisions (WHY)
*   **No Foreign Key on Read Model:** Read models are denormalized projections. Omitting the FK prevents operational coupling, allows the read model to be rebuilt independently from event logs, and avoids schema conflicts if out-of-order event delivery is introduced later. The application layer (event handlers) maintains referential integrity, not the database.
*   **Separate UoW for Event Subscribers:** The DI container instantiates a *new* `SqliteUnitOfWork` for read-model handlers. This isolates the read-model projection, ensuring that a projection failure (e.g., disk full) cannot accidentally roll back the core write-model transaction, and simplifies the DI wiring (avoiding thread-local scoped containers).
*   **Pure Domain VOs:** The `ApiKey` VO strictly validates format but does not generate the random string. Generation is delegated to the Infrastructure layer (`generators.py`) to keep the Domain pure, deterministic, and easily testable.

### 3. Rejected Alternatives
*   **Rejected:** *Injecting the active UoW into EventBus subscribers.* 
    *   **Reason:** Adds thread-local/scoped DI complexity and risks rolling back the core write transaction if a non-critical read-model projection fails.
*   **Rejected:** *Adding `FOREIGN KEY` constraints to `merchant_summaries`.* 
    *   **Reason:** Violates CQRS independence and couples the read model's lifecycle to the write model, restricting future evolution.

---

## API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **`GET /dashboard/merchants`**: Renders HTML. Triggers `GetAllMerchantsQuery` via `GetAllMerchantsHandler` using the read model.
*   **`POST /dashboard/merchants/add`**: Form data (`name`). Triggers `OnboardMerchantCommand`.
*   **`POST /dashboard/merchants/toggle/<int:id>`**: Path param (`id`). Triggers `ToggleMerchantCommand`.
*   **Error Handling:** The Flask controller wraps execution in a generic `except Exception as e: flash(str(e), 'error')`.

### 2. Contract Choices (WHY)
*   **Internal Admin Tool:** No REST/JSON API is exposed. The module is consumed directly by server-side rendered HTML forms to avoid duplicating authentication/authorization layers for an API that currently has no external consumers.
*   **Synchronous Execution:** The `InMemoryEventBus` executes synchronously to provide immediate UI feedback (via Flask `flash` messages) to the administrator.

### 3. Rejected Alternatives
*   **Rejected:** *Exposing a pure REST/JSON API.* 
    *   **Reason:** No external consumers exist yet; the dashboard handles operations directly.
*   **Rejected:** *Implementing HTTP Idempotency Keys on the toggle route.* 
    *   **Reason:** Deferred to post-MVP. Relying on UI debouncing for now due to the low blast radius of double-toggles in an internal tool.

---

## Execution Flows

### 1. Step-by-step Sequence (WHAT)
*   **Onboarding Flow:**
    1. HTTP POST to `/add` -> Controller instantiates `OnboardMerchantCommand`.
    2. Handler calls `generate_api_key()` (Infrastructure).
    3. Raw string passed to `ApiKey` VO for validation.
    4. `Merchant` entity instantiated (`is_active=True`).
    5. `SqliteUnitOfWork` commits to `merchants` table.
    6. `MerchantOnboardedEvent` published to `InMemoryEventBus`.
    7. `MerchantOnboardedReadModelHandler` catches event, opens a *new* UoW, and inserts into `merchant_summaries`.
*   **Toggle Flow:**
    1. HTTP POST to `/toggle/<id>` -> Controller instantiates `ToggleMerchantCommand`.
    2. Handler fetches `Merchant` via repository.
    3. `merchant.toggle()` invoked.
    4. UoW commits.
    5. Appropriate event (`Activated`/`Deactivated`) published.
    6. Read Model Handler updates `is_active` in `merchant_summaries`.

### 2. Sequence Justification (WHY)
*   **Post-Commit Event Publishing:** Events are published after the UoW commits to ensure that subscribers do not react to phantom entities that might be rolled back.
*   **Synchronous Bus:** Chosen for MVP simplicity and immediate admin feedback, avoiding the complexity of background workers or async queues.

### 3. Rejected Alternatives
*   **Rejected:** *Pre-commit event publishing.* 
    *   **Reason:** Subscribers might query the database for an entity that hasn't been committed yet, leading to race conditions.
*   **Rejected:** *Asynchronous Message Broker (Kafka/RabbitMQ).* 
    *   **Reason:** Unnecessary latency and infrastructure overhead for an internal admin dashboard.

---

## Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **Transaction Inconsistency (Split UoWs):** The write transaction commits, but the read-model projection fails (e.g., SQLite `SQLITE_BUSY`). The merchant exists in `merchants` but is missing from `merchant_summaries`.
*   **Exception Leakage:** `ToggleMerchantHandler` raises a generic `ValueError` for missing merchants. The controller catches generic `Exception` and flashes raw error strings to the UI.
*   **Double-Toggle Race Condition:** Rapid clicking on the toggle button without idempotency guards causes unintended state flips.

### 2. Root Cause & Impact (WHY)
*   **Inconsistency:** Sacrificed strict ACID consistency for DI simplicity and handler isolation. *Impact:* Dashboard may temporarily hide active merchants. *Mitigation:* Planned upgrade to the Outbox Pattern.
*   **Exception Leakage:** Unconscious MVP speed shortcut. *Impact:* Security and UX hazard (raw internal DB errors exposed to admin). *Mitigation:* High-priority fix required (implement `MerchantNotFoundError(DomainException)` and a global Flask `@app.errorhandler`).
*   **Double-Toggle:** Lack of HTTP idempotency. *Impact:* Low blast radius, but unacceptable for production. *Mitigation:* Add client-side debounce or server-side version checks before release.

### 3. Rejected Alternatives
*   **Rejected:** *Implementing the Outbox Pattern immediately.* 
    *   **Reason:** Over-engineering for the current MVP simulator phase.
*   **Rejected:** *Adding retry logic for API key collisions.* 
    *   **Reason:** 256-bit entropy makes collisions astronomically rare; retry loops complicate the handler unnecessarily.

---

## Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Modular DI Container:** `identity_di.py` acts as an isolated wiring module for the Identity bounded context, registering factory functions to the main container and subscribing handlers to the event bus.
*   **Exception Hierarchy:** A base `DomainException` exists in `common/domain/exceptions.py`, establishing a foundation for typed domain errors, though it currently lacks specific Identity exceptions like `MerchantNotFoundError`.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Discarded:** *Monolithic DI Container.* 
    *   **Reason:** Poor separation of concerns; context-specific wiring keeps the main container clean, decoupled, and strictly adheres to the Dependency Inversion Principle.
*   **Discarded:** *Using primitive `str` for all domain errors.* 
    *   **Reason:** Typed exceptions are strictly required for future global error handling, localized translations, and maintaining rigid domain boundaries.