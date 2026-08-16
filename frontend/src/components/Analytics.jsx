import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import { Loading, ErrorState, EmptyState } from "./StateViews";
import {
  fetchAnalyticsDepartments,
  fetchAnalyticsCategories,
  fetchAnalyticsPriorities,
  fetchAnalyticsStatus,
  ApiError,
} from "../services/api";

const PRIORITY_COLORS = {
  CRITICAL: "#c0392b",
  HIGH: "#d97706",
  MEDIUM: "#ca8a04",
  LOW: "#16a34a",
};

const STATUS_COLORS = {
  PENDING: "#64748b",
  ASSIGNED: "#2563eb",
  IN_PROGRESS: "#7c3aed",
  RESOLVED: "#16a34a",
  CLOSED: "#334155",
};

function ChartCard({ title, loading, error, empty, children }) {
  return (
    <div className="chart-card">
      <h3 className="chart-card-title">{title}</h3>
      {loading && <Loading label="Loading…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && empty && <EmptyState message="No data yet." />}
      {!loading && !error && !empty && <div className="chart-body">{children}</div>}
    </div>
  );
}

export default function Analytics() {
  const [departments, setDepartments] = useState(null);
  const [categories, setCategories] = useState(null);
  const [priorities, setPriorities] = useState(null);
  const [status, setStatus] = useState(null);
  const [errors, setErrors] = useState({});
  const [loadingAll, setLoadingAll] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadOne(fn, setter, key) {
      try {
        const data = await fn();
        if (!cancelled) setter(data);
      } catch (err) {
        if (!cancelled) {
          setErrors((prev) => ({
            ...prev,
            [key]: err instanceof ApiError ? err.message : "Unexpected error.",
          }));
        }
      }
    }

    (async () => {
      setLoadingAll(true);
      await Promise.all([
        loadOne(fetchAnalyticsDepartments, setDepartments, "departments"),
        loadOne(fetchAnalyticsCategories, setCategories, "categories"),
        loadOne(fetchAnalyticsPriorities, setPriorities, "priorities"),
        loadOne(fetchAnalyticsStatus, setStatus, "status"),
      ]);
      if (!cancelled) setLoadingAll(false);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const statusData = status
    ? Object.entries(status).map(([name, count]) => ({ name: name.replace("_", " "), count, key: name }))
    : null;

  return (
    <div className="analytics-grid">
      <ChartCard
        title="Complaints by Department"
        loading={loadingAll && !departments}
        error={errors.departments}
        empty={departments && departments.length === 0}
      >
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={departments || []} layout="vertical" margin={{ left: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="department" width={110} />
            <Tooltip />
            <Bar dataKey="count" fill="var(--primary)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Complaints by Category"
        loading={loadingAll && !categories}
        error={errors.categories}
        empty={categories && categories.length === 0}
      >
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={categories || []} layout="vertical" margin={{ left: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="category" width={110} />
            <Tooltip />
            <Bar dataKey="count" fill="var(--primary-light-accent)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Priority Distribution"
        loading={loadingAll && !priorities}
        error={errors.priorities}
        empty={priorities && priorities.every((p) => p.count === 0)}
      >
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={priorities || []}
              dataKey="count"
              nameKey="priority"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={(entry) => `${entry.priority}: ${entry.count}`}
            >
              {(priorities || []).map((entry) => (
                <Cell key={entry.priority} fill={PRIORITY_COLORS[entry.priority] || "#999"} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard
        title="Status Distribution"
        loading={loadingAll && !statusData}
        error={errors.status}
        empty={statusData && statusData.every((s) => s.count === 0)}
      >
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={statusData || []}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {(statusData || []).map((entry) => (
                <Cell key={entry.key} fill={STATUS_COLORS[entry.key] || "#999"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
