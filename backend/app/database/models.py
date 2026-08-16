from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String, unique=True, index=True, nullable=False)
    transcript = Column(Text, nullable=False)
    language = Column(String, default="en")
    category = Column(String, nullable=False)
    department = Column(String, nullable=False)
    priority = Column(String, default="MEDIUM")
    summary = Column(Text, nullable=False)
    location = Column(String, nullable=True)
    keywords = Column(Text, nullable=True)  # JSON-encoded list[str] from Module 2 analysis
    status = Column(String, default="PENDING", nullable=False)
    duplicate_status = Column(String, default="NEW", nullable=False)
    duplicate_of = Column(String, nullable=True)
    similarity_score = Column(Float, nullable=True)
    sla_duration_hours = Column(Integer, default=24, nullable=False)
    sla_deadline = Column(DateTime, nullable=False)
    sla_status = Column(String, default="ACTIVE", nullable=False)
    escalation_level = Column(Integer, default=0, nullable=False)
    escalated_at = Column(DateTime, nullable=True)
    was_breached = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    ticket = relationship("Ticket", back_populates="complaint", uselist=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(String, unique=True, index=True, nullable=False)
    complaint_id = Column(
        String, ForeignKey("complaints.complaint_id"), nullable=False
    )
    department = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    parent_ticket = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    complaint = relationship("Complaint", back_populates="ticket")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String, nullable=False)
    old_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
