**✅ DOCUMENT : SINGLE SOURCE OF TRUTH – CONSTITUTION**  
**Project:** Paymenter  
**Version:** 1.0.0 (IMMUTABLE)  
**Effective Date:** Upon Delivery  
**Status:** This document is the permanent, unchangeable source of truth for all development, debugging, code generation, and architectural decisions.

---

### 📜 PREAMBLE: THE IRON LAWS

**Rule 0: This Document Is Immutable**  
This constitution is sealed. It will never be edited, appended, or deprecated. All future development, debugging, refactoring, and AI code generation **MUST** derive authority from this document. If a new requirement appears to conflict with this constitution, the requirement must be adjusted — not this document.

**Rule 1: The Dependency Rule (Inviolable)**  
Source code dependencies must point **only inward** toward higher-level policies:

- **Domain** → Never imports Application, Infrastructure, or any framework  
- **Application** → May import Domain, but never Infrastructure or Framework  
- **Infrastructure** → May import Domain and Application (to implement ports), but never the reverse  
- **Framework / Delivery** → May import all layers to wire the application, but business logic never knows about Flask, SQLite, etc.

**Rule 2: New Feature = New File (Strict OCP & SRP Enforcement)**  
When adding new capability:
- **DO**: Create new files (Command, Handler, Event, Adapter, Port, etc.)
- **NEVER**: Modify existing files to add behavior
- **Allowed modifications** (strict exceptions):
  - Pure bug fixes inside the file’s single responsibility
  - Wiring new components within their specific Bounded Context DI module (e.g., app/di/ledger_di.py). The main app/di_container.py must only be modified to register a newly created context module, never individual handlers.
  - Registering new routes/blueprints in framework configuration
  - Extending event catalog when absolutely necessary

**Rule 3: Primitive Obsession Is Forbidden**  
Never pass raw primitives (`float`, `str`, `int`) across layer boundaries for domain concepts. Always use **Value Objects**:

- `float amount + str currency` → `Money(amount: Decimal, currency: CurrencyCode)`
- `str card_number` → `CardNumber(value: str)` (with Luhn validation)
- `str email` → `EmailAddress(value: str)`
- `str token` → `SessionToken(value: str)`

**Rule 4: Aggregates Protect Their Own Invariants**  
Business rules and invariants live **inside Aggregate Roots**. Application services only orchestrate.

**Rule 5: Cross-Context Communication via Domain Events Only**  
Bounded Contexts never call each other directly. They communicate exclusively through **Domain Events** (in-memory EventBus in development, replaceable with Kafka/RabbitMQ in production).

**Rule 6: Infrastructure Is a Plugin**  
Flask, SQLite, SMTP, HTTP clients, etc. are implementation details. They implement interfaces (Ports) defined in the Domain or Application layers.

---

### 🏗️ ARCHITECTURAL LAYERS

1. **Domain Layer** (Core)  
   Pure Python. Entities, Value Objects, Domain Events, Repository Ports, Domain Services.  
   Zero external imports.

2. **Application Layer**  
   Use Cases: Commands, Queries, Handlers, DTOs.  
   Orchestrates Domain and emits events. No infrastructure.

3. **Infrastructure Layer**  
   Adapters (SQLite repositories, HTTP clients, SMTP, etc.), Controllers, DI Container, Framework wiring.

---

### 🗂️ FILE CREATION PROTOCOL – ADDING A NEW FEATURE

**Example:** Adding Webhook Notification on successful transaction.

1. Identify Bounded Context (`ledger`, `checkout`, `notifications`, `identity`, etc.)
2. Create new files:
   - Domain Event: `src/ledger/domain/events/transaction_captured_event.py`
   - Port: `src/notifications/domain/ports/webhook_dispatcher_port.py`
   - Adapter: `src/notifications/infrastructure/adapters/http_webhook_adapter.py`
   - Handler: `src/notifications/application/handlers/webhook_event_handler.py`
3. Wire in `app/di_container.py` (only allowed modification)
4. Write tests first

---

### 🧭 DEVELOPMENT WORKFLOW (SOP)

**For Bug Fixes:**
1. Reproduce the bug with a failing unit test
2. Locate the responsible Aggregate or Domain Service
3. Fix the logic inside the Domain layer
4. Ensure all tests pass
5. Submit PR with test + minimal fix

**For New Features:**
1. Define Domain Model (Entities, Value Objects, Events)
2. Create Command + Handler in Application layer
3. Implement Infrastructure adapters
4. Wire dependencies
5. Write integration + unit tests
6. Document only in API/UI layer

**For Refactoring:**
1. Write characterization tests first
2. Extract Value Objects and move logic into Aggregates
3. Replace direct calls with Ports
4. Delete old code only after full test coverage

---

### 🧪 TESTING STRATEGY – THE TEST PYRAMID

**Unit Tests (Domain) – 70%**  
Location: `tests/unit/<context>/domain/`  
- Zero external dependencies  
- Test invariants and business rules  
- Must run under 10ms

**Integration Tests – 25%**  
Location: `tests/integration/<context>/`  
- Use real in-memory SQLite  
- Test handlers, repositories, event bus  
- Mock only external services

**End-to-End Tests – 5%**  
Location: `tests/e2e/`  
- Full HTTP flow using Flask test client  
- Test observable behavior only

---

### 🏷️ NAMING CONVENTIONS & CODE STANDARDS

**File Naming (snake_case):**
- Domain: `entities.py`, `value_objects.py`, `events.py`, `repositories.py`
- Application: `commands.py`, `handlers.py`, `queries.py`
- Infrastructure: `sqlite_transaction_repo.py`, `http_webhook_adapter.py`

**Class Naming:**
- Aggregates: `Transaction`, `Account`, `PaymentSession`
- Value Objects: `Money`, `CardNumber`, `EmailAddress` (`@dataclass(frozen=True)`)
- Commands: `CaptureFundsCommand`
- Handlers: `CaptureFundsHandler`
- Events: `TransactionCapturedEvent`

**Method Naming:**
- Domain: `capture()`, `authorize()`, `deposit()`
- Application: `handle(command)`
- Infrastructure: `save()`, `post()`

**Type Hints:** Mandatory everywhere.

---

### 🔐 SECURITY & COMPLIANCE

- Sensitive data (card numbers, OTPs) must **never** be logged
- Raw card numbers exist only temporarily in `checkout` context
- Ledger context never sees card data — only `AccountId` and `Money`
- All state changes must emit Domain Events for audit
- Use proper encryption and hashing (bcrypt, etc.)

---

### 🚀 PERFORMANCE & SCALABILITY

- All queries must be indexed (verified with `EXPLAIN QUERY PLAN`)
- No N+1 queries
- Pagination required for all list endpoints
- Aggregates use optimistic locking or `SELECT FOR UPDATE`
- Cache invalidation driven by Domain Events (never in Domain logic)

---

### 📚 GLOSSARY – UBIQUITOUS LANGUAGE

| Term                  | Definition                                                                 | Context      |
|-----------------------|----------------------------------------------------------------------------|--------------|
| Transaction           | Immutable record of fund movement with strict state machine                | ledger       |
| PaymentSession        | Temporary tokenized checkout flow with card + OTP                          | checkout     |
| Money                 | Value Object (Decimal + CurrencyCode)                                      | common       |
| Capture               | Finalizing a Pending transaction                                           | ledger       |
| Hold                  | Reserving funds in a Pending state                                         | ledger       |
| Bounded Context       | Logical boundary with its own domain model                                 | Architecture |
| Domain Event          | Immutable fact that something happened in the domain                       | All          |

---

### ✅ CODE REVIEW CHECKLIST (MANDATORY)

- No primitives for domain concepts
- No infrastructure imports in Domain/Application
- New files created instead of modifying existing ones (unless exception)
- Communication via Domain Events only
- All invariants protected inside Aggregates
- Tests follow the pyramid
- Follows SOLID, KISS, DRY, and this Constitution

---

**This document is the Single Source of Truth.**  
Every developer, AI agent, and automated pipeline **must** follow it strictly. Any code violating this constitution will be rejected.

---