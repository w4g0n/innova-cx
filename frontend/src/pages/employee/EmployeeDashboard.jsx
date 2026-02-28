import { useState, useEffect } from "react";
import { Link, Navigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import { apiUrl } from "../../config/apiBase";
import "./EmployeeDashboard.css";
import useScrollReveal from "../../utils/useScrollReveal";

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

function getStoredToken() {
  const direct =
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken");

  if (direct) return direct;

  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser) return "";
    const user = JSON.parse(rawUser);
    return user?.access_token || "";
  } catch {
    return "";
  }
}

export default function EmployeeDashboard() {
  const revealRef = useScrollReveal();
  const [employee, setEmployee] = useState(null);
  const [kpis, setKpis] = useState({});
  const [tickets, setTickets] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  // 🔐 MFA + Auth Enforcement
  const token = getStoredToken();
  const mfaToken = sessionStorage.getItem("mfa_token");

  useEffect(() => {
    if (!token) return;

    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await fetch(apiUrl("/api/employee/dashboard"), {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`Dashboard fetch failed (${res.status}): ${text}`);
        }

        const data = await res.json();

        if (cancelled) return;

        setEmployee(data.employee || null);
        setKpis(data.kpis || {});
        setTickets(Array.isArray(data.tickets) ? data.tickets : []);
        setReports(Array.isArray(data.reports) ? data.reports : []);
      } catch (err) {
        console.error("Error loading dashboard data:", err);

        if (!cancelled) {
          setEmployee({ name: "Employee" });
          setKpis({
            ticketsAssigned: 0,
            inProgress: 0,
            resolvedThisMonth: 0,
            critical: 0,
            overdue: 0,
            newToday: 0,
          });
          setTickets([]);
          setReports([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [token]);

  // 🔐 MFA + Auth Enforcement (after hooks)
  if (!token && mfaToken) {
    return <Navigate to="/verify" replace />;
  }
  if (!token && !mfaToken) {
    return <Navigate to="/" replace />;
  }

  if (loading)
    return (
      <Layout role="employee">
        <main>Loading...</main>
      </Layout>
    );

  return (
    <Layout role="employee">
      <div className="empDash" ref={revealRef}>
        <PageHeader
          title={`Good Morning, ${employee?.name || "Employee"}`}
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
