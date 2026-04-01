from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date, time
from decimal import Decimal


# ─── License Schemas ─────────────────────────────────────────────────────────


class LicenseActivateRequest(BaseModel):
    machine_id: str
    activation_key: str


class LicenseActivateResponse(BaseModel):
    token: str
    expires_at: datetime
    features: Optional[dict] = None


class LicenseStatusResponse(BaseModel):
    is_valid: bool
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    features: Optional[dict] = None


# ─── Auth Schemas ────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    full_name: str
    role_profile: Optional[str] = None


class TokenData(BaseModel):
    user_id: int
    machine_id: Optional[str] = None


# ─── Session Schemas ─────────────────────────────────────────────────────────


class SessionInfo(BaseModel):
    opening_entry_name: str
    pos_profile_name: str
    warehouse: str
    cashier_name: str
    period_start_date: Optional[datetime] = None
    allowed_modes_of_payment: Optional[list] = None
    default_price_list: Optional[str] = None
    validate_stock: bool = False
    printer_type: Optional[str] = None


class SessionStatusResponse(BaseModel):
    has_session: bool
    session: Optional[SessionInfo] = None


class SessionCloseRequest(BaseModel):
    actual_closing_balance: Optional[dict] = None
    force_close: bool = False


# ─── Sync Schemas ────────────────────────────────────────────────────────────


class SyncStatusItem(BaseModel):
    table_name: str
    last_synced_at: Optional[datetime] = None
    total_records: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class SyncStatusResponse(BaseModel):
    tables: list[SyncStatusItem]


class InvoiceQueueResponse(BaseModel):
    pending: int
    synced: int
    failed: int


# ─── Billing Schemas ─────────────────────────────────────────────────────────


class ItemResponse(BaseModel):
    id: int
    item_code: str
    item_name: Optional[str] = None
    item_group: Optional[str] = None
    uom: Optional[str] = None
    barcode: Optional[str] = None
    rate: Optional[Decimal] = None
    actual_qty: Optional[Decimal] = None
    projected_qty: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class CustomerResponse(BaseModel):
    id: int
    name: str
    customer_name: Optional[str] = None
    customer_group: Optional[str] = None

    model_config = {"from_attributes": True}


class InvoiceItemCreate(BaseModel):
    item_id: int
    item_code: str
    item_name: str
    qty: Decimal = Field(gt=0)
    rate: Decimal = Field(ge=0)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    amount: Decimal


class PaymentCreate(BaseModel):
    mode_of_payment_id: int
    amount: Decimal = Field(gt=0)
    reference_number: Optional[str] = None


class InvoiceCreateRequest(BaseModel):
    transaction_id: str = Field(max_length=36)
    customer_id: Optional[int] = None
    items: list[InvoiceItemCreate] = Field(min_length=1)
    payments: list[PaymentCreate] = Field(min_length=1)
    net_total: Decimal
    total_discount: Decimal = Decimal("0")
    grand_total: Decimal


class InvoiceItemResponse(BaseModel):
    id: int
    item_code: str
    item_name: Optional[str] = None
    qty: Decimal
    rate: Decimal
    amount: Decimal

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: int
    mode_of_payment_id: int
    amount: Decimal
    reference_number: Optional[str] = None

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: int
    transaction_id: str
    invoice_number: Optional[str] = None
    customer_id: Optional[int] = None
    posting_date: Optional[date] = None
    posting_time: Optional[time] = None
    status: Optional[str] = None
    net_total: Optional[Decimal] = None
    total_discount: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None
    is_complete: bool = False
    items: list[InvoiceItemResponse] = []
    payments: list[PaymentResponse] = []

    model_config = {"from_attributes": True}


# ─── Report Schemas ──────────────────────────────────────────────────────────


class DaySummaryResponse(BaseModel):
    total_invoices: int
    total_sales: Decimal
    total_discount: Decimal
    payments_by_mode: dict[str, Decimal]
    unsynced_count: int
    failed_count: int


class InvoiceFilter(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[str] = None
    customer_id: Optional[int] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20


class ErrorLogResponse(BaseModel):
    id: int
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    severity: Optional[str] = None
    invoice_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClosingSummaryPaymentMode(BaseModel):
    mode_name: str
    expected_amount: Decimal


class ClosingSummaryResponse(BaseModel):
    total_invoices: int
    total_sales: Decimal
    payments_by_mode: list[ClosingSummaryPaymentMode]
    unsynced_count: int
    failed_count: int


# ─── Health ──────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    db: str
    erp: str
    pending_invoices: int


# ─── Generic ─────────────────────────────────────────────────────────────────


class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None
