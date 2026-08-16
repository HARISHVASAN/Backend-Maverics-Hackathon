// Single place that knows the backend URL and how to talk to it.
// Every component goes through the functions below -- nothing hardcodes
// the backend origin anywhere else in the app.

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    // fetch throws TypeError on network failure / server down / CORS block
    throw new ApiError("Unable to connect to the backend.", 0);
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return null;
  return response.json();
}

function toQueryString(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------
// Complaints
// ---------------------------------------------------------------------
export function fetchComplaints(filters = {}) {
  return request(`/complaints${toQueryString(filters)}`);
}

export function fetchComplaint(complaintId) {
  return request(`/complaints/${encodeURIComponent(complaintId)}`);
}

export function fetchComplaintHistory(complaintId) {
  return request(`/complaints/${encodeURIComponent(complaintId)}/history`);
}

export function updateComplaintStatus(complaintId, status) {
  return request(`/complaints/${encodeURIComponent(complaintId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ---------------------------------------------------------------------
// SLA
// ---------------------------------------------------------------------
export function fetchComplaintSLA(complaintId) {
  return request(`/complaints/${encodeURIComponent(complaintId)}/sla`);
}

export function fetchSLAAtRisk() {
  return request("/sla/at-risk");
}

export function fetchSLABreached() {
  return request("/sla/breached");
}

// ---------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------
export function fetchAnalyticsSummary(days) {
  return request(`/analytics/summary${toQueryString({ days })}`);
}

export function fetchAnalyticsDepartments(days) {
  return request(`/analytics/departments${toQueryString({ days })}`);
}

export function fetchAnalyticsCategories(days) {
  return request(`/analytics/categories${toQueryString({ days })}`);
}

export function fetchAnalyticsPriorities(days) {
  return request(`/analytics/priorities${toQueryString({ days })}`);
}

export function fetchAnalyticsStatus(days) {
  return request(`/analytics/status${toQueryString({ days })}`);
}
