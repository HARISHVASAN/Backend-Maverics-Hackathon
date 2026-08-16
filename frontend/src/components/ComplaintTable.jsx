import PriorityBadge from "./PriorityBadge";
import StatusBadge from "./StatusBadge";
import SLABadge from "./SLABadge";
import { Loading, ErrorState, EmptyState } from "./StateViews";
import { formatDateTime } from "../utils";

export default function ComplaintTable({ complaints, loading, error, onSelect }) {
  if (loading) return <Loading label="Loading complaints…" />;
  if (error) return <ErrorState message={error} />;
  if (!complaints || complaints.length === 0) {
    return <EmptyState message="No complaints found." />;
  }

  return (
    <div className="table-scroll">
      <table className="complaint-table">
        <thead>
          <tr>
            <th>Complaint ID</th>
            <th>Category</th>
            <th>Department</th>
            <th>Priority</th>
            <th>Location</th>
            <th>Status</th>
            <th>SLA</th>
            <th>Created At</th>
          </tr>
        </thead>
        <tbody>
          {complaints.map((c) => (
            <tr key={c.complaint_id} onClick={() => onSelect(c.complaint_id)} tabIndex={0}>
              <td className="cell-id">{c.complaint_id}</td>
              <td>{c.category || "—"}</td>
              <td>{c.department || "—"}</td>
              <td>
                <PriorityBadge priority={c.priority} />
              </td>
              <td>{c.location || "—"}</td>
              <td>
                <StatusBadge status={c.status} />
              </td>
              <td>
                <SLABadge status={c.sla_status} />
              </td>
              <td className="cell-muted">{formatDateTime(c.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
