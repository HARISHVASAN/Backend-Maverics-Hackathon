import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.chroma_service import chroma_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

DEFAULT_DUPLICATE_THRESHOLD = 0.80
DEFAULT_RELATED_THRESHOLD = 0.60


class DuplicateService:

    def __init__(self):
        pass

    @property
    def duplicate_threshold(self) -> float:
        try:
            return float(os.getenv("DUPLICATE_THRESHOLD", DEFAULT_DUPLICATE_THRESHOLD))
        except ValueError:
            return DEFAULT_DUPLICATE_THRESHOLD

    @property
    def related_threshold(self) -> float:
        try:
            return float(os.getenv("RELATED_THRESHOLD", DEFAULT_RELATED_THRESHOLD))
        except ValueError:
            return DEFAULT_RELATED_THRESHOLD

    def check_and_store_complaint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        complaint_id = data.get("complaint_id")
        if not complaint_id:
            raise ValueError("complaint_id is required.")

        transcript = (data.get("transcript") or "").strip()
        summary = (data.get("summary") or "").strip()

        # Prefer English summary when available for semantic embedding, fallback to transcript
        text_to_embed = summary if summary else transcript
        if not text_to_embed:
            raise ValueError("Complaint transcript or summary is required for embedding.")

        embedding = embedding_service.get_embedding(text_to_embed)

        # Query ChromaDB for top 5 matches
        all_matches = chroma_service.query_similar(embedding, n_results=5)
        # Exclude self if complaint_id is already stored
        matches = [m for m in all_matches if m["id"] != complaint_id]

        status = "NEW"
        duplicate_of: Optional[str] = None
        related_complaint: Optional[str] = None
        similarity = 0.0
        matched_complaint_info: Optional[Dict[str, Any]] = None

        if matches:
            top_match = matches[0]
            similarity = float(top_match["similarity"])
            top_id = top_match["id"]
            top_meta = top_match["metadata"] or {}

            root_id = top_meta.get("duplicate_of")
            if not root_id or str(root_id).strip() in {"", "null", "None"}:
                root_id = top_id

            # Location comparison
            new_loc = str(data.get("location") or "").strip().lower()
            match_loc = str(top_meta.get("location") or "").strip().lower()
            unknown_markers = {"", "null", "none", "n/a", "unknown"}
            loc_unknown = (new_loc in unknown_markers) or (match_loc in unknown_markers)
            same_location = (new_loc == match_loc)

            # Category comparison
            new_cat = str(data.get("category") or "").strip().lower()
            match_cat = str(top_meta.get("category") or "").strip().lower()
            same_category = (new_cat == match_cat)

            dup_thresh = self.duplicate_threshold
            rel_thresh = self.related_threshold

            if similarity >= dup_thresh:
                if same_category and (same_location or loc_unknown):
                    status = "DUPLICATE"
                    duplicate_of = root_id
                    related_complaint = None
                else:
                    status = "RELATED"
                    duplicate_of = None
                    related_complaint = top_id
            elif similarity >= rel_thresh:
                status = "RELATED"
                duplicate_of = None
                related_complaint = top_id
            else:
                status = "NEW"
                duplicate_of = None
                related_complaint = None

            matched_complaint_info = {
                "complaint_id": top_id,
                "category": top_meta.get("category") or "Other",
                "department": top_meta.get("department") or "Other",
                "location": top_meta.get("location") or None,
                "summary": top_meta.get("summary") or top_match.get("document") or "",
            }

        # Store complaint in ChromaDB to preserve history and enable future grouping.
        # call_sid/recording_sid are only present for complaints that originated from
        # a Twilio phone call (Module 8A) -- empty string for every other input source.
        metadata_to_store = {
            "complaint_id": complaint_id,
            "category": str(data.get("category") or ""),
            "department": str(data.get("department") or ""),
            "priority": str(data.get("priority") or ""),
            "location": str(data.get("location") or ""),
            "summary": summary,
            "transcript": transcript,
            "duplicate_of": duplicate_of or "",
            "call_sid": str(data.get("call_sid") or ""),
            "recording_sid": str(data.get("recording_sid") or ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        chroma_service.add_complaint(
            complaint_id=complaint_id,
            document=text_to_embed,
            embedding=embedding,
            metadata=metadata_to_store,
        )

        response = {
            "complaint_id": complaint_id,
            "status": status,
            "duplicate_of": duplicate_of,
            "related_complaint": related_complaint,
            "similarity": similarity,
        }

        if matched_complaint_info:
            response["matched_complaint"] = matched_complaint_info

        return response


duplicate_service = DuplicateService()
