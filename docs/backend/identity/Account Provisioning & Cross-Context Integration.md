# Module 4: Account Provisioning & Cross-Context Integration
## Paymenter Project | Version 1.1.0 (SSOT Revised)

---

## 1. Overview
This module defines the **current (temporary) implementation** for creating Ledger accounts from the Identity context, used **only during merchant onboarding**. User registration no longer triggers automatic account creation. The document also describes the architectural violations and the planned event‑driven target state.

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
  1. Generates `account_number` and `card_number`.
  2. Inserts directly into `accounts` (Ledger table) with zero balance.
  3. Inserts into `user_cards` (Identity table) to map card to account.
  4. Returns `account_id`.
- **⚠️ Violation:** Direct SQL INSERT into `accounts` (Ledger table). The adapter acts as a transaction script across two contexts, bypassing the Ledger’s domain logic and event emission.

---

## 4. Usage in Current Codebase

The adapter is **only** called by `OnboardMerchantHandler`:
```
OnboardMerchantHandler → account_port.create_default_account(user_id, active_currencies[0].id)
```
- It uses the first active currency.
- **`RegisterUserHandler` does NOT use this port.** User registration no longer provisions an account.

---

## 5. Flows

**Merchant Onboarding (current, temporary):**
```
OnboardMerchantHandler
  ├── Creates synthetic user
  ├── account_port.create_default_account(user_id, first_active_currency.id)
  │     ├── INSERT INTO accounts (Ledger table) – direct SQL
  │     └── INSERT INTO user_cards (Identity table)
  └── Creates Merchant with settlement_account_id = account_id
```
No domain events are emitted from this process.

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Constitution Rule | Description |
|-------|----------|-------------------|-------------|
| **Cross‑Context SQL Writes** | Critical | Rule 5 | Adapter INSERTs directly into `accounts`. Identity must emit events, Ledger must consume them. |
| **Blind Currency Selection** | Medium | – | First active currency is used; no user choice. |
| **No Domain Events** | Medium | Rule 5 | No event (e.g., `MerchantAccountCreated`) is published; Ledger is unaware of the account creation through this path. |
| **Single UOW for Two Contexts** | Medium | – | The write to both contexts happens inside the same `SqliteUnitOfWork`; a failure in Ledger may leave Identity in an inconsistent state. |
| **Synthetic User Pollution** | Medium | – | The adapter still receives a `user_id` from a synthetic user created solely for the merchant. |

---

## 7. Notes & Refactoring Roadmap

### Medium‑Term: Event‑Driven Account Provisioning
1. Identity emits `MerchantOnboarded` event (or similar) after merchant is persisted.
2. Ledger subscribes and creates the settlement account internally, emitting `AccountCreatedEvent`.
3. Identity listens to `AccountCreatedEvent` and updates `merchants.settlement_account_id`.
4. **Delete** `LedgerAccountProvisioningAdapter` and `AccountProvisioningPort`.

### Long‑Term
- Remove synthetic user creation; associate settlement accounts directly with merchants.
- Consider eventual consistency; the settlement account may not be immediately available after merchant onboarding.