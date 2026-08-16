import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.analytics_service import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()

DaysParam = Optional[int]


def _days_query(
    days: DaysParam = Query(
        None, description="Optional lookback window in days (e.g. 7, 30, 90). Filters by created_at."
    )
) -> DaysParam:
    return days


@router.get("/analytics/summary")
async def get_analytics_summary(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        return analytics_service.get_summary(db, days=days)
    except Exception as e:
        logger.exception("Error building analytics summary: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build analytics summary.")


@router.get("/analytics/departments")
async def get_analytics_departments(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return analytics_service.get_department_breakdown(db, days=days)
    except Exception as e:
        logger.exception("Error building department breakdown: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build department breakdown.")


@router.get("/analytics/categories")
async def get_analytics_categories(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return analytics_service.get_category_breakdown(db, days=days)
    except Exception as e:
        logger.exception("Error building category breakdown: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build category breakdown.")


@router.get("/analytics/priorities")
async def get_analytics_priorities(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return analytics_service.get_priority_breakdown(db, days=days)
    except Exception as e:
        logger.exception("Error building priority breakdown: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build priority breakdown.")


@router.get("/analytics/status")
async def get_analytics_status(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> Dict[str, int]:
    try:
        return analytics_service.get_status_breakdown(db, days=days)
    except Exception as e:
        logger.exception("Error building status breakdown: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build status breakdown.")


@router.get("/analytics/duplicates")
async def get_analytics_duplicates(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        return analytics_service.get_duplicate_stats(db, days=days)
    except Exception as e:
        logger.exception("Error building duplicate statistics: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build duplicate statistics.")


@router.get("/analytics/sla")
async def get_analytics_sla(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        return analytics_service.get_sla_stats(db, days=days)
    except Exception as e:
        logger.exception("Error building SLA statistics: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build SLA statistics.")


@router.get("/analytics/locations")
async def get_analytics_locations(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return analytics_service.get_location_breakdown(db, days=days)
    except Exception as e:
        logger.exception("Error building location breakdown: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build location breakdown.")


@router.get("/analytics/top-issues")
async def get_analytics_top_issues(
    days: DaysParam = Depends(_days_query), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    try:
        return analytics_service.get_top_issues(db, days=days)
    except Exception as e:
        logger.exception("Error building top issues: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to build top issues.")
