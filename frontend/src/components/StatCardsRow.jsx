import StatCard from "./StatCard";
import { Loading, ErrorState } from "./StateViews";

export default function StatCardsRow({ summary, loading, error }) {
  if (loading) return <Loading label="Loading statistics…" />;
  if (error) return <ErrorState message={error} />;
  if (!summary) return null;

  const criticalHigh = (summary.critical || 0) + (summary.high || 0);

  return (
    <div className="stat-cards-row">
      <StatCard label="Total Complaints" value={summary.total_complaints ?? 0} tone="default" />
      <StatCard label="Pending" value={summary.pending ?? 0} tone="pending" />
      <StatCard label="In Progress" value={summary.in_progress ?? 0} tone="progress" />
      <StatCard label="Critical / High" value={criticalHigh} tone="critical" />
      <StatCard label="Resolved" value={summary.resolved ?? 0} tone="resolved" />
      <StatCard label="SLA Breached" value={summary.sla_breached ?? 0} tone="breached" />
    </div>
  );
}
