// Mirrors backend/app/database/schemas.py and the workflow rules in
// backend/app/services/complaint_service.py. The backend is still the
// source of truth / enforcement point -- this just drives the UI so
// officers aren't offered invalid choices.

export const DEPARTMENTS = [
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
];

export const PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const STATUSES = ["PENDING", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"];

export const ALLOWED_TRANSITIONS = {
  PENDING: ["ASSIGNED", "CLOSED"],
  ASSIGNED: ["IN_PROGRESS", "PENDING", "CLOSED"],
  IN_PROGRESS: ["RESOLVED", "ASSIGNED", "CLOSED"],
  RESOLVED: ["CLOSED", "IN_PROGRESS"],
  CLOSED: ["IN_PROGRESS", "PENDING"],
};

export const SLA_STATUSES = ["ACTIVE", "AT_RISK", "BREACHED", "COMPLETED"];
