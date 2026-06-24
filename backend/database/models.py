from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base

class ChecksheetTemplate(Base):
    __tablename__ = "checksheet_templates"

    id              = Column(Integer, primary_key=True, index=True)
    template_name   = Column(String, nullable=False)
    form_ref        = Column(String)
    org_name        = Column(String)
    checksheet_type = Column(String, nullable=False)
    created_at      = Column(DateTime, server_default=func.now())

    check_items = relationship("CheckItem", back_populates="template")
    sessions    = relationship("InspectionSession", back_populates="template")


class CheckItem(Base):
    __tablename__ = "check_items"

    id             = Column(Integer, primary_key=True, index=True)
    template_id    = Column(Integer, ForeignKey("checksheet_templates.id"), nullable=False)
    ref_number     = Column(Integer, nullable=False)
    parameter_name = Column(String, nullable=False)
    unit           = Column(String)
    range_standard = Column(String)
    range_min      = Column(Float)
    range_max      = Column(Float)
    range_type     = Column(String, default="between")

    template = relationship("ChecksheetTemplate", back_populates="check_items")
    results  = relationship("InspectionResult", back_populates="check_item")


class InspectionSession(Base):
    __tablename__ = "inspection_sessions"

    id              = Column(Integer, primary_key=True, index=True)
    template_id     = Column(Integer, ForeignKey("checksheet_templates.id"), nullable=False)
    vehicle_model   = Column(String)
    vin_chassis     = Column(String)
    odometer_km     = Column(String)
    instrument_name = Column(String)
    model_serial    = Column(String)
    location_dept   = Column(String)
    next_due_date   = Column(String)
    lead_technician = Column(String)
    job_card_no     = Column(String)
    inspection_date = Column(String)
    overall_status  = Column(String, default="PENDING")
    submitted_at    = Column(DateTime, server_default=func.now())

    template = relationship("ChecksheetTemplate", back_populates="sessions")
    results  = relationship("InspectionResult", back_populates="session", cascade="all, delete")


class InspectionResult(Base):
    __tablename__ = "inspection_results"

    id               = Column(Integer, primary_key=True, index=True)
    session_id       = Column(Integer, ForeignKey("inspection_sessions.id", ondelete="CASCADE"), nullable=False)
    check_item_id    = Column(Integer, ForeignKey("check_items.id"), nullable=False)
    measured_value   = Column(String)
    measured_numeric = Column(Float)
    status           = Column(String, default="PENDING")
    notes            = Column(Text)

    session    = relationship("InspectionSession", back_populates="results")
    check_item = relationship("CheckItem", back_populates="results")


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String, nullable=False)
    role       = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    timestamp  = Column(DateTime, server_default=func.now())
    status     = Column(String, default="SUCCESS")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    jti        = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)

