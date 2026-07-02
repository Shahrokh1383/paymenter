# Module 1: User Management
## Paymenter Project | Version 1.0.0

## 1. Overview
This module manages **Users** – natural persons or system actors who hold financial accounts in the Paymenter platform.  
It covers user registration, querying, and the invariants that protect the User aggregate.

**Boundary note:** The User aggregate is owned entirely by the Identity context. Cross‑context concerns (like account creation) are described in *Module 4: Account Provisioning & Cross‑Context Integration*.

---

## 2. Business Rules & Domain Invariants

### 2.1 User Aggregate
- A `User` must have a unique `phone_email` (composite identifier treated as a single string field).
- A `User` is created with `id=0` as a transient identifier; the infrastructure assigns the permanent `id` upon persistence.
- Upon registration, a default Ledger account **must** be provisioned for the user (this is delegated to the `AccountProvisioningPort` – see Module 4).
- A `User` may hold zero or more accounts (one-to-many via Ledger).
- A `User` may have zero or more cards mapped via `user_cards`.

---

## 3. Backend Architecture

### 3.1 Domain Layer

**Entity: `User`** (`src/identity/domain/entities/user.py`)
```python
@dataclass
class User:
    id: int          # Transient (0) until persisted
    name: str
    phone_email: str # Raw primitive; should be PhoneEmail VO (Technical Debt)
```
- **Responsibility:** Represents a system actor.
- **Invariant:** None enforced in the entity itself; uniqueness is guaranteed by the repository's database constraint.

**Port: `UserRepository`** (`src/identity/domain/repositories.py`)
```python
class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> int: ...
    @abstractmethod
    def get_all_summaries(self) -> List[Any]: ...
    @abstractmethod
    def search_summaries(self, query: str) -> List[Any]: ...
```

### 3.2 Application Layer

**Command: `RegisterUserCommand`** (`src/identity/application/commands/register_user_command.py`)
- **Payload:** `name: str`, `phone_email: str`
- **Purpose:** Register a new user and provision a default account.

**Query: `GetAllUsersQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** *(empty)*
- **Purpose:** Retrieve all user summaries.

**Query: `SearchUsersQuery`** (`src/identity/application/queries/identity_queries.py`)
- **Payload:** `query: str`
- **Purpose:** Search users by name, account number, or card number.

**Command Handler: `RegisterUserHandler`** (`src/identity/application/handlers/register_user_handler.py`)
- **Dependencies:** `UnitOfWork`, `UserRepository`, `AccountProvisioningPort`
- **Flow:**
  1. Create transient `User(id=0, ...)`.
  2. Persist via `user_repo.add(user)` → receive `user_id`.
  3. Call `account_port.create_default_account(user_id=user_id, currency_id=1)`.
  4. Commit UOW.
- **⚠️ Fragility:** `currency_id=1` is hardcoded. This assumes the first currency always has ID 1 and is active.

**Query Handler: `GetAllUsersHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[Any]` (raw tuples/dicts from SQLite).
- **⚠️ Coupling:** Repository JOINs with `accounts`, `user_cards`, and `currencies` (Ledger tables).

**Query Handler: `SearchUsersHandler`** (`src/identity/application/handlers/identity_query_handlers.py`)
- **Returns:** `List[Any]` filtered by `LIKE` on `users.name`, `accounts.account_number`, `user_cards.card_number`.
- **⚠️ Coupling:** Same cross‑context JOIN issue.

### 3.3 Infrastructure Layer

**Persistence Adapter: `SqliteUserRepository`** (`src/identity/infrastructure/persistence/sqlite_user_repository.py`)
- **Implements:** `UserRepository`
- **`add(user)`:** Inserts into `users` table; returns `lastrowid`.
- **`get_all_summaries()`:** LEFT JOINs `users` with `accounts`, `user_cards`, and `currencies`.
- **`search_summaries(query)`:** Same JOINs with `WHERE ... LIKE ...` on name, account_number, card_number.
- **⚠️ Violation:** Direct SQL access to Ledger tables (`accounts`, `currencies`) from an Identity repository.

---

## 4. API Contract

All routes are served by the Identity Dashboard Web API (see Module 6). The user-specific endpoints are:

**GET /dashboard/users**
- **Description:** List all users or search by query.
- **Query Params:** `query` (optional search string).
- **Response:** HTML render (`users.html`) with `users_list`, `query`, `currencies`.
- **Query Handler:** `GetAllUsersHandler` (if no query) or `SearchUsersHandler`.

**POST /dashboard/users/add**
- **Description:** Register a new user and provision a default account.
- **Form Data:** `name`, `phone_email`
- **Command:** `RegisterUserCommand`
- **Success:** Redirect to `/dashboard/users`.
- **Error:** Flash message.

---

## 5. Flows

### 5.1 Register User
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- POST /dashboard/users/add
    |
    v
[RegisterUserHandler]
    |-- 1. Create User(id=0, name, phone_email)
    |-- 2. UserRepository.add(user) -> user_id
    |-- 3. AccountProvisioningPort.create_default_account(user_id, currency_id=1)
    |       |
    |       v
    |   [LedgerAccountProvisioningAdapter]   (see Module 4)
    |       |-- generate_account_number()
    |       |-- generate_card_number()
    |       |-- INSERT INTO accounts (...)
    |       |-- INSERT INTO user_cards (...)
    |       |-- return account_id
    |-- 4. UnitOfWork.commit()
    |
    v
[SQLite DB]
```
**⚠️ Known Issues:**
- `currency_id=1` is hardcoded.
- No domain event is emitted.

### 5.2 Query Users
```
[HTTP Client]
    |
    v
[Dashboard Controller] -- GET /dashboard/users?query=...
    |
    v
[GetAllUsersHandler] OR [SearchUsersHandler]
    |-- SQL JOIN: users LEFT JOIN accounts LEFT JOIN user_cards LEFT JOIN currencies
    |-- Returns: List of tuples/dicts with user + account + card + currency data
```
**⚠️ Known Issues:**
- Cross‑context JOINs.
- Returns raw database rows instead of DTOs.

---

## 6. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Hardcoded Currency ID** | High | `RegisterUserHandler` uses `currency_id=1`. Fragile; breaks if database is re‑seeded. |
| **Primitive Obsession** | Medium | `User.phone_email` uses a raw string instead of a Value Object. |
| **Cross-Context SQL Reads** | Critical | `SqliteUserRepository` JOINs with Ledger tables. Implement CQRS read models. |
| **No Domain Events** | Medium | `RegisterUserHandler` does not emit `UserRegisteredEvent`. |
| **Duplicate `phone_email`** | – | SQLite UNIQUE constraint violation propagates as unhandled exception → 500 error; no domain-level validation. |

---

## 7. Notes & Refactoring Roadmap

### Immediate
- Replace hardcoded `currency_id=1` with a resolved default currency (e.g., by `currency_code` in command).

### Medium Term
- Emit `UserRegisteredEvent` from the handler; remove direct account provisioning call once event‑driven flow is ready.
- Build a local `user_summaries` read model to avoid cross‑context JOINs.

### Long Term
- Introduce `PhoneEmail` Value Object with validation.
- Move `RegisterUserCommand` to accept a `CurrencyCode` value object.

---