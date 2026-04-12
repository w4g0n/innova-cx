import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerDashboard.css";

import KpiCard from "../../components/common/KpiCard";
import { apiUrl } from "../../config/apiBase";
import useScrollReveal from "../../utils/useScrollReveal";
import { sanitizeText } from "./ManagerSanitize";

function getAuthToken() {
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

  const [kpis, setKpis] = useState({
    openComplaints:   0,
    inProgress:       0,
    resolvedToday:    0,
    activeEmployees:  0,
    pendingApprovals: 0,
  });

  // Identity seeded immediately from localStorage (populated by Login on sign-in)
  // then confirmed/updated from the /api/manager response which is scoped to the
  // authenticated user via get_current_user joining user_profiles.
  const [managerName, setManagerName] = useState(() => {
    try {
      const raw = localStorage.getItem("user");
      if (raw) {
        const u = JSON.parse(raw);
        return sanitizeText(u?.full_name || "", 100);
      }
    } catch { /* ignore */ }
    return "";
  });

  useEffect(() => {
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
        if (!data) return;
        setKpis(data);
        // Backend returns these from the authenticated session (get_current_user
        // now joins user_profiles, so these are always the logged-in manager's values)
        if (data.managerName) setManagerName(sanitizeText(data.managerName, 100));
      })
      .catch((err) => {
        console.error("Failed to fetch manager KPIs:", err);
      });
  }, []);

  const greeting = useMemo(() => {
    const h = new Date().getHours();
    const tod = h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
    return managerName ? `${tod}, ${managerName}` : tod;
  }, [managerName]);

  return (
    <Layout role="manager">
      <div className="mgrDashboard" ref={revealRef}>
        <div className="empNotifs__hero">
          <h1 className="empNotifs__heroTitle">{greeting}</h1>
        </div>

        <section className="managerKpiRow">
          <KpiCard label="Open Complaints" value={kpis.openComplaints} />
          <KpiCard label="In Progress" value={kpis.inProgress} />
          <KpiCard label="Resolved Today" value={kpis.resolvedToday} />
          <KpiCard label="Active Employees" value={kpis.activeEmployees} />
          <KpiCard label="Pending Approvals" value={kpis.pendingApprovals} />
        </section>

        <section className="managerBubbleGrid">
          <Link to="/manager/complaints" className="managerBubbleCard">
            <span className="managerBubbleLabel">Complaints</span>
            <div className="managerBubbleTitle">Ticket Management</div>
            <div className="managerBubbleMetric">
              Handle assignments and follow up on open tickets.
            </div>
            <div className="managerBubbleLink">Go to complaints →</div>
          </Link>

          <Link to="/manager/employees" className="managerBubbleCard">
            <span className="managerBubbleLabel">Team</span>
            <div className="managerBubbleTitle">View Employees</div>
            <div className="managerBubbleMetric">
              Review workload &amp; auto-generated reports.
            </div>
            <div className="managerBubbleLink">Go to employees →</div>
          </Link>

          <Link to="/manager/approvals" className="managerBubbleCard">
            <span className="managerBubbleLabel">Approvals</span>
            <div className="managerBubbleTitle">Rescoring &amp; Rerouting</div>
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