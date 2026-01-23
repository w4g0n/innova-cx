import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
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

// SORT HELPERS
const priorityOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 };
const statusOrder = { Unassigned: 1, Assigned: 2, Escalated: 3, Overdue: 4, Resolved: 5 };

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

  const [tickets] = useState(initialTickets);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [showDateFilter, setShowDateFilter] = useState(false);

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") direction = "desc";
    else if (sortConfig.key === key && sortConfig.direction === "desc") {
      key = null;
      direction = null;
    }
    setSortConfig({ key, direction });
  };

  const filteredTickets = useMemo(() => {
    let filtered = tickets.filter((t) => {
      const matchesSearch =
        t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.subject.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus = statusFilter === "All Status" || t.status === statusFilter;
      const matchesPriority = priorityFilter === "All Priorities" || t.priority === priorityFilter;

      let matchesDate = true;
      if (dateRange.from) {
        const [d, m, y] = t.issueDate.split("/").map(Number);
        if (new Date(y, m - 1, d) < new Date(dateRange.from)) matchesDate = false;
      }
      if (dateRange.to && matchesDate) {
        const [d, m, y] = t.issueDate.split("/").map(Number);
        if (new Date(y, m - 1, d) > new Date(dateRange.to)) matchesDate = false;
      }

      return matchesSearch && matchesStatus && matchesPriority && matchesDate;
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aVal, bVal;

        switch (sortConfig.key) {
          case "priority":
            aVal = priorityOrder[a.priority];
            bVal = priorityOrder[b.priority];
            break;
          case "status":
            aVal = statusOrder[a.status];
            bVal = statusOrder[b.status];
            break;
          case "issueDate":
            const [dA, mA, yA] = a.issueDate.split("/").map(Number);
            const [dB, mB, yB] = b.issueDate.split("/").map(Number);
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

        {/* KPI */}
        <section className="kpi-row-EV-VAC">
          <KpiCard label="Open Tickets" value={kpiCounts.openTickets} />
          <KpiCard label="Assigned to Me" value={kpiCounts.assignedToMe} />
          <KpiCard label="In Progress" value={kpiCounts.inProgress} />
          <KpiCard label="New" value={kpiCounts.newTickets} />
          <KpiCard label="High Priority" value={kpiCounts.highPriority} />
          <KpiCard label="Overdue Tickets" value={kpiCounts.overdueTickets} />
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
                  <th key={col.label} onClick={() => col.key && handleSort(col.key)}>
                    {col.label}
                    {col.key && getSortArrow(col.key)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {filteredTickets.map((t) => (
                <tr key={t.id}>
                  <td className="complaint-link-EV-VAC clickable" onClick={() => navigate(`/employee/details/${t.id}`)}>{t.id}</td>
                  <td>{t.subject}</td>
                  <td><span className={`pill-EV-VAC ${t.priority.toLowerCase()}`}>{t.priority}</span></td>
                  <td>{t.status}</td>
                  <td>{t.issueDate}</td>
                  <td>{t.responseTime}</td>
                  <td>{t.resolutionTime}</td>
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
