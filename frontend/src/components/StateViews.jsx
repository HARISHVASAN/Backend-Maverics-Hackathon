export function Loading({ label = "Loading…" }) {
  return (
    <div className="state-view state-loading">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="state-view state-error" role="alert">
      <strong>Unable to connect to the backend.</strong>
      {message ? <span className="state-error-detail">{message}</span> : null}
    </div>
  );
}

export function EmptyState({ message = "No data found." }) {
  return <div className="state-view state-empty">{message}</div>;
}
