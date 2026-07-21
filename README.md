# Paymenter: Custom Payment Gateway Simulator (Hosted Payment Page Edition)

## Overview

In modern software development, building and testing payment workflows without interacting with real financial institutions or compromising PCI-DSS compliance is a critical requirement. This project provides a robust, local payment gateway simulator featuring a **Hosted Payment Page (HPP)**, 3D Secure (OTP) simulation, an automated email receipt lifecycle, and a resilient **webhook engine** for asynchronous merchant notifications.

It intercepts payment requests from applications during the development phase, securely isolates sensitive card data collection on a branded gateway page, processes transactions using strict double-entry bookkeeping principles, and presents the financial data in a secure, sandboxed admin dashboard.

This system eliminates the dependency on external SaaS payment sandboxes, ensuring data privacy, zero transaction costs, and zero latency during local development. It simulates payment intents, OTP authorizations, successful captures, refunds, automated customer notifications, and **reliable webhook delivery with guaranteed at-least-once semantics**, allowing developers to build and test complex, secure e-commerce workflows (such as a Laravel application) entirely on their local machine.

## Architecture and Principles

The codebase is engineered with maintainability and scalability in mind. It strictly adheres to the following software design principles:

*   **SOLID:** Dependencies are injected rather than hardcoded, and modules are designed for extension but closed for modification.
*   **Single Responsibility Principle (SRP):** Components are strictly segregated. The architecture uses a 3-tier layering system: **Controllers** (handling HTTP and routing), **Services** (handling business logic and orchestration), and **Repositories** (handling raw SQL and data access). Email dispatch, Gateway UI, and the webhook dispatch worker are completely isolated from the Admin Dashboard.
*   **Domain-Driven Design (DDD) Alignment:** Core business processes (payment authorisation, fund capture, refund) are implemented as domain events. Side effects such as webhook delivery are triggered by these events, keeping the write‑side pure and decoupled.
*   **KISS (Keep It Simple, Stupid):** The execution flow is straightforward, avoiding unnecessary abstractions. Raw SQL is used over heavy ORMs for transparency and performance in a simulator.
*   **DRY (Don't Repeat Yourself):** Database connections, transaction management, utility generators, SMTP configurations, and webhook cryptographic signing are centralized and reused across the application.

## Core Features

*   **Hosted Payment Page (HPP) & PCI Compliance Simulation:** The merchant application (e.g., Laravel) never touches raw credit card numbers. Users are redirected to a secure, isolated Paymenter Gateway page to enter sensitive data, perfectly mimicking Stripe Checkout or PayPal.
*   **3D Secure (OTP) Simulation:** Generates secure 5-digit One-Time Passwords and dispatches them via a local SMTP sink server. The user must retrieve the OTP from their local email inbox and enter it on the Gateway page to authorize the transaction.
*   **Automated Email Lifecycle:** Automatically dispatches OTP emails for authorization, and sends beautifully formatted HTML receipts to the customer when an Admin manually “Completes” (Success) or “Fails” (Refund) a transaction in the dashboard.
*   **Double-Entry Bookkeeping Engine:** Strictly enforces financial integrity. Funds are held (Pending) after OTP verification before being captured (Success) or refunded (Failed/Refunded), ensuring balances never drop below zero unexpectedly.
*   **Two-Phase Commit Architecture:** Separates the “Payment Intent” (Session creation) from the actual “Authorization” (Fund holding), ensuring robust state management.
*   **Atomic Database Transactions:** Utilizes Python context managers to guarantee that multi-step financial operations either completely succeed or completely roll back.
*   **Multi-Currency Enforcement:** Automatically validates that source and destination accounts share the same currency before allowing a transfer.
*   **Secure RESTful API:** Exposes `/api/pay`, `/api/refund`, and `/api/verify` endpoints secured by an `x-api-key` authentication middleware.
*   **Dynamic Admin Dashboard:** Provides a clean UI to manage entities, top up accounts, and manually approve/decline transactions with seamless Vanilla JS updates.
*   **Smart Port Allocation & DevEx:** Features one-click startup scripts. The server automatically detects if the default port is busy and assigns the next available port (5000-5100), then programmatically opens the web browser.
*   **Resilient Webhook System (Store-and-Forward):** Guarantees merchant notifications for transaction state changes (`payment.completed`, `payment.failed`, `payment.refunded`) using an outbox pattern, cryptographically signed payloads, automatic retries with exponential backoff, and a dedicated admin dashboard for observability.

## Webhook System

Paymenter implements a fully decoupled webhook delivery engine that treats notifications as first‑class side effects of domain events. The system adheres to a store‑and‑forward architecture built on the transactional outbox pattern, ensuring zero data loss even if the server crashes immediately after a transaction completes.

### How it works

1. **Domain Event Emission:** When an admin finalises a transaction (completes, fails, or refunds), the ledger service mutates the aggregate and publishes a strongly‑typed domain event (e.g., `TransactionCompletedEvent`). No webhook logic exists inside the admin controllers or ledger handlers.

2. **Outbox Persistence:** Dedicated event subscribers listen for these domain events. For each merchant with a configured and enabled webhook URL, the subscriber constructs the exact JSON payload, computes an HMAC‑SHA256 signature using the merchant’s unique secret, and persists a record into the `webhook_outbox` table. This write happens within the same database transaction as the business operation, guaranteeing atomicity – either both the transaction and the outbox record are committed, or neither.

3. **Background Worker:** A lightweight background process (the webhook worker) continuously polls the outbox for records in `pending` status whose scheduled time has arrived. For each message, it sends an HTTP POST to the merchant’s endpoint with the following headers:
   - `Content-Type: application/json`
   - `X-Paymenter-Signature: sha256=<hmac_signature>`
   - `X-Paymenter-Event: <event_type>`
   - `X-Paymenter-Delivery: <outbox_id>`

4. **Retry Policy with Exponential Backoff:** If the delivery fails (non‑2xx response or network error), the worker updates the outbox record with an incremented attempt counter and schedules the next attempt using exponential backoff (1 min, 5 min, 30 min, 1 hour, 2 hours, up to a maximum of 5 attempts). Once the maximum retries are exhausted, the record is marked as `failed` and no further delivery attempts are made unless manually retried.

5. **Observability and Administration:** A dedicated section in the Admin Dashboard provides a real‑time view of all webhook deliveries, colour‑coded by status (pending, sent, failed). Administrators can inspect the full payload, signature, and HTTP response for every attempt. A “Manual Retry” action allows resetting a failed delivery so the worker picks it up on the next cycle.

6. **Cryptographic Signing:** The HMAC‑SHA256 signature is computed once at outbox creation time and stored alongside the payload. This prevents signature regeneration on retries and allows merchants to verify the integrity and origin of the notification using their own copy of the webhook secret. The `X-Paymenter-Signature` header follows the standard `sha256=<hex_digest>` format.

### Merchant Configuration

Webhook endpoints are configured per merchant through the Admin Dashboard (Identity context). Each merchant can define:
- A target `webhook_url` (must be an absolute HTTPS URL in production, but HTTP is accepted for local development).
- A cryptographically generated `webhook_secret` (displayed only once upon generation; stored in hashed form thereafter for security).
- An enable/disable toggle.

When disabled, no outbox records are created for that merchant, completely halting webhook traffic without affecting transaction processing.

## Prerequisites

*   Python 3.10 or higher
*   pip (Python package installer)
*   **Local SMTP Sink Server:** You must run the companion [smtp-server](https://github.com/Shahrokh1383/smtp-server) project locally on port `1025` to intercept and view the OTP and Receipt emails. This is mandatory for the email lifecycle to function.

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

Both the main Paymenter server and the webhook worker must be running simultaneously for full functionality. The webhook worker is responsible for dispatching outbound merchant notifications and must be kept alive for the entire development session.

### Option 1: Using the Launcher Scripts (Recommended)
*   **Paymenter Server:** On Windows, double-click the `start.bat` file or run: `./start.bat`. On Linux/macOS, execute: `chmod +x start.sh && ./start.sh`.
*   **Webhook Worker (Windows):** Open a second terminal and run the dedicated batch file: `start_worker.bat`. This script activates the virtual environment and launches the background worker.
*   **Webhook Worker (Linux/macOS):** Open a second terminal, activate the virtual environment, and execute the worker command:
    ```bash
    source venv/bin/activate
    export FLASK_APP=src/app/flask_app.py:create_app
    flask webhook-worker
    ```

Upon startup, the main server will initialize the database, seed default data, and dynamically find an available port starting from `5000`. The default web browser will automatically open to the assigned Admin Dashboard URL.

### Option 2: Manual Execution
Ensure your virtual environment is activated.

**Start the main Paymenter server:**
```bash
python app.py
```

**Start the webhook worker in a separate terminal:**
Activate the virtual environment first, then set the `FLASK_APP` environment variable and invoke the worker command.

*   On Windows (Command Prompt or PowerShell after activation):
    ```cmd
    set FLASK_APP=src/app/flask_app.py:create_app
    flask webhook-worker
    ```
*   On Linux/macOS:
    ```bash
    export FLASK_APP=src/app/flask_app.py:create_app
    flask webhook-worker
    ```

The worker will output log lines indicating it is polling for outbox records. Leave this terminal open. If the worker is not running, webhook deliveries will remain queued in the outbox but will never be dispatched.

### Workflow Example:

1.  **Setup:** Start your local `smtp-server` (port 1025) and `paymenter` along with the webhook worker. Create a Currency, Merchant, and test User in the Paymenter Dashboard. Configure the merchant’s webhook URL and enable it if you wish to receive asynchronous notifications.
2.  **Initiation:** Laravel calls `POST /api/pay` with the amount, email, and callback URL. Paymenter creates a session and emails a 5-digit OTP to the user’s local SMTP inbox.
3.  **Redirection:** Laravel receives the `payment_url` and redirects the user’s browser to the Paymenter Gateway Page.
4.  **Authorization (3D Secure):** The user opens their SMTP Web UI, copies the OTP, and enters it along with their 16-digit Card Number on the Paymenter Gateway Page.
5.  **Hold & Callback:** Paymenter validates the OTP/Card, calls `hold_funds()`, and redirects the user back to the Laravel `callback_url` with the `transaction_id`.
6.  **Admin Settlement:** The Admin views the Paymenter Dashboard -> Transactions and clicks **[Complete]** or **[Fail]**.
7.  **Automated Receipts:** Upon Admin action, Paymenter automatically emails a “Payment Successful” or “Payment Refunded” HTML receipt to the user’s local SMTP inbox.
8.  **Webhook Dispatch:** Simultaneously, the webhook worker picks up the corresponding outbox record and delivers a signed HTTP POST to the merchant’s configured endpoint.

## Critical Dependencies and Further Documentation

*   **Mandatory SMTP Companion:** This project relies entirely on the separate [smtp-server](https://github.com/Shahrokh1383/smtp-server) application for the receipt and OTP email lifecycle. Without it running on port `1025`, no emails will be generated and the 3D Secure flow will be unusable. Please ensure the SMTP server is active before starting any test scenario.

*   **Laravel Integration Guide:** For a comprehensive walkthrough on connecting a Laravel application to Paymenter, handling callbacks, and consuming webhook notifications, refer to the dedicated integration document located at:
  [docs/backend/guideline/Laravel_Integration_Guide.md](docs/backend/guideline/Laravel_Integration_Guide.md)
  This guide covers end-to-end setup, request signing, idempotency, and recommended error handling patterns.