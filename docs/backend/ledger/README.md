# Ledger Module — High-Level Architecture & Single Source of Truth

> **Immutable Document**: This document captures the permanent architectural
> decisions and core principles of the Ledger bounded context. It does not
> change with implementation details; those live in the detailed module docs.

---

## Purpose

The Ledger is the **financial core** of the Paymenter platform, responsible for
immutable recording of all fund movements, account balance management, and
enforcement of double-entry accounting invariants. It operates under **Domain-
Driven Design (DDD)** with **Clean Architecture** layering.

---

## Core Architectural Principles (Constitution)

1. **Dependency Inward** – Domain has zero external imports; infrastructure
   depends on domain ports.
2. **Aggregates Protect Invariants** – `Account` and `Transaction` entities
   enforce their own business rules (non‑negative balance, state machine, etc.).
3. **No Primitive Obsession** – All monetary values use `Money` value objects;
   statuses are not raw strings (debt: TD‑1, TD‑6).
4. **Cross‑Context via Events** – Ledger never calls other contexts directly;
   all communication is through domain events published **after** Unit of Work
   commit.
5. **CQRS for Queries** – Read models (`AccountSummary`, `TransactionListItem`)
   are served through dedicated query ports, never through the domain
   aggregates.
6. **Double‑Entry Accounting** – Every fund movement has a debit and a credit.
   A system escrow account (liability) will be introduced to hold pending funds
   (debt: TD‑7).

---

## High-Level Structure

```
Ledger Bounded Context
├── Domain Layer (pure business logic)
│   ├── Account aggregate (balance, currency, invariants)
│   ├── Transaction aggregate (state machine: Pending → Success/Failed/Refunded)
│   ├── DoubleEntryLedger domain service
│   └── Domain events (TransactionCompleted, Failed, Refunded)
├── Application Layer (use cases)
│   ├── Commands: HoldFunds, CompleteFunds, FailAndRefund, TopupAccount,
│   │            UpdateAccountCurrency
│   ├── Queries: GetTransactions, GetAllAccounts
│   └── Handlers that orchestrate domain objects and publish events
├── Infrastructure Layer
│   ├── SQLite repositories (implement domain ports)
│   ├── Unit of Work (transactional boundary)
│   ├── Flask API controller (HTTP endpoints)
│   └── CQRS read models (SQLite views for queries)
└── Cross‑Context Integration
    ├── InMemoryEventBus (synchronous pub/sub)
    └── ReceiptEmailHandler (subscribes to transaction events)
```

### Logical Modules (Detailed Docs)

The full documentation is split into 8 focused modules (each a separate,
stable document):

1. **Account Domain** – Entity, value objects, repository port, balance invariants.
2. **Account Application** – Topup/currency change commands, account queries.
3. **Transaction Domain** – Transaction entity, state machine, double-entry service, domain events.
4. **Transaction Application (Commands)** – Hold/complete/refund handlers, event publishing.
5. **Transaction Application (Queries)** – Read model for transaction lists.
6. **Ledger Infrastructure & Persistence** – SQLite repos, Unit of Work, database schema.
7. **Ledger HTTP API** – Flask routes, API contract, temporary DI.
8. **Eventing & Cross‑Context Integration** – DI container, EventBus, email notifications.

> **Important**: Those module documents contain the evolving implementation
> details, known issues, and technical debt. This README remains the
> permanent architectural anchor.

---

## Key Business Rules (Immutable)

| ID  | Rule | Enforced By |
|-----|------|-------------|
| BR‑1 | Account balance never negative | `Account.withdraw()` |
| BR‑2 | All inter‑account ops require same currency | Domain service / handlers |
| BR‑3 | Transaction state machine is strict (Pending→Success/Failed, Success→Refunded) | `Transaction` entity |
| BR‑4 | Double‑entry: every movement balances (debit = credit) | `DoubleEntryLedger` service |
| BR‑5 | Currency change only when balance = 0 | `Account.can_change_currency()` |
| BR‑6 | Topup amount > 0 | `TopupAccountHandler` |
| BR‑7 | Every state change emits a domain event | Handlers publish after UoW commit |

---

## API at a Glance (Permanent Contract)

All endpoints are under `/transactions`:

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| `GET`  | `/` | List transactions (optional `?status=`) | HTML page |
| `POST` | `/create` | Initiate a hold (form data) | Redirect + flash |
| `POST` | `/complete/<id>` | Finalise a pending transaction | JSON `{success, new_status}` |
| `POST` | `/fail/<id>` | Fail or refund a transaction | JSON `{success, new_status}` |

- Complete and Fail endpoints return JSON; the others return HTML (subject to
  future API versioning but this contract defines the core operations).

---

## Integration & Event Flow

1. A transaction is created/updated inside a Unit of Work.
2. After `uow.commit()`, the handler publishes one of:
   - `TransactionCompletedEvent`
   - `TransactionFailedEvent`
   - `TransactionRefundedEvent`
3. The `InMemoryEventBus` delivers the event to `ReceiptEmailHandler` (and
   potentially other subscribers in different contexts).
4. **Ledger never knows about email sending** – only the event is published.

---

## Known Architectural Debts (Permanent Warnings)

These are fundamental design issues that must be addressed for production
readiness. They are tracked in the detailed module docs.

- **TD‑1** – Transaction status is a primitive string (should be enum).
- **TD‑7** – No escrow account during pending state; double‑entry is temporarily violated.
- **TD‑4** – Missing optimistic locking → concurrent balance updates can be lost.
- **TD‑3** – Transaction ID not assigned back to aggregate after insert → events carry `id=0`.
- **TD‑5** – Currency update bypasses the aggregate.
- **TD‑8** – Refund when destination is insolvent is unhandled.

All developers **must** consult the relevant module document for current status
and planned fixes. This README exists to ensure no one loses sight of the big
picture.

---

## How to Use This Documentation

- For **architecture onboarding**, read this README.
- For **implementation details**, navigate to the appropriate module document
  (e.g., `account_domain.md`, `transaction_application_commands.md`).
- For **API integration**, see the `ledger_http_api.md` module.
- For **database schema**, see the `ledger_infrastructure_persistence.md` module.

---