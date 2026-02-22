import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import PriorityPill from "../../components/common/PriorityPill";
import "./ViewAllComplaint.css";

const API_BASE = "http://localhost:8000/api";

const priorityOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 };

const statusOrder = {
  Unassigned: 1,
  Assigned: 2,
  "In Progress": 3,
  Escalated: 4,
  Overdue: 5,
  Resolved: 6,
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

function getStoredToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

export default function EmployeeViewAllComplaints() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ─── STUBS — Employee "Tickets Viewer and Management" page (/employee/complaints) ────────────
  // These controls are fully designed and the data layer is complete, but the UI elements
  // (search bar, filter dropdowns, date picker, sortable column headers) have not yet been
  // added to the JSX return below.
  //
  // HOW TO ACTIVATE a stub:
  //   • Remove the leading _ from any setter/variable you are wiring up — that's all it takes.
  //   • PillSearch  → onChange={_setSearchTerm}
  //   • PillSelect  → onChange={_setStatusFilter} / onChange={_setPriorityFilter}
  //   • Date inputs → onChange for from/to wired to _setDateRange({ ...dateRange, from/to: v })
  //   • Date filter toggle button → onClick={_setShowDateFilter(s => !s)}, show when _showDateFilter
  //   • Column <th> → onClick={() => _handleSort("fieldKey")} (supported keys listed on the handler)
  //   • Row clicks  → onClick={() => _navigate(`/employee/details/${t.ticketId}`)}
  //
  // All filtering + sorting logic in filteredTickets already reads these values — no changes
  // needed there once the setters are wired up.
  // ────────────────────────────────────────────────────────────────────────────────────────────
  const _navigate = useNavigate();
  const [searchTerm, _setSearchTerm] = useState("");
  const [statusFilter, _setStatusFilter] = useState("All Status");
  const [priorityFilter, _setPriorityFilter] = useState("All Priorities");
  const [sortConfig, _setSortConfig] = useState({ key: null, direction: null });
  const [dateRange, _setDateRange] = useState({ from: "", to: "" });
  const [_showDateFilter, _setShowDateFilter] = useState(false);

  // STUB: column sort handler — attach to <th onClick={() => _handleSort("fieldKey")} />.
  // Supported sort keys: "priority", "status", "issueDate", "responseTime", "resolutionTime".
  // Clicking the same column again toggles asc ↔ desc. First click on a new column is asc.
  const _handleSort = (key) => {
    _setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  useEffect(() => {
    const fetchTickets = async () => {
      const token = getStoredToken();
      if (!token) {
        setError("No auth token found.");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/employee/tickets`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          throw new Error(`Failed to fetch tickets (${res.status})`);
        }

        const data = await res.json();
        setTickets(data.tickets || []);
      } catch (err) {
        setError(err.message || "Failed to load tickets.");
      } finally {
        setLoading(false);
      }
    };

    fetchTickets();
  }, []);

  const normalizedTickets = useMemo(() => {
    return (tickets || []).map((t) => {
      const issueDateRaw = t.issueDate ?? t.issue_date ?? t.createdAt ?? "";
      const responseTimeRaw =
        t.metrics?.meanTimeToRespond ?? t.response_time ?? t.responseTime ?? "";
      const resolutionTimeRaw =
        t.metrics?.meanTimeToResolve ?? t.resolution_time ?? t.resolutionTime ?? "";

      return {
        ...t,
        _issueDateRaw: issueDateRaw,
        _responseTimeRaw: responseTimeRaw,
        _resolutionTimeRaw: resolutionTimeRaw,
      };
    });
  }, [tickets]);

  const filteredTickets = useMemo(() => {
    const q = searchTerm.toLowerCase().trim();

    let filtered = normalizedTickets.filter((t) => {
      const id = (t.ticketId ?? "").toLowerCase();
      const subj = (t.subject ?? "").toLowerCase();

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

  const kpiCounts = useMemo(() => {
    const notResolved = filteredTickets.filter((t) => t.status !== "Resolved");

    const isToday = (raw) => {
      const d = toDate(raw);
      if (!d) return false;
      const now = new Date();
      return (
        d.getFullYear() === now.getFullYear() &&
        d.getMonth() === now.getMonth() &&
        d.getDate() === now.getDate()
      );
    };

    return {
      openTickets: notResolved.length,
      assignedToMe: notResolved.length,
      inProgress: filteredTickets.filter(
        (t) => t.status === "Assigned" || t.status === "In Progress"
      ).length,
      newTickets: filteredTickets.filter((t) => isToday(t._issueDateRaw)).length,
      highPriority: notResolved.filter(
        (t) => t.priority === "High" || t.priority === "Critical"
      ).length,
      overdueTickets: filteredTickets.filter((t) => t.status === "Overdue").length,
    };
  }, [filteredTickets]);

  if (loading) return <Layout role="employee"><div>Loading tickets...</div></Layout>;
  if (error) return <Layout role="employee"><div>{error}</div></Layout>;

  return (
    <Layout role="employee">
      <main className="main-EV-VAC">
        <PageHeader
          title="Tickets Viewer and Management"
          subtitle="View, search, sort, and manage all complaints and requests assigned to you."
        />

        <section className="kpi-row-EV-VAC">
          <KpiCard label="Open Tickets" value={kpiCounts.openTickets} />
          <KpiCard label="In Progress" value={kpiCounts.inProgress} />
          <KpiCard label="New Today" value={kpiCounts.newTickets} />
          <KpiCard label="High Priority" value={kpiCounts.highPriority} />
          <KpiCard label="Overdue Tickets" value={kpiCounts.overdueTickets} />
        </section>
      </main>
    </Layout>
  );
}