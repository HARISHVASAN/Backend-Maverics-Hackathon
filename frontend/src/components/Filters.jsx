import { DEPARTMENTS, PRIORITIES, STATUSES } from "../constants";

export default function Filters({ filters, onChange, search, onSearchChange }) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  return (
    <div className="filters-bar">
      <select className="filter-select" value={filters.department} onChange={set("department")}>
        <option value="">All Departments</option>
        {DEPARTMENTS.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </select>

      <select className="filter-select" value={filters.priority} onChange={set("priority")}>
        <option value="">All Priorities</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <select className="filter-select" value={filters.status} onChange={set("status")}>
        <option value="">All Statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s.replace("_", " ")}
          </option>
        ))}
      </select>

      <input
        className="filter-select filter-category"
        type="text"
        placeholder="Category…"
        value={filters.category}
        onChange={set("category")}
      />

      <input
        className="search-input"
        type="text"
        placeholder="Search by ID, category, or location…"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />
    </div>
  );
}
