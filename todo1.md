LedgerKernel.md :


2. Business Logic & Invariant Bugs

    [Critical Bug] Business Key Dependency on Database Auto-Increment:
        Issue: The formula 9000000000 + currency_id (in BR-6 and Issue 2) heavily relies on the database's ID generation strategy.
        Rejection Reason: Business Keys must never depend on physical database sequences. If you ever migrate to PostgreSQL, switch to UUIDs, or shard the data, this formula completely falls apart. Furthermore, a 10-digit limit (9 billion accounts) is highly restrictive for a scalable Ledger.
        Solution: AccountNumber generation should utilize a database-independent deterministic algorithm (e.g., hashing the currency's UUID + Salt) or an independent Sequence Generator (like Redis INCR or Snowflake IDs).
    [Logical Bug] Ignoring Holds/Authorizations in Currency Mutation (BR-3):
        Issue: Rule BR-3 states that if the balance is zero, the currency can be changed.
        Rejection Reason: In financial systems, a "zero balance" does not mean "no pending transactions." An account might have a zero available balance but still have an active Hold or Authorization. Changing the currency in this state leaves the hold in the old currency while the settlement occurs in the new one, which is catastrophic.
        Solution: The change_currency method must verify pending_holds == 0 and open_authorizations == 0 in addition to balance == 0.
    [Logical Bug] Lack of Idempotency in Escrow Account Bootstrapping:
        Issue: If the CreateCurrencyHandler in Flow 1 crashes due to a network drop or UoW error after creating the Currency but before creating the Escrow Account, what happens on a retry?
        Solution: An Idempotency mechanism must be implemented to prevent the creation of duplicate Escrow accounts.

3. Data, Persistence & Execution Flow Issues

    [Execution Bug] ID Generation Paradox within the Unit of Work (Flow 1):
        Issue: Flow 1 states that the Handler creates the currency, then calls EscrowBootstrapper with the currency_id, persisting both in a single UoW.
        Rejection Reason: If currency_id is a database Auto-Increment, the ID is not generated until the Currency is flushed or saved to the database. You cannot pass the ID to the EscrowBootstrapper before persisting unless you break the UoW pattern with a mid-transaction flush.
        Solution: Use UUIDs for currency_id (generating the ID in the Application layer before hitting the database) or shift the architecture towards Event-Driven (as mentioned in Section 1).
    [Hidden SQLite Bug] Decimal Precision Loss:
        Issue: Section 3.3 mentions SQLite. SQLite does not have a native DECIMAL type; it uses NUMERIC, which often degrades to REAL (Float).
        Rejection Reason: Using Floats for financial quantities (Money) introduces rounding errors.
        Solution: In SQLite, Money values must strictly be stored as INTEGER (representing the smallest currency unit, e.g., cents) or TEXT (exact Decimal string). The ORM must be configured to handle this conversion seamlessly.
    [Concurrency Bug] Missing Retry Strategy for OCC (Issue 1):
        Issue: Issue 1 notes that ConcurrencyException is unhandled, merely stating that the caller should manage it.
        Rejection Reason: In high-throughput systems, OCC collisions are normal. Pushing the burden to the caller complicates the codebase significantly.
        Solution: Implement a Retry with Exponential Backoff pattern at the Application Layer (e.g., using Python decorators for Commands).

4. Operational & Lifecycle Gaps

    [Documentation/Logical Gap] Deactivated Currency Lifecycle Management:
        Issue: CurrencyDeactivatedEvent is listed in Domain Events, but no Business Rule governs it.
        Unanswered Question: If a currency is deactivated, what happens to accounts still holding it? Can they initiate new transactions?
        Solution: Add a new Invariant: "No new transactions can be processed on accounts with a deactivated currency," or "Upon deactivation, all accounts holding the currency must be migrated to the Base Currency."
    [Security/Audit Gap] Lack of Soft Delete for Aggregates:
        Issue: In Ledger architectures, physical deletion (Hard Delete) of an Account or Currency is strictly forbidden. The document lacks a Soft Delete or Archiving mechanism.
        Solution: Introduce is_deleted and deleted_at fields and apply Global Query Filters in the Read Models.




SettlementCore.md