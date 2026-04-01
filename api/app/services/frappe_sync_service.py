"""Empty service stubs — will be implemented in Phase 4."""


class FrappeSyncService:
    """Pull master data from ERPNext into local MySQL."""

    def run_full_sync(self, db):
        raise NotImplementedError("Phase 4")

    def run_incremental_sync(self, db):
        raise NotImplementedError("Phase 4")
