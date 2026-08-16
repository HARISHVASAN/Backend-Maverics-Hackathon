import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.sla_service import sla_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/complaints/{complaint_id}/sla")
async def get_complaint_sla(
    complaint_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    res = sla_service.get_complaint_sla(db, complaint_id)
    if not res:
        raise HTTPException(
            status_code=404, detail=f"Complaint '{complaint_id}' not found."
        )
    return res


@router.get("/sla/summary")
async def get_sla_summary(db: Session = Depends(get_db)) -> Dict[str, int]:
    try:
        return sla_service.get_sla_summary(db)
    except Exception as e:
        logger.exception("Error getting SLA summary: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch SLA summary.")


@router.get("/sla/breached")
async def get_breached_complaints(
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return sla_service.get_breached_complaints(db)
    except Exception as e:
        logger.exception("Error getting breached complaints: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch breached complaints.")


@router.get("/sla/at-risk")
async def get_at_risk_complaints(
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return sla_service.get_at_risk_complaints(db)
    except Exception as e:
        logger.exception("Error getting at-risk complaints: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch at-risk complaints.")


@router.post("/sla/recalculate")
async def recalculate_slas(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return sla_service.recalculate_all_slas(db)
    except Exception as e:
        logger.exception("Error recalculating SLAs: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to recalculate SLAs.")
