🗺️ THE MASTER EXECUTION ROADMAP (Batch 2 & Batch 3)
To prevent token limits and ensure 100% precision, here is the exact, file-by-file execution plan for the remainder of the project. When you are ready to begin Batch 2, we will follow this map strictly.
BATCH 2: The Checkout Bounded Context
Step 1: Domain Layer & Events

    Review Legacy: services/gateway_service.py, utils/generators.py
    Create:
        src/checkout/domain/entities/payment_session.py: Aggregate Root representing the gateway session (Token, OTP, Status, Amount).
        src/checkout/domain/value_objects/session_token.py, otp_code.py, callback_url.py: Strict VOs.
        src/checkout/domain/events/payment_initiated_event.py: Event carrying OTP and email data for the Notifications context.
        src/checkout/domain/repositories.py: SessionRepository port.

Step 2: Anti-Corruption Layer (Ports)

    Review Legacy: How gateway_service.py calls hold_funds and how api_service.py calls fail_and_refund and verify_transaction.
    Create (in Checkout Domain):
        src/checkout/domain/ports/fund_reservation_port.py: Interface to hold funds.
        src/checkout/domain/ports/transaction_refund_port.py: Interface to refund.
        src/checkout/domain/ports/transaction_verification_port.py: Interface to verify status.

Step 3: Application Layer (Commands & Handlers)

    Review Legacy: services/api_service.py, services/gateway_service.py
    Create:
        Commands: initiate_payment_command.py, authorize_payment_command.py, refund_payment_command.py.
        Queries: get_session_details_query.py.
        Handlers: Corresponding handlers that use the SessionRepository and the ACL Ports defined in Step 2.

Step 4: Infrastructure Layer (Adapters & Persistence)

    Review Legacy: repositories/gateway_repo.py
    Create:
        src/checkout/infrastructure/persistence/sqlite_session_repository.py: Implements SessionRepository.
        src/checkout/infrastructure/persistence/ledger_fund_reservation_adapter.py: Implements FundReservationPort by importing and calling Ledger's HoldFundsHandler.
        src/checkout/infrastructure/persistence/ledger_refund_adapter.py: Implements TransactionRefundPort.
        src/checkout/infrastructure/persistence/ledger_verification_adapter.py: Implements TransactionVerificationPort.

Step 5: Infrastructure Layer (Web Controllers)

    Review Legacy: controllers/gateway_controller.py, controllers/api_controller.py
    Create:
        src/checkout/infrastructure/web/gateway_controller.py: Pure HTTP adapter for the user UI.
        src/checkout/infrastructure/web/api_controller.py: Pure HTTP adapter for merchant callbacks, including the x-api-key middleware.

Step 6: Event Wiring (Notifications Context Update)

    Update: src/notifications/application/handlers/receipt_email_handler.py to add a method handling PaymentInitiatedEvent (sending the OTP email).
    Update: The Event Bus wiring (which will be finalized in Batch 3) to subscribe this handler.

BATCH 3: Application Bootstrap & Final Purge
Step 1: The Dependency Injection Container

    Create: app/di_container.py. This file will instantiate the InMemoryEventBus, subscribe all cross-context handlers (like Notifications listening to Ledger and Checkout events), and provide factory methods to inject dependencies into the Flask controllers.

Step 2: The Flask App Factory

    Review Legacy: app.py
    Create: app/flask_app.py. Initializes the Database, registers the new Blueprints (dashboard_bp, transaction_bp, gateway_bp, api_bp), and injects dependencies via the DI Container.
    Create: app/main.py. The clean entry point (if __name__ == '__main__':).

Step 3: The Final Dead Code Purge

    Action: Permanently delete the following legacy directories and files:
        controllers/
        services/
        repositories/
        database/
        utils/
        Root app.py