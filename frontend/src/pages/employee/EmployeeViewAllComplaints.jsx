import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import { apiUrl } from "../../config/apiBase";
import PriorityPill from "../../components/common/PriorityPill";
import {
  sanitizeText,
  sanitizeId,
  sanitizeSearchQuery,
  sanitizePriority,
  sanitizeTicketSource,
  MAX_SEARCH_LEN,
} from "./EmployeeSanitize";
import "./ViewAllComplaint.css";
import useScrollReveal from "../../utils/useScrollReveal";

const API_BASE = apiUrl("/api");

const priorityOrder = { Critical: 4, High: 3, Medium: 2, Low: 1 };

const statusOrder = {
  Unassigned:    1,
  Assigned:      2,
  "In Progress": 3,
  Escalated:     4,
  Overdue:       5,
  Resolved:      6,
};

// Allowlists for filter dropdowns — only these values are ever used in filter logic
const ALLOWED_STATUS_FILTERS   = ["Hide Resolved", "All Status", "Open", "In Progress", "Assigned", "Overdue", "Resolved"];
const ALLOWED_PRIORITY_FILTERS = ["All Priorities", "Low", "Medium", "High", "Critical"];
const ALLOWED_SORT_KEYS        = ["ticketId", "subject", "priority", "status", "issueDate", "responseTime", "resolutionTime"];

const timeToMinutes = (value) => {
  if (!value) return 0;
  const [num, unit] = String(value).split(" ");
  const n = Number(num);
  if (Number.isNaN(n)) return 0;
  if (unit?.startsWith("Minute")) return n;
  if (unit?.startsWith("Hour"))   return n * 60;
  if (unit?.startsWith("Day"))    return n * 1440;
  return 0;
};

const formatTimeLeft = (rawSeconds) => {
  if (rawSeconds == null) return "";
  const seconds = Math.max(0, Number(rawSeconds) || 0);
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60)   return `${minutes} Minutes left`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} Hours left`;
  return `${Math.floor(minutes / 1440)} Days left`;
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

const STATUS_CLASS = {
  "Open":        "ev-status-open",
  "Assigned":    "ev-status-assigned",
  "In Progress": "ev-status-inprogress",
  "Escalated":   "ev-status-escalated",
  "Overdue":     "ev-status-overdue",
  "Resolved":    "ev-status-resolved",
};

function getStoredToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token")        ||
    localStorage.getItem("jwt")          ||
    localStorage.getItem("authToken")    ||
    ""
  );
}

export default function EmployeeViewAllComplaints() {
  const revealRef = useScrollReveal();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  // Fixed internal error messages — raw err.message is never rendered
  const [error,   setError]   = useState("");

  const _navigate = useNavigate();
  const [searchTerm,      _setSearchTerm]      = useState("");
  const [statusFilter,    _setStatusFilter]    = useState("Hide Resolved");
  const [priorityFilter,  _setPriorityFilter]  = useState("All Priorities");
  const [sortConfig,      _setSortConfig]      = useState({ key: null, direction: null });
  const [dateRange,       _setDateRange]       = useState({ from: "", to: "" });
  const [_showDateFilter, _setShowDateFilter]  = useState(false);

  const _handleSort = (key) => {
    // Validate sort key against allowlist before using it in comparator
    if (!ALLOWED_SORT_KEYS.includes(key)) return;
    _setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  useEffect(() => {
    const fetchTickets = async () => {
      const token = getStoredToken();
      if (!token) {
        setTickets([]);
        setError("Unauthorized. Please log in again.");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/employee/tickets`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (res.status === 401) {
          setTickets([]);
          setError("Unauthorized. Please log in again.");
          return;
        }

        if (!res.ok) {
          // Never expose raw server response text — use a fixed message
          throw new Error("fetch_failed");
        }

        const data = await res.json();
        setTickets(data.tickets || []);
      } catch {
        setTickets([]);
        // Fixed string — never raw error.message
        setError("Failed to load tickets. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchTickets();
  }, []);

  const normalizedTickets = useMemo(() => {
    return (tickets || []).map((t) => {
      const issueDateRaw = t.issueDate ?? t.issue_date ?? t.createdAt ?? "";
      const responseLeftRaw =
        t.respond_time_left_seconds ?? t.respondTimeLeftSeconds ?? null;
      const resolveLeftRaw =
        t.resolve_time_left_seconds ?? t.resolveTimeLeftSeconds ?? null;
      const responseTimeRaw =
        formatTimeLeft(responseLeftRaw) ||
        t.metrics?.minTimeToRespond      ||
        t.min_time_to_respond            ||
        t.minTimeToRespond               ||
        "";
      const resolutionTimeRaw =
        formatTimeLeft(resolveLeftRaw) ||
        t.metrics?.minTimeToResolve    ||
        t.min_time_to_resolve          ||
        t.minTimeToResolve             ||
        "";

      return {
        ...t,
        // Sanitize all API fields at normalisation time — render-safe from here on
        _ticketId:          sanitizeId(t.ticketId, 48),
        _subject:           sanitizeText(t.subject, 200),
        _status:            sanitizeText(t.status,  40),
        _priority:          sanitizePriority(t.priority),
        _ticketSourceRaw:   sanitizeTicketSource(t.ticketSource),
        _issueDateRaw:      sanitizeText(issueDateRaw,      40),
        _responseTimeRaw:   sanitizeText(responseTimeRaw,   40),
        _resolutionTimeRaw: sanitizeText(resolutionTimeRaw, 40),
      };
    });
  }, [tickets]);

  const filteredTickets = useMemo(() => {
    // sanitizeSearchQuery caps + strips dangerous chars
    const q = sanitizeSearchQuery(searchTerm).toLowerCase();

    // Validate filter values against allowlists before use in logic
    const safeStatus   = ALLOWED_STATUS_FILTERS.includes(statusFilter)     ? statusFilter   : "Hide Resolved";
    const safePriority = ALLOWED_PRIORITY_FILTERS.includes(priorityFilter) ? priorityFilter : "All Priorities";

    let filtered = normalizedTickets.filter((t) => {
      const matchesSearch = !q ||
        t._ticketId.toLowerCase().includes(q) ||
        t._subject.toLowerCase().includes(q);

      const matchesStatus =
        safeStatus === "All Status"     ? true :
        safeStatus === "Hide Resolved"  ? t._status !== "Resolved" :
        t._status === safeStatus;

      const matchesPriority =
        safePriority === "All Priorities" || t._priority === safePriority;

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

    if (sortConfig.key && ALLOWED_SORT_KEYS.includes(sortConfig.key)) {
      filtered.sort((a, b) => {
        let aVal, bVal;

        switch (sortConfig.key) {
          case "priority":
            aVal = priorityOrder[a._priority] || 0;
            bVal = priorityOrder[b._priority] || 0;
            break;
          case "status":
            aVal = statusOrder[a._status] || 0;
            bVal = statusOrder[b._status] || 0;
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
        if (aVal > bVal) return sortConfig.direction === "asc" ?  1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [normalizedTickets, searchTerm, statusFilter, priorityFilter, dateRange, sortConfig]);

  const kpiCounts = useMemo(() => {
    const notResolved = filteredTickets.filter((t) => t._status !== "Resolved");

    const isToday = (raw) => {
      const d = toDate(raw);
      if (!d) return false;
      const now = new Date();
      return (
        d.getFullYear() === now.getFullYear() &&
        d.getMonth()    === now.getMonth()    &&
        d.getDate()     === now.getDate()
      );
    };

    return {
      openTickets:    notResolved.length,
      assignedToMe:   notResolved.length,
      inProgress:     filteredTickets.filter(
        (t) => t._status === "Assigned" || t._status === "In Progress"
      ).length,
      newTickets:     filteredTickets.filter((t) => isToday(t._issueDateRaw)).length,
      highPriority:   notResolved.filter(
        (t) => t._priority === "High" || t._priority === "Critical"
      ).length,
      overdueTickets: filteredTickets.filter((t) => t._status === "Overdue").length,
    };
  }, [filteredTickets]);

  if (loading)
    return <Layout role="employee"><div>Loading tickets...</div></Layout>;

  const hasActiveFilter =
    statusFilter !== "All Status" ||
    priorityFilter !== "All Priorities" ||
    searchTerm.trim() !== "";

  const rawOpenCount = normalizedTickets.filter((t) => t._status !== "Resolved").length;

  const allResolved =
    normalizedTickets.length > 0 && (
      (!hasActiveFilter && kpiCounts.openTickets === 0) ||
      (hasActiveFilter && filteredTickets.length === 0)
    );

  return (
    <Layout role="employee">
      <main className="main-EV-VAC" ref={revealRef}>
        <PageHeader
          title="Tickets Viewer and Management"
          subtitle="View, search, sort, and manage all complaints and requests assigned to you."
        />

        <section className="kpi-row-EV-VAC">
          <KpiCard label="Open Tickets"    value={kpiCounts.openTickets}    />
          <KpiCard label="In Progress"     value={kpiCounts.inProgress}     />
          <KpiCard label="New Today"       value={kpiCounts.newTickets}     />
          <KpiCard label="High Priority"   value={kpiCounts.highPriority}   />
          <KpiCard label="Overdue Tickets" value={kpiCounts.overdueTickets} />
        </section>

        {/* error is a fixed internal string — never raw network error text */}
        {error ? <div className="ev-warning">{error}</div> : null}

        <section className="search-section-EV-VAC">
          <PillSearch
            value={searchTerm}
            onChange={(v) => {
              // Cap search input client-side before it enters state
              const raw = typeof v === "string" ? v : (v?.target?.value ?? "");
              if (raw.length <= MAX_SEARCH_LEN) _setSearchTerm(raw);
            }}
            placeholder="Search tickets by ID or subject..."
            maxLength={MAX_SEARCH_LEN}
          />
        </section>

        <section className="filters-row-EV-VAC">
          <div className="filter-group-EV-VAC">
            <PillSelect
              value={statusFilter}
              onChange={(v) => {
                // Validate against allowlist before updating state
                if (ALLOWED_STATUS_FILTERS.includes(v)) _setStatusFilter(v);
              }}
              ariaLabel="Filter by status"
              options={[
                { label: "Hide Resolved", value: "Hide Resolved" },
                { label: "All Status",    value: "All Status"    },
                { label: "Open",          value: "Open"          },
                { label: "In Progress",   value: "In Progress"   },
                { label: "Assigned",      value: "Assigned"      },
                { label: "Overdue",       value: "Overdue"       },
                { label: "Resolved",      value: "Resolved"      },
              ]}
            />
            <PillSelect
              value={priorityFilter}
              onChange={(v) => {
                if (ALLOWED_PRIORITY_FILTERS.includes(v)) _setPriorityFilter(v);
              }}
              ariaLabel="Filter by priority"
              options={[
                { label: "All Priorities", value: "All Priorities" },
                { label: "Low",            value: "Low"            },
                { label: "Medium",         value: "Medium"         },
                { label: "High",           value: "High"           },
                { label: "Critical",       value: "Critical"       },
              ]}
            />
            <FilterPillButton
              onClick={() => {
                _setSearchTerm("");
                _setStatusFilter("Hide Resolved");
                _setPriorityFilter("All Priorities");
              }}
              label="Reset"
            />
          </div>
        </section>

        {allResolved ? (
          <section className="ev-all-resolved">
            <div className="ev-all-resolved__rings">
              <div className="ev-all-resolved__ring ev-all-resolved__ring--3" />
              <div className="ev-all-resolved__ring ev-all-resolved__ring--2" />
              <div className="ev-all-resolved__ring ev-all-resolved__ring--1" />
              <div className="ev-all-resolved__iconwrap">
                <svg className="ev-all-resolved__svg" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="32" cy="32" r="30" stroke="url(#evGrad)" strokeWidth="2.5" />
                  <polyline className="ev-all-resolved__checkpath" points="18,33 27,42 46,22" stroke="url(#evGrad)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                  <defs>
                    <linearGradient id="evGrad" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
                      <stop offset="0%"   stopColor="#16a34a" />
                      <stop offset="100%" stopColor="#4ade80" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </div>
            {hasActiveFilter ? (
              <>
                <h2 className="ev-all-resolved__title">No Tickets Found</h2>
                <p className="ev-all-resolved__sub">
                  No tickets match your current filters.
                  {rawOpenCount > 0 &&
                    ` There ${rawOpenCount === 1 ? "is" : "are"} still ${rawOpenCount} open ticket${rawOpenCount === 1 ? "" : "s"} in your queue.`}
                </p>
                <button
                  className="ev-all-resolved__btn"
                  onClick={() => {
                    _setSearchTerm("");
                    _setStatusFilter("Hide Resolved");
                    _setPriorityFilter("All Priorities");
                  }}
                >
                  Clear filters
                </button>
              </>
            ) : (
              <>
                <h2 className="ev-all-resolved__title">All Caught Up!</h2>
                <p className="ev-all-resolved__sub">Every ticket in your queue has been resolved. Great work.</p>
                <button
                  className="ev-all-resolved__btn"
                  onClick={() => _setStatusFilter("All Status")}
                >
                  View all tickets including resolved
                </button>
              </>
            )}
          </section>
        ) : (
          <section className="table-wrapper-EV-VAC">
            <table className="complaints-table-EV-VAC">
              <thead>
                <tr>
                  <th onClick={() => _handleSort("ticketId")}>Ticket ID</th>
                  <th onClick={() => _handleSort("subject")}>Subject</th>
                  <th onClick={() => _handleSort("priority")}>Priority</th>
                  <th onClick={() => _handleSort("status")}>Status</th>
                  <th>Source</th>
                  <th onClick={() => _handleSort("issueDate")}>Issue Date</th>
                  <th onClick={() => _handleSort("responseTime")}>Min Time To Respond</th>
                  <th onClick={() => _handleSort("resolutionTime")}>Min Time To Resolve</th>
                </tr>
              </thead>
              <tbody>
                {filteredTickets.map((t) => (
                  <tr
                    key={t._ticketId}
                    onClick={() =>
                      // _ticketId is already sanitizeId'd — encodeURIComponent as final safety layer
                      _navigate(`/employee/details/${encodeURIComponent(t._ticketId)}`)
                    }
                  >
                    <td>
                      <span className="complaint-link-EV-VAC">{t._ticketId}</span>
                    </td>
                    {/* All fields are sanitized during normalization above */}
                    <td>{t._subject}</td>
                    <td><PriorityPill priority={t._priority} /></td>
                    <td>
                      <span className={`ev-status-badge ${STATUS_CLASS[t._status] || "ev-status-assigned"}`}>
                        {t._status}
                      </span>
                    </td>
                    <td>{t._ticketSourceRaw}</td>
                    <td>{t._issueDateRaw}</td>
                    <td>{t._responseTimeRaw   || "—"}</td>
                    <td>{t._resolutionTimeRaw || "—"}</td>
                  </tr>
                ))}
                {filteredTickets.length === 0 ? (
                  <tr>
                    <td colSpan={8}>No tickets match your filters.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
        )}
      </main>
    </Layout>
  );
}