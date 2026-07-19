LedgerKernel.md :



4. Operational & Lifecycle Gaps

    [Documentation/Logical Gap] Deactivated Currency Lifecycle Management:
        Issue: CurrencyDeactivatedEvent is listed in Domain Events, but no Business Rule governs it.
        Unanswered Question: If a currency is deactivated, what happens to accounts still holding it? Can they initiate new transactions?
        Solution: Add a new Invariant: "No new transactions can be processed on accounts with a deactivated currency," or "Upon deactivation, all accounts holding the currency must be migrated to the Base Currency."
    [Security/Audit Gap] Lack of Soft Delete for Aggregates:
        Issue: In Ledger architectures, physical deletion (Hard Delete) of an Account or Currency is strictly forbidden. The document lacks a Soft Delete or Archiving mechanism.
        Solution: Introduce is_deleted and deleted_at fields and apply Global Query Filters in the Read Models.




SettlementCore.md