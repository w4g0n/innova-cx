import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import "./Approvals.css";

export default function Approvals() {
  const [query, setQuery] = useState("");
  const [requestType, setRequestType] = useState("All Request Types");
  const [status, setStatus] = useState("All Status");

  const [rows, setRows] = useState([
    {
      requestId: "REQ-3101",
      ticketId: "CX-2011",
      type: "Rescoring",
      current: "Priority: Medium",
      requested: "Priority: Critical",
      submittedBy: "Ahmed Hassan",
      submittedOn: "18/11/2025 – 10:22",
      status: "Pending",
    },
    {
      requestId: "REQ-3110",
      ticketId: "CX-2034",
      type: "Rerouting",
      current: "Dept: Facilities",
      requested: "Dept: Security",
      submittedBy: "Ahmed Hassan",
      submittedOn: "18/11/2025 – 11:05",
      status: "Pending",
    },
    {
      requestId: "REQ-3125",
      ticketId: "CX-2078",
      type: "Rescoring",
      current: "Priority: High",
      requested: "Priority: Medium",
      submittedBy: "Maria Lopez",
      submittedOn: "17/11/2025 – 15:40",
      status: "Pending",
    },
  ]);

  const approve = (requestId) => {
    setRows((prev) =>
      prev.map((r) => (r.requestId === requestId ? { ...r, status: "Approved" } : r))
    );
  };

  const reject = (requestId) => {
    setRows((prev) =>
      prev.map((r) => (r.requestId === requestId ? { ...r, status: "Rejected" } : r))
    );
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return rows.filter((r) => {
      const matchesQuery =
        !q ||
        r.requestId.toLowerCase().includes(q) ||
        r.ticketId.toLowerCase().includes(q) ||
        r.submittedBy.toLowerCase().includes(q);

      const matchesType =
        requestType === "All Request Types" || r.type === requestType;

      const matchesStatus = status === "All Status" || r.status === status;

      return matchesQuery && matchesType && matchesStatus;
    });
  }, [rows, query, requestType, status]);

  const totals = useMemo(() => {
    const total = rows.length;
    const pending = rows.filter((r) => r.status === "Pending").length;
    const approved = rows.filter((r) => r.status === "Approved").length;
    const rejected = rows.filter((r) => r.status === "Rejected").length;
    return { total, pending, approved, rejected };
  }, [rows]);

  return (
    <Layout role="manager">
      <div className="mgrApprovals">
        <header className="mgrHeader">
          <div>
            <h1 className="mgrTitle">Approvals</h1>
            <p className="mgrSubtitle">
              Approve or reject requests for rescoring and rerouting complaints.
            </p>
          </div>
        </header>

        <section className="kpiRow">
          <div className="kpiCard">
            <span className="kpiLabel">Total Requests</span>
            <span className="kpiValue">{totals.total}</span>
            <span className="kpiCaption">All approval requests</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Pending</span>
            <span className="kpiValue">{totals.pending}</span>
            <span className="kpiCaption">Awaiting decision</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Approved</span>
            <span className="kpiValue">{totals.approved}</span>
            <span className="kpiCaption">Approved by manager</span>
          </div>

          <div className="kpiCard">
            <span className="kpiLabel">Rejected</span>
            <span className="kpiValue">{totals.rejected}</span>
            <span className="kpiCaption">Rejected by manager</span>
          </div>
        </section>

        <section className="searchSection">
          <div className="searchWrapper">
            <span className="searchIcon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path
                  d="M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                />
                <path
                  d="M16.5 16.5 21 21"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <input
              className="searchInput"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search approval requests by ID, ticket, or employee..."
            />
          </div>
        </section>

        <section className="filtersRow">
          <div className="filtersLeft">
            <div className="selectWrapper">
              <select
                value={requestType}
                onChange={(e) => setRequestType(e.target.value)}
              >
                <option>All Request Types</option>
                <option>Rescoring</option>
                <option>Rerouting</option>
              </select>
            </div>

            <div className="selectWrapper">
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option>All Status</option>
                <option>Pending</option>
                <option>Approved</option>
                <option>Rejected</option>
              </select>
            </div>
          </div>

          <button className="filterBtn" type="button">
            <span className="filterIcon">
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M3 4h18l-7 8v6l-4 2v-8L3 4z"
                  fill="currentColor"
                />
              </svg>
            </span>
            Filters
          </button>
        </section>

        <section className="tableWrapper">
          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Ticket ID</th>
                  <th>Request Type</th>
                  <th>Current</th>
                  <th>Requested Change</th>
                  <th>Submitted By</th>
                  <th>Submitted On</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((r) => (
                  <tr key={r.requestId}>
                    <td>{r.requestId}</td>
                    <td className="ticketLink">{r.ticketId}</td>
                    <td>{r.type}</td>
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
                      <button
                        className="actionBtn actionBtn--primary"
                        type="button"
                        onClick={() => approve(r.requestId)}
                        disabled={r.status !== "Pending"}
                      >
                        Approve
                      </button>
                      <button
                        className="actionBtn"
                        type="button"
                        onClick={() => reject(r.requestId)}
                        disabled={r.status !== "Pending"}
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}

                {filtered.length === 0 && (
                  <tr>
                    <td className="emptyRow" colSpan={9}>
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
