import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import { isSkipToken, skipManagerKpis } from "../../data/skipViewData";

export default function ManagerDashboard() {
  const navigate = useNavigate();

  // State to hold backend KPIs
  const [kpis, setKpis] = useState({
    open_complaints: 0,
    in_progress: 0,
    resolved_today: 0,
    active_employees: 0,
    pending_approvals: 0,
  });

  useEffect(() => {
    const token = localStorage.getItem("access_token"); // assuming JWT stored here
    if (!token) {
      setKpis(skipManagerKpis);
      return;
    }

    if (isSkipToken(token)) {
      setKpis(skipManagerKpis);
      return;
    }

    fetch("http://localhost:8000/manager", {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`, // pass token in header
      },
    })
      .then((res) => {
        if (res.status === 401) {
          setKpis(skipManagerKpis);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data) setKpis(data);
      })
      .catch((err) => {
        console.error("Failed to fetch KPIs:", err);
        setKpis(skipManagerKpis);
      });
  }, [navigate]);

  return (
    <Layout role="manager">
      <div className="mgrDashboard">
        <PageHeader
          title="Dr. Farhad - Facilities Management"
          subtitle="Quick overview of your department’s activity."
        />

        <section className="managerKpiRow">
          <KpiCard label="Open Complaints" value={kpis.open_complaints} />
          <KpiCard label="In Progress" value={kpis.in_progress} />
          <KpiCard label="Resolved Today" value={kpis.resolved_today} />
          <KpiCard label="Active Employees" value={kpis.active_employees} />
          <KpiCard label="Pending Approvals" value={kpis.pending_approvals} />
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
