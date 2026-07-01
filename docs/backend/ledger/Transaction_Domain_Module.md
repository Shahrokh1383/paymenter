# Transaction Domain Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Business Rules](#business-rules)
3. [Backend Architecture — Domain Layer](#backend-architecture--domain-layer)
   - [Transaction Entity](#transaction-entity)
   - [DoubleEntryLedger (Domain Service)](#doubleentryledger-domain-service)
   - [Domain Events](#domain-events)
   - [Repository Port](#repository-port)
4. [Flows](#flows)
   - [Hold Funds](#1-hold-funds)
   - [Complete Funds](#2-complete-funds)
   - [Fail & Refund](#3-fail--refund)
5. [Edge Cases & Known Issues](#edge-cases--known-issues)
6. [Notes & Technical Debt](#notes--technical-debt)

---

## Overview

The **Transaction Domain** module is the financial core of the Ledger bounded context. It defines the `Transaction` aggregate with its strict state machine, the `DoubleEntryLedger` domain service that orchestrates mathematically balanced fund movements via a System Escrow account, and the domain events emitted for cross-context communication. This module is pure domain logic with zero external dependencies.

### Core Responsibilities
- **Transaction Lifecycle**: Enforcing the immutable state machine: `Pending` → `Success` / `Failed` / `Refunded`.
- **Double-Entry Enforcement**: Guaranteeing that every debit has an immediate, corresponding credit. The `Pending` state is balanced by routing funds through a dynamically resolved System Escrow account.
- **State Transition Protection**: The aggregate exclusively controls its own status mutations, raising `InvalidTransactionStateError` on illegal transitions.
- **Audit & Events**: Defining strictly isolated Domain Events (free of Identity leakage) for downstream contexts.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Enforced. Domain has zero external/framework imports. |
| Rule 2: New Feature = New File | ✅ Enforced. Entity, service, events, and ports are strictly isolated. |
| Rule 3: No Primitive Obsession | ⚠️ Partially Accepted — `status: str` uses controlled magic strings (see TD-1). Currency/Amount strictly use `Money` & `CurrencyCode` VOs. |
| Rule 4: Aggregates Protect Invariants | ✅ Transaction enforces its own state transitions. Account protects balance invariants. |
| Rule 5: Cross-Context via Events | ✅ Events defined here; publishing orchestrated in Application layer via Outbox. |

---

## Business Rules

### BR-2: Currency Homogeneity
All operations involving two accounts require identical currencies. Enforced at the Application layer before invoking the Domain service, and re-validated inside `Account` methods during `withdraw()`/`deposit()`.

### BR-3: Transaction State Machine
A `Transaction` has a strict, immutable state machine:
- `Pending` → `Success` (via `mark_as_success()`)
- `Pending` → `Failed` (via `mark_as_failed()`)
- `Success` → `Refunded` (via `mark_as_refunded()`)
Any illegal transition raises `InvalidTransactionStateError`.

### BR-4: Double-Entry Accounting
Every fund movement must balance. The `DoubleEntryLedger` domain service guarantees mathematical equilibrium at every micro-step:
- **Hold**: Debit `from_acc`, Credit `escrow_acc`. (Funds are safely held, never in "limbo").
- **Complete**: Debit `escrow_acc`, Credit `to_acc`.
- **Fail (Pending)**: Debit `escrow_acc`, Credit `from_acc`.
- **Refund (Success)**: Credit `from_acc`, Force Debit `to_acc` (via system reversal).

### BR-7: Audit Trail
All terminal state changes must emit a `DomainEvent` for downstream audit and notification. Events are constructed inside the Unit of Work but published strictly after `uow.commit()`.

---

## Backend Architecture — Domain Layer

### Directory
```text
src/ledger/domain/
├── entities/
│   └── transaction.py          # Transaction aggregate
├── services/
│   └── double_entry_ledger.py  # Pure domain service
├── events/
│   └── transaction_events.py   # Frozen dataclass events
└── repositories.py             # TransactionRepository abstract port
```

### Transaction Entity
```python
@dataclass
class Transaction:
    id: int
    from_account_id: int
    to_account_id: int
    amount: Money                 # Strict Value Object (Decimal + CurrencyCode)
    status: str                   # ⚠️ Controlled primitive (see TD-1)
    merchant_id: Optional[int]
    user_email: Optional[str]     # Retained strictly for legacy audit/display
    version: int = 0
```
**Domain Methods:**
- `create_pending(...) -> Transaction`: Factory method. Initializes with `id=0` and `status='Pending'`.
- `mark_as_success()`: Validates `status == 'Pending'`, transitions to `'Success'`.
- `mark_as_failed()`: Validates `status == 'Pending'`, transitions to `'Failed'`.
- `mark_as_refunded()`: Validates `status == 'Success'`, transitions to `'Refunded'`.

### DoubleEntryLedger (Domain Service)
Pure domain service orchestrating fund movements. Contains **zero** infrastructure dependencies. Relies on `Account` aggregates to enforce balance invariants.

- `hold_funds(from_acc, to_acc, amount, escrow_acc, merchant_id, user_email) -> Transaction`:
  - Calls `from_acc.withdraw(amount)`.
  - Calls `escrow_acc.deposit(amount)`.
  - Returns a new `Pending` Transaction.
  - **Guarantees**: Global ledger remains balanced during the pending phase.

- `complete_funds(txn, to_acc, escrow_acc) -> None`:
  - Calls `txn.mark_as_success()`.
  - Calls `escrow_acc.withdraw(txn.amount)`.
  - Calls `to_acc.deposit(txn.amount)`.

- `fail_and_refund(txn, from_acc, to_acc, escrow_acc) -> None`:
  - If `Pending`: `txn.mark_as_failed()`, `escrow_acc.withdraw(amount)`, `from_acc.deposit(amount)`.
  - If `Success`: `txn.mark_as_refunded()`, `from_acc.deposit(amount)`, `to_acc.apply_system_reversal(amount)`.
  - **Guarantees**: Refunds never crash due to receiver insolvency (uses `apply_system_reversal` to bypass standard overdraft checks).

### Domain Events
All frozen dataclasses defined in `transaction_events.py`. **Identity concepts (`user_email`) are strictly excluded** to prevent bounded context leakage (TD-11 Resolved).

- `TransactionCompletedEvent`: `(transaction_id: int, payer_account_id: int, amount: Money, merchant_id: Optional[int])`
- `TransactionFailedEvent`: Same fields.
- `TransactionRefundedEvent`: Same fields.

**Event Publishing Rule**: Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). The `OutboxEventBusDecorator` intercepts publication, persists the event atomically, and delegates I/O to a background worker.

### Repository Port (Abstract)
```python
class TransactionRepository(ABC):
    def get_by_id(self, transaction_id: int) -> Transaction
    def add(self, transaction: Transaction) -> int
    def update(self, transaction: Transaction) -> None
```

---

## Flows

### 1. Hold Funds (Domain Logic)
```text
DoubleEntryLedger.hold_funds(from_acc, to_acc, amount, escrow_acc, ...)
  → from_acc.withdraw(amount)              [Debit Sender]
  → escrow_acc.deposit(amount)             [Credit Escrow - Balances Ledger]
  → Transaction.create_pending(...)        [Create Pending Record]
  → Returns Transaction (status='Pending')
```

### 2. Complete Funds (Domain Logic)
```text
DoubleEntryLedger.complete_funds(txn, to_acc, escrow_acc)
  → txn.mark_as_success()                  [State Machine: Pending → Success]
  → escrow_acc.withdraw(txn.amount)        [Debit Escrow]
  → to_acc.deposit(txn.amount)             [Credit Receiver]
```

### 3. Fail & Refund (Domain Logic)
```text
DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc, escrow_acc)
  → IF status == 'Pending':
    → txn.mark_as_failed()                 [State Machine: Pending → Failed]
    → escrow_acc.withdraw(amount)          [Debit Escrow]
    → from_acc.deposit(amount)             [Credit Sender]
  → ELIF status == 'Success':
    → txn.mark_as_refunded()               [State Machine: Success → Refunded]
    → from_acc.deposit(amount)             [Credit Sender]
    → to_acc.apply_system_reversal(amount) [Force Debit Receiver - Bypasses Overdraft]
```

---

## Edge Cases & Known Issues

### EC-2: Refund of Spent Funds (Receiver Insolvency) — ✅ RESOLVED
**Previous Scenario**: Refunding a `Success` transaction called `to_acc.withdraw()`. If the receiver spent the funds, `InsufficientFundsError` crashed the flow.
**Resolution**: Introduced `Account.apply_system_reversal(amount)`. This dedicated domain method forces a debit, explicitly allowing negative balances for system-initiated chargebacks. The refund flow now completes deterministically regardless of the receiver's balance.

### EC-7: Ghost Funds on Crash During Hold — ✅ RESOLVED
**Previous Scenario**: Crash after `from_acc.withdraw()` but before persisting the transaction left funds in an unaccounted state.
**Resolution**: 
1. The entire operation is wrapped in `SqliteUnitOfWork`. Any crash before `commit()` triggers an automatic database rollback.
2. The introduction of the Escrow account ensures that even in-memory, the accounting equation (`Assets = Liabilities + Equity`) is never violated. Funds are explicitly credited to Escrow before the transaction record is created.

---

## Notes & Technical Debt

*(Resolved) TD-7: Missing Escrow Account in Double-Entry*
**Previous Violation**: `hold_funds` debited the sender but never credited a destination, violating double-entry accounting and leaving funds in "limbo".
**Resolution**: Refactored `DoubleEntryLedger` to accept an `escrow_acc: Account` parameter. `hold_funds` now explicitly credits the escrow account. `complete_funds` and `fail_and_refund` correctly debit/credit escrow to maintain perfect ledger equilibrium at every state transition.
**Status**: ✅ Resolved

*(Resolved) TD-8: Unhandled Refund Insolvency*
**Previous Violation**: Business Rule Gap. Refunds crashed if the destination account lacked funds.
**Resolution**: Implemented `Account.apply_system_reversal(amount)` in the Domain layer. The `fail_and_refund` service now routes successful refunds through this method, guaranteeing system-level reversals never fail due to user-side balance constraints.
**Status**: ✅ Resolved

*(Resolved) TD-11: Identity Leakage in Ledger Domain Events*
**Previous Violation**: Constitution Rule 1 & 5. Events carried `user_email`, leaking Identity context into Ledger.
**Resolution**: Replaced `user_email` with `payer_account_id: int` in all transaction events. The Notifications context resolves the email dynamically via an Anti-Corruption Layer.
**Status**: ✅ Resolved

### TD-1: TransactionStatus as Primitive String
**Violation**: Constitution Rule 3 (Primitive Obsession)
**Location**: `src/ledger/domain/entities/transaction.py`
**Current**: `status: str` relies on controlled magic strings (`'Pending'`, `'Success'`, `'Failed'`, `'Refunded'`).
**Impact**: Low. The aggregate strictly controls transitions via dedicated methods (`mark_as_success()`, etc.), preventing invalid states. No external code can mutate `status` directly without bypassing the domain API.
**Recommended Future Fix**: Introduce a `TransactionStatus(Enum)` or sealed Value Object and expose a `transition_to(new_status)` method. Deferred to maintain KISS and avoid over-engineering until status-dependent business logic expands.
**Status**: ⚠️ Accepted / Low Priority