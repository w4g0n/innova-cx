import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./EmployeeDashboard.css";

export default function EmployeeDashboard() {
  return (
    <Layout role="employee">
      <div className="empDash">
        <header className="empDash__header">
          <div>
            <h1 className="empDash__title">Good Morning, Mayed Sharaf</h1>
            <p className="empDash__subtitle">
              Here’s your activity and assigned workload.
            </p>
          </div>
        </header>

        <section className="empDash__kpis">
          <Kpi value="7" label="Tickets Assigned" />
          <Kpi value="2" label="In Progress" />
          <Kpi value="48" label="Resolved This Month" />
          <Kpi value="2" label="Critical" />
          <Kpi value="2" label="Overdue" />
          <Kpi value="1" label="New Today" />
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
                  <tr>
                    <td>CX-3201</td>
                    <td>AC not cooling – Office 302</td>
                    <td>
                      <span className="empPill empPill--critical">Critical</span>
                    </td>
                    <td>In Progress</td>
                  </tr>

                  <tr>
                    <td>CX-3210</td>
                    <td>Water leak near lobby</td>
                    <td>
                      <span className="empPill empPill--high">High</span>
                    </td>
                    <td>In Progress</td>
                  </tr>

                  <tr>
                    <td>CX-3244</td>
                    <td>Light flickering in corridor</td>
                    <td>
                      <span className="empPill empPill--medium">Medium</span>
                    </td>
                    <td>Assigned</td>
                  </tr>

                  <tr>
                    <td>CX-3302</td>
                    <td>Cleaning missed in meeting room</td>
                    <td>
                      <span className="empPill empPill--low">Low</span>
                    </td>
                    <td>Assigned</td>
                  </tr>
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

            <ReportItem month="October 2025" />
            <ReportItem month="September 2025" />
            <ReportItem month="August 2025" />
            <ReportItem month="July 2025" />
          </aside>
        </section>
      </div>
    </Layout>
  );
}

function Kpi({ value, label }) {
  return (
    <div className="empKpi">
      <span className="empKpi__value">{value}</span>
      <span className="empKpi__label">{label}</span>
    </div>
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
