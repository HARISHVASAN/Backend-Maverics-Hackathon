const SLA_CLASS = {
  ACTIVE: "badge badge-sla-active",
  AT_RISK: "badge badge-sla-at-risk",
  BREACHED: "badge badge-sla-breached",
  COMPLETED: "badge badge-sla-completed",
};

const SLA_LABEL = {
  ACTIVE: "ACTIVE",
  AT_RISK: "AT RISK",
  BREACHED: "BREACHED",
  COMPLETED: "COMPLETED",
};

export default function SLABadge({ status }) {
  const cls = SLA_CLASS[status] || "badge";
  return <span className={cls}>{SLA_LABEL[status] || status || "—"}</span>;
}
