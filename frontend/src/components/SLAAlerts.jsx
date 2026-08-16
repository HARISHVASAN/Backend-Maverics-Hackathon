import { useEffect, useState, useCallback } from "react";
import { fetchSLAAtRisk, fetchSLABreached, ApiError } from "../services/api";
import { Loading, ErrorState } from "./StateViews";

export default function SLAAlerts({ onOpenComplaint, refreshKey }) {
  const [atRisk, setAtRisk] = useState(null);
  const [breached, setBreached] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [riskList, breachedList] = await Promise.all([fetchSLAAtRisk(), fetchSLABreached()]);
      setAtRisk(riskList);
      setBreached(breachedList);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (loading) return <div className="sla-alerts-section"><Loading label="Loading SLA alerts…" /></div>;
  if (error) return <div className="sla-alerts-section"><ErrorState message={error} /></div>;

  const hasAny = (atRisk?.length || 0) + (breached?.length || 0) > 0;

  return (
    <div className="sla-alerts-section">
      <h3 className="section-title">SLA Attention Required</h3>
      {!hasAny && <p className="detail-muted">No complaints currently at risk or breached.</p>}

      {hasAny && (
        <div className="sla-alerts-columns">
          <div>
            <div className="sla-alerts-heading sla-alerts-heading-risk">
              AT RISK <span>{atRisk.length}</span>
            </div>
            <ul className="sla-alerts-list">
              {atRisk.map((item) => (
                <li key={item.complaint_id}>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => onOpenComplaint(item.complaint_id)}
                  >
                    {item.complaint_id}
                  </button>
                  <span className="sla-alerts-meta">
                    {item.department} · {item.priority}
                  </span>
                </li>
              ))}
              {atRisk.length === 0 && <li className="detail-muted">None</li>}
            </ul>
          </div>

          <div>
            <div className="sla-alerts-heading sla-alerts-heading-breach">
              BREACHED <span>{breached.length}</span>
            </div>
            <ul className="sla-alerts-list">
              {breached.map((item) => (
                <li key={item.complaint_id}>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => onOpenComplaint(item.complaint_id)}
                  >
                    {item.complaint_id}
                  </button>
                  <span className="sla-alerts-meta">
                    {item.department} · Level {item.escalation_level}
                  </span>
                </li>
              ))}
              {breached.length === 0 && <li className="detail-muted">None</li>}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
