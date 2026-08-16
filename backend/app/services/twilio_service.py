"""Twilio integration for Module 8A: PHONE CALL -> RECORDING only.

Twilio's job stops at "here is a recording". Everything after that
(transcription, AI analysis, duplicate detection, ticketing, SLA) is the
EXISTING pipeline in routes/complaints.py's run_audio_pipeline() -- this
module never touches Whisper/LLM/ChromaDB/complaint logic.
"""

import logging
import os
from typing import Dict, Optional

import requests
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)

RECORDING_GREETING = (
    "Your call may be recorded for complaint processing. "
    "Please describe your issue after the tone."
)
RECORDING_CLOSING = "Thank you. Your complaint has been recorded. Goodbye."

MAX_RECORDING_SECONDS = 120


class TwilioService:
    """Thin wrapper around the Twilio SDK. Holds no state beyond reading
    env vars lazily, so it's safe to import even when Twilio isn't
    configured at all (browser upload keeps working either way)."""

    @property
    def account_sid(self) -> str:
        return os.getenv("TWILIO_ACCOUNT_SID", "")

    @property
    def auth_token(self) -> str:
        return os.getenv("TWILIO_AUTH_TOKEN", "")

    @property
    def phone_number(self) -> str:
        return os.getenv("TWILIO_PHONE_NUMBER", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def build_voice_twiml(self, recording_status_callback_url: str) -> str:
        """Answer the call, warn about recording, and record the citizen's
        complaint. This is the ENTIRE Twilio-side behavior -- no IVR menus,
        no Media Streams, no conversational logic."""
        response = VoiceResponse()
        response.say(RECORDING_GREETING)
        response.record(
            recording_status_callback=recording_status_callback_url,
            recording_status_callback_event="completed",
            recording_status_callback_method="POST",
            max_length=MAX_RECORDING_SECONDS,
            play_beep=True,
            trim="trim-silence",
        )
        response.say(RECORDING_CLOSING)
        response.hangup()
        return str(response)

    def validate_signature(self, url: str, params: Dict[str, str], signature: Optional[str]) -> bool:
        """Validate an inbound webhook actually came from Twilio using the
        account's auth token (HMAC-SHA1 over the URL + sorted params, per
        Twilio's request-signing scheme). If no auth token is configured
        (local dev without real Twilio credentials), validation is skipped
        and this returns True -- callers must log that distinctly so it's
        never mistaken for a verified request."""
        if not self.auth_token:
            return True
        validator = RequestValidator(self.auth_token)
        return validator.validate(url, params, signature or "")

    def download_recording(self, recording_url: str, timeout: int = 30) -> bytes:
        """Download a completed recording from Twilio over HTTPS using
        Account SID / Auth Token as HTTP Basic Auth. Raises on failure --
        callers decide how to surface that as an HTTP response."""
        if not self.is_configured:
            raise RuntimeError(
                "Twilio is not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN missing)."
            )

        # Twilio's bare RecordingUrl returns an HTML page; appending an
        # extension downloads the actual audio bytes in that format.
        url = recording_url if recording_url.endswith((".wav", ".mp3")) else f"{recording_url}.wav"

        response = requests.get(url, auth=(self.account_sid, self.auth_token), timeout=timeout)
        response.raise_for_status()
        return response.content


twilio_service = TwilioService()
