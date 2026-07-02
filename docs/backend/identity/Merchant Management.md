# Module 2: Merchant Management
## Paymenter Project | Version 1.0.0

---

## 1. Overview
This module governs **Merchants** – business entities that process payments through the platform. Each merchant receives a unique API key for authentication and possesses a settlement account for fund collection.

---

## 2. Business Rules & Domain Invariants

### 2.1 Merchant Aggregate
- A `Merchant` must have a unique `api_key` (generated cryptographically, not set by clients).
- A `Merchant` must have a `settlement_account_id` referencing a Ledger account at the time of onboarding.
- A `Merchant` can be toggled between `active` and `inactive` states. This is a soft-toggle; no data is deleted.
- The `Merchant` aggregate protects its own invariants via the `toggle()` domain method.

### 2.2 API Key Value Object
- Immutable (`frozen=True` dataclass).
- Format: `pay_{secrets.token_urlsafe(32)}`.
- Currently lacks runtime validation (length, prefix, entropy). This is a known gap.

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
    settlement_account_id: int

    def toggle(self) -> None:
        self.is_active = not self.is_active
```
- **Responsibility:** Represents a business entity authorized to process payments.
- **Invariant:** State toggle is protected by the aggregate method `toggle()`.

**Value Object: `ApiKey`** (`src/identity/domain/value_objects/api_key.py`)
```python
@dataclass(frozen=True)
class ApiKey:
    value: str
```
- **Responsibility:** Immutable wrapper for merchant API keys.
- **Gap:** No `__post_init__` validation (length, prefix, format).

**Port: `MerchantRepository`** (`src/identity/domain/repositories.py`)
```python
class MerchantRepository(ABC):
    @abstractmethod
    def add(self, merchant: Merchant) -> int: ...
    @abstractmethod
    def update(self, merchant: Merchant) -> None: ...
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: ...
    @abstractmethod
    def get_by_api_key(self, api_key: ApiKey) -> Optional[Merchant]: ...
```
- **⚠️ Gap:** `toggle_status(self, merchant_id: int)` is missing from the abstract interface but is called by `ToggleMerchantHandler`. This is a DIP violation; the handler implicitly depends on the concrete `SqliteMerchantRepository`.

### 3.2 Application Layer

**Commands:**
| Command | Payload | Purpose |
|---------|---------|---------|
| `OnboardMerchantCommand` | `name: str` | Create a merchant, system user, and settlement account. |
| `ToggleMerchantCommand` | `merchant_id: int` | Toggle merchant active status. |

**Handler: `OnboardMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `UserRepository`, `MerchantRepository`, `AccountProvisioningPort`, `CurrencyRepository`
- **Flow:**
  1. Create a synthetic `User` with email `system_merchant_{name}@paymenter.com`.
  2. Persist synthetic user → `user_id`.
  3. Query `currency_repo.get_active()`; fail if empty.
  4. Provision settlement account via `account_port.create_default_account(user_id, active_currencies[0].id)`.
  5. Create `Merchant` with generated `ApiKey`.
  6. Persist merchant via `merchant_repo.add(merchant)`.
  7. Commit UOW.
- **⚠️ Domain Flaw:** Synthetic user creation is unnecessary (accounts.user_id is nullable). Merchants should not need a fake user.

**Handler: `ToggleMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `MerchantRepository`
- **Flow:**
  1. Call `merchant_repo.toggle_status(cmd.merchant_id)`.
  2. Commit UOW.
- **⚠️ DIP Violation:** `toggle_status` is not declared on `MerchantRepository` interface.

**Query: `GetAllMerchantsQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** *(empty)*
- **Purpose:** Retrieve all merchant summaries.

**Query Handler: `GetAllMerchantsHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[Any]` merchant summaries.
- **⚠️ Coupling:** Repository JOINs with `accounts` for `settlement_balance`.

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteMerchantRepository`** (`src/identity/infrastructure/persistence/sqlite_merchant_repository.py`)
- **Implements:** `MerchantRepository`
- **`add(merchant)`:** Inserts into `merchants` table.
- **`update(merchant)`:** Updates `is_active`.
- **`toggle_status(merchant_id)`:** Raw SQL `UPDATE merchants SET is_active = NOT is_active WHERE id = ?`.
- **`get_all_summaries()`:** LEFT JOIN with `accounts` for `settlement_balance`.
- **`get_by_api_key(api_key)`:** SELECT by `api_key` value; reconstructs `Merchant` entity.
- **⚠️ Violation:** `toggle_status` is not on the abstract port. `get_all_summaries` JOINs with `accounts`.

---

## 4. API Contract

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML render (`merchants.html`) with `merchants_list`.
- **Query Handler:** `GetAllMerchantsHandler`

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant.
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.
- **Error:** Flash message (e.g., "No active currencies found").

**POST /dashboard/merchants/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle merchant active status.
- **Path Params:** `id` (merchant ID), `is_active` (unused path param).
- **Command:** `ToggleMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.

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
    |-- 1. Create synthetic User(name="Merchant: X", phone_email="system_merchant_X@paymenter.com")
    |-- 2. UserRepository.add(synthetic_user) -> user_id
    |-- 3. CurrencyRepository.get_active() -> [Currency, ...]
    |-- 4. AccountProvisioningPort.create_default_account(user_id, active_currencies[0].id)
    |-- 5. Create Merchant(id=0, name, api_key=ApiKey(...), is_active=True, settlement_account_id)
    |-- 6. MerchantRepository.add(merchant)
    |-- 7. UnitOfWork.commit()
```
**⚠️ Issues:** Synthetic user pollution, blind selection of first active currency, direct SQL writes.

### 5.2 Toggle Merchant Status
```
[Dashboard Controller] -- POST /dashboard/merchants/toggle/<id>/<is_active>
    |
    v
[ToggleMerchantHandler]
    |-- 1. MerchantRepository.toggle_status(merchant_id)  (SQL UPDATE)
    |-- 2. UnitOfWork.commit()
```
**⚠️ Issues:** No abstract method for `toggle_status`; no domain event emitted.

### 5.3 Query Merchants
```
[Dashboard Controller] -- GET /dashboard/merchants
    |
    v
[GetAllMerchantsHandler]
    |-- SQL JOIN: merchants LEFT JOIN accounts
    |-- Returns: List of dicts with merchant + settlement_balance
```
**⚠️ Issues:** Cross‑context JOIN with `accounts`.

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Missing Abstract `toggle_status`** | High | Handler depends on concrete repository method not declared in port. |
| **Synthetic User Creation** | Medium | Merchants create fake user entries; accounts table allows NULL user_id. |
| **No Domain Events** | Medium | No `MerchantActivatedEvent`/`MerchantDeactivatedEvent` emitted. |
| **Toggle non‑existing merchant** | – | UPDATE on missing ID silently succeeds. |
| **ApiKey validation missing** | Low | `ApiKey` VO lacks format checks. |

---

## 7. Notes & Refactoring Roadmap

### Immediate
- Add `toggle_status(merchant_id: int)` to `MerchantRepository` abstract port.

### Medium Term
- Remove synthetic user creation; add `merchant_id` to accounts or use polymorphic owner.
- Emit domain events on merchant state changes.
- Build local `merchant_summaries` read model.

### Long Term
- Add validation to `ApiKey`.
- Move settlement account provisioning to an event‑driven flow.