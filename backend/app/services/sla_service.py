import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import Complaint

logger = logging.getLogger(__name__)

# Central SLA Configuration (hours)
SLA_DURATIONS_HOURS: Dict[str, int] = {
    "CRITICAL": 2,
    "HIGH": 8,
    "MEDIUM": 24,
    "LOW": 72,
}

# Configurable At-Risk Threshold Percentage (20% of SLA duration)
SLA_AT_RISK_PERCENT: float = 20.0


class SLAService:

    def get_sla_duration_hours(self, priority: Optional[str]) -> int:
        norm_priority = (priority or "MEDIUM").strip().upper()
        return SLA_DURATIONS_HOURS.get(norm_priority, 24)

    def calculate_sla_deadline(self, created_at: datetime, duration_hours: int) -> datetime:
        # Ensure created_at is timezone-aware in UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at + timedelta(hours=duration_hours)

    def evaluate_sla_state(
        self,
        created_at: datetime,
        sla_deadline: datetime,
        sla_duration_hours: int,
        status: str,
        was_breached: bool = False,
        escalated_at: Optional[datetime] = None,
        override_now: Optional[datetime] = None,
        previous_escalation_level: int = 0,
    ) -> Dict[str, Any]:
        # Ensure datetimes are UTC aware
        now = override_now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if sla_deadline.tzinfo is None:
            sla_deadline = sla_deadline.replace(tzinfo=timezone.utc)

        sla_duration_seconds = float(sla_duration_hours * 3600)
        at_risk_threshold_seconds = sla_duration_seconds * (SLA_AT_RISK_PERCENT / 100.0)

        remaining_seconds = (sla_deadline - now).total_seconds()
        remaining_hours = round(remaining_seconds / 3600.0, 2)

        norm_status = (status or "PENDING").strip().upper()
        is_resolved = norm_status in {"RESOLVED", "CLOSED"}

        is_currently_overdue = now > sla_deadline
        current_was_breached = was_breached or is_currently_overdue

        # Determine SLA Status
        if is_resolved:
            if current_was_breached:
                sla_status = "BREACHED"
            else:
                sla_status = "COMPLETED"
        else:
            if is_currently_overdue:
                sla_status = "BREACHED"
            elif remaining_seconds <= at_risk_threshold_seconds:
                sla_status = "AT_RISK"
            else:
                sla_status = "ACTIVE"

        # Determine Escalation Level (live, time-based)
        if not is_currently_overdue:
            live_escalation_level = 0
        else:
            overdue_seconds = (now - sla_deadline).total_seconds()
            if overdue_seconds > sla_duration_seconds:
                # Level 2: Deadline exceeded by more than another full SLA duration
                live_escalation_level = 2
            else:
                # Level 1: Deadline exceeded
                live_escalation_level = 1

        if is_resolved:
            # Once resolved/closed, freeze the escalation level at whatever it had
            # already reached instead of letting it keep climbing (or reset) as
            # real wall-clock time continues to move past the deadline.
            escalation_level = max(previous_escalation_level, live_escalation_level) if current_was_breached else 0
        else:
            escalation_level = live_escalation_level

        # Determine Escalated At timestamp
        new_escalated_at = escalated_at
        if is_currently_overdue and new_escalated_at is None:
            new_escalated_at = sla_deadline

        return {
            "sla_duration_hours": sla_duration_hours,
            "sla_deadline": sla_deadline,
            "sla_status": sla_status,
            "remaining_seconds": round(remaining_seconds, 2),
            "remaining_hours": remaining_hours,
            "escalation_level": escalation_level,
            "escalated_at": new_escalated_at,
            "was_breached": current_was_breached,
        }

    def sync_complaint_sla(self, db: Session, complaint: Complaint, override_now: Optional[datetime] = None) -> Dict[str, Any]:
        state = self.evaluate_sla_state(
            created_at=complaint.created_at,
            sla_deadline=complaint.sla_deadline,
            sla_duration_hours=complaint.sla_duration_hours,
            status=complaint.status,
            was_breached=complaint.was_breached,
            escalated_at=complaint.escalated_at,
            override_now=override_now,
            previous_escalation_level=complaint.escalation_level,
        )

        # Persist breach/escalation fields if state changed
        dirty = False
        if complaint.sla_status != state["sla_status"]:
            complaint.sla_status = state["sla_status"]
            dirty = True

        if complaint.escalation_level != state["escalation_level"]:
            complaint.escalation_level = state["escalation_level"]
            dirty = True

        if complaint.was_breached != state["was_breached"]:
            complaint.was_breached = state["was_breached"]
            dirty = True

        if complaint.escalated_at != state["escalated_at"]:
            complaint.escalated_at = state["escalated_at"]
            dirty = True

        if dirty:
            db.commit()
            db.refresh(complaint)

        return state

    def get_complaint_sla(
        self, db: Session, complaint_id: str, override_now: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        cmp_obj = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not cmp_obj:
            return None

        state = self.sync_complaint_sla(db, cmp_obj, override_now=override_now)

        tkt_id = cmp_obj.ticket.ticket_id if cmp_obj.ticket else None

        return {
            "complaint_id": cmp_obj.complaint_id,
            "ticket_id": tkt_id,
            "priority": cmp_obj.priority,
            "sla_duration_hours": cmp_obj.sla_duration_hours,
            "created_at": cmp_obj.created_at,
            "sla_deadline": cmp_obj.sla_deadline,
            "sla_status": state["sla_status"],
            "remaining_seconds": state["remaining_seconds"],
            "remaining_hours": state["remaining_hours"],
            "escalation_level": state["escalation_level"],
            "escalated_at": state["escalated_at"],
            "was_breached": state["was_breached"],
        }

    def get_sla_summary(self, db: Session, override_now: Optional[datetime] = None) -> Dict[str, int]:
        all_complaints = db.query(Complaint).all()

        active_cnt = 0
        at_risk_cnt = 0
        breached_cnt = 0
        completed_cnt = 0

        for c in all_complaints:
            state = self.sync_complaint_sla(db, c, override_now=override_now)
            st = state["sla_status"]
            if st == "ACTIVE":
                active_cnt += 1
            elif st == "AT_RISK":
                at_risk_cnt += 1
            elif st == "BREACHED":
                breached_cnt += 1
            elif st == "COMPLETED":
                completed_cnt += 1

        total_active = active_cnt + at_risk_cnt + breached_cnt

        return {
            "total_active": total_active,
            "active": active_cnt,
            "at_risk": at_risk_cnt,
            "breached": breached_cnt,
            "completed": completed_cnt,
        }

    def get_breached_complaints(
        self, db: Session, override_now: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        all_complaints = db.query(Complaint).all()
        results = []
        for c in all_complaints:
            state = self.sync_complaint_sla(db, c, override_now=override_now)
            if state["sla_status"] == "BREACHED" or state["was_breached"]:
                tkt_id = c.ticket.ticket_id if c.ticket else None
                results.append(
                    {
                        "complaint_id": c.complaint_id,
                        "ticket_id": tkt_id,
                        "department": c.department,
                        "priority": c.priority,
                        "location": c.location,
                        "status": c.status,
                        "sla_deadline": c.sla_deadline,
                        "escalation_level": state["escalation_level"],
                        "escalated_at": state["escalated_at"],
                        "was_breached": state["was_breached"],
                    }
                )

        results.sort(key=lambda x: x["escalation_level"], reverse=True)
        return results

    def get_at_risk_complaints(
        self, db: Session, override_now: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        all_complaints = db.query(Complaint).all()
        results = []
        for c in all_complaints:
            state = self.sync_complaint_sla(db, c, override_now=override_now)
            if state["sla_status"] == "AT_RISK":
                tkt_id = c.ticket.ticket_id if c.ticket else None
                results.append(
                    {
                        "complaint_id": c.complaint_id,
                        "ticket_id": tkt_id,
                        "department": c.department,
                        "priority": c.priority,
                        "location": c.location,
                        "status": c.status,
                        "sla_deadline": c.sla_deadline,
                        "remaining_hours": state["remaining_hours"],
                    }
                )

        results.sort(key=lambda x: x["remaining_hours"])
        return results

    def recalculate_all_slas(self, db: Session, override_now: Optional[datetime] = None) -> Dict[str, Any]:
        all_complaints = db.query(Complaint).all()
        recalculated_count = 0
        for c in all_complaints:
            self.sync_complaint_sla(db, c, override_now=override_now)
            recalculated_count += 1

        summary = self.get_sla_summary(db, override_now=override_now)
        return {
            "message": f"Successfully recalculated SLA states for {recalculated_count} complaints.",
            "recalculated_count": recalculated_count,
            "summary": summary,
        }


sla_service = SLAService()
