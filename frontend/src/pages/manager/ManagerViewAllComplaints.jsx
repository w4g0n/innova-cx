import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import { Link } from "react-router-dom";
import "./ManagerViewAllComplaints.css";

import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import PriorityPill from "../../components/common/PriorityPill";

export default function ManagerViewComplaints() {
  const employees = [
    "Ahmed Hassan",
    "Maria Lopez",
    "Omar Ali",
    "Sara Ahmed",
    "Bilal Khan",
    "Fatima Noor",
    "Yousef Karim",
    "Khalid Musa",
  ];

  const departments = ["IT", "Facilities", "Security", "HR", "Admin"];

  const [rows, setRows] = useState([
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
  ]);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");

  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [activeTicketId, setActiveTicketId] = useState(null);
  const [originalAssignee, setOriginalAssignee] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState("");

  const [openMenuFor, setOpenMenuFor] = useState(null);

  const toggleMenu = (ticketId) => {
    setOpenMenuFor((prev) => (prev === ticketId ? null : ticketId));
  };

  const closeMenu = () => setOpenMenuFor(null);

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
    setRows((prev) =>
      prev.map((r) => (r.id === ticketId ? { ...r, reroutedTo: undefined } : r))
    );
    closeMenu();
  };

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

    if (!selectedEmployee) {
      setRows((prev) =>
        prev.map((r) =>
          r.id === activeTicketId
            ? { ...r, assignee: "—", status: "Unassigned", action: "Assign" }
            : r
        )
      );
      closeAssignModal();
      return;
    }

    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== activeTicketId) return r;
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

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();

    return rows.filter((r) => {
      const matchesSearch =
        q === "" || r.id.toLowerCase().includes(q) || r.subject.toLowerCase().includes(q);

      const matchesStatus = statusFilter === "All Status" || r.status === statusFilter;

      const matchesPriority =
        priorityFilter === "All Priorities" || r.priorityText === priorityFilter;

      return matchesSearch && matchesStatus && matchesPriority;
    });
  }, [rows, search, statusFilter, priorityFilter]);

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
      resolvedToday: 0,
    };
  }, [filteredRows]);

  const handleReset = () => {
    setSearch("");
    setStatusFilter("All Status");
    setPriorityFilter("All Priorities");
  };

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
          </div>

          <div className="mv-reset">
            <FilterPillButton onClick={handleReset} label="Reset" />
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
                        className={`mv-statusPill ${
                          r.status === "Overdue" ? "mv-statusPill--overdue" : ""
                        }`}
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
            <div
              className="mv-modal"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
            >
              <div className="mv-modalHeader">
                <h3 className="mv-modalTitle">Assign Ticket</h3>
                <button className="mv-modalClose" type="button" onClick={closeAssignModal}>
                  ✕
                </button>
              </div>

              <p className="mv-modalSub">
                Select an employee to assign <span className="mv-modalTicket">{activeTicketId}</span>
              </p>

              <div className="mv-employeeList">
                {employees.map((name) => (
                  <button
                    key={name}
                    type="button"
                    className={`mv-employeeItem ${
                      selectedEmployee === name ? "mv-employeeItem--selected" : ""
                    }`}
                    onClick={() => setSelectedEmployee(name)}
                  >
                    {name}
                  </button>
                ))}
              </div>

              <div className="mv-modalActions">
                <button className="mv-modalClear" type="button" onClick={clearSelection}>
                  Unassign / Clear
                </button>

                <button className="mv-modalCancel" type="button" onClick={closeAssignModal}>
                  Cancel
                </button>

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
