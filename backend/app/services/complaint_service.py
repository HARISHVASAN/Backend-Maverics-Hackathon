import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import Complaint, StatusHistory, Ticket
from app.database.schemas import VALID_DEPARTMENTS, VALID_PRIORITIES, VALID_STATUSES
from app.services.department_routing import department_routing_service
from app.services.sla_service import sla_service

logger = logging.getLogger(__name__)

# Valid workflow transitions
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "PENDING": ["ASSIGNED", "CLOSED"],
    "ASSIGNED": ["IN_PROGRESS", "PENDING", "CLOSED"],
    "IN_PROGRESS": ["RESOLVED", "ASSIGNED", "CLOSED"],
    "RESOLVED": ["CLOSED", "IN_PROGRESS"],
    "CLOSED": ["IN_PROGRESS", "PENDING"],
}


class ComplaintService:

    def _parse_keywords(self, raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []

    def _generate_next_ids(self, db: Session, requested_cmp_id: Optional[str] = None) -> Tuple[str, str]:
        if requested_cmp_id and str(requested_cmp_id).strip():
            cmp_id = str(requested_cmp_id).strip()
        else:
            last_cmp = (
                db.query(Complaint.complaint_id)
                .filter(Complaint.complaint_id.like("CMP-%"))
                .order_by(Complaint.id.desc())
                .first()
            )
            next_num = 1001
            if last_cmp and last_cmp[0]:
                match = re.search(r"CMP-(\d+)", last_cmp[0])
                if match:
                    next_num = int(match.group(1)) + 1
            cmp_id = f"CMP-{next_num}"

        last_tkt = (
            db.query(Ticket.ticket_id)
            .filter(Ticket.ticket_id.like("TKT-%"))
            .order_by(Ticket.id.desc())
            .first()
        )
        tkt_num = 1001
        if last_tkt and last_tkt[0]:
            match = re.search(r"TKT-(\d+)", last_tkt[0])
            if match:
                tkt_num = int(match.group(1)) + 1
        tkt_id = f"TKT-{tkt_num}"

        return cmp_id, tkt_id

    def create_complaint(
        self,
        db: Session,
        transcript: str,
        summary: str,
        category: Optional[str] = "Other",
        department: Optional[str] = "Other",
        priority: Optional[str] = "MEDIUM",
        location: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        language: Optional[str] = "en",
        duplicate_status: Optional[str] = "NEW",
        duplicate_of: Optional[str] = None,
        similarity_score: Optional[float] = None,
        requested_complaint_id: Optional[str] = None,
        custom_created_at: Optional[datetime] = None,
    ) -> Tuple[Complaint, Ticket]:
        norm_dept = department_routing_service.normalize_department(department)
        
        norm_priority = (priority or "MEDIUM").strip().upper()
        if norm_priority not in VALID_PRIORITIES:
            norm_priority = "MEDIUM"

        dup_status = (duplicate_status or "NEW").strip().upper()
        dup_of = str(duplicate_of).strip() if duplicate_of and str(duplicate_of).strip() not in {"", "none", "null"} else None

        cmp_id, tkt_id = self._generate_next_ids(db, requested_complaint_id)

        # SLA calculation
        created_at_dt = custom_created_at or datetime.now(timezone.utc)
        if created_at_dt.tzinfo is None:
            created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)

        sla_hours = sla_service.get_sla_duration_hours(norm_priority)
        sla_deadline = sla_service.calculate_sla_deadline(created_at_dt, sla_hours)

        clean_keywords = [str(k).strip() for k in (keywords or []) if str(k).strip()]
        keywords_json = json.dumps(clean_keywords) if clean_keywords else None

        parent_ticket = None
        if dup_of:
            parent_cmp = db.query(Complaint).filter(Complaint.complaint_id == dup_of).first()
            if parent_cmp and parent_cmp.ticket:
                parent_ticket = parent_cmp.ticket.ticket_id

        new_complaint = Complaint(
            complaint_id=cmp_id,
            transcript=transcript,
            language=language or "en",
            category=category or "Other",
            department=norm_dept,
            priority=norm_priority,
            summary=summary,
            location=location,
            keywords=keywords_json,
            status="PENDING",
            duplicate_status=dup_status,
            duplicate_of=dup_of,
            similarity_score=similarity_score,
            sla_duration_hours=sla_hours,
            sla_deadline=sla_deadline,
            sla_status="ACTIVE",
            escalation_level=0,
            was_breached=False,
            created_at=created_at_dt,
            updated_at=created_at_dt,
        )
        db.add(new_complaint)
        db.flush()

        new_ticket = Ticket(
            ticket_id=tkt_id,
            complaint_id=cmp_id,
            department=norm_dept,
            priority=norm_priority,
            status="PENDING",
            parent_ticket=parent_ticket,
            created_at=created_at_dt,
            updated_at=created_at_dt,
        )
        db.add(new_ticket)

        history_entry = StatusHistory(
            complaint_id=cmp_id,
            old_status="NONE",
            new_status="PENDING",
            changed_at=created_at_dt,
        )
        db.add(history_entry)

        db.commit()
        db.refresh(new_complaint)
        db.refresh(new_ticket)

        # Sync SLA state
        sla_service.sync_complaint_sla(db, new_complaint)

        logger.info(
            "Created complaint '%s' and ticket '%s' assigned to department '%s' with SLA deadline %s.",
            cmp_id,
            tkt_id,
            norm_dept,
            sla_deadline.isoformat(),
        )
        return new_complaint, new_ticket

    def calculate_report_count(self, db: Session, complaint_id: str) -> int:
        target_cmp = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not target_cmp:
            return 1

        root_id = target_cmp.duplicate_of if target_cmp.duplicate_of else target_cmp.complaint_id

        count = (
            db.query(func.count(Complaint.id))
            .filter(
                or_(
                    Complaint.complaint_id == root_id,
                    Complaint.duplicate_of == root_id,
                )
            )
            .scalar()
        )
        return count or 1

    def get_complaint_by_id(
        self, db: Session, complaint_id: str, override_now: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        cmp_obj = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not cmp_obj:
            return None

        sla_state = sla_service.sync_complaint_sla(db, cmp_obj, override_now=override_now)
        report_count = self.calculate_report_count(db, complaint_id)

        ticket_data = None
        if cmp_obj.ticket:
            t = cmp_obj.ticket
            ticket_data = {
                "ticket_id": t.ticket_id,
                "complaint_id": t.complaint_id,
                "department": t.department,
                "priority": t.priority,
                "status": t.status,
                "parent_ticket": t.parent_ticket,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }

        return {
            "complaint_id": cmp_obj.complaint_id,
            "transcript": cmp_obj.transcript,
            "language": cmp_obj.language,
            "category": cmp_obj.category,
            "department": cmp_obj.department,
            "priority": cmp_obj.priority,
            "summary": cmp_obj.summary,
            "location": cmp_obj.location,
            "keywords": self._parse_keywords(cmp_obj.keywords),
            "status": cmp_obj.status,
            "duplicate_status": cmp_obj.duplicate_status,
            "duplicate_of": cmp_obj.duplicate_of,
            "similarity_score": cmp_obj.similarity_score,
            "report_count": report_count,
            "sla_duration_hours": cmp_obj.sla_duration_hours,
            "sla_deadline": cmp_obj.sla_deadline,
            "sla_status": sla_state["sla_status"],
            "escalation_level": sla_state["escalation_level"],
            "escalated_at": sla_state["escalated_at"],
            "was_breached": sla_state["was_breached"],
            "created_at": cmp_obj.created_at,
            "updated_at": cmp_obj.updated_at,
            "ticket": ticket_data,
        }

    def list_complaints(
        self,
        db: Session,
        department: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        location: Optional[str] = None,
        override_now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        query = db.query(Complaint)

        if department:
            norm_dept = department_routing_service.normalize_department(department)
            query = query.filter(Complaint.department == norm_dept)

        if priority:
            query = query.filter(Complaint.priority == priority.upper())

        if status:
            query = query.filter(Complaint.status == status.upper())

        if category:
            query = query.filter(Complaint.category.ilike(f"%{category}%"))

        if location:
            query = query.filter(Complaint.location.ilike(f"%{location}%"))

        complaints = query.order_by(Complaint.created_at.desc()).all()

        results = []
        for c in complaints:
            sla_state = sla_service.sync_complaint_sla(db, c, override_now=override_now)
            r_count = self.calculate_report_count(db, c.complaint_id)
            ticket_data = None
            if c.ticket:
                t = c.ticket
                ticket_data = {
                    "ticket_id": t.ticket_id,
                    "complaint_id": t.complaint_id,
                    "department": t.department,
                    "priority": t.priority,
                    "status": t.status,
                    "parent_ticket": t.parent_ticket,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }

            results.append(
                {
                    "complaint_id": c.complaint_id,
                    "transcript": c.transcript,
                    "language": c.language,
                    "category": c.category,
                    "department": c.department,
                    "priority": c.priority,
                    "summary": c.summary,
                    "location": c.location,
                    "keywords": self._parse_keywords(c.keywords),
                    "status": c.status,
                    "duplicate_status": c.duplicate_status,
                    "duplicate_of": c.duplicate_of,
                    "similarity_score": c.similarity_score,
                    "report_count": r_count,
                    "sla_duration_hours": c.sla_duration_hours,
                    "sla_deadline": c.sla_deadline,
                    "sla_status": sla_state["sla_status"],
                    "escalation_level": sla_state["escalation_level"],
                    "escalated_at": sla_state["escalated_at"],
                    "was_breached": sla_state["was_breached"],
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "ticket": ticket_data,
                }
            )

        return results

    def update_status(
        self, db: Session, complaint_id: str, new_status: str, override_now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        norm_status = new_status.strip().upper()
        if norm_status not in VALID_STATUSES:
            valid_list = ", ".join(sorted(VALID_STATUSES))
            raise ValueError(f"Invalid status '{new_status}'. Allowed statuses: {valid_list}")

        cmp_obj = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not cmp_obj:
            raise KeyError(f"Complaint '{complaint_id}' not found.")

        old_status = cmp_obj.status
        if old_status == norm_status:
            return self.get_complaint_by_id(db, complaint_id, override_now=override_now)

        allowed_next = ALLOWED_TRANSITIONS.get(old_status, [])
        if norm_status not in allowed_next:
            allowed_str = ", ".join(allowed_next)
            raise ValueError(
                f"Invalid status transition from {old_status} to {norm_status}. Allowed next statuses: [{allowed_str}]"
            )

        now = override_now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Update complaint and ticket status
        cmp_obj.status = norm_status
        cmp_obj.updated_at = now

        if cmp_obj.ticket:
            cmp_obj.ticket.status = norm_status
            cmp_obj.ticket.updated_at = now

        # Record history
        history_entry = StatusHistory(
            complaint_id=complaint_id,
            old_status=old_status,
            new_status=norm_status,
            changed_at=now,
        )
        db.add(history_entry)

        # Check breach condition during status resolution
        if norm_status in {"RESOLVED", "CLOSED"}:
            deadline = cmp_obj.sla_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            if now > deadline or cmp_obj.was_breached:
                cmp_obj.was_breached = True
                cmp_obj.sla_status = "BREACHED"
                if cmp_obj.escalated_at is None:
                    cmp_obj.escalated_at = deadline
            else:
                cmp_obj.sla_status = "COMPLETED"

        db.commit()
        db.refresh(cmp_obj)

        sla_service.sync_complaint_sla(db, cmp_obj, override_now=now)

        logger.info("Updated complaint '%s' status: %s -> %s", complaint_id, old_status, norm_status)
        return self.get_complaint_by_id(db, complaint_id, override_now=now)

    def get_status_history(self, db: Session, complaint_id: str) -> List[Dict[str, Any]]:
        records = (
            db.query(StatusHistory)
            .filter(StatusHistory.complaint_id == complaint_id)
            .order_by(StatusHistory.changed_at.asc())
            .all()
        )
        return [
            {
                "id": r.id,
                "complaint_id": r.complaint_id,
                "old_status": r.old_status,
                "new_status": r.new_status,
                "changed_at": r.changed_at,
            }
            for r in records
        ]


complaint_service = ComplaintService()
