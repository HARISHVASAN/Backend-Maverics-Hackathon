import SLABadge from "./SLABadge";
import { Loading, ErrorState } from "./StateViews";
import { formatDateTime, formatRemaining } from "../utils";

export default function SLAInfoPanel({ sla, loading, error }) {
  if (loading) return <Loading label="Loading SLA information…" />;
  if (error) return <ErrorState message={error} />;
  if (!sla) return null;

  const breached = sla.sla_status === "BREACHED";

  return (
    <div className={`sla-panel ${breached ? "sla-panel-breached" : ""}`}>
      {breached && <div className="sla-breach-banner">⚠ SLA BREACHED</div>}
      <div className="sla-grid">
        <div className="sla-field">
          <span className="sla-field-label">SLA Duration</span>
          <span className="sla-field-value">{sla.sla_duration_hours}h</span>
        </div>
        <div className="sla-field">
          <span className="sla-field-label">Deadline</span>
          <span className="sla-field-value">{formatDateTime(sla.sla_deadline)}</span>
        </div>
        <div className="sla-field">
          <span className="sla-field-label">Status</span>
          <span className="sla-field-value">
            <SLABadge status={sla.sla_status} />
          </span>
        </div>
        <div className="sla-field">
          <span className="sla-field-label">Remaining Time</span>
          <span className="sla-field-value">{formatRemaining(sla.remaining_hours)}</span>
        </div>
        <div className="sla-field">
          <span className="sla-field-label">Escalation Level</span>
          <span className="sla-field-value">
            {sla.escalation_level > 0 ? (
              <span className="escalation-pill">Level {sla.escalation_level}</span>
            ) : (
              "None"
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
