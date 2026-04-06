import sys
import os
sys.path.insert(0, os.getcwd())
from app.database import engine, SessionLocal, Base
from app.models.models import SystemSetting
from sqlalchemy import text

def init_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if settings already exist
        existing = db.query(SystemSetting).count()
        if existing == 0:
            print("Seeding default settings...")
            defaults = [
                SystemSetting(key="erp_sync_interval_mins", value="5", description="Master Data Sync Interval (minutes)"),
                SystemSetting(key="stock_sync_interval_mins", value="15", description="Stock Level Sync Interval (minutes)"),
                SystemSetting(key="invoice_sync_interval_secs", value="30", description="Invoice Push Interval (seconds)"),
            ]
            db.add_all(defaults)
            db.commit()
            print("Default settings seeded.")
        else:
            print(f"Database already has {existing} settings.")
    except Exception as e:
        print(f"Error seeding settings: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
