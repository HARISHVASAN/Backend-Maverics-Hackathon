"""Module 8A: PHONE CALL -> TWILIO -> RECORDING -> existing audio pipeline.

Twilio is responsible for exactly two things here: answering the call and
handing back a completed recording. Everything from "download the
recording" onward reuses the EXISTING pipeline (run_audio_pipeline in
routes/complaints.py) -- the same one the browser-upload endpoint uses.
No second Whisper/LLM/duplicate-detection pipeline is created here.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.routes.complaints import UPLOAD_DIR, run_audio_pipeline
from app.services.twilio_service import twilio_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _public_base_url(request: Request) -> str:
    """The base URL Twilio can actually reach. Behind a local tunnel
    (ngrok etc.) the app's own idea of its host is wrong, so an explicit
    override is preferred; otherwise fall back to forwarded headers (which
    ngrok sets) and finally to the request's own URL."""
    override = os.getenv("TWILIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if override:
        return override
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


def _signing_url(request: Request) -> str:
    """URL used for Twilio signature validation -- must match what Twilio
    itself signed, i.e. the public URL of this exact webhook."""
    override = os.getenv("TWILIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if override:
        return f"{override}{request.url.path}"
    return str(request.url)


async def _read_form_params(request: Request) -> Dict[str, str]:
    form = await request.form()
    return {k: str(v) for k, v in form.items()}


def _verify_twilio_request(request: Request, params: Dict[str, str]) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    if not twilio_service.auth_token:
        logger.warning(
            "Twilio signature validation SKIPPED (TWILIO_AUTH_TOKEN not configured) -- "
            "do not use this mode in production."
        )
        return

    signing_url = _signing_url(request)
    if not twilio_service.validate_signature(signing_url, params, signature):
        logger.warning("Rejected Twilio webhook: signature validation failed.")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")


@router.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    """Answers an incoming call and starts recording. This is the ONLY
    voice behavior implemented -- no IVR, no menus, no live conversation."""
    try:
        params = await _read_form_params(request)
    except Exception:
        logger.exception("Failed to parse /twilio/voice webhook payload.")
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    _verify_twilio_request(request, params)

    call_sid = params.get("CallSid", "unknown")
    logger.info("Incoming Twilio call: CallSid=%s", call_sid)

    recording_callback_url = f"{_public_base_url(request)}/twilio/recording"
    twiml = twilio_service.build_voice_twiml(recording_callback_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/recording")
async def twilio_recording(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Recording status callback. Only acts once RecordingStatus=='completed';
    every other status (in-progress, failed, absent) is acknowledged and
    ignored -- Twilio does not expect TwiML back from this endpoint."""
    try:
        params = await _read_form_params(request)
    except Exception:
        logger.exception("Failed to parse /twilio/recording webhook payload.")
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    _verify_twilio_request(request, params)

    call_sid = params.get("CallSid")
    recording_sid = params.get("RecordingSid")
    recording_status = params.get("RecordingStatus")
    recording_url = params.get("RecordingUrl")

    logger.info(
        "Twilio recording callback: CallSid=%s RecordingSid=%s status=%s",
        call_sid,
        recording_sid,
        recording_status,
    )

    if recording_status != "completed":
        logger.info("Ignoring Twilio recording with status=%s (not yet available).", recording_status)
        return {"received": True, "processed": False, "reason": f"status={recording_status}"}

    if not recording_url:
        logger.error("Twilio 'completed' callback missing RecordingUrl (CallSid=%s).", call_sid)
        raise HTTPException(status_code=400, detail="Missing RecordingUrl.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"twilio_{recording_sid or uuid.uuid4().hex}.wav"

    try:
        try:
            audio_bytes = await asyncio.to_thread(twilio_service.download_recording, recording_url)
        except Exception:
            logger.exception("Failed to download Twilio recording (RecordingSid=%s).", recording_sid)
            raise HTTPException(status_code=502, detail="Failed to download Twilio recording.")

        if not audio_bytes:
            logger.error("Downloaded Twilio recording is empty (RecordingSid=%s).", recording_sid)
            raise HTTPException(status_code=422, detail="Downloaded recording is empty.")

        file_path.write_bytes(audio_bytes)

        # >>> The existing audio pipeline. Same function the browser-upload
        # endpoint calls -- Whisper -> LLM analysis -> duplicate detection ->
        # complaint/ticket creation -> department routing -> SLA. <<<
        try:
            pipeline_result = await run_audio_pipeline(
                str(file_path), db, call_sid=call_sid, recording_sid=recording_sid
            )
        except ValueError as ve:
            logger.exception("Twilio pipeline validation error (RecordingSid=%s).", recording_sid)
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception:
            logger.exception("Twilio audio pipeline failed (RecordingSid=%s).", recording_sid)
            raise HTTPException(status_code=500, detail="Failed to process Twilio recording.")

        complaint_id = pipeline_result["full_complaint"]["complaint_id"]
        logger.info(
            "Twilio call processed into complaint %s (CallSid=%s, RecordingSid=%s).",
            complaint_id,
            call_sid,
            recording_sid,
        )
        return {"received": True, "processed": True, "complaint_id": complaint_id}

    except HTTPException:
        raise
    finally:
        if file_path.exists():
            file_path.unlink()
