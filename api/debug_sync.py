import sys
import traceback
from app.database import get_db_context
from app.services.frappe_sync_service import FrappeSyncService

try:
    with get_db_context() as db:
        svc = FrappeSyncService()
        print("Starting users sync")
        count = svc._run_sync(db, full=True)
        print("Users synced:", count.get("erp_user"))
        print("All sync results:", count)
except Exception as e:
    print("Error:", traceback.format_exc())
