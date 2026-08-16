const STATUS_CLASS = {
  PENDING: "badge badge-status-pending",
  ASSIGNED: "badge badge-status-assigned",
  IN_PROGRESS: "badge badge-status-in-progress",
  RESOLVED: "badge badge-status-resolved",
  CLOSED: "badge badge-status-closed",
};

export default function StatusBadge({ status }) {
  const cls = STATUS_CLASS[status] || "badge";
  return <span className={cls}>{status?.replace("_", " ") || "—"}</span>;
}
