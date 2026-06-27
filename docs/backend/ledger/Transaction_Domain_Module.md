# Transaction Domain Module — Single Source of Truth Documentation
## Paymenter Project | Version 1.0.0

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

The **Transaction Domain** module is the financial core of the Ledger bounded context. It defines the `Transaction` aggregate with its strict state machine, the `DoubleEntryLedger` domain service that orchestrates fund movements, and the domain events emitted for cross-context communication. This module is pure domain logic with zero external dependencies.

### Core Responsibilities
- **Transaction Lifecycle**: Enforcing the immutable state machine: `Pending` → `Success` / `Failed` / `Refunded`.
- **Double-Entry Enforcement**: Ensuring every fund movement has a corresponding debit and credit (currently partially flawed — see TD-7).
- **Currency Validation**: All fund movements between two accounts require identical currencies.
- **Audit & Events**: Defining `TransactionCompletedEvent`, `TransactionFailedEvent`, `TransactionRefundedEvent` for downstream contexts.

### Architectural Alignment
| Constitution Rule | Implementation Status |
|---|---|
| Rule 1: Dependency Inward | ✅ Enforced. Domain has zero external imports. |
| Rule 2: New Feature = New File | ✅ Enforced. Every entity/service/event is isolated. |
| Rule 3: No Primitive Obsession | ⚠️ Violated — `status: str` with magic strings (see TD-1). |
| Rule 4: Aggregates Protect Invariants | ✅ Transaction enforces its own state transitions. |
| Rule 5: Cross-Context via Events | ✅ Events defined here; publishing orchestrated in Application layer. |

---

## Business Rules

### BR-2: Currency Homogeneity
All operations involving two accounts (hold, complete, refund) require identical currencies. `CurrencyMismatchError` is raised if `from_acc.balance.currency != to_acc.balance.currency`.

### BR-3: Transaction State Machine
A `Transaction` has a strict, immutable state machine:
- `Pending` → `Success` (via `mark_as_success()`)
- `Pending` → `Failed` (via `mark_as_failed()`)
- `Success` → `Refunded` (via `mark_as_refunded()`)
Any other transition raises `InvalidTransactionStateError`.

### BR-4: Double-Entry Accounting
Every fund movement must balance. The `DoubleEntryLedger` domain service ensures:
- **Hold**: Debit `from_acc`, Credit `to_acc` (currently **flawed** — see TD-7). Funds enter a "limbo" state.
- **Complete**: Debit `Pending` liability, Credit `to_acc`.
- **Refund (Pending)**: Credit `from_acc` (reverse the hold).
- **Refund (Success)**: Credit `from_acc`, Debit `to_acc` (reverse the completion).

### BR-7: Audit Trail
All state changes (Transaction status changes, Account balance changes) must emit a `DomainEvent` for downstream audit and notification.

---

## Backend Architecture — Domain Layer

### Directory
```
src/ledger/domain/
├── entities/
│   └── transaction.py      # Transaction aggregate
├── services/
│   └── double_entry_ledger.py  # Domain service
├── events/
│   ├── transaction_completed_event.py
│   ├── transaction_failed_event.py
│   └── transaction_refunded_event.py
└── repositories.py         # TransactionRepository abstract port
```

### Transaction Entity
```python
@dataclass
class Transaction:
    id: int
    from_account_id: int
    to_account_id: int
    amount: Money
    status: str                        # ⚠️ PRIMITIVE OBSESSION (see TD-1)
    merchant_id: Optional[int]
    user_email: Optional[str]
```
**Methods:**
- `create_pending(...) -> Transaction`: Factory method. Initializes with `id=0` and `status='Pending'`.
- `mark_as_success()`: Validates `status == 'Pending'`, then sets `'Success'`.
- `mark_as_failed()`: Validates `status == 'Pending'`, then sets `'Failed'`.
- `mark_as_refunded()`: Validates `status == 'Success'`, then sets `'Refunded'`.

### DoubleEntryLedger (Domain Service)
Pure domain service orchestrating fund movements. Contains **NO** infrastructure dependencies.

- `hold_funds(from_acc, to_acc, amount, merchant_id, user_email) -> Transaction`:
  - Calls `from_acc.withdraw(amount)`.
  - Returns a new `Pending` Transaction.
  - ⚠️ **DOES NOT CREDIT `to_acc`** (see TD-7). Funds enter a "limbo" state.

- `complete_funds(txn, to_acc) -> None`:
  - Calls `txn.mark_as_success()`.
  - Calls `to_acc.deposit(txn.amount)`.

- `fail_and_refund(txn, from_acc, to_acc) -> None`:
  - If `Pending`: `mark_as_failed()`, then `from_acc.deposit(amount)` (refund sender).
  - If `Success`: `mark_as_refunded()`, then `from_acc.deposit(amount)` AND `to_acc.withdraw(amount)` (reverse both legs).
  - ⚠️ If `to_acc` is insolvent, `InsufficientFundsError` bubbles up unhandled (see TD-8).

### Domain Events
All frozen dataclasses:
- `TransactionCompletedEvent`: `(transaction_id, user_email, amount: Decimal, currency_code, merchant_id)`
- `TransactionFailedEvent`: Same fields.
- `TransactionRefundedEvent`: Same fields.

**Event Publishing Rule**: Events are prepared **inside** the Unit of Work but published **outside** (after `uow.commit()`). This prevents "phantom events" from rolling back transactions.

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
```
DoubleEntryLedger.hold_funds(from_acc, to_acc, amount, merchant_id, user_email)
  → from_acc.withdraw(amount)              [Debit Sender]
  → Transaction.create_pending(...)        [Create Pending Record]
  → ⚠️ NO CREDIT TO to_acc (LIMBO — see TD-7)
  → Returns Transaction with status='Pending'
```

### 2. Complete Funds (Domain Logic)
```
DoubleEntryLedger.complete_funds(txn, to_acc)
  → txn.mark_as_success()                  [State Machine Check: must be Pending]
  → to_acc.deposit(txn.amount)             [Credit Receiver]
```

### 3. Fail & Refund (Domain Logic)
```
DoubleEntryLedger.fail_and_refund(txn, from_acc, to_acc)
  → IF status == 'Pending':
    → txn.mark_as_failed()
    → from_acc.deposit(amount)             [Refund Sender]
  → ELIF status == 'Success':
    → txn.mark_as_refunded()
    → from_acc.deposit(amount)             [Refund Sender]
    → to_acc.withdraw(amount)              [Debit Receiver]
    → ⚠️ May raise InsufficientFundsError if receiver spent funds (see TD-8)
```

---

## Edge Cases & Known Issues

### EC-2: Refund of Spent Funds (To Account Insolvency)
**Scenario**: A transaction is `Success`. The receiver (`to_acc`) spends the funds. Later, the merchant/system requests a refund.
**Current Behavior**: `DoubleEntryLedger.fail_and_refund()` calls `to_acc.withdraw(amount)`, which raises `InsufficientFundsError`. This bubbles up to the caller unhandled.
**Impact**: **CRITICAL**. Refund operations can fail unpredictably. No domain policy exists for overdrafts or refund rejection workflows.
**Status**: Unhandled. See TD-8.

### EC-7: Ghost Funds on Crash During Hold
**Scenario**: System crashes after `from_acc.withdraw()` but before `TransactionRepository.add()` (in Application layer).
**Current Behavior**: The sender's balance is decremented, but no transaction record exists. The money is unaccounted for.
**Impact**: **CRITICAL**. Money disappears from the system.
**Mitigation**: The entire operation is wrapped in `UnitOfWork` (at Application layer), so a crash before `commit()` results in a database rollback. However, the lack of an escrow account means the accounting equation is violated during the `Pending` state (see TD-7).

---

## Notes & Technical Debt

### TD-1: TransactionStatus as Primitive String
**Violation**: Constitution Rule 3 (Primitive Obsession)
**Location**: `src/ledger/domain/entities/transaction.py`
**Current**: `status: str` with magic strings `'Pending'`, `'Success'`, `'Failed'`, `'Refunded'`.
**Required Fix**: Introduce `TransactionStatus` as an Enum or sealed Value Object:
```python
class TransactionStatus(Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"
    REFUNDED = "Refunded"
```
The `Transaction` entity should expose `transition_to(new_status: TransactionStatus)` which validates allowed transitions internally.

### TD-7: Missing Escrow Account in Double-Entry
**Violation**: Double-Entry Accounting Integrity
**Location**: `src/ledger/domain/services/double_entry_ledger.py` → `hold_funds()`
**Current**: `hold_funds` debits `from_acc` but never credits `to_acc`. Funds are in "limbo." The global accounting equation is violated during the `Pending` state.
**Required Fix**:
1. Introduce a system-level `EscrowAccount` (or `PendingTransactions` liability account).
2. `hold_funds` should:
   - `from_acc.withdraw(amount)`
   - `escrow_acc.deposit(amount)`
3. `complete_funds` should:
   - `escrow_acc.withdraw(amount)`
   - `to_acc.deposit(amount)`
4. `fail_and_refund` (Pending) should:
   - `escrow_acc.withdraw(amount)`
   - `from_acc.deposit(amount)`
5. `fail_and_refund` (Success) should:
   - `to_acc.withdraw(amount)`
   - `from_acc.deposit(amount)`
   (No escrow involved because funds already settled).

### TD-8: Unhandled Refund Insolvency
**Violation**: Business Rule Gap
**Location**: `src/ledger/domain/services/double_entry_ledger.py` → `fail_and_refund()`
**Current**: If `to_acc` lacks funds during a `Success` → `Refunded` transition, `InsufficientFundsError` propagates uncaught.
**Required Fix**:
**Option A (Overdraft Policy)**: Allow `to_acc` balance to go negative during refund reversals. Introduce `Account.withdraw(amount, allow_overdraft: bool = False)`.
**Option B (Policy Rejection)**: Before calling `fail_and_refund`, check `to_acc.balance >= txn.amount`. If insufficient, emit `RefundRejectedEvent` and return a graceful failure to the caller instead of raising an exception.