import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import { apiUrl } from "../../config/apiBase";
import useScrollReveal from "../../utils/useScrollReveal";

export default function ManagerDashboard() {
  const revealRef = useScrollReveal();
  const token = localStorage.getItem("access_token");

  // State to hold backend KPIs — keys match GET /api/manager response (camelCase)
  const [kpis, setKpis] = useState({
    openComplaints:   0,
    inProgress:       0,
    resolvedToday:    0,
    activeEmployees:  0,
    pendingApprovals: 0,
  });

  useEffect(() => {
    if (!token) return;

    fetch(apiUrl("/api/manager"), {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (res.status === 401) return null;
        return res.json();
      })
      .then((data) => {
        if (data) setKpis(data);
        console.log("Manager API response:", data);
      })
      .catch((err) => {
        console.error("Failed to fetch KPIs:", err);
      });
  }, [token]);

  return (
    <Layout role="manager">
      <div className="mgrDashboard" ref={revealRef}>
        <PageHeader
          title="Dr. Farhad - Facilities Management"
          subtitle="Quick overview of your department’s activity."
        />

        <section className="managerKpiRow">
          <KpiCard label="Open Complaints" value={kpis.openComplaints} />
          <KpiCard label="In Progress" value={kpis.inProgress} />
          <KpiCard label="Resolved Today" value={kpis.resolvedToday} />
          <KpiCard label="Active Employees" value={kpis.activeEmployees} />
          <KpiCard label="Pending Approvals" value={kpis.pendingApprovals} />
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
            <div className="managerBubbleMetric">
              View insights and trend analysis.
            </div>
            <div className="managerBubbleLink">View trends →</div>
          </Link>
        </section>
      </div>
    </Layout>
  );
}
