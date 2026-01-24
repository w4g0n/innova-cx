import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import "./ViewAllComplaint.css";

// SORT ORDER HELPERS
const priorityOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 };
const statusOrder = { Unassigned: 1, Assigned: 2, Escalated: 3, Overdue: 4, Resolved: 5 };

// Convert time strings like "30 Minutes" or "6 Hours" to minutes
const timeToMinutes = (value) => {
  if (!value) return 0;
  const [num, unit] = value.split(" ");
  const n = Number(num);
  if (unit.startsWith("Minute")) return n;
  if (unit.startsWith("Hour")) return n * 60;
  if (unit.startsWith("Day")) return n * 1440;
  return 0;
};

export default function EmployeeViewAllComplaints() {
  const navigate = useNavigate();

  // STATES
  const [tickets, setTickets] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [showDateFilter, setShowDateFilter] = useState(false);

  // FETCH TICKETS FROM POSTMAN MOCK SERVER
  useEffect(() => {
    fetch("https://7634c816-eb5c-4638-b90c-dc17b4c1eee7.mock.pstmn.io/tickets/overview", {
      headers: {
        "Authorization": "Bearer employee-demo-token"
      }
    })
      .then((res) => res.json())
      .then((data) => {
        setTickets(data.tickets || []);
      })
      .catch((err) => console.error("Error loading tickets JSON:", err));
  }, []);

  // SORT HANDLER
  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") direction = "desc";
    else if (sortConfig.key === key && sortConfig.direction === "desc") key = null, direction = null;
    setSortConfig({ key, direction });
  };

  // FILTER & SORTED TICKETS
  const filteredTickets = useMemo(() => {
    let filtered = tickets.filter((t) => {
      const matchesSearch =
        t.id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.subject?.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus = statusFilter === "All Status" || t.status === statusFilter;
      const matchesPriority = priorityFilter === "All Priorities" || t.priority === priorityFilter;

      let matchesDate = true;
      if (dateRange.from) {
        const [d, m, y] = t.issue_date?.split("/").map(Number) || [];
        if (new Date(y, m - 1, d) < new Date(dateRange.from)) matchesDate = false;
      }
      if (dateRange.to && matchesDate) {
        const [d, m, y] = t.issue_date?.split("/").map(Number) || [];
        if (new Date(y, m - 1, d) > new Date(dateRange.to)) matchesDate = false;
      }

      return matchesSearch && matchesStatus && matchesPriority && matchesDate;
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aVal, bVal;
        switch (sortConfig.key) {
          case "priority":
            aVal = priorityOrder[a.priority] || 0;
            bVal = priorityOrder[b.priority] || 0;
            break;
          case "status":
            aVal = statusOrder[a.status] || 0;
            bVal = statusOrder[b.status] || 0;
            break;
          case "issueDate":
            const [dA, mA, yA] = a.issue_date?.split("/").map(Number) || [];
            const [dB, mB, yB] = b.issue_date?.split("/").map(Number) || [];
            aVal = new Date(yA, mA - 1, dA);
            bVal = new Date(yB, mB - 1, dB);
            break;
          case "responseTime":
          case "resolutionTime":
            aVal = timeToMinutes(a[sortConfig.key]);
            bVal = timeToMinutes(b[sortConfig.key]);
            break;
          default:
            aVal = a[sortConfig.key];
            bVal = b[sortConfig.key];
        }

        if (aVal < bVal) return sortConfig.direction === "asc" ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [tickets, searchTerm, statusFilter, priorityFilter, dateRange, sortConfig]);

  // KPI COUNTS
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
    return sortConfig.direction === "asc" ? "   ↑" : "   ↓";
  };

  return (
    <Layout role="employee">
      <main className="main-EV-VAC">
        <PageHeader
          title="Tickets Viewer and Management"
          subtitle="View, search, sort, and manage all complaints and requests assigned to you."
        />

        {/* SEARCH */}
        <section className="search-section-EV-VAC">
          <PillSearch
            value={searchTerm}
            onChange={setSearchTerm}
            placeholder="Search tickets by ID or summary..."
          />
        </section>

        {/* FILTERS */}
        <section className="filters-row-EV-VAC">
          <div className="filter-group-EV-VAC">
            <PillSelect
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "All Status", label: "All Status" },
                { value: "Unassigned", label: "Unassigned" },
                { value: "Assigned", label: "Assigned" },
                { value: "Escalated", label: "Escalated" },
                { value: "Resolved", label: "Resolved" },
                { value: "Overdue", label: "Overdue" },
              ]}
            />
            <PillSelect
              value={priorityFilter}
              onChange={setPriorityFilter}
              options={[
                { value: "All Priorities", label: "All Priorities" },
                { value: "Low", label: "Low" },
                { value: "Medium", label: "Medium" },
                { value: "High", label: "High" },
                { value: "Critical", label: "Critical" },
              ]}
            />
          </div>
          <button className="filter-btn-EV-VAC" onClick={() => setShowDateFilter(!showDateFilter)}>
            Filters
          </button>
        </section>

        {/* DATE FILTER */}
        {showDateFilter && (
          <section className="filters-row-EV-VAC">
            <div className="filter-group-EV-VAC">
              <input type="date" value={dateRange.from} onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })} />
              <input type="date" value={dateRange.to} onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })} />
            </div>
          </section>
        )}

        {/* KPI CARDS */}
        <section className="kpi-row-EV-VAC">
          <KpiCard label="Open Tickets" value={kpiCounts.openTickets} />
          <KpiCard label="Assigned to Me" value={kpiCounts.assignedToMe} />
          <KpiCard label="In Progress" value={kpiCounts.inProgress} />
          <KpiCard label="New" value={kpiCounts.newTickets} />
          <KpiCard label="High Priority" value={kpiCounts.highPriority} />
          <KpiCard label="Overdue Tickets" value={kpiCounts.overdueTickets} />
        </section>

        {/* TICKETS TABLE */}
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
                  { key: null, label: "" }
                ].map((col) => (
                  <th key={col.label} onClick={() => col.key && handleSort(col.key)}>
                    {col.label}{col.key && getSortArrow(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredTickets.map((t) => (
                <tr key={t.id}>
                  <td className="complaint-link-EV-VAC clickable" onClick={() => navigate(`/employee/details/${t.id}`)}>
                    {t.id}
                  </td>
                  <td>{t.subject}</td>
                  <td><span className={`pill-EV-VAC ${t.priority?.toLowerCase()}`}>{t.priority}</span></td>
                  <td>{t.status}</td>
                  <td>{t.issue_date}</td>
                  <td>{t.response_time}</td>
                  <td>{t.resolution_time}</td>
                  <td className="arrow-cell-EV-VAC clickable" onClick={() => navigate(`/employee/details/${t.id}`)}>➜</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </Layout>
  );
}
