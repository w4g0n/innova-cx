import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
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

      const matchesType = requestType === "All Request Types" || r.type === requestType;
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

  const handleReset = () => {
    setQuery("");
    setRequestType("All Request Types");
    setStatus("All Status");
  };

  return (
    <Layout role="manager">
      <div className="mgrApprovals">
        <PageHeader
          title="Approvals"
          subtitle="Approve or reject requests for rescoring and rerouting complaints."
        />

        <section className="kpiRow">
          <KpiCard label="Total Requests" value={totals.total} caption="All approval requests" />
          <KpiCard label="Pending" value={totals.pending} caption="Awaiting decision" />
          <KpiCard label="Approved" value={totals.approved} caption="Approved by manager" />
          <KpiCard label="Rejected" value={totals.rejected} caption="Rejected by manager" />
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