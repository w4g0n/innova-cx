import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import employeeDashboard from "../../mock-data/employeeDashboard.json";
import employeeOpenTickets from "../../mock-data/employeeOpenTickets.json";
import employeeMonthlyReports from "../../mock-data/employeeMonthlyReports.json";
import "./EmployeeDashboard.css";

function monthKeyToReportId(monthKey) {
  if (!monthKey || typeof monthKey !== "string") return "";
  const match = monthKey.match(/^(\d{4})-(\d{2})$/);
  if (!match) return "";

  const year = match[1];
  const mm = match[2];

  const map = {
    "01": "jan",
    "02": "feb",
    "03": "mar",
    "04": "apr",
    "05": "may",
    "06": "jun",
    "07": "jul",
    "08": "aug",
    "09": "sep",
    "10": "oct",
    "11": "nov",
    "12": "dec",
  };

  const abbr = map[mm];
  return abbr ? `${abbr}-${year}` : "";
}

export default function EmployeeDashboard() {
  const [employee, setEmployee] = useState(null);
  const [kpis, setKpis] = useState({});
  const [tickets, setTickets] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      // Set local JSON data directly
      setEmployee(employeeDashboard.employee);
      setKpis(employeeDashboard.kpis);
      setTickets(employeeOpenTickets.tickets);
      setReports(employeeMonthlyReports.reports);
    } catch (err) {
      console.error("Error loading local JSON data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  if (loading)
    return (
      <Layout role="employee">
        <main>Loading...</main>
      </Layout>
    );

  return (
    <Layout role="employee">
      <div className="empDash">
        <PageHeader
          title={`Good Morning, ${employee.name}`}
          subtitle="Here’s your activity and assigned workload."
        />

        {/* KPI Section */}
        <section className="empDash__kpis">
          <KpiCard label="Tickets Assigned" value={kpis.ticketsAssigned} />
          <KpiCard label="In Progress" value={kpis.inProgress} />
          <KpiCard label="Resolved This Month" value={kpis.resolvedThisMonth} />
          <KpiCard label="Critical" value={kpis.critical} />
          <KpiCard label="Overdue" value={kpis.overdue} />
          <KpiCard label="New Today" value={kpis.newToday} />
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
                  {tickets.map((t) => (
                    <tr key={t.ticketId}>
                      <td>{t.ticketId}</td>
                      <td>{t.subject}</td>
                      <td>
                        <PriorityPill priority={t.priority} />
                      </td>
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

          {/* Reports Section */}
          <aside className="empCard empReports">
            <h2 className="empCard__title">Reports</h2>
            <p className="empCard__subtitle">
              Monthly summaries auto-generated for you.
            </p>

            {reports.map((r) => (
              <ReportItem
                key={r.month || r.label}
                month={r.label}
                reportId={monthKeyToReportId(r.month)} 
              />
            ))}
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
