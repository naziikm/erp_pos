import sys
import os
sys.path.insert(0, os.getcwd())
from app.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print("Database connection OK")
except Exception as e:
    print(f"Database connection FAILED: {e}")
