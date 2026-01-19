// src/pages/manager/ManagerViewAllComplaints.jsx
import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import { Link } from "react-router-dom";
import "./ManagerViewAllComplaints.css";

export default function ManagerViewComplaints() {
  const rows = [
    {
      id: "CX-1122",
      subject: "Air conditioning not working",
      priority: "critical",
      priorityText: "Critical",
      status: "Unassigned",
      assignee: "—",
      issueDate: "19/11/2025",
      respondTime: "30 Minutes",
      resolveTime: "6 Hours",
      action: "Assign",
    },
    {
      id: "CX-3862",
      subject: "Water leakage in pantry",
      priority: "critical",
      priorityText: "Critical",
      status: "Overdue",
      assignee: "Maria Lopez",
      issueDate: "18/11/2025",
      respondTime: "30 Minutes",
      resolveTime: "6 Hours",
      action: "Reassign",
    },
    {
      id: "CX-4587",
      subject: "Wi-Fi connection unstable",
      priority: "high",
      priorityText: "High",
      status: "Escalated",
      assignee: "Supervisor Team",
      issueDate: "19/11/2025",
      respondTime: "1 Hour",
      resolveTime: "18 Hours",
      action: "Reassign",
    },
    {
      id: "CX-4630",
      subject: "Lift stopping between floors",
      priority: "high",
      priorityText: "High",
      status: "Assigned",
      assignee: "Ahmed Hassan",
      issueDate: "18/11/2025",
      respondTime: "1 Hour",
      resolveTime: "18 Hours",
      action: "Reassign",
    },
    {
      id: "CX-4701",
      subject: "Cleaning service missed schedule",
      priority: "medium",
      priorityText: "Medium",
      status: "Unassigned",
      assignee: "—",
      issueDate: "16/11/2025",
      respondTime: "3 Hours",
      resolveTime: "2 Days",
      action: "Assign",
    },
    {
      id: "CX-4725",
      subject: "Parking access card not working",
      priority: "medium",
      priorityText: "Medium",
      status: "Overdue",
      assignee: "Omar Ali",
      issueDate: "13/11/2025",
      respondTime: "3 Hours",
      resolveTime: "2 Days",
      action: "Reassign",
    },
    {
      id: "CX-4780",
      subject: "Noise from maintenance works",
      priority: "low",
      priorityText: "Low",
      status: "Escalated",
      assignee: "Sara Ahmed",
      issueDate: "09/11/2025",
      respondTime: "6 Hours",
      resolveTime: "3 Days",
      action: "Reassign",
    },
  ];

  // ✅ NEW: state (no layout changes)
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");

  // ✅ NEW: filtered rows (no layout changes)
  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();

    return rows.filter((r) => {
      const matchesSearch =
        q === "" ||
        r.id.toLowerCase().includes(q) ||
        r.subject.toLowerCase().includes(q);

      const matchesStatus =
        statusFilter === "All Status" || r.status === statusFilter;

      const matchesPriority =
        priorityFilter === "All Priorities" ||
        r.priorityText === priorityFilter;

      return matchesSearch && matchesStatus && matchesPriority;
    });
  }, [rows, search, statusFilter, priorityFilter]);

  // (optional) KPIs from filtered list:
  const kpis = useMemo(() => {
    const list = filteredRows;
    const unassigned = list.filter((r) => r.status === "Unassigned").length;
    const critical = list.filter((r) => r.priority === "critical").length;
    const overdue = list.filter((r) => r.status === "Overdue").length;
    const inProgress = list.filter((r) => r.status === "Assigned").length;

    return {
      openTickets: list.length,
      unassigned,
      critical,
      overdue,
      inProgress,
      resolvedToday: 0, // (keep as-is for now unless you have data)
    };
  }, [filteredRows]);

  const handleReset = () => {
    setSearch("");
    setStatusFilter("All Status");
    setPriorityFilter("All Priorities");
  };

  return (
    <Layout role="manager">
      <main className="mv-main">
        <section className="mv-kpiRow">
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">Open Tickets</span>
            <span className="mv-kpiValue">{kpis.openTickets}</span>
          </div>
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">Unassigned</span>
            <span className="mv-kpiValue">{kpis.unassigned}</span>
          </div>
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">Critical Priority</span>
            <span className="mv-kpiValue">{kpis.critical}</span>
          </div>
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">Overdue</span>
            <span className="mv-kpiValue">{kpis.overdue}</span>
          </div>
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">In Progress</span>
            <span className="mv-kpiValue">{kpis.inProgress}</span>
          </div>
          <div className="mv-kpiCard">
            <span className="mv-kpiLabel">Resolved Today</span>
            <span className="mv-kpiValue">{kpis.resolvedToday}</span>
          </div>
        </section>

        <section className="mv-searchSection">
          <div className="mv-searchWrapper">
            <span className="mv-searchIcon">🔍</span>
            <input
              type="text"
              className="mv-searchInput"
              placeholder="Search tickets by ID or summary..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </section>

        <section className="mv-filtersRow">
          <div className="mv-filterGroup">
            <div className="mv-selectWrapper">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option>All Status</option>
                <option>Submitted</option>
                <option>Assigned</option>
                <option>Escalated</option>
                <option>Resolved</option>
                <option>Unassigned</option>
                <option>Overdue</option>
              </select>
            </div>

            <div className="mv-selectWrapper">
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
              >
                <option>All Priorities</option>
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>
          </div>

          {/* Keeping your button style exactly.
              We’ll make it useful: Reset filters. */}
          <button className="mv-filterBtn" type="button" onClick={handleReset}>
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 4h18l-7 8v6l-4 2v-8L3 4z" fill="currentColor" />
            </svg>
            Reset
          </button>
        </section>

        <section className="mv-tableWrapper">
          <table className="mv-table">
            <thead>
              <tr>
                <th>TICKET ID</th>
                <th>SUBJECT</th>
                <th>PRIORITY</th>
                <th>STATUS</th>
                <th>ASSIGNEE</th>
                <th>ISSUE DATE</th>
                <th>RESPOND TIME</th>
                <th>RESOLVE TIME</th>
                <th>ACTION</th>
              </tr>
            </thead>

            <tbody>
              {filteredRows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link className="mv-complaintLink" to={`/manager/complaints/${r.id}`}>
                      {r.id}
                    </Link>
                  </td>
                  <td className="mv-subjectCell">{r.subject}</td>
                  <td>
                    <span className={`mv-pill mv-${r.priority}`}>{r.priorityText}</span>
                  </td>
                  <td>{r.status}</td>
                  <td>{r.assignee}</td>
                  <td>{r.issueDate}</td>
                  <td>{r.respondTime}</td>
                  <td>{r.resolveTime}</td>
                  <td>
                    <button className="mv-actionBtn" type="button">
                      {r.action}
                    </button>
                  </td>
                </tr>
              ))}

              {/* Optional: if nothing matches */}
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ padding: "18px", textAlign: "center" }}>
                    No tickets match your search/filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <div className="mv-footerTimestamp">20/11/2025 – 14:32</div>
      </main>
    </Layout>
  );
}
