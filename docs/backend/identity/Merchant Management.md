# Module 2: Merchant Management
## Paymenter Project | Version 1.0.1 (SSOT Revised)

---

## 1. Overview
This module governs **Merchants** – business entities that process payments through the platform. Each merchant receives a unique API key for authentication and possesses a settlement account for fund collection.

**Current status:** Functional but with several architectural gaps and anti‑patterns that are documented below for future refactoring.

---

## 2. Business Rules & Domain Invariants

### 2.1 Merchant Aggregate
- A `Merchant` must have a unique `api_key` (generated cryptographically, not set by clients).
- A `Merchant` must have a `settlement_account_id` referencing a Ledger account at the time of onboarding.
- A `Merchant` can be toggled between `active` and `inactive` states. This is a soft-toggle; no data is deleted.
- **The aggregate's `toggle()` method exists in the domain entity but is currently unused in the application flow.** The `ToggleMerchantHandler` bypasses the domain logic and directly executes SQL via `toggle_status()` on the concrete repository.

### 2.2 API Key Value Object
- Immutable (`frozen=True` dataclass).
- Value generated using `generate_api_key()`: format `pay_{secrets.token_urlsafe(32)}`.
- **No runtime validation** (length, prefix, entropy) inside `ApiKey.__post_init__`.

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
- **Note:** The `toggle()` method is defined but never called by the handler.

**Value Object: `ApiKey`** (`src/identity/domain/value_objects/api_key.py`)
```python
@dataclass(frozen=True)
class ApiKey:
    value: str
```
- **Gap:** No `__post_init__` validation of the key’s format.

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
- **Missing method:** `toggle_status(merchant_id: int)` is **not** in the abstract interface but is called by `ToggleMerchantHandler`, forcing a dependency on the concrete `SqliteMerchantRepository`.

### 3.2 Application Layer

**Commands:**
| Command | Payload | Purpose |
|---------|---------|---------|
| `OnboardMerchantCommand` | `name: str` | Create a merchant, synthetic user, and settlement account. |
| `ToggleMerchantCommand` | `merchant_id: int` | Toggle merchant active status. |

**Handler: `OnboardMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `UserRepository`, `MerchantRepository`, `AccountProvisioningPort`, `CurrencyRepository`
- **Actual flow:**
  1. Create a synthetic `User` object with `id=0`, `name="Merchant: {name}"`, and `phone_email` set to a **plain string** `f"system_merchant_{cmd.name}@paymenter.com"`. This string is **not** a `PhoneEmail` Value Object, causing a type mismatch with the `User` entity’s field.
  2. Persist the synthetic user via `user_repo.add(user)` → `user_id`.
  3. Retrieve active currencies; if none, raise `ValueError`.
  4. Provision a settlement account via `account_port.create_default_account(user_id, active_currencies[0].id)` – the first active currency is used blindly.
  5. Create a `Merchant` with `id=0`, generated `ApiKey`, `is_active=True`, and the settlement account ID.
  6. Persist merchant via `merchant_repo.add(merchant)`.
  7. Commit UOW.
- **No domain events are published.**

**Handler: `ToggleMerchantHandler`** (`src/identity/application/handlers/identity_handlers.py`)
- **Dependencies:** `UnitOfWork`, `MerchantRepository`
- **Actual flow:**
  1. Call `self._merchant_repo.toggle_status(cmd.merchant_id)` – a method **not** on the abstract port.
  2. Commit UOW.
- **No domain event is emitted.**

**Query Handler: `GetAllMerchantsHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[Any]` – raw `dict` objects from the repository.
- The repository’s `get_all_summaries()` performs a **cross‑context LEFT JOIN** with `accounts` to fetch `settlement_balance`. No local read model is used.

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteMerchantRepository`** (`src/identity/infrastructure/persistence/sqlite_merchant_repository.py`)
- **Implements:** `MerchantRepository`
- **`add(merchant)`:** Inserts into `merchants` table.
- **`update(merchant)`:** Updates `is_active` directly.
- **`toggle_status(merchant_id)`:** Raw SQL `UPDATE merchants SET is_active = NOT is_active WHERE id = ?`. **No row‑count check** – silently succeeds for non‑existent IDs.
- **`get_all_summaries()`:** Executes:
  ```sql
  SELECT m.*, a.balance as settlement_balance 
  FROM merchants m LEFT JOIN accounts a ON m.settlement_account_id = a.id
  ```
  Returns list of `dict` – no DTO.
- **`get_by_api_key(api_key)`:** SELECT by `api_key` value, reconstructs `Merchant` entity.

**Database Schema** – table `merchants` defined in `identity.py` schema:
- Columns: `id`, `name`, `api_key` (TEXT UNIQUE), `is_active` (BOOLEAN DEFAULT 1), `settlement_account_id` (INTEGER REFERENCES accounts(id)).

**Web Template** (`templates/merchants.html`)
- Displays columns: ID, Name, API Key (with copy button), Settlement Bal, Active, Action (toggle button).
- Uses `{{ m.settlement_balance }}` from the raw dict.

---

## 4. API Contract

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML render (`merchants.html`) with `merchants` (list of dicts with keys: `id`, `name`, `api_key`, `settlement_balance`, `is_active`).
- **Query Handler:** `GetAllMerchantsHandler`

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant (creates synthetic user + settlement account).
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.
- **Error:** Flash message.

**POST /dashboard/merchants/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle merchant active status. The `is_active` path parameter is ignored; the toggle always flips the current state.
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
    |-- 1. Create synthetic User(id=0, name, phone_email=plain string)  ⚠️ Type violation
    |-- 2. UserRepository.add(user) -> user_id
    |-- 3. CurrencyRepository.get_active() -> first active currency
    |-- 4. AccountProvisioningPort.create_default_account(user_id, first_currency.id) -> settlement_acc_id
    |-- 5. Create Merchant(id=0, name, api_key, is_active=True, settlement_account_id)
    |-- 6. MerchantRepository.add(merchant)
    |-- 7. UnitOfWork.commit()
```
**No domain events, no read model update.**

### 5.2 Toggle Merchant Status
```
[Dashboard Controller] -- POST /dashboard/merchants/toggle/<id>/<is_active>
    |
    v
[ToggleMerchantHandler]
    |-- 1. MerchantRepository.toggle_status(merchant_id)  ⚠️ Not on port
    |-- 2. UnitOfWork.commit()
```
**No domain event, no check if merchant exists.**

### 5.3 Query Merchants
```
[Dashboard Controller] -- GET /dashboard/merchants
    |
    v
[GetAllMerchantsHandler]
    |-- merchant_repo.get_all_summaries()
    |-- SQL: merchants LEFT JOIN accounts
    |-- Returns: List[dict]
```

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Missing abstract `toggle_status`** | High | `ToggleMerchantHandler` calls `toggle_status` which is not on `MerchantRepository` interface. Violates DIP. |
| **Domain `toggle()` bypassed** | High | The aggregate’s `toggle()` method is never used; business logic is in SQL. |
| **Synthetic user creation** | Medium | Unnecessary fake user created; `accounts.user_id` is nullable. Also passes plain string for `phone_email` instead of `PhoneEmail` VO – potential runtime error. |
| **No domain events** | Medium | State changes (onboard, toggle) do not emit events, breaking audit trail and cross‑context communication. |
| **Toggle on non‑existent merchant** | Low | UPDATE runs regardless of whether the merchant exists; no error thrown. |
| **ApiKey validation missing** | Low | No format checks in `ApiKey` VO. |
| **Cross‑context JOIN** | Medium | `get_all_summaries` joins directly with `accounts` table from Ledger context, violating bounded context boundaries. |
| **Return type `Any`** | Medium | Repository and handlers return untyped `dict` instead of a DTO. |

---

## 7. Notes & Refactoring Roadmap

### Immediate (High Priority)
- Add `toggle_status(merchant_id: int)` to the `MerchantRepository` abstract interface.
- Use the domain `toggle()` method: fetch the entity, call `toggle()`, then `update()`.

### Medium Term
- Remove synthetic user creation; `accounts.user_id` is nullable. Associate settlement account directly with merchant.
- Introduce a local `merchant_summaries` read model populated via domain events.
- Emit `MerchantActivatedEvent` / `MerchantDeactivatedEvent` on toggle.

### Long Term
- Add `ApiKey` validation in `__post_init__`.
- Replace raw dicts with proper `MerchantSummaryDTO`.
- Decouple the read model from Ledger tables.

---