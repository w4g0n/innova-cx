import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import "./EmployeeDashboard.css";

export default function EmployeeDashboard() {
  const [employee, setEmployee] = useState(null);
  const [kpis, setKpis] = useState({});
  const [tickets, setTickets] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  const baseUrl = "https://7634c816-eb5c-4638-b90c-dc17b4c1eee7.mock.pstmn.io";

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch Dashboard
        const dashRes = await fetch(`${baseUrl}/api/employee/dashboard`, {
          headers: { Authorization: "Bearer employee-demo-token" },
        });
        const dashData = await dashRes.json();
        setEmployee(dashData.employee);
        setKpis(dashData.kpis);

        // Fetch Open Tickets
        const ticketRes = await fetch(`${baseUrl}/api/employee/tickets/open`, {
          headers: { Authorization: "Bearer employee-demo-token" },
        });
        const ticketData = await ticketRes.json();
        setTickets(ticketData.tickets);

        // Fetch Reports
        const reportRes = await fetch(`${baseUrl}/api/employee/reports`, {
          headers: { Authorization: "Bearer employee-demo-token" },
        });
        const reportData = await reportRes.json();
        setReports(reportData.reports);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <Layout role="employee"><main>Loading...</main></Layout>;

  return (
    <Layout role="employee">
      <div className="empDash">
        <PageHeader
          title={`Good Morning, ${employee.full_name}`}
          subtitle="Here’s your activity and assigned workload."
        />

        <section className="empDash__kpis">
          <KpiCard label="Tickets Assigned" value={kpis.ticketsAssigned} />
          <KpiCard label="In Progress" value={kpis.inProgress} />
          <KpiCard label="Resolved This Month" value={kpis.resolvedThisMonth} />
          <KpiCard label="Critical" value={kpis.critical} />
          <KpiCard label="Overdue" value={kpis.overdue} />
          <KpiCard label="New Today" value={kpis.newToday} />
        </section>

        <section className="empDash__grid">
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
                  {tickets.map((t) => (
                    <tr key={t.ticketId}>
                      <td>{t.ticketId}</td>
                      <td>{t.subject}</td>
                      <td><PriorityPill priority={t.priority} /></td>
                      <td>{t.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="empCard__actions">
              <Link className="empLinkBtn" to="/employee/complaints">
                View all my tickets →
              </Link>
            </div>
          </article>

          <aside className="empCard empReports">
            <h2 className="empCard__title">Reports</h2>
            <p className="empCard__subtitle">
              Monthly summaries auto-generated for you.
            </p>

            {reports.map((r) => (
              <ReportItem key={r.month} month={r.label} />
            ))}
          </aside>
        </section>
      </div>
    </Layout>
  );
}

function ReportItem({ month }) {
  return (
    <div className="empReportCard">
      <div className="empReportCard__month">{month}</div>
      <div className="empReportCard__desc">Performance Summary</div>
      <Link className="empReportCard__link" to="/employee/reports">
        View report →
      </Link>
    </div>
  );
}
