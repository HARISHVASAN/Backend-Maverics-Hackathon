import json
import logging
import os
import re
from typing import Any, Dict

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

ALLOWED_DEPARTMENTS = {
    "Water",
    "Electricity",
    "Roads",
    "Sanitation",
    "Healthcare",
    "Police",
    "Transport",
    "Municipal",
    "Disaster Management",
    "Other",
}

ALLOWED_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

DEPRECATED_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp",
}

SYSTEM_PROMPT = """You are an AI government citizen complaint classification system.
Your job is to analyze unstructured citizen complaint transcripts (written in English, Tamil, Hindi, Telugu, Malayalam, Kannada, or any other language) and convert them into structured JSON.

Rules:
1. Category: A descriptive English title for the complaint (e.g., "Water Supply", "Electricity Outage", "Road Damage", "Garbage Collection", "Street Lighting", "Public Safety", "Healthcare", "Public Transport", "Flooding", "Drainage", "Other").
2. Department: Must be EXACTLY one of these allowed values:
   - Water
   - Electricity
   - Roads
   - Sanitation
   - Healthcare
   - Police
   - Transport
   - Municipal
   - Disaster Management
   - Other

3. Priority: Must be EXACTLY one of these allowed values:
   - CRITICAL: Life-threatening emergencies, Fire, Major accidents, Building collapse, Flood threatening lives, Serious medical emergency, Dangerous electrical situations, Immediate public safety threats.
   - HIGH: No water for several days, Major electricity outage, Sewage overflow, Dangerous roads, Major public infrastructure failures, Significant public safety problems.
   - MEDIUM: Garbage collection problems, Broken street lights, Minor road damage, Routine service complaints.
   - LOW: General information requests, Non-urgent requests, Minor inquiries.

4. Summary: Concise 1-2 sentence summary of the complaint written in ENGLISH, regardless of the input language.
5. Location: Extract the location ONLY if explicitly mentioned in the transcript (e.g. "Anna Nagar", "MG Road"). If no location is explicitly mentioned, return null. NEVER invent or assume a location.
6. Keywords: An array of 2-5 relevant English keywords.

Output Format:
Return ONLY valid JSON matching this schema:
{
  "category": "string",
  "department": "string",
  "priority": "CRITICAL | HIGH | MEDIUM | LOW",
  "summary": "string",
  "location": "string | null",
  "keywords": ["string"]
}
Do NOT include markdown formatting, explanations, or code blocks.
"""


class AnalysisService:

    def analyze_complaint(self, transcript: str) -> Dict[str, Any]:
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty.")

        api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key or not api_key.strip():
            logger.error("LLM_API_KEY environment variable is missing or empty.")
            raise RuntimeError("LLM API key is not configured on the server.")

        env_model = os.getenv("LLM_MODEL", "gemini-3.6-flash").strip()
        if env_model.lower() in DEPRECATED_MODELS:
            logger.warning(
                "Requested model '%s' is deprecated by Gemini API. Substituting with 'gemini-3.6-flash'.",
                env_model,
            )
            model_name = "gemini-3.6-flash"
        else:
            model_name = env_model or "gemini-3.6-flash"

        raw_text = None
        try:
            client = genai.Client(api_key=api_key)

            # Try Interactions API first (recommended)
            try:
                interaction = client.interactions.create(
                    model=model_name,
                    input=f"{SYSTEM_PROMPT}\n\nCitizen Complaint Transcript: {transcript}",
                )
                raw_text = interaction.output_text
            except Exception as ie:
                logger.warning(
                    "Interactions API call failed (%s), falling back to generate_content: %s",
                    model_name,
                    str(ie),
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=f"Citizen Complaint Transcript: {transcript}",
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                raw_text = response.text

        except Exception as e:
            logger.exception("LLM API call failed: %s", str(e))
            raise RuntimeError("LLM API request failed. Please check your API key or model configuration.") from e

        if not raw_text:
            raise ValueError("Empty response received from LLM.")

        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from LLM: %s", raw_text)
            raise ValueError("Invalid JSON returned by LLM.") from e

        return self._validate_and_sanitize(data)

    def _validate_and_sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("LLM output is not a valid JSON object.")

        # Category
        category = str(data.get("category", "Other")).strip() or "Other"

        # Department
        raw_dept = str(data.get("department", "Other")).strip()
        dept_match = next(
            (d for d in ALLOWED_DEPARTMENTS if d.lower() == raw_dept.lower()),
            "Other",
        )

        # Priority
        raw_priority = str(data.get("priority", "MEDIUM")).strip().upper()
        priority = raw_priority if raw_priority in ALLOWED_PRIORITIES else "MEDIUM"

        # Summary
        summary = str(data.get("summary", "")).strip()
        if not summary:
            summary = "No summary available."

        # Location
        raw_loc = data.get("location")
        if isinstance(raw_loc, str):
            clean_loc = raw_loc.strip()
            if clean_loc.lower() in {"null", "none", "n/a", "unknown", ""}:
                location = None
            else:
                location = clean_loc
        else:
            location = None

        # Keywords
        raw_keywords = data.get("keywords", [])
        if isinstance(raw_keywords, list):
            keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
        else:
            keywords = []

        return {
            "category": category,
            "department": dept_match,
            "priority": priority,
            "summary": summary,
            "location": location,
            "keywords": keywords,
        }


analysis_service = AnalysisService()
