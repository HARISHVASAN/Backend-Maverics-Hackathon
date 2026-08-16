"""Module 8A tests: Twilio phone-call input.

No real Twilio call is required. Twilio's network calls (signature
validation, recording download) are mocked; everything downstream
(Whisper -> LLM -> ChromaDB -> complaint/ticket/SLA) is the REAL existing
pipeline, exercised end-to-end exactly like the browser-upload path
already is in test_api_endpoints.py.
"""

import sys
from pathlib import Path
from unittest.mock import PropertyMock, patch

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

from app.main import app
from app.services.whisper_service import whisper_service
from app.services.twilio_service import TwilioService, twilio_service

client = TestClient(app)

SAMPLE_WAV = backend_dir / "sample_test.wav"

BASE_FORM = {
    "CallSid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "From": "+15551234567",
    "To": "+15557654321",
}


def _recording_form(status="completed", recording_sid="RExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", url="https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx"):
    form = dict(BASE_FORM)
    form["RecordingSid"] = recording_sid
    form["RecordingStatus"] = status
    form["RecordingDuration"] = "12"
    if url is not None:
        form["RecordingUrl"] = url
    return form


def _total_complaints() -> int:
    resp = client.get("/analytics/summary")
    resp.raise_for_status()
    return resp.json()["total_complaints"]


def run_tests():
    print("==================================================")
    print("STARTING MODULE 8A UNIT & INTEGRATION TESTS")
    print("==================================================")

    if not SAMPLE_WAV.exists():
        raise RuntimeError(f"Missing fixture audio file: {SAMPLE_WAV}")

    # --------------------------------------------------------------
    # TEST 1: /twilio/voice returns valid TwiML
    # --------------------------------------------------------------
    print("\n--- [TEST 1] /twilio/voice RETURNS VALID TWIML ---")
    with patch.object(twilio_service, "validate_signature", return_value=True):
        resp = client.post("/twilio/voice", data=BASE_FORM)
    print("Status:", resp.status_code, "| Content-Type:", resp.headers.get("content-type"))
    print(resp.text)
    assert resp.status_code == 200
    assert "xml" in resp.headers.get("content-type", "")
    assert "<Response>" in resp.text
    assert "<Say>" in resp.text
    assert "<Record" in resp.text
    assert "recordingStatusCallback" in resp.text or "RecordingStatusCallback" in resp.text or "twilio/recording" in resp.text
    print("[OK] TEST 1 PASSED: /twilio/voice returns valid TwiML with Say + Record.")

    # --------------------------------------------------------------
    # TEST 2: recording callback ignores incomplete recordings
    # --------------------------------------------------------------
    print("\n--- [TEST 2] RECORDING CALLBACK IGNORES INCOMPLETE RECORDINGS ---")
    before = _total_complaints()
    with patch.object(twilio_service, "validate_signature", return_value=True), \
         patch.object(twilio_service, "download_recording") as mock_download:
        resp = client.post("/twilio/recording", data=_recording_form(status="in-progress"))
    print("Status:", resp.status_code, "Body:", resp.json())
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] is False
    mock_download.assert_not_called()
    after = _total_complaints()
    assert after == before, "No complaint should be created for an incomplete recording."
    print("[OK] TEST 2 PASSED: in-progress/failed recordings are acknowledged and ignored.")

    # --------------------------------------------------------------
    # TEST 3: missing RecordingUrl is handled
    # --------------------------------------------------------------
    print("\n--- [TEST 3] MISSING RecordingUrl IS HANDLED ---")
    before = _total_complaints()
    with patch.object(twilio_service, "validate_signature", return_value=True):
        resp = client.post("/twilio/recording", data=_recording_form(status="completed", url=None))
    print("Status:", resp.status_code, "Body:", resp.text)
    assert resp.status_code == 400
    after = _total_complaints()
    assert after == before
    print("[OK] TEST 3 PASSED: missing RecordingUrl returns 400, no complaint created.")

    # --------------------------------------------------------------
    # TEST 4: Twilio recording download failure is handled
    # --------------------------------------------------------------
    print("\n--- [TEST 4] TWILIO RECORDING DOWNLOAD FAILURE IS HANDLED ---")
    before = _total_complaints()
    with patch.object(twilio_service, "validate_signature", return_value=True), \
         patch.object(twilio_service, "download_recording", side_effect=RuntimeError("simulated network failure")):
        resp = client.post("/twilio/recording", data=_recording_form(status="completed"))
    print("Status:", resp.status_code, "Body:", resp.text)
    assert resp.status_code == 502
    after = _total_complaints()
    assert after == before, "A failed download must not create a complaint."
    print("[OK] TEST 4 PASSED: download failure returns 502, server does not crash, no orphan complaint.")

    # --------------------------------------------------------------
    # TEST 5: completed recording is accepted and reaches the EXISTING
    # audio pipeline (real Whisper + LLM + ChromaDB + complaint creation).
    # --------------------------------------------------------------
    print("\n--- [TEST 5] COMPLETED RECORDING REACHES THE EXISTING AUDIO PIPELINE ---")
    before = _total_complaints()
    real_bytes = SAMPLE_WAV.read_bytes()

    with patch.object(twilio_service, "validate_signature", return_value=True), \
         patch.object(twilio_service, "download_recording", return_value=real_bytes) as mock_download, \
         patch.object(whisper_service, "transcribe", wraps=whisper_service.transcribe) as spy_transcribe:
        resp = client.post(
            "/twilio/recording",
            data=_recording_form(status="completed", recording_sid="RE_MODULE8_TEST"),
        )
    print("Status:", resp.status_code, "Body:", resp.json())
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] is True
    complaint_id = body["complaint_id"]
    assert complaint_id

    # download_recording was actually invoked with the RecordingUrl from the callback
    mock_download.assert_called_once()
    called_url = mock_download.call_args.args[0] if mock_download.call_args.args else mock_download.call_args.kwargs.get("recording_url")
    assert called_url == _recording_form()["RecordingUrl"]

    # Whisper (the EXISTING transcription service) was actually called on the downloaded audio
    spy_transcribe.assert_called_once()

    # The resulting complaint looks exactly like one created via the browser-upload path:
    # real category/department/priority/SLA fields, not fake data.
    detail_resp = client.get(f"/complaints/{complaint_id}")
    assert detail_resp.status_code == 200
    complaint = detail_resp.json()
    print("Created complaint:", complaint)
    assert complaint["complaint_id"] == complaint_id
    assert complaint["status"] == "PENDING"
    assert complaint["department"]
    assert complaint["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert complaint["sla_deadline"] is not None
    assert complaint["sla_duration_hours"] > 0
    assert complaint["ticket"] is not None

    after = _total_complaints()
    assert after == before + 1
    print("[OK] TEST 5 PASSED: completed recording flows through the real existing pipeline end-to-end.")

    # --------------------------------------------------------------
    # TEST 6: Twilio signature validation actually rejects bad signatures
    # --------------------------------------------------------------
    print("\n--- [TEST 6] INVALID TWILIO SIGNATURE IS REJECTED ---")
    with patch.object(TwilioService, "auth_token", new_callable=PropertyMock) as mock_auth_token:
        mock_auth_token.return_value = "fake_token_for_test"
        # auth_token configured (non-empty) + validate_signature forced False -> must reject
        with patch.object(twilio_service, "validate_signature", return_value=False):
            resp = client.post("/twilio/voice", data=BASE_FORM, headers={"X-Twilio-Signature": "bogus"})
    print("Status:", resp.status_code)
    assert resp.status_code == 403
    print("[OK] TEST 6 PASSED: requests with an invalid Twilio signature are rejected (403).")

    print("\n==================================================")
    print("ALL MODULE 8A UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
