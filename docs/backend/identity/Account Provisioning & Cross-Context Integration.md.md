# Module 4: Account Provisioning & Cross-Context Integration
## Paymenter Project | Version 1.0.0

---

## 1. Overview
This module defines the **contract and current (temporary) implementation** for creating Ledger accounts from the Identity context. It also documents the architectural violations and the planned event‑driven target state.

---

## 2. Business Rules & Domain Invariants

### 2.1 Account Provisioning Port (ACL)
- The `AccountProvisioningPort` is the **only** sanctioned boundary between Identity and Ledger for account creation.
- It accepts `user_id` and `currency_id` and returns the newly created `account_id`.
- The current implementation (`LedgerAccountProvisioningAdapter`) writes directly to Ledger tables. This is a temporary adapter that must be replaced by an event‑driven mechanism.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Domain Service Port: `AccountProvisioningPort`** (`src/identity/domain/ports/account_provisioning_port.py`)
```python
class AccountProvisioningPort(ABC):
    @abstractmethod
    def create_default_account(self, user_id: int, currency_id: int) -> int: ...
```
- **Responsibility:** Abstract contract for requesting account creation from the Ledger context.

### 3.2 Infrastructure Layer

**Adapter: `LedgerAccountProvisioningAdapter`** (`src/identity/infrastructure/persistence/ledger_account_provisioning_adapter.py`)
- **Implements:** `AccountProvisioningPort`
- **`create_default_account(user_id, currency_id)`:**
  1. Generates `account_number` and `card_number` via `generate_account_number` / `generate_card_number`.
  2. Inserts into `accounts` (Ledger table) with zero balance.
  3. Inserts into `user_cards` (Identity table) to map card to account.
  4. Returns `account_id`.
- **⚠️ Violation:** Direct SQL INSERT into `accounts` (Ledger table). This is a boundary breach, not a true ACL. The adapter acts as a transaction script across two contexts.

---

## 4. API Contract
This module has no HTTP endpoints of its own; it is called internally by `RegisterUserHandler` and `OnboardMerchantHandler`.

---

## 5. Flows

The adapter is used in two flows:

**Register User:**
`RegisterUserHandler` → `AccountProvisioningPort.create_default_account(user_id, currency_id=1)`

**Onboard Merchant:**
`OnboardMerchantHandler` → `AccountProvisioningPort.create_default_account(user_id, active_currencies[0].id)`

In both cases the adapter:
- Generates account/card numbers
- Inserts into `accounts` (Ledger)
- Inserts into `user_cards` (Identity)
- Returns `account_id`

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Constitution Rule | Description |
|-------|----------|-------------------|-------------|
| **Cross-Context SQL Writes** | Critical | Rule 5 | Adapter INSERTs directly into `accounts`. Identity must emit events, Ledger must consume them. |
| **Hardcoded Currency ID** | High | – | `RegisterUserHandler` sends `currency_id=1`; fragile. |
| **No Domain Events** | Medium | Rule 5 | No `UserRegisteredEvent` or `MerchantOnboardedEvent` emitted; Ledger is not notified through the event bus. |
| **Account provisioning in same transaction** | Medium | – | The write to both contexts happens in one UOW; a failure in Ledger may leave Identity in an inconsistent state. |

---

## 7. Notes & Refactoring Roadmap

### Medium-Term: Event-Driven Account Provisioning
1. Identity emits `UserRegisteredEvent` / `MerchantOnboardedEvent`.
2. Ledger subscribes via event bus and creates accounts internally.
3. Ledger emits `AccountProvisionedEvent` with `account_id`.
4. Identity updates local references (e.g., `settlement_account_id`).
5. **Delete** `LedgerAccountProvisioningAdapter` and `AccountProvisioningPort`.

### Long-Term
- Consider eventual consistency patterns; the account may not be immediately available after user registration.

---