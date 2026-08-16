import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.database.models import Complaint
from app.database.schemas import VALID_PRIORITIES, VALID_STATUSES
from app.services.sla_service import sla_service

logger = logging.getLogger(__name__)

# Fixed severity order (NOT count order) for priority breakdowns.
PRIORITY_ORDER: List[str] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Fixed workflow order for status breakdowns.
STATUS_ORDER: List[str] = ["PENDING", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]

TOP_N_DEFAULT = 10


class AnalyticsService:
    """Aggregates real statistics from the existing SQLite complaint/ticket
    database. No new storage, no ML, no forecasting -- plain SQL COUNT/GROUP BY
    over data that Modules 1-5 already persist.
    """

    def _days_cutoff(self, days: Optional[int]) -> Optional[datetime]:
        if not days or days <= 0:
            return None
        # created_at is persisted as naive-UTC (see Complaint.created_at default),
        # so the cutoff must also be naive-UTC to compare correctly.
        return datetime.utcnow() - timedelta(days=days)

    def _base_query(self, db: Session, days: Optional[int] = None) -> Query:
        query = db.query(Complaint)
        cutoff = self._days_cutoff(days)
        if cutoff is not None:
            query = query.filter(Complaint.created_at >= cutoff)
        return query

    # ------------------------------------------------------------------
    # 1. Overall summary
    # ------------------------------------------------------------------
    def get_summary(self, db: Session, days: Optional[int] = None) -> Dict[str, Any]:
        status_counts = self._status_counts(db, days)
        priority_counts = self._priority_counts(db, days)
        total = sum(status_counts.values())
        duplicate_count = self._count_by_duplicate_status(db, days).get("DUPLICATE", 0)

        sla_active_counts = self._sla_counts(db, days)

        return {
            "total_complaints": total,
            "pending": status_counts.get("PENDING", 0),
            "assigned": status_counts.get("ASSIGNED", 0),
            "in_progress": status_counts.get("IN_PROGRESS", 0),
            "resolved": status_counts.get("RESOLVED", 0),
            "closed": status_counts.get("CLOSED", 0),
            "critical": priority_counts.get("CRITICAL", 0),
            "high": priority_counts.get("HIGH", 0),
            "medium": priority_counts.get("MEDIUM", 0),
            "low": priority_counts.get("LOW", 0),
            "duplicates": duplicate_count,
            "sla_at_risk": sla_active_counts.get("at_risk", 0),
            "sla_breached": sla_active_counts.get("breached", 0),
        }

    # ------------------------------------------------------------------
    # 2. Department breakdown
    # ------------------------------------------------------------------
    def get_department_breakdown(self, db: Session, days: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self._group_count(db, Complaint.department, days)
        return [{"department": dept, "count": count} for dept, count in rows]

    # ------------------------------------------------------------------
    # 3. Category breakdown
    # ------------------------------------------------------------------
    def get_category_breakdown(self, db: Session, days: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self._group_count(db, Complaint.category, days)
        return [{"category": cat, "count": count} for cat, count in rows]

    # ------------------------------------------------------------------
    # 4. Priority breakdown (fixed severity order, zero-filled)
    # ------------------------------------------------------------------
    def get_priority_breakdown(self, db: Session, days: Optional[int] = None) -> List[Dict[str, Any]]:
        counts = self._priority_counts(db, days)
        return [{"priority": p, "count": counts.get(p, 0)} for p in PRIORITY_ORDER]

    # ------------------------------------------------------------------
    # 5. Status breakdown (fixed workflow order, zero-filled)
    # ------------------------------------------------------------------
    def get_status_breakdown(self, db: Session, days: Optional[int] = None) -> Dict[str, int]:
        counts = self._status_counts(db, days)
        return {s: counts.get(s, 0) for s in STATUS_ORDER}

    # ------------------------------------------------------------------
    # 6. Duplicate statistics
    # ------------------------------------------------------------------
    def get_duplicate_stats(self, db: Session, days: Optional[int] = None) -> Dict[str, Any]:
        counts = self._count_by_duplicate_status(db, days)
        total = sum(counts.values())
        duplicates = counts.get("DUPLICATE", 0)
        duplicate_percentage = round((duplicates / total) * 100, 2) if total > 0 else 0.0

        return {
            "total_complaints": total,
            "new": counts.get("NEW", 0),
            "related": counts.get("RELATED", 0),
            "duplicates": duplicates,
            "duplicate_percentage": duplicate_percentage,
        }

    # ------------------------------------------------------------------
    # 7. SLA statistics (reuses Module 5's sla_service -- no second SLA
    #    calculation system is created here).
    # ------------------------------------------------------------------
    def get_sla_stats(self, db: Session, days: Optional[int] = None) -> Dict[str, Any]:
        counts = self._sla_counts(db, days)
        active = counts.get("active", 0)
        at_risk = counts.get("at_risk", 0)
        breached = counts.get("breached", 0)
        completed = counts.get("completed", 0)

        denom = completed + breached
        sla_compliance_percentage = round((completed / denom) * 100, 2) if denom > 0 else 0.0

        return {
            "active": active,
            "at_risk": at_risk,
            "breached": breached,
            "completed": completed,
            "sla_compliance_percentage": sla_compliance_percentage,
        }

    # ------------------------------------------------------------------
    # 8. Location breakdown (top 10, nulls/empty ignored)
    # ------------------------------------------------------------------
    def get_location_breakdown(
        self, db: Session, days: Optional[int] = None, limit: int = TOP_N_DEFAULT
    ) -> List[Dict[str, Any]]:
        query = self._base_query(db, days).filter(
            Complaint.location.isnot(None), Complaint.location != ""
        )
        rows = (
            query.with_entities(Complaint.location, func.count(Complaint.id).label("cnt"))
            .group_by(Complaint.location)
            .order_by(func.count(Complaint.id).desc())
            .limit(limit)
            .all()
        )
        return [{"location": loc, "count": count} for loc, count in rows]

    # ------------------------------------------------------------------
    # 9. Top issues (top 10 categories by complaint count)
    # ------------------------------------------------------------------
    def get_top_issues(
        self, db: Session, days: Optional[int] = None, limit: int = TOP_N_DEFAULT
    ) -> List[Dict[str, Any]]:
        rows = self._group_count(db, Complaint.category, days, limit=limit)
        return [{"category": cat, "count": count} for cat, count in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _group_count(
        self, db: Session, column, days: Optional[int], limit: Optional[int] = None
    ):
        query = (
            self._base_query(db, days)
            .with_entities(column, func.count(Complaint.id).label("cnt"))
            .group_by(column)
            .order_by(func.count(Complaint.id).desc())
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def _status_counts(self, db: Session, days: Optional[int]) -> Dict[str, int]:
        rows = self._group_count(db, Complaint.status, days)
        return {status: count for status, count in rows if status in VALID_STATUSES}

    def _priority_counts(self, db: Session, days: Optional[int]) -> Dict[str, int]:
        rows = self._group_count(db, Complaint.priority, days)
        return {priority: count for priority, count in rows if priority in VALID_PRIORITIES}

    def _count_by_duplicate_status(self, db: Session, days: Optional[int]) -> Dict[str, int]:
        rows = self._group_count(db, Complaint.duplicate_status, days)
        return {dup_status: count for dup_status, count in rows}

    def _sla_counts(self, db: Session, days: Optional[int]) -> Dict[str, int]:
        """Reuses Module 5's sla_service for the actual SLA state calculation.
        When no date filter is given, this delegates straight to
        sla_service.get_sla_summary(). When a date filter is given, it walks
        only the filtered complaints but still relies on
        sla_service.sync_complaint_sla() (the same evaluate_sla_state logic)
        for the per-complaint status -- no SLA math is duplicated here.
        """
        if days is None or days <= 0:
            summary = sla_service.get_sla_summary(db)
            return {
                "active": summary["active"],
                "at_risk": summary["at_risk"],
                "breached": summary["breached"],
                "completed": summary["completed"],
            }

        complaints = self._base_query(db, days).all()
        counts = {"active": 0, "at_risk": 0, "breached": 0, "completed": 0}
        for c in complaints:
            state = sla_service.sync_complaint_sla(db, c)
            st = state["sla_status"]
            if st == "ACTIVE":
                counts["active"] += 1
            elif st == "AT_RISK":
                counts["at_risk"] += 1
            elif st == "BREACHED":
                counts["breached"] += 1
            elif st == "COMPLETED":
                counts["completed"] += 1
        return counts


analytics_service = AnalyticsService()
