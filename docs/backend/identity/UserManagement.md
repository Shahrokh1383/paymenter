# MODULE DOCUMENTATION: USER MANAGEMENT

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
The User Management module manages the lifecycle of `User` entities within the Identity bounded context. It operates on a strict Hexagonal/DDD architecture with a CQRS-lite read-model projection. The write-side handles registration, enforcing domain invariants via the `PhoneEmail` Value Object. The read-side maintains a denormalized `user_summaries` table to serve the internal Administration Dashboard. The module is designed as a zero-ops local simulator, prioritizing immediate consistency and simplicity over production-grade fault isolation and horizontal scalability.

## Business Rules

### 1. Specification (WHAT)
*   **User Uniqueness & Normalization:** Users are uniquely identified by a `PhoneEmail` Value Object. Emails are normalized to lowercase; phones are validated against E.164. A user cannot be registered if the `PhoneEmail` exists in the `users` table.
*   **Entity Attributes:** A `User` consists of an auto-incrementing integer `id`, a `name`, and the `PhoneEmail` contact.
*   **Domain Events:** Successful registration emits a `UserRegisteredEvent` containing the `user_id`, `name`, and normalized `PhoneEmail`.

### 2. Rationale (WHY)
*   **Single String Value Object:** Combining phone and email into a single `PhoneEmail` string simplifies the UI and allows a single `UNIQUE` constraint in SQLite to prevent duplicate accounts across both mediums. Normalization prevents casing-based duplicates.
*   **Surrogate Key:** Using an auto-incrementing integer ID decouples the user's internal identity from their mutable contact information, allowing future contact updates without breaking foreign keys.

### 3. Rejected Alternatives
*   **Rejected:** *Separate `Phone` and `Email` Value Objects / Two Nullable Columns.*
    *   **Reason:** Discarded because it complicates the database schema (requiring composite constraints or complex domain logic to ensure at least one is present) and makes the SQLite `UNIQUE` constraint implementation significantly harder. We sacrificed downstream type-ambiguity (forcing the Notifications context to re-parse the string to decide between SMS/Email routing) to achieve write-side simplicity.

## Backend Architecture

### 1. Technical Details (WHAT)
*   **Domain & Application:** Pure Python dataclasses (`User`, `PhoneEmail`, `RegisterUserCommand`). Handlers rely strictly on the `UnitOfWork` and `EventBus` ports.
*   **Persistence:** `SqliteUserRepository` persists to SQLite. The `SqliteUnitOfWork` creates a fresh `sqlite3` connection per request, enforcing `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode=WAL`.
*   **CQRS Read Model:** A `user_summaries` table is populated synchronously via `UserRegisteredReadModelHandler` listening to `UserRegisteredEvent`.

### 2. Decisions (WHY)
*   **SQLite with WAL Mode:** Chosen explicitly for a "zero-ops" local simulator environment. It requires no external database services, making the project instantly runnable on any developer machine.
*   **Synchronous In-Memory Event Bus:** Ensures immediate consistency for the read model. When the HTTP request completes, the dashboard is guaranteed to show the new user.
*   **Denormalized Read Model (`user_summaries`):** Pre-joins user data with future account/card data to prepare the Identity context for a future microservice split, strictly adhering to the architectural constitution that contexts must not share database schemas or perform cross-context JOINs.

### 3. Rejected Alternatives
*   **Rejected:** *PostgreSQL / MySQL with Connection Pooling.*
    *   **Reason:** Discarded to maintain the zero-ops simulator mandate. We sacrificed concurrent write throughput, row-level locking, and advanced indexing to eliminate infrastructure dependencies.
*   **Rejected:** *Out-of-Process Message Broker (Kafka/RabbitMQ) or Async Background Workers.*
    *   **Reason:** Discarded to avoid infrastructure complexity and maintain immediate consistency in the local simulator. We sacrificed fault-isolation (a failing read-model handler crashes the write request) and horizontal scalability.
*   **Rejected:** *SQL JOINs across `users`, `accounts`, and `user_cards` at query time.*
    *   **Reason:** Discarded to enforce strict bounded-context isolation. We sacrificed DRY principles and short-term query simplicity to ensure the Identity context can be physically separated into a microservice later without breaking read capabilities.

## API Contract / Integration

### 1. Exact Endpoints/Schemas (WHAT)
*   **Delivery Mechanism:** Server-Side Rendered (SSR) HTML via Flask/Jinja2. No public JSON API exists.
*   **Internal Routes:**
    *   `GET /dashboard/users` -> Executes `GetAllUsersQuery` or `SearchUsersQuery`.
    *   `POST /dashboard/users/add` -> Accepts form data, maps to `RegisterUserCommand`.
*   **Integration:** Consumed exclusively by the Administration Dashboard module. Downstream contexts (Ledger, Checkout) integrate via the `InMemoryEventBus`.

### 2. Contract Choices (WHY)
*   **SSR via Flask:** Chosen for rapid MVP delivery. It eliminates the need for a frontend build pipeline (React/Next.js) and allows a single developer to ship a fully functional admin UI alongside the backend.
*   **No CSRF Protection:** The simulator relies on a hardcoded `secret_key` and implicit trust, assuming it runs strictly on `localhost` accessed only by the developer.

### 3. Rejected Alternatives
*   **Rejected:** *Decoupled SPA (React/Next.js) consuming a JSON API.*
    *   **Reason:** Discarded to accelerate MVP delivery. We sacrificed API-first design, frontend/backend separation, and built-in web security (CSRF tokens) to deliver a functional local UI in the shortest possible time.

## Execution Flows

### 1. Step-by-step Sequence (WHAT)
1.  **Input:** Admin submits form to `POST /dashboard/users/add`.
2.  **Translation:** `dashboard_controller` maps form data to `RegisterUserCommand`.
3.  **Validation:** `RegisterUserHandler` instantiates `PhoneEmail` (validates regex, normalizes).
4.  **Transaction Start:** `SqliteUnitOfWork` opens a connection and begins transaction.
5.  **Invariant Check:** Handler calls `exists_by_phone_email`.
6.  **Persistence:** Handler calls `repo.add(user)`, SQLite assigns `lastrowid`.
7.  **Commit:** `uow.commit()` is called. The `users` row is permanently written.
8.  **Event Emission:** Handler publishes `UserRegisteredEvent` to `InMemoryEventBus`.
9.  **Read-Model Projection:** `UserRegisteredReadModelHandler` catches the event, opens a *new* UoW, inserts into `user_summaries`, and commits.
10. **Response:** Controller redirects to `GET /dashboard/users`.

### 2. Sequence Justification (WHY)
*   **Commit before Publish:** The write-side transaction must be committed before publishing events to ensure downstream handlers don't attempt to read uncommitted data (though in SQLite with a single connection pool, this is less risky, it is a strict DDD best practice).
*   **New UoW in Read-Model Handler:** The read-model handler creates its own `SqliteUnitOfWork` to ensure its projection is committed independently, though in this synchronous setup, it executes in the same thread.

### 3. Rejected Alternatives
*   **Rejected:** *Catching `IntegrityError` instead of an explicit existence check.*
    *   **Reason:** Discarded because relying on database exceptions leaks infrastructure concerns into the application layer and makes it difficult to return clean, user-friendly flash messages to the SSR dashboard.

## Edge Cases & Known Issues

### 1. Specific Scenario (WHAT)
*   **The "Phantom User" Anomaly:** If `uow.commit()` succeeds, but the synchronous `UserRegisteredReadModelHandler` fails (e.g., disk full, or a bug in the projection SQL), the HTTP request crashes with a 500 error. However, the `users` table retains the new user, while the `user_summaries` table does not. The user exists in the domain but is invisible to the dashboard.
*   **Downstream Ambiguity:** The `Notifications` context receives the `UserRegisteredEvent` containing a raw `PhoneEmail` string. It has no native way to know if it should dispatch an SMS or an Email without re-implementing the regex parsing logic.

### 2. Root Cause & Impact (WHY)
*   **Root Cause:** The decision to use a synchronous, in-process event bus without a distributed transaction (Saga/Outbox pattern) or a retry mechanism for read-model projections.
*   **Impact:** Low for a local simulator, but catastrophic for a production payment system. Data inconsistency between the write-model and read-model.

### 3. Rejected Alternatives
*   **Rejected:** *Implementing the Transactional Outbox Pattern or Distributed Sagas.*
    *   **Reason:** Discarded as massive over-engineering for a local simulator. We accepted the risk of phantom users to maintain absolute architectural simplicity and zero external dependencies.

## Architectural Notes

### 1. Current Implementation (WHAT)
*   **Centralized Generators:** Utility functions like `generate_card_number` (Luhn algorithm) and `generate_api_key` are housed in a generic `src/common/infrastructure/generators.py` file.
*   **Connection-per-Request:** The `SqliteUnitOfWork` does not use connection pooling. It opens and closes a file handle on every single command/query execution.

### 2. Discarded Alternatives (WHY)
*   **Centralized Generators:** Kept in `common` for DRY (Don't Repeat Yourself) convenience across the simulator, even though card generation technically belongs to the Checkout/Card domain.
*   **Connection-per-Request:** Kept because SQLite's file-system locking mechanism (even in WAL mode) means a connection pool would not significantly improve write throughput, and managing pool lifecycles in a simple Flask app adds unnecessary boilerplate.

### 3. Rejected Alternatives
*   **Rejected:** *Context-Specific Domain Factories (e.g., `CardNumberFactory` inside the Identity or Checkout context).*
    *   **Reason:** Discarded to prioritize developer speed and DRY principles in the simulator. We sacrificed strict bounded-context purity (making generic infrastructure aware of domain-specific generation rules like Luhn) to maintain a single, easily accessible utility file.
*   **Rejected:** *SQLAlchemy or an ORM for the Unit of Work.*
    *   **Reason:** Discarded to maintain raw SQL transparency and avoid the "magic" and heavy dependency footprint of an ORM, keeping the simulator lightweight and the CQRS projections explicitly visible in the codebase.