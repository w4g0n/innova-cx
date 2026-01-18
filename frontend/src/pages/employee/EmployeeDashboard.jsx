import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import "./EmployeeDashboard.css";

export default function EmployeeDashboard() {
  return (
    <Layout role="employee">
      <div className="empDash">
        <PageHeader
          title="Good Morning, Mayed Sharaf"
          subtitle="Here’s your activity and assigned workload."
        />

        <section className="empDash__kpis">
          <KpiCard label="Tickets Assigned" value="7" />
          <KpiCard label="In Progress" value="2" />
          <KpiCard label="Resolved This Month" value="48" />
          <KpiCard label="Critical" value="2" />
          <KpiCard label="Overdue" value="2" />
          <KpiCard label="New Today" value="1" />
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
                      <PriorityPill priority="Critical" />
                    </td>
                    <td>In Progress</td>
                  </tr>

                  <tr>
                    <td>CX-3210</td>
                    <td>Water leak near lobby</td>
                    <td>
                      <PriorityPill priority="High" />
                    </td>
                    <td>In Progress</td>
                  </tr>

                  <tr>
                    <td>CX-3244</td>
                    <td>Light flickering in corridor</td>
                    <td>
                      <PriorityPill priority="Medium" />
                    </td>
                    <td>Assigned</td>
                  </tr>

                  <tr>
                    <td>CX-3302</td>
                    <td>Cleaning missed in meeting room</td>
                    <td>
                      <PriorityPill priority="Low" />
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
