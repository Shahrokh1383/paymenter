# MODULE DOCUMENTATION: MERCHANT MANAGEMENT

**Version:** 1.0.0 (SSOT - Code-Synchronized)  

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
The Merchant Management module governs the lifecycle of `Merchant` entities. It is responsible for onboarding new merchants, generating cryptographically sufficient API keys, and managing the merchant’s active/inactive state. It operates entirely within the Identity bounded context as an internal service, exposing no direct HTTP endpoints. Its functionality is consumed by the Administration Dashboard, and it emits domain events (`MerchantOnboardedEvent`, `MerchantActivatedEvent`, `MerchantDeactivatedEvent`) to notify the rest of the system of state changes.

---

## Business Rules

### 1. Specification (WHAT)
*   **Merchant API Key Generation:**
    *   Every `Merchant` is issued an `ApiKey` upon onboarding.
    *   **Format:** Strictly `pay_` followed by exactly 43 URL-safe characters (Base64URL), validated by the regex `^pay_[A-Za-z0-9\-_]{43}$`.
    *   The key is unique across all merchants.
*   **Merchant State Machine:**
    *   Merchants possess a boolean `is_active` state.
    *   State transitions emit `MerchantActivatedEvent` (when toggled active) or `MerchantDeactivatedEvent` (when toggled inactive).
*   **Merchant Entity Attributes & Behavior:** A `Merchant` has an identifier, a `name`, an `ApiKey`, the `is_active` flag, and a `toggle()` method to encapsulate state mutation.

### 2. Rationale & Trade-offs (WHY)
*   **Why strict `pay_` prefix and 43-char length for API keys?** Ensures immediate visual identification of keys in logs/UI and provides sufficient entropy (~256 bits) for secure external merchant integrations without requiring asymmetric cryptography overhead.
*   **Why a boolean state instead of a full status enum?** The MVP only requires active/inactive; a full status machine (pending, suspended, etc.) would be over-engineering. The event emission per toggle prepares the system for future complex states.

### 3. Rejected Alternatives
*   **Rejected:** *Using JWTs or OAuth2 tokens for Merchant API keys.*
    *   **Reason:** API keys in this context act as long-lived, stateless identifiers for server-to-server integrations. JWTs introduce expiration and rotation complexity that is currently out of scope.
*   **Rejected:** *Generating API keys without the `pay_` prefix.*
    *   **Reason:** Without the prefix, it is harder to distinguish a merchant key from other tokens or identifiers in logs and debugging.

---

## Backend Architecture

### 1. Specification (WHAT)
*   **Domain Layer:**
    *   Entity: `Merchant` (with `id`, `name`, `api_key`, `is_active`, and `toggle()` method).
    *   Value Object: `ApiKey` – encapsulates format validation and the `pay_` prefix invariant.
    *   Domain Events: `MerchantOnboardedEvent`, `MerchantActivatedEvent`, `MerchantDeactivatedEvent`.
    *   Repository Interface: `MerchantRepository` with methods `add(merchant)`, `update(merchant)`, `get_by_id(id)`, `get_all_summaries()`, and `get_by_api_key(api_key)`.
*   **Application Layer:**
    *   Commands: `OnboardMerchantCommand(name)`, `ToggleMerchantCommand(merchant_id)`.
    *   Handlers: `OnboardMerchantHandler` (invokes infrastructure generator, instantiates VO/Entity, persists, publishes event) and `ToggleMerchantHandler` (retrieves merchant, invokes entity toggle, updates, emits event).
*   **Infrastructure Layer:**
    *   Repository Implementation: `SqliteMerchantRepository`.
    *   API Key Generator: `src.common.infrastructure.generators` provides the secure random string generation function.
    *   Dependency Injection: `src/app/di_container.py` acts as the central registry, delegating bounded-context wiring to modular files (e.g., `src/app/di/identity_di.py`).
    *   Database Schema: Defines the `merchants` write-model table and aggregates the `merchant_summaries` read-model schema.

### 2. Rationale & Trade-offs (WHY)
*   **Why separate API key generation (Infrastructure) from validation (Domain VO)?** Secure random generation is an infrastructure concern. By generating the raw string outside and passing it to the `ApiKey` VO, we keep the Domain layer pure, easily testable, and strictly focused on format invariants.
*   **Why encapsulate the state toggle inside the Entity?** Calling `merchant.toggle()` prevents an Anemic Domain Model. It ensures that state mutations are co-located within the entity rather than scattered across application handlers.

### 3. Rejected Alternatives
*   **Rejected:** *Letting the handler directly manipulate the `is_active` attribute.*
    *   **Reason:** Direct manipulation leads to an anemic domain model. Encapsulating the logic via `merchant.toggle()` is cleaner and protects entity invariants.
*   **Rejected:** *Putting API key validation logic in the infrastructure layer.*
    *   **Reason:** Validation rules (format, prefix) are domain invariants and strictly belong to the domain layer's Value Objects.

---

## API Contract / Integration

### 1. Specification (WHAT)
*   **Contract Type:** This module exposes no direct HTTP API. It provides application-level services consumed by the Administration Dashboard.
*   **Public Interface:** `OnboardMerchantHandler` and `ToggleMerchantHandler` are the entry points, invoked via command DTOs.
*   **Output:** Domain events are published; the handlers raise exceptions for errors (e.g., not found).

### 2. Rationale & Trade-offs (WHY)
*   **Why no Merchant CRUD REST API?** Merchants are managed internally by the back-office. The dashboard renders HTML and calls these handlers directly. A separate API would duplicate authentication and authorization concerns with no current consumer.

### 3. Rejected Alternatives
*   **Rejected:** *Exposing an endpoint to retrieve the API key after onboarding.*
    *   **Reason:** The key is displayed in the dashboard HTML during the onboarding flow. Adding a separate retrieval endpoint could lead to security risks if not properly protected; the dashboard’s server-side rendering mitigates this.

---

## Execution Flows

### 1. Specification (WHAT)
**Flow: Merchant Onboarding**
1.  **Command:** Admin submits `OnboardMerchantCommand(name)`.
2.  **Key Generation:** Handler invokes `generate_api_key()` from the infrastructure `generators` module.
3.  **Validation & Entity Creation:** The raw string is passed to the `ApiKey` VO (which validates the format), then the `Merchant` entity is instantiated with `is_active = True`.
4.  **Persistence:** `MerchantRepository.add(merchant)` is called; the Unit of Work commits.
5.  **Event:** `MerchantOnboardedEvent` is published.

**Flow: Merchant Activation/Deactivation**
1.  **Command:** Admin triggers `ToggleMerchantCommand(merchant_id)`.
2.  **Fetch:** Handler retrieves the `Merchant` via repository.
3.  **State Flip:** The handler invokes the entity's `merchant.toggle()` method.
4.  **Persistence:** Repository updates the merchant; UoW commits.
5.  **Event:** `MerchantActivatedEvent` or `MerchantDeactivatedEvent` is published based on the new state.

### 2. Rationale & Trade-offs (WHY)
*   **Why generate the key outside the VO?** It keeps the `ApiKey` VO free from randomness and external dependencies, making it a pure, easily testable value object that only enforces invariants.
*   **Why a single toggle command?** Reduces API surface; the handler inspects the current state and emits the appropriate event. This is simpler than exposing separate `Activate` and `Deactivate` commands.

### 3. Rejected Alternatives
*   **Rejected:** *Allowing the dashboard to directly toggle via a raw SQL update.*
    *   **Reason:** Bypasses domain logic and event emission, breaking the reactive architecture.

---

## Edge Cases & Known Issues

### 1. Specification (WHAT)
*   **API Key Collision:** The generation uses a cryptographically random string. In theory, a collision could occur, but with 256 bits of entropy the probability is astronomically low. There is no retry logic.
*   **Concurrent Toggle:** Two simultaneous toggles could lead to a lost update. With SQLite’s serialized writes, the second transaction will see the updated state and apply its toggle correctly; however, the resulting events may be fired in a sequence that briefly represents an incorrect intermediate state if not observed carefully.

### 2. Rationale & Trade-offs (WHY)
*   **Why no key collision retry?** The chance is negligible; adding a retry loop would complicate the handler for no practical benefit in an MVP.
*   **Why accept eventual ordering issues?** The in-memory synchronous bus ensures that within a single request, the event is processed immediately. Across requests, the state is eventually consistent; this is acceptable for an admin tool.

### 3. Rejected Alternatives
*   **Rejected:** *Using a monotonic counter for API key generation.*
    *   **Reason:** Predictable keys are less secure; they would allow an attacker to guess valid keys.

---

## Architectural Notes & Rejected Decisions

### 1. Current Implementation (WHAT)
*   **Modular DI Container Usage:** The central `DIContainer` initializes global singletons (like `InMemoryEventBus`) and delegates context-specific handler registrations to isolated modules (e.g., `register_identity(self)` inside `src/app/di/identity_di.py`), keeping the main container class clean and decoupled.
*   **CQRS-lite / Read Models:** The `SqliteMerchantRepository` implements `get_all_summaries()` which queries a dedicated `merchant_summaries` read-model table (returning `MerchantSummaryDTO`). This optimizes dashboard list queries without the overhead of hydrating full domain entities.

### 2. Discarded Alternatives & Reasons (WHY)
*   **Rejected:** *Storing API keys as a hash.*
    *   **Reason:** For the MVP simulator, the key must be displayable to the admin. Hashing would prevent display and require a separate “reveal once” mechanism, adding complexity.
*   **Rejected:** *Hydrating full entities for dashboard lists.*
    *   **Reason:** Fetching full `Merchant` entities just to display a list of names and statuses is inefficient. A dedicated read-model schema (`merchant_summaries`) provides better performance for UI rendering.