import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import { apiUrl } from "../../config/apiBase";
import useScrollReveal from "../../utils/useScrollReveal";

// FIX (Issue 1 — KPI cards show 0):
// The original code used localStorage.getItem("access_token") directly.
// In this project the token may be stored inside a "user" JSON object under
// the "user" key (user.access_token), which means getItem("access_token")
// returns null, the useEffect guard fires and no fetch is made → all KPIs stay 0.
// This helper matches the pattern used by every other manager page.
function getAuthToken() {
  try {
    const raw = localStorage.getItem("user");
    if (raw) {
      const u = JSON.parse(raw);
      if (u?.access_token) return u.access_token;
    }
  } catch { /* ignore malformed payload */ }
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

export default function ManagerDashboard() {
  const revealRef = useScrollReveal();

  // State to hold backend KPIs — keys match GET /api/manager response (camelCase)
  const [kpis, setKpis] = useState({
    openComplaints:   0,
    inProgress:       0,
    resolvedToday:    0,
    activeEmployees:  0,
    pendingApprovals: 0,
  });

  useEffect(() => {
    // Read token inside the effect so we always get the freshest value, even
    // if localStorage was populated after the component first rendered.
    const token = getAuthToken();
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
      })
      .catch((err) => {
        console.error("Failed to fetch manager KPIs:", err);
      });
  }, []); // run once on mount — token is read fresh inside the effect

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
