const PRIORITY_CLASS = {
  CRITICAL: "badge badge-priority-critical",
  HIGH: "badge badge-priority-high",
  MEDIUM: "badge badge-priority-medium",
  LOW: "badge badge-priority-low",
};

export default function PriorityBadge({ priority }) {
  const cls = PRIORITY_CLASS[priority] || "badge";
  return <span className={cls}>{priority || "—"}</span>;
}
