import React, { useState, useMemo } from "react";
import Layout from "../../components/Layout";
import "./ViewAllComplaint.css";

const initialTickets = [
  { id: "CX-1122", subject: "Air conditioning not working", priority: "Critical", status: "Unassigned", issueDate: "19/11/2025", responseTime: "30 Minutes", resolutionTime: "6 Hours" },
  { id: "CX-3862", subject: "Water leakage in pantry", priority: "Critical", status: "Overdue", issueDate: "18/11/2025", responseTime: "30 Minutes", resolutionTime: "6 Hours" },
  { id: "CX-4587", subject: "Wi-Fi connection unstable", priority: "High", status: "Escalated", issueDate: "19/11/2025", responseTime: "1 Hour", resolutionTime: "18 Hours" },
  { id: "CX-4630", subject: "Lift stopping between floors", priority: "High", status: "Assigned", issueDate: "18/11/2025", responseTime: "1 Hour", resolutionTime: "18 Hours" },
  { id: "CX-4701", subject: "Cleaning service missed schedule", priority: "Medium", status: "Unassigned", issueDate: "16/11/2025", responseTime: "3 Hours", resolutionTime: "2 Days" },
  { id: "CX-4725", subject: "Parking access card not working", priority: "Medium", status: "Overdue", issueDate: "13/11/2025", responseTime: "3 Hours", resolutionTime: "2 Days" },
  { id: "CX-4780", subject: "Noise from maintenance works", priority: "Low", status: "Escalated", issueDate: "9/11/2025", responseTime: "6 Hours", resolutionTime: "3 Days" },
  { id: "CX-4801", subject: "Projector not working in conference room", priority: "High", status: "Assigned", issueDate: "21/11/2025", responseTime: "1 Hour", resolutionTime: "12 Hours" },
  { id: "CX-4812", subject: "Server room temperature high", priority: "Critical", status: "Unassigned", issueDate: "20/11/2025", responseTime: "15 Minutes", resolutionTime: "4 Hours" },
  { id: "CX-4823", subject: "Printer malfunction in HR office", priority: "Medium", status: "Resolved", issueDate: "18/11/2025", responseTime: "2 Hours", resolutionTime: "1 Day" },
  { id: "CX-4834", subject: "Coffee machine leaking", priority: "Low", status: "Unassigned", issueDate: "17/11/2025", responseTime: "6 Hours", resolutionTime: "2 Days" },
  { id: "CX-4845", subject: "Security badge not granting access", priority: "High", status: "Escalated", issueDate: "19/11/2025", responseTime: "1 Hour", resolutionTime: "12 Hours" },
  { id: "CX-4856", subject: "Fire alarm sensor faulty", priority: "Critical", status: "Assigned", issueDate: "15/11/2025", responseTime: "15 Minutes", resolutionTime: "6 Hours" },
  { id: "CX-4867", subject: "Elevator button not responding", priority: "Medium", status: "Overdue", issueDate: "12/11/2025", responseTime: "3 Hours", resolutionTime: "1 Day" },
  { id: "CX-4878", subject: "Lighting issue in parking lot", priority: "Low", status: "Unassigned", issueDate: "10/11/2025", responseTime: "6 Hours", resolutionTime: "2 Days" }
];

export default function EmployeeViewAllComplaints() {
  const [tickets] = useState(initialTickets);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [showDateFilter, setShowDateFilter] = useState(false);

  // --- Sorting ---
  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") direction = "desc";
    else if (sortConfig.key === key && sortConfig.direction === "desc") {
      key = null;
      direction = null;
    }
    setSortConfig({ key, direction });
  };

  // --- Filtered & Sorted Tickets ---
  const filteredTickets = useMemo(() => {
    let filtered = tickets.filter((t) => {
      const matchesSearch =
        t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.subject.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === "All Status" || t.status === statusFilter;
      const matchesPriority = priorityFilter === "All Priorities" || t.priority === priorityFilter;

      // Date filter
      let matchesDate = true;
      if (dateRange.from) {
        const [d, m, y] = t.issueDate.split("/").map(Number);
        const issue = new Date(y, m - 1, d);
        const from = new Date(dateRange.from);
        if (issue < from) matchesDate = false;
      }
      if (dateRange.to && matchesDate) {
        const [d, m, y] = t.issueDate.split("/").map(Number);
        const issue = new Date(y, m - 1, d);
        const to = new Date(dateRange.to);
        if (issue > to) matchesDate = false;
      }

      return matchesSearch && matchesStatus && matchesPriority && matchesDate;
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];

        if (sortConfig.key === "issueDate") {
          const [dA, mA, yA] = aVal.split("/").map(Number);
          const [dB, mB, yB] = bVal.split("/").map(Number);
          aVal = new Date(yA, mA - 1, dA);
          bVal = new Date(yB, mB - 1, dB);
        }

        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [tickets, searchTerm, statusFilter, priorityFilter, dateRange, sortConfig]);

  // --- KPI Counts ---
  const kpiCounts = useMemo(() => ({
    openTickets: filteredTickets.length,
    assignedToMe: filteredTickets.filter((t) => t.status === "Assigned").length,
    inProgress: filteredTickets.filter((t) => t.status === "Escalated").length,
    newTickets: filteredTickets.filter((t) => t.status === "Unassigned").length,
    highPriority: filteredTickets.filter((t) => t.priority === "High" || t.priority === "Critical").length,
    overdueTickets: filteredTickets.filter((t) => t.status === "Overdue").length,
  }), [filteredTickets]);

  const getSortArrow = (key) => {
    if (sortConfig.key !== key) return "   ↑↓";
    return sortConfig.direction === "asc" ? "   ↑" : sortConfig.direction === "desc" ? "   ↓" : "";
    

  };

  return (
    <Layout role="employee">
      <main className="main-EV-VAC">

        {/* TOP BAR */}
        <header className="top-bar">
          <div>
            <h1 className="page-title">Tickets Viewer and Management</h1>
            <p className="page-subtitle">
              View, search, sort, and manage all complaints and requests assigned to you.
            </p>
          </div>
        </header>



        {/* SEARCH */}
        <section className="search-section-EV-VAC">
          <div className="search-wrapper-EV-VAC">
            <span className="search-icon-EV-VAC">🔍</span>
            <input
              type="text"
              className="search-input-EV-VAC"
              placeholder="Search tickets by ID or summary..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </section>

        {/* FILTERS */}
        <section className="filters-row-EV-VAC">
          <div className="filter-group-EV-VAC">
            <div className="select-wrapper-EV-VAC">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option>All Status</option>
                <option>Submitted</option>
                <option>Assigned</option>
                <option>Escalated</option>
                <option>Resolved</option>
              </select>
            </div>

            <div className="select-wrapper-EV-VAC">
              <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
                <option>All Priorities</option>
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>
          </div>

          <button
            className="filter-btn-EV-VAC"
            onClick={() => setShowDateFilter(!showDateFilter)}
          >
            Filters
          </button>
        </section>

        {/* Date Range Picker */}
        {showDateFilter && (
          <section className="filters-row-EV-VAC">
            <div className="filter-group-EV-VAC">
              <label>
                From:{" "}
                <input
                  type="date"
                  value={dateRange.from}
                  onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
                />
              </label>
              <label>
                To:{" "}
                <input
                  type="date"
                  value={dateRange.to}
                  onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
                />
              </label>
              <button
                className="filter-btn-EV-VAC"
                onClick={() => setDateRange({ from: "", to: "" })}
              >
                Reset Dates
              </button>
            </div>
          </section>
        )}

        {/* KPI ROW */}
        <section className="kpi-row-EV-VAC">
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">Open Tickets</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.openTickets}</span>
          </div>
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">Assigned to Me</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.assignedToMe}</span>
          </div>
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">In Progress</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.inProgress}</span>
          </div>
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">New</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.newTickets}</span>
          </div>
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">High Priority</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.highPriority}</span>
          </div>
          <div className="kpi-card-EV-VAC">
            <span className="kpi-label-EV-VAC">Overdue Tickets</span>
            <span className="kpi-value-EV-VAC">{kpiCounts.overdueTickets}</span>
          </div>
        </section>

        {/* TABLE */}
        <section className="table-wrapper-EV-VAC">
          <table className="complaints-table-EV-VAC">
            <thead>
              <tr>
                {[
                  { key: "id", label: "Ticket ID" },
                  { key: "subject", label: "Subject" },
                  { key: "priority", label: "Priority" },
                  { key: "status", label: "Status" },
                  { key: "issueDate", label: "Issue Date" },
                  { key: "responseTime", label: "Response Time" },
                  { key: "resolutionTime", label: "Resolution Time" },
                  { key: null, label: "" },
                ].map((col) => (
                  <th key={col.key || col.label} onClick={() => col.key && handleSort(col.key)}>
                    {col.label}
                    {col.key && getSortArrow(col.key)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {filteredTickets.map((t) => (
                <tr key={t.id}>
                  <td className="complaint-link-EV-VAC">{t.id}</td>
                  <td>{t.subject}</td>
                  <td>
                    <span className={`pill-EV-VAC ${t.priority.toLowerCase()}`}>{t.priority}</span>
                  </td>
                  <td>{t.status}</td>
                  <td>{t.issueDate}</td>
                  <td>{t.responseTime}</td>
                  <td>{t.resolutionTime}</td>
                  <td className="arrow-cell-EV-VAC">➜</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <div className="footer-timestamp-EV-VAC">
          <span id="timestamp">20/11/2025 – 14:32</span>
        </div>
      </main>
    </Layout>
  );
}
