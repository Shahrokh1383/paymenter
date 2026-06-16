# Paymenter: Custom Payment Gateway Simulator (Hosted Payment Page Edition)

## Overview

In modern software development, building and testing payment workflows without interacting with real financial institutions or compromising PCI-DSS compliance is a critical requirement. This project provides a robust, local payment gateway simulator featuring a **Hosted Payment Page (HPP)**, 3D Secure (OTP) simulation, and an automated email receipt lifecycle. 

It intercepts payment requests from applications during the development phase, securely isolates sensitive card data collection on a branded gateway page, processes transactions using strict double-entry bookkeeping principles, and presents the financial data in a secure, sandboxed admin dashboard.

This system eliminates the dependency on external SaaS payment sandboxes, ensuring data privacy, zero transaction costs, and zero latency during local development. It is designed to simulate payment intents, OTP authorizations, successful captures, refunds, and automated customer notifications, allowing developers to build and test complex, secure e-commerce workflows (like a Laravel application) directly from their local machine.

## Architecture and Principles

The codebase is engineered with maintainability and scalability in mind. It strictly adheres to the following software design principles:

*   **SOLID:** Dependencies are injected rather than hardcoded, and modules are designed for extension but closed for modification.
*   **Single Responsibility Principle (SRP):** Components are strictly segregated. The architecture uses a 3-tier layering system: **Controllers** (handling HTTP and routing), **Services** (handling business logic and orchestration), and **Repositories** (handling raw SQL and data access). Email dispatch and Gateway UI are completely isolated from the Admin Dashboard.
*   **KISS (Keep It Simple, Stupid):** The execution flow is straightforward, avoiding unnecessary abstractions. Raw SQL is used over heavy ORMs for transparency and performance in a simulator.
*   **DRY (Don't Repeat Yourself):** Database connections, transaction management, utility generators, and SMTP configurations are centralized and reused across the application.

## Core Features

*   **Hosted Payment Page (HPP) & PCI Compliance Simulation:** The merchant application (e.g., Laravel) never touches raw credit card numbers. Users are redirected to a secure, isolated Paymenter Gateway page to enter sensitive data, perfectly mimicking Stripe Checkout or PayPal.
*   **3D Secure (OTP) Simulation:** Generates secure 5-digit One-Time Passwords and dispatches them via a local SMTP sink server. The user must retrieve the OTP from their local email inbox and enter it on the Gateway page to authorize the transaction.
*   **Automated Email Lifecycle:** Automatically dispatches OTP emails for authorization, and sends beautifully formatted HTML receipts to the customer when an Admin manually "Completes" (Success) or "Fails" (Refund) a transaction in the dashboard.
*   **Double-Entry Bookkeeping Engine:** Strictly enforces financial integrity. Funds are held (Pending) after OTP verification before being captured (Success) or refunded (Failed/Refunded), ensuring balances never drop below zero unexpectedly.
*   **Two-Phase Commit Architecture:** Separates the "Payment Intent" (Session creation) from the actual "Authorization" (Fund holding), ensuring robust state management.
*   **Atomic Database Transactions:** Utilizes Python context managers to guarantee that multi-step financial operations either completely succeed or completely roll back.
*   **Multi-Currency Enforcement:** Automatically validates that source and destination accounts share the same currency before allowing a transfer.
*   **Secure RESTful API:** Exposes `/api/pay`, `/api/refund`, and `/api/verify` endpoints secured by an `x-api-key` authentication middleware.
*   **Dynamic Admin Dashboard:** Provides a clean UI to manage entities, top up accounts, and manually approve/decline transactions with seamless Vanilla JS updates.
*   **Smart Port Allocation & DevEx:** Features one-click startup scripts. The server automatically detects if the default port is busy and assigns the next available port (5000-5100), then programmatically opens the web browser.

## Prerequisites

*   Python 3.10 or higher
*   pip (Python package installer)
*   **Local SMTP Sink Server:** You must run the companion [smtp-server](https://github.com/Shahrokh1383/smtp-server) project locally on port `1025` to intercept and view the OTP and Receipt emails.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/Shahrokh1383/paymenter
    ```
2.  Navigate into the project directory:
    ```bash
    cd paymenter
    ```
3.  Create a virtual environment:
    ```bash
    python -m venv venv
    ```
4.  Activate the virtual environment:
    *   On Windows: `venv\Scripts\activate`
    *   On Linux/macOS: `source venv/bin/activate`
5.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Execution

### Option 1: Using the Launcher Scripts (Recommended)
*   On Windows, double-click the `start.bat` file or run: `./start.bat`
*   On Linux/macOS, execute the shell script: `chmod +x start.sh && ./start.sh`

### Option 2: Manual Execution
Ensure your virtual environment is activated, then run:
```bash
python app.py
```
Upon startup, the system will initialize the database, seed default data, and dynamically find an available port starting from `5000`. The default web browser will automatically open to the assigned Admin Dashboard URL.

## Laravel Integration

To route payment requests from a Laravel application to this local simulator, you must configure Laravel to request a Payment Session and redirect the user to the Paymenter Gateway.

1.  Update your Laravel project's `.env` file:
    ```env
    PAYMENT_GATEWAY_API_URL=http://127.0.0.1:5000/api
    PAYMENT_GATEWAY_API_KEY=your_merchant_api_key_here
    ```

2.  Example Laravel Payment Dispatch (using `Http` facade):
    ```php
    use Illuminate\Support\Facades\Http;

    public function initiatePayment($amount, $currencyCode, $userEmail, $callbackUrl)
    {
        $response = Http::withHeaders([
            'x-api-key' => env('PAYMENT_GATEWAY_API_KEY'),
        ])->post(env('PAYMENT_GATEWAY_API_URL') . '/pay', [
            'amount'        => $amount,
            'currency_code' => $currencyCode,
            'user_email'    => $userEmail,
            'callback_url'  => $callbackUrl,
        ]);

        if ($response->successful()) {
            // Returns the secure Gateway URL
            return $response->json('payment_url'); 
        }

        throw new \Exception($response->json('error'));
    }
    ```

### Workflow Example:

1.  **Setup:** Start your local `smtp-server` (port 1025) and `paymenter`. Create a Currency, Merchant, and test User in the Paymenter Dashboard.
2.  **Initiation:** Laravel calls `POST /api/pay` with the amount, email, and callback URL. Paymenter creates a session and emails a 5-digit OTP to the user's local SMTP inbox.
3.  **Redirection:** Laravel receives the `payment_url` and redirects the user's browser to the Paymenter Gateway Page.
4.  **Authorization (3D Secure):** The user opens their SMTP Web UI, copies the OTP, and enters it along with their 16-digit Card Number on the Paymenter Gateway Page.
5.  **Hold & Callback:** Paymenter validates the OTP/Card, calls `hold_funds()`, and redirects the user back to the Laravel `callback_url` with the `transaction_id`.
6.  **Admin Settlement:** The Admin views the Paymenter Dashboard -> Transactions and clicks **[Complete]** or **[Fail]**.
7.  **Automated Receipts:** Upon Admin action, Paymenter automatically emails a "Payment Successful" or "Payment Refunded" HTML receipt to the user's local SMTP inbox.

## Project Structure

## Project Structure

```text
paymenter/
|-- app.py                      # Flask application factory, dynamic port allocation, and entry point
|-- requirements.txt            # Python dependencies
|-- start.bat                   # Windows one-click launcher
|-- start.sh                    # Linux/macOS one-click launcher
|
|-- controllers/                # Routing Layer (Thin Controllers)
|   |-- __init__.py
|   |-- api_controller.py       # API routes & before_request auth middleware
|   |-- gateway_controller.py   # Public-facing Hosted Payment Page routes
|   |-- dashboard_controller.py # Dashboard UI routes & form handling
|   |-- transaction_controller.py# Transaction UI routes & JSON endpoints
|
|-- database/                   # Data Persistence Layer
|   |-- __init__.py             # Exposes init_db to the app
|   |-- connection.py           # SQLite connection factory
|   |-- schema.py               # Database table creation
|   |-- seed.py                 # Default data insertion
|   |-- transaction.py          # Atomic DB context manager (Commit/Rollback)
|   |-- storage/                # Physical storage for SQLite file
|
|-- repositories/               # Data Access Layer (Raw SQL)
|   |-- __init__.py
|   |-- account_repo.py
|   |-- currency_repo.py
|   |-- gateway_repo.py
|   |-- merchant_repo.py
|   |-- transaction_repo.py
|   |-- user_repo.py
|
|-- services/                   # Business Logic Layer
|   |-- __init__.py
|   |-- account_service.py
|   |-- api_service.py          # API orchestration & validation
|   |-- currency_service.py
|   |-- email_service.py        # SMTP dispatch for OTPs and Automated Receipts
|   |-- gateway_service.py      # OTP verification and Two-Phase commit logic
|   |-- ledger.py               # Core Double-Entry Bookkeeping Engine
|   |-- merchant_service.py
|   |-- transaction_service.py
|   |-- user_service.py
|
|-- utils/                      # Stateful Utilities
|   |-- __init__.py
|   |-- generators.py           # API Key, Card, Account, Gateway Token, OTP generators
|
|-- static/                     # Frontend Assets
|   |-- css/                    # Modular CSS (app.css, user.css, etc.)
|   |-- js/                     # Modular Vanilla JS (main.js, merchant.js, etc.)
|
|-- templates/                  # Jinja2 HTML Templates
|   |-- base.html               # Sidebar layout
|   |-- accounts.html
|   |-- gateway.html            # Isolated, public-facing Hosted Payment Page
|   |-- gateway_error.html      # Isolated error page for expired/invalid sessions
|   |-- currencies.html
|   |-- merchants.html
|   |-- transactions.html
|   |-- users.html
|
|-- tests/                      # Test Scripts
    |-- __init__.py
    |-- test_phase2.py          # Integration test for Ledger & Generators
```