import { useMemo, useState, useEffect } from "react";
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

export default function ManagerViewComplaints() {
  const token = localStorage.getItem("access_token");

  // Tickets & Employees
  const [rows, setRows] = useState([]);
  const [employees, setEmployees] = useState([]);

  // Filters & Search
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");

  // Assignment modal state
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [activeTicketId, setActiveTicketId] = useState(null);
  const [originalAssignee, setOriginalAssignee] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState("");

  // More actions menu
  const [openMenuFor, setOpenMenuFor] = useState(null);

  // Departments for rerouting (dummy placeholder, replace with real list if needed)
  const departments = ["Maintenance", "IT", "Security", "Cleaning", "Facilities"];

  // Fetch tickets & employees with session token
  useEffect(() => {
    if (!token) return;

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };

    // Fetch complaints
    fetch(apiUrl("/manager/complaints"), { headers })
      .then((res) => {
        if (res.status === 401) return null;
        return res.json();
      })
      .then((data) => data && setRows(data || []))
      .catch((err) => {
        console.error("Failed to fetch tickets:", err);
        setRows([]);
      });

    // Fetch employees for assignment modal
    fetch(apiUrl("/manager/employees"), { headers })
      .then((res) => {
        if (res.status === 401) return null;
        return res.json();
      })
      .then((data) => data && setEmployees(data.map((e) => e.name)))
      .catch((err) => {
        console.error("Failed to fetch employees:", err);
        setEmployees([]);
      });
  }, [token]);

  // ------------------- Menu / Modal Handlers -------------------
  const toggleMenu = (ticketId) => setOpenMenuFor((prev) => (prev === ticketId ? null : ticketId));
  const closeMenu = () => setOpenMenuFor(null);

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

  const confirmAssignment = () => {
    if (!activeTicketId) return;

    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== activeTicketId) return r;

        if (!selectedEmployee) {
          return { ...r, assignee: "—", status: "Unassigned", action: "Assign" };
        }

        const nextStatus = r.status === "Unassigned" ? "Assigned" : r.status;
        return {
          ...r,
          assignee: selectedEmployee,
          status: nextStatus,
          action: "Reassign",
          reroutedTo: undefined,
        };
      })
    );

    closeAssignModal();
  };

  const handleReroute = (ticketId, dept) => {
    setRows((prev) =>
      prev.map((r) =>
        r.id === ticketId
          ? { ...r, status: "Unassigned", assignee: "—", action: "Assign", reroutedTo: dept }
          : r
      )
    );
    closeMenu();
  };

  const cancelReroute = (ticketId) => {
    setRows((prev) => prev.map((r) => (r.id === ticketId ? { ...r, reroutedTo: undefined } : r)));
    closeMenu();
  };

  // ------------------- Filtering & KPIs -------------------
  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesSearch = q === "" || r.id.toLowerCase().includes(q) || r.subject.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "All Status" || r.status === statusFilter;
      const matchesPriority = priorityFilter === "All Priorities" || r.priorityText === priorityFilter;
      return matchesSearch && matchesStatus && matchesPriority;
    });
  }, [rows, search, statusFilter, priorityFilter]);

  const kpis = useMemo(() => {
    const list = filteredRows;
    return {
      openTickets: list.length,
      unassigned: list.filter((r) => r.status === "Unassigned").length,
      critical: list.filter((r) => r.priority === "critical").length,
      overdue: list.filter((r) => r.status === "Overdue").length,
      inProgress: list.filter((r) => r.status === "Assigned").length,
      resolvedToday: 0,
    };
  }, [filteredRows]);

  const handleReset = () => {
    setSearch("");
    setStatusFilter("All Status");
    setPriorityFilter("All Priorities");
  };

  // ------------------- JSX -------------------
  return (
    <Layout role="manager">
      <main className="mv-main" onClick={closeMenu}>
        <section className="mv-header">
          <PageHeader
            title="View All Complaints"
            subtitle="Monitor all complaints, filter by status/priority, and open tickets for details."
          />
        </section>

        <section className="mv-kpiRow">
          <KpiCard label="Open Tickets" value={kpis.openTickets} />
          <KpiCard label="Unassigned" value={kpis.unassigned} />
          <KpiCard label="Critical Priority" value={kpis.critical} />
          <KpiCard label="Overdue" value={kpis.overdue} />
          <KpiCard label="In Progress" value={kpis.inProgress} />
          <KpiCard label="Resolved Today" value={kpis.resolvedToday} />
        </section>

        <section className="mv-searchSection">
          <PillSearch
            value={search}
            onChange={setSearch}
            placeholder="Search tickets by ID or summary..."
          />
        </section>

        <section className="mv-filtersRow">
          <div className="mv-filterGroup">
            <div className="mv-select">
              <PillSelect
                value={statusFilter}
                onChange={setStatusFilter}
                ariaLabel="Filter by status"
                options={[
                  { label: "All Status", value: "All Status" },
                  { label: "Submitted", value: "Submitted" },
                  { label: "Assigned", value: "Assigned" },
                  { label: "Escalated", value: "Escalated" },
                  { label: "Resolved", value: "Resolved" },
                  { label: "Unassigned", value: "Unassigned" },
                  { label: "Overdue", value: "Overdue" },
                ]}
              />
            </div>

            <div className="mv-select">
              <PillSelect
                value={priorityFilter}
                onChange={setPriorityFilter}
                ariaLabel="Filter by priority"
                options={[
                  { label: "All Priorities", value: "All Priorities" },
                  { label: "Low", value: "Low" },
                  { label: "Medium", value: "Medium" },
                  { label: "High", value: "High" },
                  { label: "Critical", value: "Critical" },
                ]}
              />
            </div>

            <div className="mv-reset">
              <FilterPillButton onClick={handleReset} label="Reset" />
            </div>
          </div>
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
                <th className="mv-moreHeader" aria-label="More actions column" />
              </tr>
            </thead>

            <tbody>
              {filteredRows.map((r, idx) => {
                const showMore = r.status === "Unassigned";
                const showCancelReroute = Boolean(r.reroutedTo);
                const openUp = idx >= filteredRows.length - 2;

                return (
                  <tr key={r.id}>
                    <td className="mv-cellTight">
                      <Link
                        className="mv-complaintLink"
                        to={`/manager/complaints/${r.id}`}
                        state={{ ticket: r }}
                      >
                        {r.id}
                      </Link>
                    </td>
                    <td className="mv-subjectCell mv-cellGrow">{r.subject}</td>
                    <td className="mv-cellTight">
                      <PriorityPill priority={r.priorityText} />
                    </td>
                    <td className="mv-cellTight">
                      <span
                        className={`mv-statusPill ${r.status === "Overdue" ? "mv-statusPill--overdue" : ""}`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="mv-cellMid">
                      <div className="mv-assigneeCell">
                        <div className="mv-ellipsis">{r.assignee}</div>
                        {r.reroutedTo && r.assignee === "—" && (
                          <span className="mv-reroutePill">Rerouted: {r.reroutedTo}</span>
                        )}
                      </div>
                    </td>
                    <td className="mv-cellTight">{r.issueDate}</td>
                    <td className="mv-cellTight">{r.respondTime}</td>
                    <td className="mv-cellTight">{r.resolveTime}</td>
                    <td className="mv-cellTight" onClick={(e) => e.stopPropagation()}>
                      <div className="mv-actionCell">
                        <button
                          className="mv-actionBtn"
                          type="button"
                          onClick={() => openAssignModal(r.id, r.assignee)}
                        >
                          {r.action}
                        </button>
                      </div>
                    </td>
                    <td className="mv-cellTight" onClick={(e) => e.stopPropagation()}>
                      <div className="mv-moreCell">
                        {showMore ? (
                          <>
                            <button
                              type="button"
                              className="mv-moreBtn"
                              aria-label="More actions"
                              onClick={() => toggleMenu(r.id)}
                            >
                              ⋯
                            </button>
                            {openMenuFor === r.id && (
                              <div className={`mv-menu ${openUp ? "mv-menu--up" : ""}`}>
                                <div className="mv-menuTitle">Reroute to</div>
                                {departments.map((d) => (
                                  <button
                                    key={d}
                                    type="button"
                                    className="mv-menuItem"
                                    onClick={() => handleReroute(r.id, d)}
                                  >
                                    <span className="mv-menuDot" />
                                    {d}
                                  </button>
                                ))}
                                {showCancelReroute && (
                                  <button
                                    type="button"
                                    className="mv-menuCancelReroute"
                                    onClick={() => cancelReroute(r.id)}
                                  >
                                    Cancel reroute
                                  </button>
                                )}
                              </div>
                            )}
                          </>
                        ) : (
                          <span className="mv-morePlaceholder" aria-hidden="true" />
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={10} className="mv-empty">
                    No tickets match your search/filters.
                  </td>
                </tr>
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
                <button className="mv-modalClear" type="button" onClick={clearSelection}>Unassign / Clear</button>
                <button className="mv-modalCancel" type="button" onClick={closeAssignModal}>Cancel</button>
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
