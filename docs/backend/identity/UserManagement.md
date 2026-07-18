# MODULE DOCUMENTATION: USER MANAGEMENT

**Version:** 1.0.0 (SSOT)  

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
The User Management module is responsible for the entire lifecycle of `User` entities within the Identity bounded context. It enforces domain invariants related to contact uniqueness and normalization through the `PhoneEmail` Value Object. It operates as a purely internal domain, exposing no public API; its functionality is consumed exclusively by application-layer command handlers that react to administrative inputs. The module emits `UserRegisteredEvent` to signal user creation, enabling downstream read-model projection and cross-context coordination (notably virtual card provisioning).

---

## Business Rules

### 1. Specification (WHAT)
*   **User Uniqueness & Normalization:** 
    *   Users are uniquely identified by a `PhoneEmail` Value Object.
    *   **Emails:** Validated via regex, automatically stripped of whitespace, and normalized to lowercase.
    *   **Phones:** Validated against E.164 format (`^\+?[1-9]\d{1,14}$`).
    *   **Invariant:** A user cannot be registered if the `PhoneEmail` already exists in the `users` table.
*   **User Entity Attributes:** A `User` consists of an immutable identifier, a display `name`, and the `PhoneEmail` contact. The identifier is generated upon persistence.
*   **Domain Events:** Every successful user registration emits a `UserRegisteredEvent` containing the user’s id, name, and normalized contact.

### 2. Rationale & Trade-offs (WHY)
*   **Why `PhoneEmail` as a single Value Object?** To allow users to register with either a phone number or an email seamlessly while preventing primitive obsession at the domain boundary. Normalization (lowercase emails) prevents duplicate account creation due to casing differences.
*   **Why enforce the invariant at the repository level?** The `exists_by_phone_email` check, combined with the `UNIQUE` constraint on the `phone_email` column, provides a defence-in-depth guarantee against duplicates, even in concurrent scenarios.

### 3. Rejected Alternatives
*   **Rejected:** *Separate `Phone` and `Email` Value Objects.*
    *   **Reason:** The business requirement allows registration via *either* method in a single field. Combining them into `PhoneEmail` simplifies the UI and the unique constraint logic in the database.

---

## Backend Architecture

### 1. Specification (WHAT)
*   **Domain Layer:**
    *   Entity: `User` (with `id`, `name`, `phone_email`).
    *   Value Object: `PhoneEmail` – encapsulates validation, stripping, and normalization logic.
    *   Domain Event: `UserRegisteredEvent`.
    *   Repository Interface: `UserRepository` (abstraction) with methods `add(user)`, `exists_by_phone_email(value)`.
*   **Application Layer:**
    *   Command: `RegisterUserCommand(name, phone_email)`.
    *   Handler: `RegisterUserHandler` – validates input, creates `User`, checks uniqueness via repository, persists, and publishes `UserRegisteredEvent`.
*   **Infrastructure Layer:**
    *   Repository Implementation: `SqliteUserRepository` persisting to the `users` table.
    *   Database Schema:
        ```sql
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_email TEXT NOT NULL UNIQUE
        );
        ```
    *   The `users` table is defined in an isolated schema file (`identity.py`) and aggregated into the master schema via `src/common/infrastructure/database/__init__.py`.

### 2. Rationale & Trade-offs (WHY)
*   **Why a dedicated repository interface?** It strictly adheres to the Dependency Inversion Principle. The domain and application layers have zero knowledge of SQLite; the infrastructure layer becomes a plugin that can be swapped without touching business logic.
*   **Why an autoincrement integer primary key?** For MVP simplicity, providing a sequential, lightweight identifier for internal references. The user’s external identity is carried by the `PhoneEmail`.

### 3. Rejected Alternatives
*   **Rejected:** *Using `PhoneEmail` as the primary key.*
    *   **Reason:** A user may wish to change their contact in the future. Using a surrogate key decouples identity from the mutable contact attribute.

---

## API Contract / Integration

### 1. Specification (WHAT)
*   **Contract Type:** This module exposes no direct HTTP or network API. It is an internal bounded-context component.
*   **Public Interface:** The module’s functionality is accessible only through the `RegisterUserHandler` application service, which is invoked by the Administration Dashboard module (or potentially by other contexts in the future).
*   **Input:** `RegisterUserCommand` Data Transfer Object (DTO).
*   **Output:** On success, a `UserRegisteredEvent` is published; no return value is expected by the caller besides a success indication via exception handling.

### 2. Rationale & Trade-offs (WHY)
*   **Why no public API?** User management is an internal administrative function. All external interaction is channelled through the admin dashboard’s HTML forms. Exposing a raw API would widen the attack surface without business need.
*   **Why communicate only through events?** The event is the contract that allows other modules (Read Model Projections, Card Provisioning) to react without knowing user registration internals.

### 3. Rejected Alternatives
*   **Rejected:** *Direct method calls between modules for post-registration actions.*
    *   **Reason:** Would create source-code coupling. The event-driven approach keeps the User module oblivious of downstream consumers.

---

## Execution Flows

### 1. Specification (WHAT)
**Flow: User Registration (within User Management scope)**
1.  **Command:** Admin submits form data, which is translated into `RegisterUserCommand(name, phone_email)`.
2.  **Validation:** `RegisterUserHandler` instantiates `PhoneEmail` – the Value Object constructor validates format (email regex or E.164), strips whitespace, normalizes email to lowercase. If invalid, an exception is raised.
3.  **Uniqueness Check:** Handler calls `UserRepository.exists_by_phone_email(phone_email_value)`. If `True`, registration is rejected with a domain error.
4.  **Entity Creation:** A new `User` entity is instantiated with the provided `name` and the valid `PhoneEmail`.
5.  **Persistence:** The repository’s `add(user)` is called, and the Unit of Work commits the transaction.
6.  **Event Emission:** `UserRegisteredEvent` is published via the in-memory event bus. The handler then returns.

### 2. Rationale & Trade-offs (WHY)
*   **Why validate in the Value Object constructor?** Guarantees that any `PhoneEmail` instance in the system is always valid, making invalid states unrepresentable.
*   **Why a separate existence check before `add`?** SQLite’s `UNIQUE` constraint acts as a final safeguard, but the explicit check enables a clear, user-friendly error message (e.g., “User already exists”) without relying on parsing a database exception.

### 3. Rejected Alternatives
*   **Rejected:** *Catching `IntegrityError` instead of an explicit existence check.*
    *   **Reason:** Relying solely on database exceptions leaks infrastructure concerns into the application layer and makes it harder to distinguish “duplicate user” from other integrity violations.

---

## Edge Cases & Known Issues

### 1. Specification (WHAT)
*   **Concurrent Duplicate Registration:** In a high-concurrency scenario, two requests could both pass the existence check before either commits, causing the second to fail on the `UNIQUE` constraint. This results in an unhandled `IntegrityError` that must be caught and translated into a domain error.
*   **Normalization Bypass:** Any code that constructs a `User` entity without going through the `PhoneEmail` VO could bypass validation. The architecture mitigates this by making `PhoneEmail` the sole constructor parameter for the contact.

### 2. Rationale & Trade-offs (WHY)
*   **Why accept a possible `IntegrityError`?** The probability is negligible for an admin-facing dashboard with human-speed inputs. Adding a pessimistic lock or advisory lock on SQLite would introduce complexity unjustified by the risk.
*   **Why enforce construction strictly?** The domain layer is kept pure by ensuring all contact creation passes through the Value Object; no raw strings are ever assigned to the entity’s contact attribute.

### 3. Rejected Alternatives
*   **Rejected:** *Application-level pessimistic lock before the existence check.*
    *   **Reason:** SQLite’s write lock already serializes writers; an additional lock would be redundant and could introduce deadlocks in future multi-context scenarios.

---

## Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Schema Isolation:** The `users` table DDL is defined in a dedicated file and imported into the master database schema initializer, preserving separation of concerns.
*   **Dependency Injection:** The `RegisterUserHandler` is never instantiated directly by controllers; it is obtained through `current_app.di_container.get_register_user_handler(uow)`. This ensures the handler depends only on abstractions (repository, event bus) and supports testability.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Including user read-model updates directly in the registration handler.*
    *   **Reason:** Would violate Single Responsibility Principle. The handler focuses on the write side; materialization is delegated to a dedicated Read Model Projections module through event handling.
*   **Rejected:** *Storing `PhoneEmail` as two separate columns (phone, email) and deducing type.*
    *   **Reason:** Overcomplicates the schema and does not reflect the business rule that the field is a single “contact” regardless of type.
