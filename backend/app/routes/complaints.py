import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import ComplaintCreate, StatusUpdateRequest
from app.services.analysis_service import analysis_service
from app.services.complaint_service import complaint_service
from app.services.department_routing import department_routing_service
from app.services.duplicate_service import duplicate_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)

router = APIRouter()

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".mp4"}


def _validate_audio_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed formats: {allowed}",
        )


@router.post("/complaints")
async def create_complaint(
    request: ComplaintCreate, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    if not request.transcript or not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is required.")

    if not request.summary or not request.summary.strip():
        raise HTTPException(status_code=400, detail="Summary is required.")

    try:
        cmp_obj, tkt_obj = complaint_service.create_complaint(
            db=db,
            transcript=request.transcript,
            summary=request.summary,
            category=request.category,
            department=request.department,
            priority=request.priority,
            location=request.location,
            keywords=request.keywords,
            language=request.language,
            duplicate_status=request.duplicate_status,
            duplicate_of=request.duplicate_of,
            similarity_score=request.similarity_score,
            requested_complaint_id=request.complaint_id,
        )
        return complaint_service.get_complaint_by_id(db, cmp_obj.complaint_id)
    except Exception as e:
        logger.exception("Error creating complaint: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create complaint: {str(e)}")


@router.get("/complaints")
async def list_complaints(
    department: Optional[str] = Query(None, description="Filter by department"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    try:
        return complaint_service.list_complaints(
            db=db,
            department=department,
            priority=priority,
            status=status,
            category=category,
            location=location,
        )
    except Exception as e:
        logger.exception("Error listing complaints: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to list complaints.")


@router.get("/complaints/{complaint_id}")
async def get_complaint(
    complaint_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    res = complaint_service.get_complaint_by_id(db, complaint_id)
    if not res:
        raise HTTPException(
            status_code=404, detail=f"Complaint '{complaint_id}' not found."
        )
    return res


@router.patch("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: str,
    request: StatusUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not request.status or not request.status.strip():
        raise HTTPException(status_code=400, detail="Status field is required.")

    try:
        updated = complaint_service.update_status(
            db=db, complaint_id=complaint_id, new_status=request.status
        )
        return updated
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error updating status for '%s': %s", complaint_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to update complaint status.")


@router.get("/departments/{department}/complaints")
async def get_department_queue(
    department: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    norm_dept = department_routing_service.normalize_department(department)
    try:
        return complaint_service.list_complaints(
            db=db, department=norm_dept, priority=priority, status=status
        )
    except Exception as e:
        logger.exception("Error querying department queue: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch department queue.")


@router.get("/complaints/{complaint_id}/history")
async def get_complaint_status_history(
    complaint_id: str, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    cmp_res = complaint_service.get_complaint_by_id(db, complaint_id)
    if not cmp_res:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")
    return complaint_service.get_status_history(db, complaint_id)


async def run_audio_pipeline(
    file_path: str,
    db: Session,
    call_sid: Optional[str] = None,
    recording_sid: Optional[str] = None,
) -> Dict[str, Any]:
    """The ONE existing audio-processing pipeline shared by every input
    source (browser upload today, Twilio phone calls in Module 8A).

    audio file -> Whisper -> LLM analysis -> duplicate detection ->
    complaint/ticket creation (which also assigns department + SLA).

    Do not duplicate this sequence elsewhere -- new input sources should
    call this function, not reimplement it.
    """
    # Step 1: STT (existing Whisper service, unchanged)
    stt_result = await asyncio.to_thread(whisper_service.transcribe, str(file_path))
    transcript = (stt_result.get("transcript") or "").strip()
    if not transcript:
        transcript = "Citizen call audio recorded."
    lang = stt_result.get("language", "en")

    # Step 2: LLM Analysis (existing analysis service, unchanged)
    analysis_result = await asyncio.to_thread(analysis_service.analyze_complaint, transcript)

    # Step 3: Semantic Duplicate Detection (existing ChromaDB service, unchanged)
    temp_cmp_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    dup_input = {
        "complaint_id": temp_cmp_id,
        "transcript": transcript,
        "category": analysis_result.get("category", "Other"),
        "department": analysis_result.get("department", "Other"),
        "priority": analysis_result.get("priority", "MEDIUM"),
        "summary": analysis_result.get("summary", transcript),
        "location": analysis_result.get("location"),
        "call_sid": call_sid or "",
        "recording_sid": recording_sid or "",
    }
    dup_result = await asyncio.to_thread(duplicate_service.check_and_store_complaint, dup_input)

    dup_status = dup_result.get("status", "NEW")
    duplicate_of = dup_result.get("duplicate_of")
    similarity = dup_result.get("similarity", 0.0)
    temp_cmp_id = dup_result.get("complaint_id")

    # Step 4: Create SQLite Complaint & Ticket Record (existing service; this
    # also assigns department routing and the SLA deadline, same as before)
    cmp_obj, _tkt_obj = complaint_service.create_complaint(
        db=db,
        transcript=transcript,
        summary=analysis_result.get("summary", transcript),
        category=analysis_result.get("category", "Other"),
        department=analysis_result.get("department", "Other"),
        priority=analysis_result.get("priority", "MEDIUM"),
        location=analysis_result.get("location"),
        keywords=analysis_result.get("keywords"),
        language=lang,
        duplicate_status=dup_status,
        duplicate_of=duplicate_of,
        similarity_score=similarity,
        requested_complaint_id=temp_cmp_id,
    )

    return {
        "full_complaint": complaint_service.get_complaint_by_id(db, cmp_obj.complaint_id),
        "dup_status": dup_status,
        "duplicate_of": duplicate_of,
        "similarity": similarity,
    }


@router.post("/process-and-create-ticket")
async def process_and_create_ticket(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    _validate_audio_file(file)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name
    file_path = UPLOAD_DIR / safe_filename

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        file_path.write_bytes(contents)

        pipeline_result = await run_audio_pipeline(str(file_path), db)
        full_complaint = pipeline_result["full_complaint"]

        return {
            "complaint": {
                "complaint_id": full_complaint["complaint_id"],
                "category": full_complaint["category"],
                "department": full_complaint["department"],
                "priority": full_complaint["priority"],
                "summary": full_complaint["summary"],
                "location": full_complaint["location"],
                "status": full_complaint["status"],
            },
            "ticket": {
                "ticket_id": full_complaint["ticket"]["ticket_id"] if full_complaint.get("ticket") else None,
                "department": full_complaint["department"],
                "priority": full_complaint["priority"],
                "status": full_complaint["status"],
            },
            "duplicate": {
                "status": pipeline_result["dup_status"],
                "duplicate_of": pipeline_result["duplicate_of"],
                "similarity": pipeline_result["similarity"],
            },
        }

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Processing complaint and creating ticket failed: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to process complaint audio and create ticket.",
        )
    finally:
        if file_path.exists():
            file_path.unlink()
