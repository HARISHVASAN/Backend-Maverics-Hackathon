import { useEffect, useState, useCallback } from "react";
import PriorityBadge from "./PriorityBadge";
import StatusBadge from "./StatusBadge";
import DuplicateInfo from "./DuplicateInfo";
import SLAInfoPanel from "./SLAInfoPanel";
import { Loading, ErrorState } from "./StateViews";
import { fetchComplaint, fetchComplaintSLA, updateComplaintStatus, ApiError } from "../services/api";
import { ALLOWED_TRANSITIONS } from "../constants";
import { formatDateTime } from "../utils";

export default function ComplaintDetails({ complaintId, onClose, onOpenComplaint, onChanged }) {
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [sla, setSla] = useState(null);
  const [slaLoading, setSlaLoading] = useState(true);
  const [slaError, setSlaError] = useState(null);

  const [nextStatus, setNextStatus] = useState("");
  const [updating, setUpdating] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null); // { type: 'success'|'error', text }

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchComplaint(complaintId);
      setComplaint(data);
      setNextStatus("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }, [complaintId]);

  const loadSla = useCallback(async () => {
    setSlaLoading(true);
    setSlaError(null);
    try {
      const data = await fetchComplaintSLA(complaintId);
      setSla(data);
    } catch (err) {
      setSlaError(err instanceof ApiError ? err.message : "Unexpected error.");
    } finally {
      setSlaLoading(false);
    }
  }, [complaintId]);

  useEffect(() => {
    load();
    loadSla();
    setStatusMessage(null);
  }, [load, loadSla]);

  async function handleStatusUpdate() {
    if (!nextStatus) return;
    setUpdating(true);
    setStatusMessage(null);
    try {
      await updateComplaintStatus(complaintId, nextStatus);
      setStatusMessage({ type: "success", text: `Status updated to ${nextStatus.replace("_", " ")}.` });
      await load();
      await loadSla();
      onChanged?.();
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof ApiError ? err.message : "Failed to update status.",
      });
    } finally {
      setUpdating(false);
    }
  }

  const allowedNext = complaint ? ALLOWED_TRANSITIONS[complaint.status] || [] : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{complaintId}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="modal-body">
          {loading && <Loading label="Loading complaint…" />}
          {error && <ErrorState message={error} />}

          {complaint && !loading && !error && (
            <>
              <section className="detail-section">
                <div className="detail-header-row">
                  <PriorityBadge priority={complaint.priority} />
                  <StatusBadge status={complaint.status} />
                </div>
                <h3>AI Summary</h3>
                <p>{complaint.summary}</p>

                <div className="detail-grid">
                  <div>
                    <span className="detail-label">Category</span>
                    <span className="detail-value">{complaint.category}</span>
                  </div>
                  <div>
                    <span className="detail-label">Department</span>
                    <span className="detail-value">{complaint.department}</span>
                  </div>
                  <div>
                    <span className="detail-label">Location</span>
                    <span className="detail-value">{complaint.location || "—"}</span>
                  </div>
                  <div>
                    <span className="detail-label">Language</span>
                    <span className="detail-value">{complaint.language}</span>
                  </div>
                  <div>
                    <span className="detail-label">Created At</span>
                    <span className="detail-value">{formatDateTime(complaint.created_at)}</span>
                  </div>
                  <div>
                    <span className="detail-label">Report Count</span>
                    <span className="detail-value">{complaint.report_count}</span>
                  </div>
                </div>

                {complaint.keywords?.length > 0 && (
                  <div className="keywords-row">
                    {complaint.keywords.map((kw) => (
                      <span key={kw} className="keyword-chip">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </section>

              <section className="detail-section">
                <h3>Original Transcript</h3>
                <p className="transcript-text">{complaint.transcript}</p>
              </section>

              <section className="detail-section">
                <h3>Duplicate Information</h3>
                <DuplicateInfo complaint={complaint} onOpenComplaint={onOpenComplaint} />
              </section>

              <section className="detail-section">
                <h3>SLA Information</h3>
                <SLAInfoPanel sla={sla} loading={slaLoading} error={slaError} />
              </section>

              <section className="detail-section">
                <h3>Update Status</h3>
                {allowedNext.length === 0 ? (
                  <p className="detail-muted">No further transitions available from {complaint.status}.</p>
                ) : (
                  <div className="status-update-row">
                    <select
                      className="filter-select"
                      value={nextStatus}
                      onChange={(e) => setNextStatus(e.target.value)}
                    >
                      <option value="">Select new status…</option>
                      {allowedNext.map((s) => (
                        <option key={s} value={s}>
                          {s.replace("_", " ")}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={!nextStatus || updating}
                      onClick={handleStatusUpdate}
                    >
                      {updating ? "Updating…" : "Update Status"}
                    </button>
                  </div>
                )}
                {statusMessage && (
                  <div
                    className={
                      statusMessage.type === "success" ? "status-message-success" : "status-message-error"
                    }
                  >
                    {statusMessage.text}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
