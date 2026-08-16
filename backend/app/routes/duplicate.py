import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.chroma_service import chroma_service
from app.services.duplicate_service import duplicate_service

logger = logging.getLogger(__name__)

router = APIRouter()


class DuplicateCheckRequest(BaseModel):
    complaint_id: Optional[str] = Field(
        None, description="Unique ID for complaint. Auto-generated if omitted."
    )
    transcript: str = Field(..., description="Transcript text of complaint.")
    category: Optional[str] = Field("Other", description="Complaint category.")
    department: Optional[str] = Field("Other", description="Government department.")
    priority: Optional[str] = Field("MEDIUM", description="Priority level.")
    summary: Optional[str] = Field(None, description="Concise summary in English.")
    location: Optional[str] = Field(None, description="Extracted location or null.")


@router.post("/duplicate-check")
async def duplicate_check(request: DuplicateCheckRequest) -> Dict[str, Any]:
    if not request.transcript or not request.transcript.strip():
        raise HTTPException(
            status_code=400,
            detail="Transcript is required and cannot be empty.",
        )

    complaint_id = request.complaint_id
    if not complaint_id or not complaint_id.strip():
        complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"

    data = {
        "complaint_id": complaint_id,
        "transcript": request.transcript,
        "category": request.category or "Other",
        "department": request.department or "Other",
        "priority": request.priority or "MEDIUM",
        "summary": request.summary or request.transcript,
        "location": request.location,
    }

    try:
        result = await asyncio.to_thread(
            duplicate_service.check_and_store_complaint, data
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error during duplicate check: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to perform duplicate check. Please try again later.",
        )


@router.post("/clear-complaints")
async def clear_complaints() -> Dict[str, Any]:
    """Helper endpoint to reset the ChromaDB vector database for testing/demos."""
    try:
        await asyncio.to_thread(chroma_service.clear_collection)
        return {"message": "ChromaDB collection cleared successfully."}
    except Exception as e:
        logger.exception("Error clearing collection: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to clear ChromaDB collection.")
