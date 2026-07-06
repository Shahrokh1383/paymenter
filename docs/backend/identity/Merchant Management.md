# Module 2: Merchant Management  
## Paymenter Project | Version 1.2.0 (SSOT Revised – Decoupled Account Provisioning)

---

## 1. Overview
This module governs **Merchants** – business entities that process payments through the platform. Each merchant receives a unique API key for authentication. 

**Current status:** Fully compliant with Constitution.md. Merchant onboarding is now strictly decoupled from Ledger account creation, mirroring the User management flow. Accounts for merchants are provisioned explicitly via the Accounts dashboard.

---

## 2. Business Rules & Domain Invariants

### 2.1 Merchant Aggregate
- A `Merchant` must have a unique `api_key` (generated cryptographically, never set by clients).
- A `Merchant` can be toggled between `active` and `inactive` states. This is a soft-toggle; no data is deleted.
- **No default settlement account is provisioned automatically.** Account creation for a merchant is a separate, explicit operation performed later from the Accounts dashboard.
- **The aggregate's `toggle()` method is the sole authority for state changes.** 

### 2.2 API Key Value Object
- Immutable (`frozen=True` dataclass).
- Value generated using `generate_api_key()`: format `pay_{secrets.token_urlsafe(32)}`.
- **Strict validation inside `__post_init__`**: must start with `pay_`, followed by exactly 43 URL‑safe characters.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `Merchant`** (`src/identity/domain/entities/merchant.py`)
```python
@dataclass
class Merchant:
    id: int
    name: str
    api_key: ApiKey
    is_active: bool
    
    def toggle(self) -> None:
        self.is_active = not self.is_active
```
- **Responsibility:** Represents a business entity authorized to process payments.
- **Decoupling:** The `settlement_account_id` has been removed to enforce strict Bounded Context boundaries. The Identity context no longer holds references to Ledger aggregates.

**Value Object: `ApiKey`** (`src/identity/domain/value_objects/api_key.py`)
- **Fully validated at creation.**

**Port: `MerchantRepository`** (`src/identity/domain/repositories.py`)
```python
class MerchantRepository(ABC):
    @abstractmethod
    def add(self, merchant: Merchant) -> int: ...
    @abstractmethod
    def update(self, merchant: Merchant) -> None: ...
    @abstractmethod
    def get_by_id(self, merchant_id: int) -> Optional[Merchant]: ...
    @abstractmethod
    def get_all_summaries(self) -> List[MerchantSummaryDTO]: ...
    @abstractmethod
    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]: ...
```

### 3.2 Application Layer

**Commands:**
| Command | Payload | Purpose |
|---------|---------|---------|
| `OnboardMerchantCommand` | `name: str` | Create a merchant entity (No account provisioning). |
| `ToggleMerchantCommand` | `merchant_id: int` | Toggle merchant active status. |

**Handler: `OnboardMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `MerchantRepository`, `EventBus`
- **Actual flow:**
  1. Generate cryptographic `ApiKey`.
  2. Create transient `Merchant(id=0, name, api_key, is_active=True)`.
  3. Persist merchant via `merchant_repo.add(merchant)`.
  4. Commit UOW.
  5. **Publish `MerchantOnboardedEvent`**.
- **No direct call to any Ledger adapter.** Cross-context coupling has been completely eliminated.

**Handler: `ToggleMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Actual flow:** Fetch entity -> `merchant.toggle()` -> Persist -> Publish `MerchantActivated/DeactivatedEvent`.

**Query Handler: `GetAllMerchantsHandler`** 
- **Returns:** `List[MerchantSummaryDTO]` from the local `merchant_summaries` read model.

### 3.3 Infrastructure Layer

**Database Schema** – table `merchants` defined in `identity.py`:
- Columns: `id`, `name`, `api_key` (TEXT UNIQUE), `is_active` (BOOLEAN DEFAULT 1).
- **Removed:** `settlement_account_id` and its Foreign Key to the Ledger context.

**Read Model Table `merchant_summaries`** (schema in `merchant_summaries_schema.py`):
  ```sql
  CREATE TABLE IF NOT EXISTS merchant_summaries (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      api_key TEXT NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT 1
  );
  ```
  - **Removed:** `settlement_balance` column. Balance is now exclusively viewed on the `/dashboard/accounts` page.

**Web Template** (`templates/merchants.html`)
- Displays columns: ID, Name, API Key (with copy button), Active, Action (toggle button).
- **Removed:** Settlement Balance column to maintain SRP and match the User list UI pattern.

---

## 4. API Contract

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML render with `merchants` (list of `MerchantSummaryDTO` objects).

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant. **Does NOT create an account.**
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.
- **Side Effects:** Publishes `MerchantOnboardedEvent`.

---

## 5. Flows

### 5.1 Onboard Merchant
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- POST /dashboard/merchants/add
    |
    v
[OnboardMerchantHandler]
    |-- 1. Generate ApiKey
    |-- 2. Create Merchant(id=0, name, api_key, is_active=True)
    |-- 3. MerchantRepository.add(merchant)
    |-- 4. UnitOfWork.commit()
    |-- 5. EventBus.publish(MerchantOnboardedEvent)
```
**Domain event triggers read model update:**
`MerchantOnboardedEvent` → `MerchantOnboardedReadModelHandler` inserts row into `merchant_summaries`.
*(Note: The admin must subsequently visit `/dashboard/accounts` to explicitly create a settlement account for this merchant).*

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **None** | — | The system is fully compliant with DDD, Constitution, and SRP. |

---

## 7. Notes & Refactoring Roadmap

### Completed (v1.1.0 - Decoupling & SRP Enforcement)
- ✅ **Cross-Context DIP Violation Fixed:** Removed `AccountProvisioningPort` and `LedgerAccountProvisioningAdapter`. Identity no longer synchronously calls Ledger.
- ✅ **Aggregate Decoupled:** Removed `settlement_account_id` from the `Merchant` entity.
- ✅ **Read Model Simplified:** Removed `settlement_balance` from `MerchantSummaryDTO` and `merchant_summaries` table. Balance is now strictly managed in the Ledger context's Account read models.
- ✅ **UI Alignment:** Removed Settlement Bal column from `merchants.html` to perfectly mirror the `users.html` pattern.
```