# Module 6: Identity Dashboard Web API
## Paymenter Project | Version 1.0.0

---

## 1. Overview
This module documents the **HTTP interface** served by the Identity (and mixed Ledger) routes in the dashboard controller. It consolidates all endpoints, their request/response contracts, and the delegation to the appropriate handlers.

---

## 2. Controller & Routing

**Controller:** `dashboard_controller.py` (`src/identity/infrastructure/web/dashboard_controller.py`)
- **Blueprint:** `dashboard_bp`, url_prefix `/dashboard`
- **DI Pattern:** Manually instantiates `SqliteUnitOfWork` and handlers inline (Identity handlers not registered in DI container).

---

## 3. API Contract

### 3.1 Currencies

**GET /dashboard/currencies**
- **Description:** List all currencies.
- **Response:** HTML (`currencies.html`), data: `currencies_list`
- **Query Handler:** `GetAllCurrenciesHandler`

**POST /dashboard/currencies/add**
- **Description:** Create a new currency (correctly delegates to Ledger).
- **Form Data:** `name`, `code`
- **Command:** `CreateCurrencyCommand` (Ledger)
- **Success:** Redirect to `/dashboard/currencies`.
- **Error:** Flash message.

**POST /dashboard/currencies/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle currency status **(deprecated Identity handler)**.
- **Path Params:** `id` (currency ID), `is_active` (unused).
- **Command:** `ToggleCurrencyCommand` (Identity)
- **Success:** Redirect to `/dashboard/currencies`.

### 3.2 Users

**GET /dashboard/users**
- **Description:** List/search users.
- **Query Params:** `query` (optional)
- **Response:** HTML (`users.html`), data: `users_list`, `query`, `currencies`
- **Handler:** `GetAllUsersHandler` / `SearchUsersHandler`

**POST /dashboard/users/add**
- **Description:** Register a new user.
- **Form Data:** `name`, `phone_email`
- **Command:** `RegisterUserCommand`
- **Success:** Redirect to `/dashboard/users`.
- **Error:** Flash message.

### 3.3 Accounts (Ledger routes hosted in the same controller)

**GET /dashboard/accounts**
- **Description:** List all accounts.
- **Query Handler:** `GetAllAccountsQuery` (Ledger)

**POST /dashboard/accounts/update-currency**
- **Form Data:** `account_id`, `currency_code`
- **Command:** `UpdateAccountCurrencyCommand` (Ledger)

**POST /dashboard/accounts/topup**
- **Form Data:** `account_id`, `amount`
- **Command:** `TopupAccountCommand` (Ledger)

**GET /dashboard/escrow**
- **Description:** List escrow accounts.
- **Query Handler:** `GetAllEscrowAccountsQuery` (Ledger)

### 3.4 Merchants

**GET /dashboard/merchants**
- **Description:** List all merchants.
- **Response:** HTML (`merchants.html`), data: `merchants_list`
- **Handler:** `GetAllMerchantsHandler`

**POST /dashboard/merchants/add**
- **Description:** Onboard a new merchant.
- **Form Data:** `name`
- **Command:** `OnboardMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.
- **Error:** Flash message.

**POST /dashboard/merchants/toggle/<int:id>/<int:is_active>**
- **Description:** Toggle merchant status.
- **Path Params:** `id` (merchant ID), `is_active` (unused)
- **Command:** `ToggleMerchantCommand`
- **Success:** Redirect to `/dashboard/merchants`.

---

## 4. Flows
*(All flows are described in their respective domain modules. The controller simply routes to the correct handler.)*

---

## 5. Edge Cases & Known Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| **Manual Wiring** | Medium | Identity handlers are instantiated inline; no DI container support. |
| **Cross-Context Routes** | Medium | The controller mixes Identity and Ledger endpoints; future refactoring should separate these into distinct blueprints. |
| **Unused `is_active` in toggle routes** | Low | The path parameter is ignored; status is derived from database. |

---

## 6. Notes & Refactoring Roadmap

### Immediate
- Register Identity handlers in `DIContainer` and refactor controller to use `current_app.di_container`.
- Move Ledger-specific routes to a separate Ledger dashboard controller (or clearly mark them).

### Medium Term
- Separate the dashboard into context‑specific blueprints (Identity, Ledger).

### Long Term
- Replace HTML rendering with a proper API layer if needed.