import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import "./EmployeeDashboard.css";

const BACKEND_URL = "http://127.0.0.1:8000";

export default function EmployeeDashboard() {
  const EMPLOYEE_ID = "E001"; // replace with actual logged-in employee ID
  const [employee, setEmployee] = useState(null);
  const [kpis, setKpis] = useState({});
  const [tickets, setTickets] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/employee/dashboard/${EMPLOYEE_ID}`);
        const data = await res.json();

        setEmployee(data.employee);
        setKpis(data.kpis || {});
        setTickets(data.tickets || []);
        setReports(data.reports || []);
      } catch (err) {
        console.error("Error fetching dashboard:", err);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  if (loading)
    return (
      <Layout role="employee">
        <main className="loading">Loading...</main>
      </Layout>
    );

  return (
    <Layout role="employee">
      <div className="empDash">
        <PageHeader
          title={`Good Morning, ${employee.full_name ?? employee.name}`}
          subtitle="Here’s your activity and assigned workload."
        />

        {/* KPI Section */}
        <section className="empDash__kpis">
          <KpiCard label="Tickets Assigned" value={kpis.ticketsAssigned ?? 0} />
          <KpiCard label="In Progress" value={kpis.inProgress ?? 0} />
          <KpiCard label="Resolved This Month" value={kpis.resolvedThisMonth ?? 0} />
          <KpiCard label="Critical" value={kpis.critical ?? 0} />
          <KpiCard label="Overdue" value={kpis.overdue ?? 0} />
          <KpiCard label="New Today" value={kpis.newToday ?? 0} />
        </section>

        {/* Dashboard Grid */}
        <section className="empDash__grid">
          {/* Open Tickets */}
          <article className="empCard">
            <h2 className="empCard__title">Open Tickets Assigned to Me</h2>
            <p className="empCard__subtitle">
              Your active complaints that require action.
            </p>

            <div className="empTableWrap">
              <table className="empTable">
                <thead>
                  <tr>
                    <th>Ticket ID</th>
                    <th>Subject</th>
                    <th>Priority</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.length > 0 ? (
                    tickets.map((t) => (
                      <tr key={t.ticketId}>
                        <td>{t.ticketId}</td>
                        <td>{t.subject}</td>
                        <td><PriorityPill priority={t.priority} /></td>
                        <td>{t.status}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ textAlign: "center" }}>
                        No open tickets assigned.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="empCard__actions">
              <Link className="empLinkBtn" to="/employee/complaints">
                View all my tickets →
              </Link>
            </div>
          </article>

          {/* Reports Section */}
          <aside className="empCard empReports">
            <h2 className="empCard__title">Reports</h2>
            <p className="empCard__subtitle">
              Monthly summaries auto-generated for you.
            </p>

            {reports.length > 0 ? (
              reports.map((r) => (
                <ReportItem key={r.reportId} month={r.month} reportId={r.reportId} />
              ))
            ) : (
              <p style={{ textAlign: "center" }}>No reports available yet.</p>
            )}
          </aside>
        </section>
      </div>
    </Layout>
  );
}

// Report Card Component
function ReportItem({ month, reportId }) {
  return (
    <div className="empReportCard">
      <div className="empReportCard__month">{month}</div>
      <div className="empReportCard__desc">Performance Summary</div>

      <Link
        className="empReportCard__link"
        to={`/employee/reports?report=${encodeURIComponent(reportId)}`}
      >
        View report →
      </Link>
    </div>
  );
}
