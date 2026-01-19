import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";

export default function ManagerDashboard() {
  return (
    <Layout role="manager">
      <div className="mgrDashboard">
        <PageHeader
          title="Patrick Mukala - Facilities Management"
          subtitle="Quick overview of your department’s activity."
        />

        <section className="managerKpiRow">
          <KpiCard label="Open Complaints" value={42} />
          <KpiCard label="Unassigned" value={7} />
          <KpiCard label="In Progress" value={18} />
          <KpiCard label="Resolved Today" value={9} />
          <KpiCard label="Active Employees" value={12} />
          <KpiCard label="Pending Approvals" value={3} />
        </section>

        <p className="managerIntro">
          Use these quick actions to move between Manager screens.
        </p>

        <section className="managerBubbleGrid">
          <Link to="/manager/complaints" className="managerBubbleCard">
            <span className="managerBubbleLabel">Complaints</span>
            <div className="managerBubbleTitle">View All Complaints</div>
            <div className="managerBubbleMetric">
              Handle assignments and follow up on open tickets.
            </div>
            <div className="managerBubbleLink">Go to complaints →</div>
          </Link>

          <Link to="/manager/employees" className="managerBubbleCard">
            <span className="managerBubbleLabel">Team</span>
            <div className="managerBubbleTitle">View Employees</div>
            <div className="managerBubbleMetric">
              Review workload & auto-generated reports.
            </div>
            <div className="managerBubbleLink">Go to employees →</div>
          </Link>

          <Link to="/manager/approvals" className="managerBubbleCard">
            <span className="managerBubbleLabel">Approvals</span>
            <div className="managerBubbleTitle">Rescoring & Rerouting</div>
            <div className="managerBubbleMetric">
              Approve or reject scoring and routing changes.
            </div>
            <div className="managerBubbleLink">Go to approvals →</div>
          </Link>

          <Link to="/manager/trends" className="managerBubbleCard">
            <span className="managerBubbleLabel">Analytics</span>
            <div className="managerBubbleTitle">Complaint Trends</div>
            <div className="managerBubbleMetric">View insights and trend analysis.</div>
            <div className="managerBubbleLink">View trends →</div>
          </Link>
        </section>
      </div>
    </Layout>
  );
}
