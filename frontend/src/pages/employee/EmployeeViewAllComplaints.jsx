import React, { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import PriorityPill from "../../components/common/PriorityPill";
import ticketsData from "../../mock-data/employeeAllTickets.json";
import "./ViewAllComplaint.css";

const priorityOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 };
const statusOrder = {
  Unassigned: 1,
  Assigned: 2,
  Escalated: 3,
  Overdue: 4,
  Resolved: 5,
};

const timeToMinutes = (value) => {
  if (!value) return 0;
  const [num, unit] = String(value).split(" ");
  const n = Number(num);
  if (Number.isNaN(n)) return 0;
  if (unit?.startsWith("Minute")) return n;
  if (unit?.startsWith("Hour")) return n * 60;
  if (unit?.startsWith("Day")) return n * 1440;
  return 0;
};

const toDate = (raw) => {
  if (!raw) return null;

  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const [y, m, d] = raw.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) {
    const [d, m, y] = raw.split("/").map(Number);
    return new Date(y, m - 1, d);
  }

  const dt = new Date(raw);
  return Number.isNaN(dt.getTime()) ? null : dt;
};

export default function EmployeeViewAllComplaints() {
  const navigate = useNavigate();

  const [tickets, setTickets] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");
  const [sortConfig, setSortConfig] = useState({ key: null, direction: null });
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [showDateFilter, setShowDateFilter] = useState(false);

  useEffect(() => {
    try {
      setTickets(ticketsData.tickets || []);
    } catch (err) {
      console.error("Error loading local tickets JSON:", err);
    }
  }, []);

  const normalizedTickets = useMemo(() => {
    return (tickets || []).map((t) => {
      const issueDateRaw = t.issueDate ?? t.issue_date ?? t.createdAt ?? "";
      const responseTimeRaw =
        t.metrics?.meanTimeToRespond ?? t.response_time ?? t.responseTime ?? "";
      const resolutionTimeRaw =
        t.metrics?.meanTimeToResolve ??
        t.resolution_time ??
        t.resolutionTime ??
        "";

      return {
        ...t,
        _issueDateRaw: issueDateRaw,
        _responseTimeRaw: responseTimeRaw,
        _resolutionTimeRaw: resolutionTimeRaw,
      };
    });
  }, [tickets]);

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
    const q = (searchTerm ?? "").toString().toLowerCase().trim();

    let filtered = normalizedTickets.filter((t) => {
      const id = (t.ticketId ?? "").toString().toLowerCase();
      const subj = (t.subject ?? "").toString().toLowerCase();

      const matchesSearch = !q || id.includes(q) || subj.includes(q);
      const matchesStatus = statusFilter === "All Status" || t.status === statusFilter;
      const matchesPriority =
        priorityFilter === "All Priorities" || t.priority === priorityFilter;

      let matchesDate = true;
      const ticketDate = toDate(t._issueDateRaw);

      if (dateRange.from && ticketDate) {
        if (ticketDate < new Date(dateRange.from)) matchesDate = false;
      }
      if (dateRange.to && matchesDate && ticketDate) {
        if (ticketDate > new Date(dateRange.to)) matchesDate = false;
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
            aVal = toDate(a._issueDateRaw) || new Date(0);
            bVal = toDate(b._issueDateRaw) || new Date(0);
            break;

          case "responseTime":
            aVal = timeToMinutes(a._responseTimeRaw);
            bVal = timeToMinutes(b._responseTimeRaw);
            break;

          case "resolutionTime":
            aVal = timeToMinutes(a._resolutionTimeRaw);
            bVal = timeToMinutes(b._resolutionTimeRaw);
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
  }, [normalizedTickets, searchTerm, statusFilter, priorityFilter, dateRange, sortConfig]);

  const kpiCounts = useMemo(
    () => ({
      openTickets: filteredTickets.length,
      assignedToMe: filteredTickets.filter((t) => t.status === "Assigned").length,
      inProgress: filteredTickets.filter((t) => t.status === "Escalated").length,
      newTickets: filteredTickets.filter((t) => t.status === "Unassigned").length,
      highPriority: filteredTickets.filter(
        (t) => t.priority === "High" || t.priority === "Critical"
      ).length,
      overdueTickets: filteredTickets.filter((t) => t.status === "Overdue").length,
    }),
    [filteredTickets]
  );

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

        
        <section className="search-section-EV-VAC">
          <PillSearch
            value={searchTerm}
            onChange={(v) => {
              if (typeof v === "string") setSearchTerm(v);
              else setSearchTerm(v?.target?.value ?? "");
            }}
            placeholder="Search tickets by ID or summary..."
          />
        </section>

        
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

            
            <FilterPillButton onClick={() => setShowDateFilter(!showDateFilter)} />
          </div>
        </section>

        
        {showDateFilter && (
          <section className="filters-row-EV-VAC">
            <div className="filter-group-EV-VAC">
              <input
                type="date"
                value={dateRange.from}
                onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
              />
              <input
                type="date"
                value={dateRange.to}
                onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
              />
            </div>
          </section>
        )}

        
        <section className="kpi-row-EV-VAC">
          <KpiCard label="Open Tickets" value={kpiCounts.openTickets} />
          <KpiCard label="Assigned to Me" value={kpiCounts.assignedToMe} />
          <KpiCard label="In Progress" value={kpiCounts.inProgress} />
          <KpiCard label="New" value={kpiCounts.newTickets} />
          <KpiCard label="High Priority" value={kpiCounts.highPriority} />
          <KpiCard label="Overdue Tickets" value={kpiCounts.overdueTickets} />
        </section>

        
        <section className="table-wrapper-EV-VAC">
          <table className="complaints-table-EV-VAC">
            <thead>
              <tr>
                {[
                  { key: "ticketId", label: "Ticket ID" },
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
                <tr key={t.ticketId}>
                  <td
                    className="complaint-link-EV-VAC clickable"
                    onClick={() => navigate(`/employee/details/${t.ticketId}`)}
                  >
                    {t.ticketId}
                  </td>

                  <td>{t.subject}</td>

                  
                  <td>
                    <PriorityPill priority={t.priority} />
                  </td>

                  <td>{t.status}</td>

                  <td>{t._issueDateRaw}</td>
                  <td>{t._responseTimeRaw}</td>
                  <td>{t._resolutionTimeRaw}</td>

                  <td
                    className="arrow-cell-EV-VAC clickable"
                    onClick={() => navigate(`/employee/details/${t.ticketId}`)}
                  >
                    ➜
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </Layout>
  );
}