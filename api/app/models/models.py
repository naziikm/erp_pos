from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Time,
    Numeric, Text, Enum, JSON, ForeignKey, UniqueConstraint, Index
)
from datetime import datetime
from sqlalchemy.orm import relationship
from app.database import Base


# ─── ERP Mirror Tables ───────────────────────────────────────────────────────


class ERPRoleProfile(Base):
    __tablename__ = "erp_role_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    permissions = Column(JSON)
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    users = relationship("ERPUser", back_populates="role_profile")


class ERPUser(Base):
    __tablename__ = "erp_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(140), unique=True)
    email = Column(String(255))
    full_name = Column(String(255))
    role_profile_id = Column(Integer, ForeignKey("erp_role_profile.id", ondelete="RESTRICT"))
    hashed_password = Column(String(255))
    is_active = Column(Boolean)
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    role_profile = relationship("ERPRoleProfile", back_populates="users")
    opening_entries = relationship("ERPPosOpeningEntry", back_populates="cashier")
    invoices = relationship("PosInvoice", back_populates="cashier")


class ERPItemGroup(Base):
    __tablename__ = "erp_item_group"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    parent_item_group = Column(String(140))
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    items = relationship("ERPItem", back_populates="item_group")


class ERPItem(Base):
    __tablename__ = "erp_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_code = Column(String(140), unique=True)
    item_name = Column(String(255))
    item_group_id = Column(Integer, ForeignKey("erp_item_group.id", ondelete="RESTRICT"))
    uom = Column(String(50))
    has_serial_no = Column(Boolean)
    is_stock_item = Column(Boolean)
    barcode = Column(String(140))
    actual_qty = Column(Numeric(18, 4))
    projected_qty = Column(Numeric(18, 4))
    stock_last_updated = Column(DateTime)
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    __table_args__ = (
        Index("idx_barcode", "barcode"),
        Index("idx_item_code", "item_code"),
        Index("idx_item_group", "item_group_id"),
    )

    item_group = relationship("ERPItemGroup", back_populates="items")
    prices = relationship("ERPItemPrice", back_populates="item")
    stock_reservations = relationship("PosStockReservation", back_populates="item")


class ERPPriceList(Base):
    __tablename__ = "erp_price_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    currency = Column(String(10))
    is_buying = Column(Boolean)
    is_selling = Column(Boolean)
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    item_prices = relationship("ERPItemPrice", back_populates="price_list")
    customers = relationship("ERPCustomer", back_populates="default_price_list")
    pos_profiles = relationship("ERPPosProfile", back_populates="default_price_list")


class ERPItemPrice(Base):
    __tablename__ = "erp_item_price"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("erp_item.id", ondelete="RESTRICT"))
    price_list_id = Column(Integer, ForeignKey("erp_price_list.id", ondelete="RESTRICT"))
    rate = Column(Numeric(18, 4))
    min_qty = Column(Numeric(18, 4))
    valid_from = Column(Date)
    valid_upto = Column(Date)
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    __table_args__ = (
        Index("idx_item_price", "item_id", "price_list_id", "valid_from", "valid_upto"),
    )

    item = relationship("ERPItem", back_populates="prices")
    price_list = relationship("ERPPriceList", back_populates="item_prices")


class ERPCustomer(Base):
    __tablename__ = "erp_customer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    customer_name = Column(String(255))
    customer_group = Column(String(140))
    tax_id = Column(String(50))
    default_price_list_id = Column(Integer, ForeignKey("erp_price_list.id", ondelete="RESTRICT"))
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    default_price_list = relationship("ERPPriceList", back_populates="customers")
    invoices = relationship("PosInvoice", back_populates="customer")


class ERPModeOfPayment(Base):
    __tablename__ = "erp_mode_of_payment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    type = Column(Enum("Cash", "Bank", "General", name="mop_type_enum"))
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    payments = relationship("PosPayment", back_populates="mode_of_payment")


class ERPPosProfile(Base):
    __tablename__ = "erp_pos_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    company = Column(String(140))
    warehouse = Column(String(140))
    default_price_list_id = Column(Integer, ForeignKey("erp_price_list.id", ondelete="RESTRICT"))
    allowed_modes_of_payment = Column(JSON)
    customer_required = Column(Boolean)
    validate_stock = Column(Boolean)
    printer_type = Column(Enum("thermal", "pdf", "none", name="printer_type_enum"))
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    default_price_list = relationship("ERPPriceList", back_populates="pos_profiles")
    opening_entries = relationship("ERPPosOpeningEntry", back_populates="pos_profile")
    invoices = relationship("PosInvoice", back_populates="pos_profile")


class ERPPosOpeningEntry(Base):
    __tablename__ = "erp_pos_opening_entry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(140), unique=True)
    pos_profile_id = Column(Integer, ForeignKey("erp_pos_profile.id", ondelete="RESTRICT"))
    cashier_id = Column(Integer, ForeignKey("erp_user.id", ondelete="RESTRICT"))
    opening_balance = Column(JSON)
    period_start_date = Column(DateTime)
    status = Column(Enum("Open", "Closed", name="opening_status_enum"))
    modified = Column(DateTime)
    synced_at = Column(DateTime)

    pos_profile = relationship("ERPPosProfile", back_populates="opening_entries")
    cashier = relationship("ERPUser", back_populates="opening_entries")
    invoices = relationship("PosInvoice", back_populates="pos_opening_entry")
    invoice_sequences = relationship("PosInvoiceSequence", back_populates="pos_opening_entry")


# ─── Transaction Tables ──────────────────────────────────────────────────────


class PosInvoice(Base):
    __tablename__ = "pos_invoice"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(36), unique=True)
    invoice_number = Column(String(50))
    customer_id = Column(Integer, ForeignKey("erp_customer.id", ondelete="RESTRICT"))
    pos_opening_entry_id = Column(Integer, ForeignKey("erp_pos_opening_entry.id", ondelete="RESTRICT"))
    cashier_id = Column(Integer, ForeignKey("erp_user.id", ondelete="RESTRICT"))
    pos_profile_id = Column(Integer, ForeignKey("erp_pos_profile.id", ondelete="RESTRICT"))
    posting_date = Column(Date)
    posting_time = Column(Time)
    status = Column(Enum("draft", "submitted", "synced", "failed", name="invoice_status_enum"))
    is_complete = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    net_total = Column(Numeric(18, 4))
    total_discount = Column(Numeric(18, 4))
    grand_total = Column(Numeric(18, 4))

    __table_args__ = (
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_date", "posting_date"),
    )

    customer = relationship("ERPCustomer", back_populates="invoices")
    cashier = relationship("ERPUser", back_populates="invoices", foreign_keys=[cashier_id])
    pos_profile = relationship("ERPPosProfile", back_populates="invoices", foreign_keys=[pos_profile_id])
    pos_opening_entry = relationship("ERPPosOpeningEntry", back_populates="invoices",
                                     foreign_keys=[pos_opening_entry_id])
    items = relationship("PosInvoiceItem", back_populates="invoice")
    payments = relationship("PosPayment", back_populates="invoice")
    sync_queue = relationship("InvoiceSyncQueue", back_populates="invoice")


class PosInvoiceItem(Base):
    __tablename__ = "pos_invoice_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("pos_invoice.id", ondelete="RESTRICT"))
    item_id = Column(Integer)
    item_code = Column(String(140))
    item_name = Column(String(255))
    qty = Column(Numeric(18, 4))
    rate = Column(Numeric(18, 4))
    amount = Column(Numeric(18, 4))

    __table_args__ = (
        Index("idx_invoice_item", "invoice_id"),
    )

    invoice = relationship("PosInvoice", back_populates="items")


class PosPayment(Base):
    __tablename__ = "pos_payment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("pos_invoice.id", ondelete="RESTRICT"))
    mode_of_payment_id = Column(Integer, ForeignKey("erp_mode_of_payment.id", ondelete="RESTRICT"))
    amount = Column(Numeric(18, 4))
    reference_number = Column(String(140))

    invoice = relationship("PosInvoice", back_populates="payments")
    mode_of_payment = relationship("ERPModeOfPayment", back_populates="payments")


class PosTransactionLog(Base):
    __tablename__ = "pos_transaction_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(36))
    status = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class PosStockReservation(Base):
    __tablename__ = "pos_stock_reservation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("erp_item.id", ondelete="RESTRICT"))
    reserved_qty = Column(Numeric(18, 4))
    created_at = Column(DateTime)

    item = relationship("ERPItem", back_populates="stock_reservations")


class PosInvoiceSequence(Base):
    __tablename__ = "pos_invoice_sequence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pos_opening_entry_id = Column(Integer, ForeignKey("erp_pos_opening_entry.id", ondelete="RESTRICT"))
    last_sequence = Column(Integer)

    pos_opening_entry = relationship("ERPPosOpeningEntry", back_populates="invoice_sequences")


# ─── Infrastructure Tables ───────────────────────────────────────────────────


class InvoiceSyncQueue(Base):
    __tablename__ = "invoice_sync_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("pos_invoice.id", ondelete="RESTRICT"))
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime)
    status = Column(Enum("pending", "synced", "failed", name="sync_status_enum"))
    error_response = Column(Text)

    __table_args__ = (
        Index("idx_sync", "status", "attempts"),
    )

    invoice = relationship("PosInvoice", back_populates="sync_queue")


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), unique=True)
    last_synced_at = Column(DateTime)
    total_records = Column(Integer)
    status = Column(Enum("success", "running", "failed", name="sync_log_status_enum"))
    error_message = Column(Text)


class PosErrorLog(Base):
    __tablename__ = "pos_error_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    error_message = Column(Text)
    error_category = Column(String(100))
    severity = Column(String(50))
    invoice_id = Column(Integer)
    created_at = Column(DateTime)

    __table_args__ = (
        Index("idx_error_category", "error_category"),
        Index("idx_severity", "severity"),
        Index("idx_created_at", "created_at"),
    )


class License(Base):
    __tablename__ = "license"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(255), unique=True)
    activation_key = Column(Text)
    license_key = Column(String(500))
    expires_at = Column(DateTime)


class SystemSetting(Base):
    __tablename__ = "system_setting"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(String(255))
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
