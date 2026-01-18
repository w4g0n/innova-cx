import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

export default function ManagerDashboard() {
  return (
    <Layout role="manager">
      <main className="managerMain">
        <header className="managerHeader">
          <div>
            <h1 className="managerTitle">Patrick Mukala - Facilities Management</h1>
            <p className="managerSubtitle">Quick overview of your department’s activity.</p>
          </div>
        </header>

        <section className="managerKpiRow">
          <div className="managerKpiCard">
            <span className="managerKpiLabel">Open Complaints</span>
            <span className="managerKpiValue">42</span>
          </div>

          <div className="managerKpiCard">
            <span className="managerKpiLabel">Unassigned</span>
            <span className="managerKpiValue">7</span>
          </div>

          <div className="managerKpiCard">
            <span className="managerKpiLabel">In Progress</span>
            <span className="managerKpiValue">18</span>
          </div>

          <div className="managerKpiCard">
            <span className="managerKpiLabel">Resolved Today</span>
            <span className="managerKpiValue">9</span>
          </div>

          <div className="managerKpiCard">
            <span className="managerKpiLabel">Active Employees</span>
            <span className="managerKpiValue">12</span>
          </div>

          <div className="managerKpiCard">
            <span className="managerKpiLabel">Pending Approvals</span>
            <span className="managerKpiValue">3</span>
          </div>
        </section>

        <p className="managerIntro">
          Use these quick actions to move between Manager screens.
        </p>

        <section className="managerBubbleGrid">
          <a href="/manager/view-complaints" className="managerBubbleCard">
            <span className="managerBubbleLabel">Complaints</span>
            <div className="managerBubbleTitle">View All Complaints</div>
            <div className="managerBubbleMetric">
              Handle assignments and follow up on open tickets.
            </div>
            <div className="managerBubbleLink">Go to complaints →</div>
          </a>

          <a href="/manager/view-employees" className="managerBubbleCard">
            <span className="managerBubbleLabel">Team</span>
            <div className="managerBubbleTitle">View Employees</div>
            <div className="managerBubbleMetric">Review workload & auto-generated reports.</div>
            <div className="managerBubbleLink">Go to employees →</div>
          </a>

          <a href="/manager/approvals" className="managerBubbleCard">
            <span className="managerBubbleLabel">Approvals</span>
            <div className="managerBubbleTitle">Rescoring & Rerouting</div>
            <div className="managerBubbleMetric">
              Approve or reject scoring and routing changes.
            </div>
            <div className="managerBubbleLink">Go to approvals →</div>
          </a>

          <a href="/manager/trends" className="managerBubbleCard">
            <span className="managerBubbleLabel">Analytics</span>
            <div className="managerBubbleTitle">Complaint Trends</div>
            <div className="managerBubbleMetric">View insights and trend analysis.</div>
            <div className="managerBubbleLink">View trends →</div>
          </a>
        </section>
      </main>
    </Layout>
  );
}
