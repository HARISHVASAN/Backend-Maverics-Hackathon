import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

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


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    _validate_audio_file(file)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name
    file_path = UPLOAD_DIR / safe_filename

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        file_path.write_bytes(contents)

        result = await asyncio.to_thread(whisper_service.transcribe, str(file_path))

        return {
            "filename": safe_filename,
            "language": result["language"],
            "language_probability": result["language_probability"],
            "transcript": result["transcript"],
            "segments": result["segments"],
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Transcription failed for file: %s", file.filename)
        raise HTTPException(
            status_code=500,
            detail=(
                "Transcription failed. Please ensure the audio file is valid "
                "and try again."
            ),
        )
    finally:
        if file_path.exists():
            file_path.unlink()
