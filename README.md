
# Paymenter: Custom Payment Gateway Simulator

## Overview

In modern software development, building and testing payment workflows without interacting with real financial institutions is a critical requirement. This project provides a robust, local payment gateway simulator combined with an administrative dashboard and a RESTful API. It intercepts payment requests from applications during the development phase, processes them using strict double-entry bookkeeping principles, and presents the financial data in a secure, sandboxed web interface.

This system eliminates the dependency on external SaaS payment sandboxes, ensuring data privacy, zero transaction costs, and zero latency during local development. It is designed to simulate payment holds, successful captures, refunds, and multi-currency validation, allowing developers to build and test complex e-commerce workflows (like a Laravel application) directly from their local machine.

## Architecture and Principles

The codebase is engineered with maintainability and scalability in mind. It strictly adheres to the following software design principles:

*   **SOLID:** Dependencies are injected rather than hardcoded, and modules are designed for extension but closed for modification.
*   **Single Responsibility Principle (SRP):** Components are strictly segregated. The architecture uses a 3-tier layering system: **Controllers** (handling HTTP and routing), **Services** (handling business logic and orchestration), and **Repositories** (handling raw SQL and data access). 
*   **KISS (Keep It Simple, Stupid):** The execution flow is straightforward, avoiding unnecessary abstractions. Raw SQL is used over heavy ORMs for transparency and performance in a simulator.
*   **DRY (Don't Repeat Yourself):** Database connections, transaction management, and utility generators are centralized and reused across the application.

## Core Features

*   **Double-Entry Bookkeeping Engine:** Strictly enforces financial integrity. Funds are held (Pending) before being captured (Success) or refunded (Failed/Refunded), ensuring balances never drop below zero unexpectedly.
*   **Atomic Database Transactions:** Utilizes Python context managers to guarantee that multi-step financial operations (like creating a merchant and its settlement account) either completely succeed or completely roll back.
*   **Multi-Currency Enforcement:** Automatically validates that source and destination accounts share the same currency before allowing a transfer, preventing cross-currency data corruption.
*   **Secure RESTful API:** Exposes `/api/pay`, `/api/refund`, and `/api/verify` endpoints secured by an `x-api-key` authentication middleware.
*   **Dynamic Admin Dashboard:** Provides a clean UI to manage entities, top up accounts, and manually approve/decline transactions with seamless Vanilla JS updates (no full page reloads).
*   **Smart Generators:** Automatically generates secure API keys, unique 16-digit card numbers, and standard account numbers with collision detection.
*   **Smart Port Allocation & DevEx:** Features one-click startup scripts for both Windows and Linux/macOS. The server automatically detects if the default port is busy and assigns the next available port (5000-5100), then programmatically opens the web browser to the correct dynamically assigned URL. No more `Address already in use` errors when running multiple local projects!

## Prerequisites

*   Python 3.10 or higher
*   pip (Python package installer)

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
    *   On Windows:

        ```cmd
        venv\Scripts\activate
        ```

    *   On Linux/macOS:

        ```bash
        source venv/bin/activate
        ```

5.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Execution

The application runs the Flask web server and the API endpoints concurrently.

### Option 1: Using the Launcher Scripts (Recommended)

*   On Windows, double-click the `start.bat` file or run:

    ```cmd
    ./start.bat
    ```

*   On Linux/macOS, execute the shell script:

    ```bash
    chmod +x start.sh
    ./start.sh
    ```

### Option 2: Manual Execution

Ensure your virtual environment is activated, then run:

```bash
python app.py
```

Upon startup, the system will initialize the database, seed default data, and dynamically find an available port starting from `5000`. The default web browser will automatically open to the assigned URL (e.g., `http://127.0.0.1:5000`, or `http://127.0.0.1:5001` if 5000 is already in use by another project).

## Laravel Integration

To route payment requests from a Laravel application to this local simulator, you need to configure Laravel's HTTP client to point to the Paymenter API and include the merchant's API key.

1.  Update your Laravel project's `.env` file with the following configuration:

    ```env
    # Note: Paymenter dynamically allocates a port starting from 5000. 
    # Ensure this URL matches the port Paymenter started on in your terminal.
    PAYMENT_GATEWAY_API_URL=http://127.0.0.1:5000/api
    PAYMENT_GATEWAY_API_KEY=your_merchant_api_key_here
    ```

2.  Ensure you have created a Merchant in the Paymenter Dashboard and copied its API Key into the `.env` file above.

3.  Example Laravel Payment Dispatch (using `Http` facade):

    ```php
    use Illuminate\Support\Facades\Http;

    public function initiatePayment($userCardNumber, $amount, $currencyCode)
    {
        $response = Http::withHeaders([
            'x-api-key' => env('PAYMENT_GATEWAY_API_KEY'),
        ])->post(env('PAYMENT_GATEWAY_API_URL') . '/pay', [
            'destination_card_number' => $userCardNumber,
            'amount'                 => $amount,
            'currency_code'          => $currencyCode,
        ]);

        if ($response->successful()) {
            // Transaction is Pending
            return $response->json('transaction_id'); 
        }

        // Handle errors (e.g., 402 Insufficient Funds, 400 Bad Request)
        throw new \Exception($response->json('error'));
    }
    ```

### Workflow Example:

1.  In the Paymenter Dashboard, create a Currency (e.g., Toman), a Merchant (e.g., Laravel Shop), and a User with an Account. Top up the User's account with a balance.
2.  Trigger a payment request from your Laravel application using the code above.
3.  Laravel sends a `POST /api/pay` request to Paymenter.
4.  Paymenter validates the funds, deducts the amount from the User, and places it in a `Pending` state. The API returns the `transaction_id`.
5.  (Manual Approval Flow): Navigate to the Paymenter Dashboard -> Transactions. Find the Pending transaction and click **[Complete]**.
6.  (Verification Flow): Trigger a verification request from Laravel (`GET /api/verify/{transaction_id}`) to check if the status has changed to `Success`, then finalize the order in your Laravel database.
7.  (Refund Flow): If the order is canceled, Laravel calls `POST /api/refund`, and Paymenter automatically returns the funds to the User's card.

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
|   |-- merchant_repo.py
|   |-- transaction_repo.py
|   |-- user_repo.py
|
|-- services/                   # Business Logic Layer
|   |-- __init__.py
|   |-- account_service.py
|   |-- api_service.py          # API orchestration & validation
|   |-- currency_service.py
|   |-- ledger.py               # Core Double-Entry Bookkeeping Engine
|   |-- merchant_service.py
|   |-- transaction_service.py
|   |-- user_service.py
|
|-- utils/                      # Stateful Utilities
|   |-- __init__.py
|   |-- generators.py           # API Key, Card, Account number generators
|
|-- static/                     # Frontend Assets
|   |-- css/                    # Modular CSS (app.css, user.css, etc.)
|   |-- js/                     # Modular Vanilla JS (main.js, merchant.js, etc.)
|
|-- templates/                  # Jinja2 HTML Templates
|   |-- base.html               # Sidebar layout
|   |-- accounts.html
|   |-- currencies.html
|   |-- merchants.html
|   |-- transactions.html
|   |-- users.html
|
|-- tests/                      # Test Scripts
    |-- __init__.py
    |-- test_phase2.py          # Integration test for Ledger & Generators
```