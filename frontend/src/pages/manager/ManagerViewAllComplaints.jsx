import { useMemo, useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerViewAllComplaints.css";

import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import PriorityPill from "../../components/common/PriorityPill";
import { apiUrl } from "../../config/apiBase";
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

function formatTicketSource(value) {
  return String(value || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
}

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, "": 4 };

// ── Toast ─────────────────────────────────────────────────────────────────────
function Toast({ toasts }) {
  return (
    <div className="mv-toastStack">
      {toasts.map((t) => (
        <div key={t.id} className={`mv-toast mv-toast--${t.type}`}>
          <span className="mv-toastIcon">
            {t.type === "success" ? "✓" : t.type === "error" ? "✕" : "ℹ"}
          </span>
          {t.message}
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = "success") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200);
  }, []);
  return { toasts, push };
}

// ── Sortable header ────────────────────────────────────────────────────────────
function SortableHeader({ label, col, sortCol, sortDir, onSort, className }) {
  const active = sortCol === col;
  const arrow = active ? (sortDir === "asc" ? " ▲" : " ▼") : " ⇅";
  return (
    <th
      className={className}
      style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
      onClick={() => onSort(col)}
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      {label}
      <span style={{ opacity: active ? 1 : 0.35, fontSize: "10px", marginLeft: "4px" }}>{arrow}</span>
    </th>
  );
}

// ── Status pill colours ────────────────────────────────────────────────────────
const STATUS_CLASS = {
  Submitted:  "mv-statusPill--submitted",
  Assigned:   "mv-statusPill--assigned",
  Escalated:  "mv-statusPill--escalated",
  Resolved:   "mv-statusPill--resolved",
  Unassigned: "mv-statusPill--unassigned",
  Overdue:    "mv-statusPill--overdue",
};

// ── KPI quick-filter map ───────────────────────────────────────────────────────
// Maps KPI label → { statusFilter, priorityFilter }
const KPI_FILTER = {
  "Open Tickets":     { statusFilter: null,       priorityFilter: null,       kpiKey: "openTickets" },
  "Unassigned":       { statusFilter: "Unassigned", priorityFilter: null,     kpiKey: "unassigned" },
  "Critical Priority":{ statusFilter: null,       priorityFilter: "Critical", kpiKey: "critical" },
  "Overdue":          { statusFilter: "Overdue",  priorityFilter: null,       kpiKey: "overdue" },
  "In Progress":      { statusFilter: null,       priorityFilter: null,       kpiKey: "inProgress" },
  "Resolved Today":   { statusFilter: "Resolved", priorityFilter: null,       kpiKey: "resolvedToday" },
};

export default function ManagerViewComplaints() {
  const revealRef = useScrollReveal();
  const token = getAuthToken();
  const { toasts, push: pushToast } = useToast();

  const [rows, setRows]           = useState([]);
  const [employees, setEmployees] = useState([]);
  const [search, setSearch]       = useState("");
  const [statusFilter, setStatusFilter]     = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");
  const [activeKpi, setActiveKpi] = useState(null); // label of active KPI filter

  const [sortCol, setSortCol] = useState("issueDate");
  const [sortDir, setSortDir] = useState("desc");

  const [isAssignOpen, setIsAssignOpen]     = useState(false);
  const [activeTicketId, setActiveTicketId] = useState(null);
  const [originalAssignee, setOriginalAssignee] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [openMenuFor, setOpenMenuFor] = useState(null);
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    if (!token) return;
    const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    fetch(apiUrl("/api/manager/complaints"), { headers })
      .then((res) => { if (res.status === 401) return null; return res.json(); })
      .then((data) => data && setRows(data || []))
      .catch((err) => { console.error("Failed to fetch tickets:", err); setRows([]); });

    fetch(apiUrl("/api/manager/departments"), { headers })
      .then((res) => res.json())
      .then((data) => Array.isArray(data) && setDepartments(data))
      .catch(() => {});

    fetch(apiUrl("/api/manager/employees"), { headers })
      .then((res) => { if (res.status === 401) return null; return res.json(); })
      .then((data) => data && setEmployees(data.map((e) => e.name)))
      .catch((err) => { console.error("Failed to fetch employees:", err); setEmployees([]); });
  }, [token]);

  // ── KPI click-to-filter ──────────────────────────────────────────────────────
  const handleKpiClick = (label) => {
    if (activeKpi === label) {
      // toggle off
      setActiveKpi(null);
      setStatusFilter("All Status");
      setPriorityFilter("All Priorities");
      return;
    }
    const cfg = KPI_FILTER[label];
    if (!cfg) return;
    setActiveKpi(label);
    setStatusFilter(cfg.statusFilter || "All Status");
    setPriorityFilter(cfg.priorityFilter || "All Priorities");
    setSearch("");
  };

  // ── Sort ─────────────────────────────────────────────────────────────────────
  const handleSort = (col) => {
  if (sortCol === col) {
    setSortDir((d) => (d === "asc" ? "desc" : "asc"));
  } else {
    setSortCol(col);
    setSortDir("asc");
  }
  };

  // ── Menu / Modal handlers ─────────────────────────────────────────────────────
  const toggleMenu = (ticketId) => setOpenMenuFor((prev) => (prev === ticketId ? null : ticketId));
  const closeMenu  = () => setOpenMenuFor(null);

  const openAssignModal = (ticketId, currentAssignee) => {
    const initial = currentAssignee && currentAssignee !== "—" ? currentAssignee : "";
    setActiveTicketId(ticketId);
    setOriginalAssignee(initial);
    setSelectedEmployee(initial);
    setIsAssignOpen(true);
    closeMenu();
  };

  const closeAssignModal = () => {
    setIsAssignOpen(false);
    setActiveTicketId(null);
    setOriginalAssignee("");
    setSelectedEmployee("");
  };

  const clearSelection = () => setSelectedEmployee("");

  const confirmAssignment = async () => {
    if (!activeTicketId) return;
    try {
      const res = await fetch(apiUrl(`/api/manager/complaints/${activeTicketId}/assign`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ employee_name: selectedEmployee || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        pushToast(`Failed to update assignment: ${err.detail || res.statusText}`, "error");
        return;
      }
      setRows((prev) =>
        prev.map((r) => {
          if (r.id !== activeTicketId) return r;
          if (!selectedEmployee) return { ...r, assignee: "—", status: "Unassigned", action: "Assign" };
          const nextStatus = r.status === "Unassigned" ? "Assigned" : r.status;
          return { ...r, assignee: selectedEmployee, status: nextStatus, action: "Reassign", reroutedTo: undefined };
        })
      );
      pushToast(
        selectedEmployee
          ? `Ticket assigned to ${selectedEmployee}`
          : "Ticket unassigned successfully",
        "success"
      );
    } catch (err) {
      console.error("Network error during assignment:", err);
      pushToast("Network error. Please try again.", "error");
    }
    closeAssignModal();
  };

  const handleReroute = async (ticketId, dept) => {
    try {
      const res = await fetch(apiUrl(`/api/manager/complaints/${ticketId}/department`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ department: dept }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        pushToast(`Failed to reroute: ${err.detail || res.statusText}`, "error");
        return;
      }
      setRows((prev) => prev.map((r) => r.id === ticketId ? { ...r, department: dept, reroutedTo: dept } : r));
      pushToast(`Ticket rerouted to ${dept}`, "success");
    } catch { pushToast("Network error during reroute.", "error"); }
    closeMenu();
  };

  const cancelReroute = (ticketId) => {
    setRows((prev) => prev.map((r) => (r.id === ticketId ? { ...r, reroutedTo: undefined } : r)));
    closeMenu();
  };

  // ── Filtering / KPIs / Sorting ────────────────────────────────────────────────
  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesSearch   = q === "" || r.id.toLowerCase().includes(q) || r.ticket_code?.toLowerCase().includes(q) || r.subject.toLowerCase().includes(q);
      const matchesStatus   = statusFilter === "All Status" || r.status === statusFilter;
      const matchesPriority = priorityFilter === "All Priorities" || r.priorityText === priorityFilter;
      // "In Progress" KPI = not resolved and not unassigned
      if (activeKpi === "In Progress") {
        return matchesSearch && !["Resolved", "Unassigned"].includes(r.status);
      }
      // "Open Tickets" KPI = not resolved
      if (activeKpi === "Open Tickets") {
        return matchesSearch && r.status !== "Resolved";
      }
      return matchesSearch && matchesStatus && matchesPriority;
    });
  }, [rows, search, statusFilter, priorityFilter, activeKpi]);

  const sortedRows = useMemo(() => {
    const sorted = [...filteredRows];
    sorted.sort((a, b) => {
      let aVal, bVal;
      switch (sortCol) {
        case "ticket_code": aVal = a.ticket_code || ""; bVal = b.ticket_code || ""; break;
        case "subject":     aVal = a.subject || "";     bVal = b.subject || "";     break;
        case "priority":    aVal = PRIORITY_ORDER[a.priority] ?? 4; bVal = PRIORITY_ORDER[b.priority] ?? 4; break;
        case "status":      aVal = a.status || "";      bVal = b.status || "";      break;
        case "source":      aVal = formatTicketSource(a.ticketSource); bVal = formatTicketSource(b.ticketSource); break;
        case "assignee":    aVal = a.assignee || "";    bVal = b.assignee || "";    break;
        case "issueDate":   aVal = a.issueDate || "";   bVal = b.issueDate || "";   break;
        case "respondTime": aVal = a.respondTime || ""; bVal = b.respondTime || ""; break;
        case "resolveTime": aVal = a.resolveTime || ""; bVal = b.resolveTime || ""; break;
        default:            return 0;
      }
      if (typeof aVal === "number") return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      return sortDir === "asc" ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
    });
    return sorted;
  }, [filteredRows, sortCol, sortDir]);

  const kpis = useMemo(() => {
    const today = new Date().toDateString();
    return {
      openTickets:   rows.filter((r) => r.status !== "Resolved").length,
      unassigned:    rows.filter((r) => r.status === "Unassigned").length,
      critical:      rows.filter((r) => r.priority === "critical" && r.status !== "Resolved").length,
      overdue:       rows.filter((r) => r.status === "Overdue").length,
      inProgress:    rows.filter((r) => !["Resolved", "Unassigned"].includes(r.status)).length,
      resolvedToday: rows.filter((r) => r.resolvedAt && new Date(r.resolvedAt).toDateString() === today).length,
    };
  }, [rows]);

  const handleReset = () => {
    setSearch("");
    setStatusFilter("All Status");
    setPriorityFilter("All Priorities");
    setActiveKpi(null);
  };

  const shProps = { sortCol, sortDir, onSort: handleSort };

  // ── JSX ───────────────────────────────────────────────────────────────────────
  return (
    <Layout role="manager">
      <Toast toasts={toasts} />
      <main className="mv-main" ref={revealRef} onClick={closeMenu}>
        <section className="mv-header">
          <PageHeader
            title="View All Complaints"
            subtitle="Monitor all complaints, filter by status/priority, and open tickets for details."
          />
        </section>

        {/* KPI cards — clickable to filter */}
        <section className="mv-kpiRow">
          {[
            { label: "Open Tickets",      value: kpis.openTickets },
            { label: "Unassigned",        value: kpis.unassigned },
            { label: "Critical Priority", value: kpis.critical },
            { label: "Overdue",           value: kpis.overdue },
            { label: "In Progress",       value: kpis.inProgress },
            { label: "Resolved Today",    value: kpis.resolvedToday },
          ].map(({ label, value }) => (
            <div
              key={label}
              className={`mv-kpiWrap ${activeKpi === label ? "mv-kpiWrap--active" : ""}`}
              onClick={() => handleKpiClick(label)}
              title={`Filter by: ${label}`}
            >
              <KpiCard label={label} value={value} />
            </div>
          ))}
        </section>

        <section className="mv-searchSection">
          <PillSearch value={search} onChange={setSearch} placeholder="Search tickets by ID or summary..." />
        </section>

        <section className="mv-filtersRow">
          <div className="mv-filterGroup">
            <div className="mv-select">
              <PillSelect
                value={statusFilter}
                onChange={(v) => { setStatusFilter(v); setActiveKpi(null); }}
                ariaLabel="Filter by status"
                options={[
                  { label: "All Status",  value: "All Status" },
                  { label: "Submitted",   value: "Submitted" },
                  { label: "Assigned",    value: "Assigned" },
                  { label: "Escalated",   value: "Escalated" },
                  { label: "Resolved",    value: "Resolved" },
                  { label: "Unassigned",  value: "Unassigned" },
                  { label: "Overdue",     value: "Overdue" },
                ]}
              />
            </div>
            <div className="mv-select">
              <PillSelect
                value={priorityFilter}
                onChange={(v) => { setPriorityFilter(v); setActiveKpi(null); }}
                ariaLabel="Filter by priority"
                options={[
                  { label: "All Priorities", value: "All Priorities" },
                  { label: "Low",            value: "Low" },
                  { label: "Medium",         value: "Medium" },
                  { label: "High",           value: "High" },
                  { label: "Critical",       value: "Critical" },
                ]}
              />
            </div>
            <div className="mv-reset">
              <FilterPillButton onClick={handleReset} label="Reset" />
            </div>
          </div>

          {/* Live result count */}
          <span className="mv-resultCount">
            {activeKpi && (
              <span className="mv-resultCount__kpi">
                {activeKpi} ·{" "}
              </span>
            )}
            Showing <strong>{sortedRows.length}</strong> of <strong>{rows.length}</strong> tickets
          </span>
        </section>

        <section className="mv-tableWrapper">
          <table className="mv-table">
            <thead>
              <tr>
                <SortableHeader label="TICKET ID"    col="ticket_code"  {...shProps} className="mv-cellTight" />
                <SortableHeader label="SUBJECT"      col="subject"      {...shProps} className="mv-cellGrow" />
                <SortableHeader label="PRIORITY"     col="priority"     {...shProps} className="mv-cellTight" />
                <SortableHeader label="STATUS"       col="status"       {...shProps} className="mv-cellTight" />
                <SortableHeader label="SOURCE"       col="source"       {...shProps} className="mv-cellTight" />
                <SortableHeader label="ASSIGNEE"     col="assignee"     {...shProps} className="mv-cellMid" />
                <SortableHeader label="ISSUE DATE"   col="issueDate"    {...shProps} className="mv-cellTight" />
                <SortableHeader label="RESPOND TIME" col="respondTime"  {...shProps} className="mv-cellTight" />
                <SortableHeader label="RESOLVE TIME" col="resolveTime"  {...shProps} className="mv-cellTight" />
                <th className="mv-cellTight">ACTION</th>
                <th className="mv-moreHeader" aria-label="More actions column" />
              </tr>
            </thead>

            <tbody>
              {sortedRows.map((r, idx) => {
                const showCancelReroute = Boolean(r.reroutedTo);
                const openUp = idx >= sortedRows.length - 2;
                const isCriticalOverdue = r.priority === "critical" && r.status === "Overdue";
                const statusClass = STATUS_CLASS[r.status] || "";

                return (
                  <tr
                    key={r.id}
                    className={isCriticalOverdue ? "mv-row--criticalOverdue" : ""}
                  >
                    <td className="mv-cellTight">
                      <Link className="mv-complaintLink" to={`/manager/complaints/${r.id}`} state={{ ticket: r }}>
                        {r.ticket_code}
                      </Link>
                    </td>
                    <td className="mv-subjectCell mv-cellGrow">{r.subject}</td>
                    <td className="mv-cellTight"><PriorityPill priority={r.priorityText} /></td>
                    <td className="mv-cellTight">
                      <span className={`mv-statusPill ${statusClass}`}>{r.status}</span>
                    </td>
                    <td className="mv-cellTight">{formatTicketSource(r.ticketSource)}</td>
                    <td className="mv-cellMid">
                      <div className="mv-assigneeCell">
                        <div className="mv-ellipsis">{r.assignee}</div>
                        {r.reroutedTo && <span className="mv-reroutePill">Rerouted: {r.reroutedTo}</span>}
                      </div>
                    </td>
                    <td className="mv-cellTight">{r.issueDate}</td>
                    <td className="mv-cellTight">{r.respondTime}</td>
                    <td className="mv-cellTight">{r.resolveTime}</td>
                    <td className="mv-cellTight" onClick={(e) => e.stopPropagation()}>
                      <div className="mv-actionCell">
                        <button className="mv-actionBtn" type="button" onClick={() => openAssignModal(r.id, r.assignee)}>
                          {r.action}
                        </button>
                      </div>
                    </td>
                    <td className="mv-cellTight" onClick={(e) => e.stopPropagation()}>
                      <div className="mv-moreCell">
                        <button type="button" className="mv-moreBtn" aria-label="More actions" onClick={() => toggleMenu(r.id)}>⋯</button>
                        {openMenuFor === r.id && (
                          <div className={`mv-menu ${openUp ? "mv-menu--up" : ""}`}>
                            <div className="mv-menuTitle">Reroute to</div>
                            {departments.map((d) => (
                              <button key={d} type="button" className="mv-menuItem" onClick={() => handleReroute(r.id, d)}>
                                <span className="mv-menuDot" />{d}
                              </button>
                            ))}
                            {showCancelReroute && (
                              <button type="button" className="mv-menuCancelReroute" onClick={() => cancelReroute(r.id)}>
                                Cancel reroute
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {sortedRows.length === 0 && (
                <tr><td colSpan={11} className="mv-empty">No tickets match your search/filters.</td></tr>
              )}
            </tbody>
          </table>
        </section>

        {isAssignOpen && (
          <div className="mv-modalOverlay" onClick={closeAssignModal} role="presentation">
            <div className="mv-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
              <div className="mv-modalHeader">
                <h3 className="mv-modalTitle">Assign Ticket</h3>
                <button className="mv-modalClose" type="button" onClick={closeAssignModal}>✕</button>
              </div>
              <p className="mv-modalSub">
                Select an employee to assign <span className="mv-modalTicket">{activeTicketId}</span>
              </p>
              <div className="mv-employeeList">
                {employees.map((name) => (
                  <button
                    key={name}
                    type="button"
                    className={`mv-employeeItem ${selectedEmployee === name ? "mv-employeeItem--selected" : ""}`}
                    onClick={() => setSelectedEmployee(name)}
                  >
                    {name}
                  </button>
                ))}
              </div>
              <div className="mv-modalActions">
                <button className="mv-modalClear"   type="button" onClick={clearSelection}>Unassign / Clear</button>
                <button className="mv-modalCancel"  type="button" onClick={closeAssignModal}>Cancel</button>
                <button
                  className="mv-modalConfirm"
                  type="button"
                  disabled={selectedEmployee === originalAssignee}
                  onClick={confirmAssignment}
                >
                  {selectedEmployee ? "Confirm Assignment" : "Confirm Unassign"}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </Layout>
  );
}