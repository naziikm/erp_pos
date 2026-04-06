from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import SystemSetting
from app.dependencies.auth_deps import get_current_user
from app.dependencies.license_deps import require_valid_license
from app.models.models import ERPUser
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/settings", tags=["Settings"])

class SystemSettingSchema(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SettingUpdate(BaseModel):
    value: str

@router.get("/", response_model=List[SystemSettingSchema])
def get_settings(
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Retrieve all system settings."""
    return db.query(SystemSetting).all()

@router.patch("/{key}", response_model=SystemSettingSchema)
def update_setting(
    key: str,
    update: SettingUpdate,
    current_user: ERPUser = Depends(get_current_user),
    license_payload: dict = Depends(require_valid_license),
    db: Session = Depends(get_db),
):
    """Update a system setting and reschedule jobs if needed."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        # If it doesn't exist, create it if it's a known key
        # For simplicity, we just create it
        setting = SystemSetting(key=key, value=update.value)
        db.add(setting)
    else:
        setting.value = update.value
    
    db.commit()
    db.refresh(setting)

    # If the key is a sync interval, we should trigger a scheduler refresh
    if key in ("erp_sync_interval_mins", "stock_sync_interval_mins", "invoice_sync_interval_secs"):
        from app.scheduler import reload_scheduler_settings
        reload_scheduler_settings()

    return setting
