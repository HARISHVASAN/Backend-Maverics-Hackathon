Citizen Call Intelligence — Backend Guide

This README is for the UI team member who needs to run the backend and connect the frontend to it.

You do not need to understand the AI implementation to use this backend.

Your job is mainly:

React UI
   ↓
Backend API
   ↓
AI + Database + Duplicate Detection + SLA
   ↓
Backend sends results back to React

1. What does the backend do?

The backend is the brain of the project.

It receives citizen complaints/audio and handles the processing.

Main flow

Citizen Voice / Audio
        ↓
   FastAPI Backend
        ↓
  Whisper Transcription
        ↓
   LLM Analysis
        ↓
Category / Department / Priority / Summary / Location / Keywords
        ↓
 ChromaDB Duplicate Detection
        ↓
 Complaint + Ticket
        ↓
     SLA Tracking
        ↓
   Analytics
        ↓
    React Dashboard

There is also a real phone-call path:

Citizen calls Twilio number
        ↓
Twilio records the call
        ↓
Backend receives recording
        ↓
Whisper
        ↓
LLM
        ↓
Duplicate Detection
        ↓
Complaint / Ticket
        ↓
Dashboard

The existing browser audio-upload path still works as a fallback.

2. What technologies are being used?

You do NOT need to install all of these manually.

The backend already contains the required Python dependencies.

Technology

Purpose

FastAPI

Backend/API

faster-whisper

Converts audio to text

LLM

Understands and structures the complaint

ChromaDB

Finds semantically similar complaints

SQLite

Stores complaints, tickets and SLA data

Twilio

Receives phone calls and records them

React

Frontend/dashboard

3. Project structure

The important structure is:

citizen-call-intelligence/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── services/
│   │
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   └── ...
│
└── frontend/
    └── React application

For UI development, you mainly need:

backend/   → run this first
frontend/  → run this second

4. What you need installed

You need:

Python 3.10+ recommended

Node.js

npm

Git

You can check them with:

python --version
node --version
npm --version
git --version

5. First-time backend setup

Open a terminal in the project root:

cd citizen-call-intelligence

Go into the backend:

cd backend

Create a Python virtual environment if one does not already exist:

python -m venv .venv

Windows

Activate it:

.venv\Scripts\activate

macOS/Linux

source .venv/bin/activate

You should see something similar to:

(.venv)

at the beginning of your terminal line.

6. Install backend dependencies

With the virtual environment activated:

pip install -r requirements.txt

You only need to do this the first time, or when requirements.txt changes.

7. Environment variables

The backend uses environment variables for configuration.

There should be:

backend/.env

Do NOT commit this file or share API keys publicly.

The example file is:

backend/.env.example

It contains the variable names without real secrets.

Important variables include the existing LLM configuration and, if Twilio is being used:

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_PUBLIC_BASE_URL=

Important

You do not need Twilio credentials to work on the React dashboard.

The normal audio-upload/API flow can still be used.

8. Start the backend

From:

citizen-call-intelligence/backend

run:

uvicorn app.main:app --reload --port 8001

If it starts correctly, you should see something similar to:

Uvicorn running on http://127.0.0.1:8001

Keep this terminal open.

Do not close it while using the frontend.

9. Check that the backend is working

Open this in your browser:

http://127.0.0.1:8001

The backend should respond.

You can also open:

http://127.0.0.1:8001/docs

This is the FastAPI Swagger UI.

It shows all available backend APIs.

If /docs opens, the backend is running.

10. Start the frontend

Open a second terminal.

Go to the frontend:

cd citizen-call-intelligence/frontend

Install frontend dependencies if this is the first time:

npm install

Then start React:

npm run dev

Vite will normally show something similar to:

http://localhost:5173

Open that URL in your browser.

11. Backend + frontend should look like this

You should have two terminals running.

Terminal 1 — Backend

backend/
uvicorn app.main:app --reload --port 8001

Running at:

http://127.0.0.1:8001

Terminal 2 — Frontend

frontend/
npm run dev

Running at:

http://localhost:5173

The frontend talks to the backend.

12. Frontend API URL

The frontend should use:

VITE_API_URL=http://127.0.0.1:8001

This should be configured in:

frontend/.env

If the backend is running on port 8001, do not change this.

If the backend is moved to another port, update the frontend .env.

After changing .env, restart the Vite server.

13. APIs your UI can use

You do not need to understand the backend code.

Just call the APIs.

Complaints

Get all complaints

GET /complaints

Example:

http://127.0.0.1:8001/complaints

Use this to populate the complaint table.

Get one complaint

GET /complaints/{complaint_id}

Example:

GET /complaints/CMP-1001

Use this when the user opens complaint details.

Change complaint status

PATCH /complaints/{complaint_id}/status

Use this when the officer changes:

PENDING
ASSIGNED
IN_PROGRESS
RESOLVED
CLOSED

The backend decides whether the status transition is valid.

The frontend should not create its own status logic.

14. SLA APIs

Get SLA information for one complaint

GET /complaints/{complaint_id}/sla

This gives information such as:

priority
sla_duration_hours
sla_deadline
sla_status
remaining_seconds
remaining_hours
escalation_level
was_breached

Use this to display the SLA panel.

Get complaints that are at risk

GET /sla/at-risk

Get breached complaints

GET /sla/breached

Get SLA summary

GET /sla/summary

Use this for dashboard SLA statistics.

15. Analytics APIs

The dashboard can use these APIs for charts.

GET /analytics/summary
GET /analytics/departments
GET /analytics/categories
GET /analytics/priorities
GET /analytics/status
GET /analytics/duplicates
GET /analytics/sla
GET /analytics/locations
GET /analytics/top-issues

Example:

GET /analytics/departments

can return something like:

[
  {
    "department": "Water",
    "count": 5
  },
  {
    "department": "Electricity",
    "count": 3
  }
]

The backend calculates these values.

Do not hardcode them in React.

16. Audio upload API

The existing browser audio processing endpoint is:

POST /process-and-create-ticket

This is the complete pipeline:

Audio
 ↓
Whisper
 ↓
Transcript
 ↓
LLM
 ↓
Category
Department
Priority
Summary
Location
Keywords
 ↓
Duplicate Detection
 ↓
Complaint
 ↓
Ticket
 ↓
SLA

If your UI has an audio-record/upload button, this is the endpoint to connect it to.

17. Twilio phone-call API

Twilio has two backend endpoints:

POST /twilio/voice
POST /twilio/recording

You normally do not call these from React.

They are used by Twilio.

The flow is:

Phone call
    ↓
Twilio
    ↓
POST /twilio/voice
    ↓
Twilio records call
    ↓
POST /twilio/recording
    ↓
Backend processes recording

So:

React does NOT need to implement Twilio recording.

The backend handles it.

18. Duplicate detection

The backend uses ChromaDB to compare a new complaint with existing complaints.

For example:

Complaint 1:
"No water supply in Anna Nagar for two days."

Complaint 2:
"Anna Nagar has had no water for the past two days."

The system can identify them as semantically similar.

The frontend only needs to display the result.

Do not implement duplicate detection inside React.

19. Multilingual audio

The transcription system supports multilingual audio through the existing Whisper pipeline.

For example:

Tamil audio
   ↓
Whisper
   ↓
Tamil transcript
   ↓
LLM analysis
   ↓
Complaint

The frontend does not need to translate the audio itself.

Just send the audio to the backend.

20. What YOU should do in the frontend

Your main responsibility is the UI.

You should:

Display

complaints

transcript

summary

category

department

priority

location

language

keywords

duplicate information

SLA status

escalation level

analytics

Allow the officer to

search complaints

filter complaints

open complaint details

update complaint status

view SLA alerts

view analytics

optionally upload/record audio

21. What you should NOT implement in React

Do NOT duplicate backend logic.

Do not calculate:

priority
department
duplicate similarity
SLA deadline
escalation level
analytics counts

The backend is the source of truth.

React should:

REQUEST → RECEIVE → DISPLAY

22. If something doesn't work

Frontend says "Unable to connect"

First check:

http://127.0.0.1:8001

If that doesn't open:

Backend is not running.

Start it:

cd backend
uvicorn app.main:app --reload --port 8001

/docs doesn't open

Check the backend terminal.

Look for an error.

Make sure you are inside:

backend/

and run:

uvicorn app.main:app --reload --port 8001

Frontend is running but API calls fail

Check:

frontend/.env

It should contain:

VITE_API_URL=http://127.0.0.1:8001

Then restart:

npm run dev

Port 8001 is already in use

This usually means another backend is already running.

You can either use the existing server or stop it before starting another one.

Do not start five copies of the backend.

23. Simple daily workflow

Every time you start working:

Terminal 1

cd citizen-call-intelligence/backend

Activate the virtual environment if necessary:

.venv\Scripts\activate

Start backend:

uvicorn app.main:app --reload --port 8001

Terminal 2

cd citizen-call-intelligence/frontend
npm run dev

Then open:

http://localhost:5173

That's it.

24. How to test your UI without making phone calls

You do NOT need a Twilio phone call every time.

Use:

POST /process-and-create-ticket

with an audio file.

This lets you test:

Audio
→ Whisper
→ AI
→ Duplicate Detection
→ Complaint
→ Ticket
→ SLA
→ Dashboard

Twilio is an additional real-world input method.

25. Important rule for integration

The backend is already working and tested.

When integrating your UI:

Do not change backend logic unless absolutely necessary.

If your UI needs a value:

Check /docs.

Check the API response.

Use the existing field.

Only ask for a backend change if the required data genuinely isn't available.

Do not create fake frontend data to make the dashboard look populated.

26. Complete system

The final system is:

                    CITIZEN
                       │
              ┌────────┴────────┐
              │                 │
          Browser Audio      Phone Call
              │                 │
              │               Twilio
              │                 │
              └────────┬────────┘
                       ↓
                  FASTAPI
                       ↓
                faster-whisper
                       ↓
                  Transcript
                       ↓
                     LLM
                       ↓
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
   Department       Priority        Summary
       ↓               ↓               ↓
       └───────────────┼───────────────┘
                       ↓
                 ChromaDB
                       ↓
             Duplicate Detection
                       ↓
               Complaint + Ticket
                       ↓
                 SLA / Escalation
                       ↓
                  Analytics
                       ↓
                 React Dashboard

27. The most important thing to remember

You don't need to understand the entire backend.

Think of it as a service:

YOUR UI
   ↓
HTTP API
   ↓
BACKEND DOES THE HARD WORK
   ↓
JSON RESPONSE
   ↓
YOUR UI DISPLAYS IT

If you can run:

Backend → port 8001
Frontend → port 5173

and the frontend can call the APIs above, you can integrate the UI.

28. Backend completion status

The following backend modules are already completed and tested:

Module 1 — Audio / transcription       ✅
Module 2 — AI analysis                 ✅
Module 3 — Duplicate detection         ✅
Module 4 — Complaint / ticket system   ✅
Module 5 — SLA / escalation            ✅
Module 6 — Analytics                   ✅
Module 7 — Dashboard/API integration  ✅
Module 8A — Twilio call input          ✅

The backend is feature-complete for the MVP.

The remaining work for the UI team is primarily:

Integrate UI
     ↓
Connect existing API endpoints
     ↓
Display real backend data
     ↓
Test end-to-end
     ↓
Final demo

29. Quick reference

Need

API

All complaints

GET /complaints

Complaint details

GET /complaints/{id}

Change status

PATCH /complaints/{id}/status

Process audio

POST /process-and-create-ticket

Complaint SLA

GET /complaints/{id}/sla

SLA summary

GET /sla/summary

At-risk complaints

GET /sla/at-risk

Breached complaints

GET /sla/breached

Analytics summary

GET /analytics/summary

Department chart

GET /analytics/departments

Category chart

GET /analytics/categories

Priority chart

GET /analytics/priorities

Status chart

GET /analytics/status

Duplicate statistics

GET /analytics/duplicates

SLA statistics

GET /analytics/sla

Location statistics

GET /analytics/locations

Top issues

GET /analytics/top-issues

Twilio call

POST /twilio/voice

Twilio recording

POST /twilio/recording

API documentation

GET /docs

If you get stuck

First check /docs:

http://127.0.0.1:8001/docs

Then check whether the backend terminal is running.

Do not change backend code just because the frontend is not displaying something correctly.

Ask the backend developer for clarification before changing API contracts.
