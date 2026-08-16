import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEPARTMENT_MAPPING: Dict[str, str] = {
    "water": "Water Department",
    "water supply": "Water Department",
    "electricity": "Electricity Department",
    "power": "Electricity Department",
    "roads": "Roads Department",
    "highways": "Roads Department",
    "sanitation": "Sanitation Department",
    "garbage": "Sanitation Department",
    "waste": "Sanitation Department",
    "healthcare": "Healthcare Department",
    "health": "Healthcare Department",
    "hospital": "Healthcare Department",
    "police": "Police Department",
    "law and order": "Police Department",
    "transport": "Transport Department",
    "bus": "Transport Department",
    "traffic": "Transport Department",
    "municipal": "Municipal Department",
    "civic": "Municipal Department",
    "disaster management": "Disaster Management Department",
    "disaster": "Disaster Management Department",
    "flood": "Disaster Management Department",
    "other": "General Department",
}

CANONICAL_DEPARTMENTS: List[str] = [
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
]


class DepartmentRoutingService:

    def normalize_department(self, raw_dept: Optional[str]) -> str:
        if not raw_dept or not str(raw_dept).strip():
            return "Other"

        dept_str = str(raw_dept).strip()
        # Direct match against canonical list
        for canonical in CANONICAL_DEPARTMENTS:
            if dept_str.lower() == canonical.lower():
                return canonical

        # Match against mapping keywords
        dept_lower = dept_str.lower()
        if dept_lower in DEPARTMENT_MAPPING:
            mapped_val = DEPARTMENT_MAPPING[dept_lower]
            # Convert mapped display name to canonical enum key (e.g. "Water Department" -> "Water")
            for canonical in CANONICAL_DEPARTMENTS:
                if canonical.lower() in mapped_val.lower():
                    return canonical

        return "Other"

    def get_department_display_name(self, canonical_dept: str) -> str:
        canonical = self.normalize_department(canonical_dept)
        lookup = canonical.lower()
        return DEPARTMENT_MAPPING.get(lookup, f"{canonical} Department")


department_routing_service = DepartmentRoutingService()
