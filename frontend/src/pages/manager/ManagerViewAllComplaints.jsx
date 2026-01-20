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

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [priorityFilter, setPriorityFilter] = useState("All Priorities");

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
      <main className="mv-main">
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
              </tr>
            </thead>

            <tbody>
              {filteredRows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link
                      className="mv-complaintLink"
                      to={`/manager/complaints/${r.id}`}
                    >
                      {r.id}
                    </Link>
                  </td>
                  <td className="mv-subjectCell">{r.subject}</td>
                  <td>
                    <PriorityPill priority={r.priorityText} />
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

              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={9} className="mv-empty">
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
