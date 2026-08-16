import { useCallback, useEffect, useMemo, useState } from "react";
import StatCardsRow from "./components/StatCardsRow";
import Filters from "./components/Filters";
import ComplaintTable from "./components/ComplaintTable";
import ComplaintDetails from "./components/ComplaintDetails";
import Analytics from "./components/Analytics";
import SLAAlerts from "./components/SLAAlerts";
import { fetchComplaints, fetchAnalyticsSummary, ApiError } from "./services/api";
import "./App.css";

const EMPTY_FILTERS = { department: "", priority: "", status: "", category: "" };

export default function App() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [search, setSearch] = useState("");

  const [complaints, setComplaints] = useState(null);
  const [complaintsLoading, setComplaintsLoading] = useState(true);
  const [complaintsError, setComplaintsError] = useState(null);

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadComplaints = useCallback(async () => {
    setComplaintsLoading(true);
    setComplaintsError(null);
    try {
      const data = await fetchComplaints(filters);
      setComplaints(data);
    } catch (err) {
      setComplaintsError(err instanceof ApiError ? err.message : "Unexpected error.");
    } finally {
      setComplaintsLoading(false);
    }
  }, [filters]);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await fetchAnalyticsSummary();
      setSummary(data);
    } catch (err) {
      setSummaryError(err instanceof ApiError ? err.message : "Unexpected error.");
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadComplaints();
  }, [loadComplaints, refreshKey]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary, refreshKey]);

  const visibleComplaints = useMemo(() => {
    if (!complaints) return complaints;
    const q = search.trim().toLowerCase();
    if (!q) return complaints;
    return complaints.filter(
      (c) =>
        c.complaint_id.toLowerCase().includes(q) ||
        (c.category || "").toLowerCase().includes(q) ||
        (c.location || "").toLowerCase().includes(q)
    );
  }, [complaints, search]);

  function handleChanged() {
    // A status update happened -- refresh stats, table, and SLA alerts.
    setRefreshKey((k) => k + 1);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <div>
            <h1>CITIZEN CALL INTELLIGENCE</h1>
            <p className="app-subtitle">AI-Powered Citizen Complaint Management</p>
          </div>
        </div>
      </header>

      <main className="app-main">
        <StatCardsRow summary={summary} loading={summaryLoading} error={summaryError} />

        <SLAAlerts onOpenComplaint={setSelectedId} refreshKey={refreshKey} />

        <section className="panel">
          <h2 className="section-title">Complaints</h2>
          <Filters filters={filters} onChange={setFilters} search={search} onSearchChange={setSearch} />
          <ComplaintTable
            complaints={visibleComplaints}
            loading={complaintsLoading}
            error={complaintsError}
            onSelect={setSelectedId}
          />
        </section>

        <section className="panel">
          <h2 className="section-title">Analytics</h2>
          <Analytics key={refreshKey} />
        </section>
      </main>

      {selectedId && (
        <ComplaintDetails
          complaintId={selectedId}
          onClose={() => setSelectedId(null)}
          onOpenComplaint={setSelectedId}
          onChanged={handleChanged}
        />
      )}
    </div>
  );
}
