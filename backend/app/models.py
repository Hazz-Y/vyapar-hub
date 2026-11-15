"""SQLModel tables. Money is stored as integer rupees."""
from datetime import date
from typing import Any, Optional

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Merchant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    owner_name: str
    shop_type: str
    city: str
    language: str = "hi"
    upi_vpa: str
    cash_buffer: int
    opening_balance: int  # balance at the start of the demo day
    opening_time: str = "08:00"


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    ts: NaiveDatetime = Field(index=True)
    amount: int
    direction: str  # in / out
    payer_hash: Optional[str] = Field(default=None, index=True)
    counterparty: Optional[str] = None
    note: Optional[str] = None
    source: str  # qr / supplier_payment / udhaar_settlement


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    name: str
    contact_name: str = ""
    phone: str
    upi_vpa: str
    category: str
    gstin: Optional[str] = None


class Payable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    supplier_id: int = Field(foreign_key="supplier.id", index=True)
    amount: int
    due_date: date = Field(index=True)
    status: str = "scheduled"  # scheduled / paid / rescheduled
    original_due_date: Optional[date] = None
    invoice_no: Optional[str] = None
    gst_rate: int = 5  # percent, used for the GST export
    paid_txn_id: Optional[int] = None


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    name: str
    phone: str = ""
    payer_hash: str = Field(index=True)
    opted_in: bool = False
    language: str = "hi"


class Udhaar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    customer_id: int = Field(foreign_key="customer.id", index=True)
    amount: int
    created_at: NaiveDatetime
    due_date: date
    status: str = "open"  # open / reminded / settled
    settled_txn_id: Optional[int] = None
    note: str = ""
    reminded_at: Optional[NaiveDatetime] = None


class PendingAction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    agent: str
    # pay_supplier / reschedule_payable / send_reminder / send_winback / log_udhaar
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    readback_text: str
    status: str = "pending"  # pending / approved / rejected / executed
    created_at: NaiveDatetime
    executed_at: Optional[NaiveDatetime] = None
    result_text: Optional[str] = None


class MessageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchant.id", index=True)
    channel: str  # whatsapp / preview
    to: str
    body: str
    status: str  # sent / preview / failed / template_fallback
    created_at: NaiveDatetime
    kind: str = ""  # udhaar_reminder / winback / ...
    detail: str = ""


class Settings(SQLModel, table=True):
    merchant_id: int = Field(foreign_key="merchant.id", primary_key=True)
    autonomy_udhaar: str = "suggest"  # suggest / auto
    autonomy_growth: str = "suggest"
    autonomy_supplier: str = "suggest"  # payments always need approval regardless
    autonomy_cash: str = "suggest"  # reschedules always need approval regardless
    language: str = "hi"


class AppState(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
