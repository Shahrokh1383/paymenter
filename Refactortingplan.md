
# 🏗️ DOCUMENT  : Master Refactoring Plan & Directory Mapping
*This document outlines the exact strategy to dismantle the current 3-tier architecture and rebuild it into an Enterprise DDD Hexagonal Architecture using the Strangler Fig Pattern.*

## 1. Target Enterprise Directory Structure
This is the exact folder hierarchy we are building. Every file must live in its designated Bounded Context and Layer.

```text
paymenter/
├── app/                                  # [Infrastructure] Bootstrap & Wiring
│   ├── di_container.py                   # Wires Ports to Adapters
│   ├── flask_app.py                      # Flask factory & Blueprint registration
│   └── main.py                           # Entry point (Port allocation)
│
├── src/                                  # Source Code Root
│   ├── common/                           # [Shared Kernel] Cross-cutting concerns
│   │   ├── domain/                       # Base Events, Exceptions, Entity base classes
│   │   └── infrastructure/               # SQLite Unit of Work, Event Bus implementation
│   │
│   ├── ledger/                           # [Bounded Context] Core Banking & Accounting
│   │   ├── domain/
│   │   │   ├── entities/                 # Account.py, Transaction.py (Aggregate Roots)
│   │   │   ├── value_objects/            # Money.py, CardNumber.py, AccountNumber.py
│   │   │   ├── services/                 # DoubleEntryLedger.py (Domain Service)
│   │   │   ├── events/                   # FundsHeldEvent.py, TransactionCapturedEvent.py
│   │   │   └── repositories.py           # Abstract interfaces (Ports)
│   │   ├── application/
│   │   │   ├── commands/                 # HoldFundsCommand.py, CaptureFundsCommand.py
│   │   │   └── handlers/                 # HoldFundsHandler.py, CaptureFundsHandler.py
│   │   └── infrastructure/
│   │       ├── persistence/              # SQLite implementations of Ledger repositories
│   │       └── web/                      # Flask API/UI controllers for Ledger
│   │
│   ├── checkout/                         # [Bounded Context] Payment Gateway & Sessions
│   │   ├── domain/                       # PaymentSession.py, OTP.py, SessionToken.py
│   │   ├── application/                  # InitiatePaymentHandler.py, AuthorizeHandler.py
│   │   └── infrastructure/               # Gateway UI controllers, Session DB repos
│   │
│   ├── identity/                         # [Bounded Context] Users & Merchants
│   │   ├── domain/                       # User.py, Merchant.py, ApiKey.py
│   │   └── infrastructure/               # Identity DB repos, Admin UI controllers
│   │
│   └── notifications/                    # [Bounded Context] Emails & Alerts
│       ├── domain/                       # EmailMessage.py, NotificationDispatcher (Port)
│       ├── application/handlers/         # ReceiptEmailHandler.py (Listens to Ledger events)
│       └── infrastructure/smtp/          # SmtpAdapter.py (Connects to local sink)
│
└── tests/                                # Testing (Unit, Integration, E2E)
```

## 2. Current to Target File Mapping
To prevent confusion during the transition, here is exactly where your current code will be migrated:

| Current 3-Tier File | Target DDD Location | Architectural Reason |
| :--- | :--- | :--- |
| `services/ledger.py` | `src/ledger/domain/services/double_entry_ledger.py`<br>`src/ledger/domain/entities/transaction.py` | Extracting state machine logic into the `Transaction` Aggregate and pure math into the Domain Service. |
| `services/gateway_service.py` | `src/checkout/application/handlers/authorize_payment_handler.py` | Moving orchestration out of the domain and into the Application layer. |
| `services/email_service.py` | `src/notifications/infrastructure/smtp/smtp_adapter.py` | SMTP is an infrastructure concern. The domain only knows about a `NotificationDispatcher` interface. |
| `controllers/*` | `src/*/infrastructure/web/*` | Controllers are just HTTP adapters. They belong in the infrastructure layer of their respective contexts. |
| `repositories/*` | `src/*/infrastructure/persistence/*` | Repositories are just database adapters implementing Domain interfaces. |
| `utils/generators.py` | `src/common/infrastructure/generators.py`<br>`src/*/domain/value_objects/*.py` | Generators are infrastructure. Value Objects (like `CardNumber`) belong in the Domain. |
| `database/*` | `src/common/infrastructure/persistence/` | Connection pooling and Unit of Work are shared kernel concerns. |

## 3. Phased Execution Strategy (The Strangler Fig Approach)
We will not rewrite the app in one massive commit. We will build the DDD structure alongside the old code, migrating one Bounded Context at a time.

### Phase 1: The Shared Kernel & Value Objects (Days 1-2)
*   **Action:** Create `src/common/` and `src/ledger/domain/value_objects/`.
*   **Tasks:** Implement `Money`, `CardNumber`, and `AccountNumber` as immutable Python `dataclasses`. Implement the `UnitOfWork` interface and the SQLite `SqliteUnitOfWork` adapter in `common/infrastructure/`.
*   **Rule:** Do not touch `app.py` or existing controllers yet.

### Phase 2: The Ledger Bounded Context (Days 3-5)
*   **Action:** Migrate `services/ledger.py` into `src/ledger/domain/`.
*   **Tasks:** Create the `Account` and `Transaction` Aggregate Roots. Move the `hold_funds` and `complete_funds` logic into the `DoubleEntryLedger` domain service. Define the `AccountRepository` and `TransactionRepository` interfaces (Ports).
*   **Infrastructure:** Create the SQLite implementations of these repositories in `src/ledger/infrastructure/persistence/`.

### Phase 3: The Application Layer & Commands (Days 6-7)
*   **Action:** Create `src/ledger/application/`.
*   **Tasks:** Define `HoldFundsCommand` and `HoldFundsHandler`. The handler will use the `UnitOfWork` and the `DoubleEntryLedger` service to execute the use case.
*   **Refactoring Controllers:** Update `transaction_controller.py` to stop calling raw SQL or services directly. It should now only instantiate a Command and pass it to the Command Handler.

### Phase 4: Decoupling via Domain Events (Days 8-9)
*   **Action:** Implement the Event Bus in `src/common/infrastructure/event_bus.py`.
*   **Tasks:** When the `Transaction` aggregate is captured, it must yield a `TransactionCapturedEvent`. 
*   **Notifications:** Create `src/notifications/`. Build the `SmtpAdapter`. Create an `EmailReceiptHandler` that subscribes to the Event Bus. Remove all `email_service` imports from your controllers.

### Phase 5: Checkout & Identity Contexts (Days 10-12)
*   **Action:** Repeat the process for `gateway_service.py` (Checkout Context) and `merchant_service.py` (Identity Context).
*   **Tasks:** Isolate the OTP generation and Session management into the Checkout context. Isolate Merchant onboarding into the Identity context. Use Anti-Corruption Layers (ACL) if the Checkout context needs to request a fund hold from the Ledger context.

## 4. Rules for Folder & File Creation
When executing the refactoring plan, the following rules apply to file creation:
1.  **One Concept Per File:** A file named `transaction.py` in the domain layer must *only* contain the `Transaction` class. It must not contain `TransactionStatus` enums or `TransactionRepository` interfaces. Those get their own files (`transaction_status.py`, `repositories.py`).
2.  **Handler Granularity:** Every Use Case gets its own Handler file. `HoldFundsHandler.py` and `RefundFundsHandler.py` must be separate files. Do not create a massive `TransactionHandler.py` class.
3.  **No Cross-Context Imports:** A file in `src/checkout/` **must never** have an `import` statement pointing to `src/ledger/` or `src/notifications/`. They must communicate strictly via the Event Bus or by calling an Interface defined in their own domain layer.

***