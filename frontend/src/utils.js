// Formatting helpers. Pure display logic only -- no SLA/status calculation
// happens here, that all comes from the backend.

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRemaining(hours) {
  if (hours === undefined || hours === null) return "—";
  if (hours < 0) {
    return `${Math.abs(hours).toFixed(1)}h overdue`;
  }
  if (hours < 1) {
    return `${Math.round(hours * 60)}m remaining`;
  }
  return `${hours.toFixed(1)}h remaining`;
}

export function formatPercent(value) {
  if (value === undefined || value === null) return "—";
  return `${value}%`;
}
