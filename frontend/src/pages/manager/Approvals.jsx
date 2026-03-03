import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import { apiUrl } from "../../config/apiBase";
import "./Approvals.css";
import useScrollReveal from "../../utils/useScrollReveal";

function getAuthToken() {
  try {
    const raw = localStorage.getItem("user");
    if (raw) { const u = JSON.parse(raw); if (u?.access_token) return u.access_token; }
  } catch { /* ignore */ }
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") || ""
  );
}

export default function Approvals() {
  const revealRef = useScrollReveal();
  const navigate = useNavigate();

  // ------------------- State -------------------
  const [query, setQuery] = useState("");
  const [requestType, setRequestType] = useState("All Request Types");
  const [status, setStatus] = useState("All Status");
  const [rows, setRows] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedDepartments, setSelectedDepartments] = useState({});
  const [loading, setLoading] = useState(true);

  // ------------------- Fetch Approvals with Session -------------------
  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      navigate("/login");
      return;
    }

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };

    setLoading(true);
    fetch(apiUrl("/api/manager/approvals"), { headers })
      .then((res) => {
        if (res.status === 401) navigate("/login");
        return res.json();
      })
      .then((data) => {
        const formatted = data.map((a) => ({
          requestId: a.requestId,
          ticketId: a.ticketCode,
          type: a.type,
          source: a.source || "employee",
          current: a.current,
          requested: a.requested,
          submittedBy: a.submittedBy,
          modelConfidence: a.modelConfidence,
          submittedOn: new Date(a.submittedOn).toLocaleString(),
          status: a.status,
        }));
        setRows(formatted);
      })
      .catch((err) => console.error("Error fetching approvals:", err))
      .finally(() => setLoading(false));

    fetch(apiUrl("/manager/departments"), { headers })
      .then((res) => res.json())
      .then((data) => setDepartments(Array.isArray(data) ? data : []))
      .catch(() => setDepartments([]));
  }, [navigate]);

  // ------------------- Actions -------------------
  const decide = async (requestId, decision, selectedDepartment = undefined) => {
    const token = getAuthToken();
    if (!token) { navigate("/login"); return; }

    // Optimistic update
    setRows((prev) =>
      prev.map((r) => (r.requestId === requestId ? { ...r, status: decision } : r))
    );

    try {
      const res = await fetch(apiUrl(`/api/manager/approvals/${requestId}`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ decision, selected_department: selectedDepartment }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }
    } catch (e) {
      // Rollback optimistic update on failure
      setRows((prev) =>
        prev.map((r) => (r.requestId === requestId ? { ...r, status: "Pending" } : r))
      );
      alert(e.message || "Failed to save decision. Please try again.");
    }
  };

  // ------------------- Filtering -------------------
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesQuery =
        !q ||
        r.requestId.toLowerCase().includes(q) ||
        r.ticketId.toLowerCase().includes(q) ||
        r.submittedBy.toLowerCase().includes(q);

      const matchesType = requestType === "All Request Types" || r.type === requestType;
      const matchesStatus = status === "All Status" || r.status === status;

      return matchesQuery && matchesType && matchesStatus;
    });
  }, [rows, query, requestType, status]);

  // ------------------- KPIs -------------------
  const totals = useMemo(() => {
    const total = rows.length;
    const pending = rows.filter((r) => r.status === "Pending").length;
    const approved = rows.filter((r) => r.status === "Approved").length;
    const rejected = rows.filter((r) => r.status === "Rejected").length;
    return { total, pending, approved, rejected };
  }, [rows]);

  const handleReset = () => {
    setQuery("");
    setRequestType("All Request Types");
    setStatus("All Status");
  };

  // ------------------- JSX -------------------
  return (
    <Layout role="manager">
      <div className="mgrApprovals" ref={revealRef}>
        <PageHeader
          title="Approvals"
          subtitle="Approve or reject requests for rescoring and rerouting complaints."
        />

        <section className="kpiRow">
          <KpiCard label="Total Requests" value={loading ? "—" : totals.total} caption="All approval requests" />
          <KpiCard label="Pending"        value={loading ? "—" : totals.pending} caption="Awaiting decision" />
          <KpiCard label="Approved"       value={loading ? "—" : totals.approved} caption="Approved by manager" />
          <KpiCard label="Rejected"       value={loading ? "—" : totals.rejected} caption="Rejected by manager" />
        </section>

        <section className="searchSection">
          <PillSearch
            value={query}
            onChange={setQuery}
            placeholder="Search approval requests by ID, ticket, or employee..."
          />
        </section>

        <section className="filtersRow">
          <div className="filtersLeft">
            <div className="pillSelectHolder">
              <PillSelect
                value={requestType}
                onChange={setRequestType}
                ariaLabel="Filter by request type"
                options={[
                  { value: "All Request Types", label: "All Request Types" },
                  { value: "Rescoring", label: "Rescoring" },
                  { value: "Rerouting", label: "Rerouting" },
                ]}
              />
            </div>

            <div className="pillSelectHolder">
              <PillSelect
                value={status}
                onChange={setStatus}
                ariaLabel="Filter by status"
                options={[
                  { value: "All Status", label: "All Status" },
                  { value: "Pending", label: "Pending" },
                  { value: "Approved", label: "Approved" },
                  { value: "Rejected", label: "Rejected" },
                ]}
              />
            </div>

            <FilterPillButton onClick={handleReset} label="Reset">
              Reset
            </FilterPillButton>
          </div>
        </section>

        <section className="tableWrapper">
          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Ticket ID</th>
                  <th>Request Type</th>
                  <th>Source</th>
                  <th>Current</th>
                  <th>Requested Change</th>
                  <th>Submitted By</th>
                  <th>Submitted On</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {loading && (
                  <tr>
                    <td className="emptyRow" colSpan={10} style={{ textAlign: "center", color: "rgba(17,17,17,0.45)" }}>
                      Loading requests…
                    </td>
                  </tr>
                )}
                {!loading && filtered.map((r) => (
                  <tr key={r.requestId}>
                    <td>{r.requestId}</td>
                    <td className="ticketLink">{r.ticketId}</td>
                    <td>{r.type}</td>
                    <td>
                      {r.source === "agent" ? "AI Agent" : "Employee"}
                      {r.source === "agent" && typeof r.modelConfidence === "number"
                        ? ` (${(r.modelConfidence * 100).toFixed(1)}%)`
                        : ""}
                    </td>
                    <td>{r.current}</td>
                    <td>{r.requested}</td>
                    <td>{r.submittedBy}</td>
                    <td>{r.submittedOn}</td>
                    <td>
                      <span
                        className={
                          r.status === "Approved"
                            ? "statusPill statusPill--approved"
                            : r.status === "Rejected"
                            ? "statusPill statusPill--rejected"
                            : "statusPill statusPill--pending"
                        }
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="actionsCell">
                      {r.type === "Rerouting" && r.status === "Pending" && (
                        <div style={{ marginBottom: 8 }}>
                          <select
                            value={selectedDepartments[r.requestId] || ""}
                            onChange={(e) =>
                              setSelectedDepartments((prev) => ({
                                ...prev,
                                [r.requestId]: e.target.value,
                              }))
                            }
                          >
                            <option value="">Use requested department</option>
                            {departments.map((dept) => (
                              <option key={dept} value={dept}>
                                {dept}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                      <button
                        className="actionBtn actionBtn--primary"
                        type="button"
                        onClick={() =>
                          decide(
                            r.requestId,
                            "Approved",
                            selectedDepartments[r.requestId] ||
                              (r.type === "Rerouting"
                                ? String(r.requested || "").replace("Dept:", "").trim()
                                : undefined)
                          )
                        }
                        disabled={r.status !== "Pending"}
                      >
                        Approve
                      </button>
                      <button
                        className="actionBtn"
                        type="button"
                        onClick={() => decide(r.requestId, "Rejected")}
                        disabled={r.status !== "Pending"}
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}

                {!loading && filtered.length === 0 && (
                  <tr>
                    <td className="emptyRow" colSpan={10}>
                      No approval requests match your filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}
