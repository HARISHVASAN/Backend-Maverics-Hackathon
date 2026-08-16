# AI-Powered Citizen Call Intelligence Platform

Pipeline: audio → Whisper transcription → LLM complaint analysis → ChromaDB
semantic duplicate detection → complaint/ticket creation with department
routing → SLA deadline + escalation tracking → React officer dashboard.

- `backend/` — FastAPI service (Whisper, LLM analysis, ChromaDB, SQLite, SLA, analytics, Twilio).
- `frontend/` — React + Vite officer dashboard.

Run the backend from `backend/` (`uvicorn app.main:app --port 8001`) and the
frontend from `frontend/` (`npm run dev`). See `backend/.env.example` for
required environment variables.

## Twilio Phone Call Input

Module 8A adds a second, real-world input path alongside the existing
browser audio upload:

```
PHONE CALL → TWILIO → RECORDING → RECORDING STATUS WEBHOOK → FASTAPI
    → DOWNLOAD RECORDING → EXISTING WHISPER/LLM/CHROMADB/COMPLAINT/SLA PIPELINE
    → REACT DASHBOARD
```

**Twilio's only job is turning a phone call into a recording.** Everything
from "download the recording" onward reuses the exact same pipeline the
browser upload already uses (`run_audio_pipeline` in
`backend/app/routes/complaints.py`) — there is no second AI pipeline, and a
complaint created from a phone call looks identical to one created from a
browser upload.

### Setup

1. **Create/configure a Twilio account** at twilio.com and buy or use a
   trial phone number with Voice capability.
2. **Obtain your phone number** from the Twilio Console (Phone Numbers →
   Manage → Active Numbers).
3. **Expose your local FastAPI server with an HTTPS tunnel** — Twilio
   cannot reach `http://127.0.0.1:8001` from the public internet:
   ```bash
   ngrok http 8001
   ```
   Copy the resulting `https://xxxx.ngrok-free.app` URL.
4. **Set environment variables** in `backend/.env` (see
   `backend/.env.example`):
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+15551234567
   TWILIO_PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
   ```
   `TWILIO_PUBLIC_BASE_URL` is used to (a) build the recording status
   callback URL Twilio calls back on, and (b) validate the Twilio request
   signature correctly when running behind a tunnel. Leaving all of these
   blank is fine — the app runs normally and the browser upload keeps
   working; only the phone-call path is unavailable.
5. **Start the backend**: `uvicorn app.main:app --host 127.0.0.1 --port 8001`
   (from `backend/`).
6. **Set the incoming voice webhook** on your Twilio phone number (Console
   → Phone Numbers → your number → Voice Configuration → "A call comes
   in") to:
   ```
   POST https://xxxx.ngrok-free.app/twilio/voice
   ```
7. The recording status callback (`POST /twilio/recording`) does **not**
   need separate configuration in the Twilio Console — `/twilio/voice`
   passes it directly to Twilio's `<Record>` verb as
   `recordingStatusCallback`, built from `TWILIO_PUBLIC_BASE_URL`.
8. **Call your Twilio number.**
9. **Speak your complaint** after the tone.
10. **Hang up** (or stay silent — the recording auto-stops after 120s).
11. Twilio POSTs the recording status to `/twilio/recording`; once
    `RecordingStatus=completed`, the backend downloads the recording and
    runs it through the existing Whisper → LLM → ChromaDB → complaint →
    SLA pipeline (usually a few seconds).
12. **Open the dashboard** — the new complaint appears exactly like any
    other, with real transcript, AI analysis, duplicate status, and an SLA
    deadline already assigned.

### If Twilio fails during a demo

The browser audio upload (`POST /process-and-create-ticket`, used by the
existing upload UI) is completely independent of Twilio and keeps working
regardless of Twilio/ngrok/network state — use it as a fallback.

### What Twilio does NOT do here

No real-time transcription, no WebRTC, no Media Streams, no conversational
AI/IVR, no outbound calling, no call transfer, no call-center queues. Twilio
answers the call, plays a short message, records the caller, and tells the
backend when the recording is ready — nothing else.
