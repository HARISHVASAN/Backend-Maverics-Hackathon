from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

VALID_STATUSES = {"PENDING", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"}
VALID_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_DEPARTMENTS = {
    "Water",
    "Electricity",
    "Roads",
    "Sanitation",
    "Healthcare",
    "Police",
    "Transport",
    "Municipal",
    "Disaster Management",
    "Other",
}


class ComplaintCreate(BaseModel):
    transcript: str = Field(..., description="Original transcript text")
    language: Optional[str] = Field("en", description="Transcript language")
    category: Optional[str] = Field("Other", description="Complaint category")
    department: Optional[str] = Field("Other", description="Assigned department")
    priority: Optional[str] = Field("MEDIUM", description="Complaint priority")
    summary: str = Field(..., description="Summary of the complaint")
    location: Optional[str] = Field(None, description="Location of issue")
    keywords: Optional[List[str]] = Field(None, description="AI-extracted keywords")
    duplicate_status: Optional[str] = Field(
        "NEW", description="Duplicate status (NEW, RELATED, DUPLICATE)"
    )
    duplicate_of: Optional[str] = Field(None, description="ID of original complaint if duplicate")
    similarity_score: Optional[float] = Field(None, description="Similarity score if duplicate")
    complaint_id: Optional[str] = Field(
        None, description="Optional custom complaint ID (e.g. CMP-1001)"
    )


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="New status value")


class TicketResponse(BaseModel):
    ticket_id: str
    complaint_id: str
    department: str
    priority: str
    status: str
    parent_ticket: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplaintResponse(BaseModel):
    complaint_id: str
    transcript: str
    language: str
    category: str
    department: str
    priority: str
    summary: str
    location: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    status: str
    duplicate_status: str
    duplicate_of: Optional[str] = None
    similarity_score: Optional[float] = None
    report_count: int = 1
    sla_duration_hours: int = 24
    sla_deadline: Optional[datetime] = None
    sla_status: str = "ACTIVE"
    escalation_level: int = 0
    escalated_at: Optional[datetime] = None
    was_breached: bool = False
    created_at: datetime
    updated_at: datetime
    ticket: Optional[TicketResponse] = None

    class Config:
        from_attributes = True


class StatusHistoryResponse(BaseModel):
    id: int
    complaint_id: str
    old_status: str
    new_status: str
    changed_at: datetime

    class Config:
        from_attributes = True


class ProcessAndCreateTicketResponse(BaseModel):
    complaint: Dict[str, Any]
    ticket: Dict[str, Any]
    duplicate: Dict[str, Any]


class SLAResponse(BaseModel):
    complaint_id: str
    ticket_id: Optional[str] = None
    priority: str
    sla_duration_hours: int
    created_at: datetime
    sla_deadline: datetime
    sla_status: str
    remaining_seconds: float
    remaining_hours: float
    escalation_level: int
    escalated_at: Optional[datetime] = None
    was_breached: bool = False


class SLASummaryResponse(BaseModel):
    total_active: int
    active: int
    at_risk: int
    breached: int
    completed: int


class SLABreachedItem(BaseModel):
    complaint_id: str
    ticket_id: Optional[str] = None
    department: str
    priority: str
    location: Optional[str] = None
    status: str
    sla_deadline: datetime
    escalation_level: int
    escalated_at: Optional[datetime] = None


class SLAAtRiskItem(BaseModel):
    complaint_id: str
    ticket_id: Optional[str] = None
    department: str
    priority: str
    location: Optional[str] = None
    status: str
    sla_deadline: datetime
    remaining_hours: float
