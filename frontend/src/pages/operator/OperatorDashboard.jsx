import { useEffect, useMemo, useState, useRef } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import "./OperatorDashboard.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";

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
  } catch { return ""; }
}

async function apiFetch(path) {
  const token = getStoredToken();
  const url = apiUrl(`/api${path}`);
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 401 || res.status === 403) { window.location.href = "/login"; throw new Error("Session expired."); }
  if (!res.ok) { const d = await res.text().catch(() => res.statusText); throw new Error(`${res.status}: ${d}`); }
  return res.json();
}

function Dot({ ok }) {
  return <span className={`opDash__dot opDash__dot--${ok ? "green" : "red"}`} />;
}

function ModuleCard({ tag, title, desc, to, rows, loading }) {
  return (
    <Link to={to} className="opDash__moduleCard">
      <div className="opDash__moduleTop">
        <span className="opDash__moduleTag">{tag}</span>
        <span className="opDash__moduleArrow">→</span>
      </div>
      <div className="opDash__moduleTitle">{title}</div>
      <div className="opDash__moduleDesc">{desc}</div>
      <div className="opDash__moduleDivider" />
      <div className="opDash__moduleStats">
        {loading ? (
          <span className="opDash__moduleLoading">Loading…</span>
        ) : (
          rows.map((r) => (
            <div key={r.label} className="opDash__moduleStat">
              {r.ok !== undefined && <Dot ok={r.ok} />}
              <span className="opDash__moduleStatLabel">{r.label}</span>
              <span className="opDash__moduleStatValue">{r.value ?? "—"}</span>
            </div>
          ))
        )}
      </div>
    </Link>
  );
}

function LiveClock() {
  const [now, setNow] = useState(() => new Date());
  const rafRef = useRef(null);

  useEffect(() => {
    let last = -1;
    const tick = () => {
      const d = new Date();
      if (d.getSeconds() !== last) {
        last = d.getSeconds();
        setNow(new Date(d));
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  });

  return (
    <div className="opDash__clock">
      <div className="opDash__clockTime">
        {hh}:{mm}
        <span className="opDash__clockSeconds">:{ss}</span>
      </div>
      <div className="opDash__clockDate">{dateStr}</div>
    </div>
  );
}

export default function OperatorDashboard() {
  const revealRef = useScrollReveal();

  const [chatbot,           setChatbot]           = useState(null);
  const [chatbotLoading,    setChatbotLoading]    = useState(true);
  const [sentiment,         setSentiment]         = useState(null);
  const [sentimentLoading,  setSentimentLoading]  = useState(true);
  const [qcAccept,          setQcAccept]          = useState(null);
  const [qcAcceptLoading,   setQcAcceptLoading]   = useState(true);
  const [qcRescore,         setQcRescore]         = useState(null);
  const [qcRescoreLoading,  setQcRescoreLoading]  = useState(true);
  const [users,             setUsers]             = useState(null);
  const [usersLoading,      setUsersLoading]      = useState(true);
  const [queueStats,        setQueueStats]        = useState(null);
  const [queueStatsLoading, setQueueStatsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = (path, set, setLoading) => {
      apiFetch(path)
        .then((d)  => { if (!cancelled) set(d); })
        .catch(()  => {})
        .finally(() => { if (!cancelled) setLoading(false); });
    };
    load("/operator/analytics/model-health/chatbot?timeRange=last30days",  setChatbot,    setChatbotLoading);
    load("/operator/analytics/model-health/sentiment?timeRange=last30days", setSentiment,  setSentimentLoading);
    load("/operator/analytics/qc/acceptance?timeRange=last30days",          setQcAccept,   setQcAcceptLoading);
    load("/operator/analytics/qc/rescoring?timeRange=last30days",           setQcRescore,  setQcRescoreLoading);
    load("/operator/users",                                                  setUsers,      setUsersLoading);
    load("/operator/pipeline-queue/stats",                                   setQueueStats, setQueueStatsLoading);
    return () => { cancelled = true; };
  }, []);

  const greeting = useMemo(() => {
    const h = new Date().getHours();
    const tod = h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
    return `${tod}, Operator`;
  }, []);

  const userStats = useMemo(() => {
    if (!users || !Array.isArray(users)) return null;
    return {
      total:    users.length,
      active:   users.filter((u) => u.status === "active").length,
      inactive: users.filter((u) => u.status === "inactive").length,
    };
  }, [users]);

  const topKpis = [
    { label: "Escalation Rate", value: chatbot?.kpis?.escalationRate     != null ? `${chatbot.kpis.escalationRate}%`           : chatbotLoading   ? "…" : "—" },
    { label: "Avg Sentiment",   value: sentiment?.kpis?.avgSentimentScore != null ? sentiment.kpis.avgSentimentScore.toFixed(2) : sentimentLoading  ? "…" : "—" },
    { label: "QC Acceptance",   value: qcAccept?.kpis?.acceptanceRate    != null ? `${qcAccept.kpis.acceptanceRate}%`          : qcAcceptLoading   ? "…" : "—" },
    { label: "Rescore Rate",    value: qcRescore?.kpis?.rescoreRate      != null ? `${qcRescore.kpis.rescoreRate}%`            : qcRescoreLoading  ? "…" : "—" },
  ];

  const modules = [
    {
      tag: "Models", title: "Model Health",
      desc: "Chatbot containment, sentiment scoring, and feature extraction diagnostics.",
      to: "/operator/model-health", loading: chatbotLoading,
      rows: [
        { label: "Containment rate", value: chatbot?.kpis?.containmentRate != null ? `${chatbot.kpis.containmentRate}%` : "—", ok: chatbot?.kpis?.containmentRate >= 70 },
        { label: "Escalation rate",  value: chatbot?.kpis?.escalationRate  != null ? `${chatbot.kpis.escalationRate}%`  : "—", ok: chatbot?.kpis?.escalationRate  <= 20 },
        { label: "Total sessions",   value: chatbot?.kpis?.totalSessions?.toLocaleString() ?? "—" },
      ],
    },
    {
      tag: "QA", title: "Quality Control",
      desc: "AI suggestion acceptance, priority rescoring, and routing override tracking.",
      to: "/operator/quality-control", loading: qcAcceptLoading,
      rows: [
        { label: "Acceptance rate",   value: qcAccept?.kpis?.acceptanceRate != null ? `${qcAccept.kpis.acceptanceRate}%` : "—", ok: qcAccept?.kpis?.acceptanceRate >= 60 },
        { label: "Declined (custom)", value: qcAccept?.kpis?.declinedRate   != null ? `${qcAccept.kpis.declinedRate}%`   : "—", ok: qcAccept?.kpis?.declinedRate   <= 40 },
        { label: "Total resolutions", value: qcAccept?.kpis?.totalResolutions?.toLocaleString() ?? "—" },
      ],
    },
    {
      tag: "Access", title: "Users",
      desc: "RBAC roles, account status, and user access management across the platform.",
      to: "/operator/users", loading: usersLoading,
      rows: [
        { label: "Total users", value: userStats?.total    ?? "—" },
        { label: "Active",      value: userStats?.active   ?? "—", ok: true },
        { label: "Inactive",    value: userStats?.inactive ?? "—", ok: userStats ? userStats.inactive === 0 : undefined },
      ],
    },
    {
      tag: "Pipeline", title: "Pipeline Queue",
      desc: "Live ticket processing queue. Held tickets require operator correction before continuing.",
      to: "/operator/pipeline-queue", loading: queueStatsLoading,
      rows: [
        { label: "Queued",     value: queueStats?.queued     ?? "—" },
        { label: "Processing", value: queueStats?.processing ?? "—" },
        { label: "Held",       value: queueStats?.held       ?? "—", ok: queueStats ? queueStats.held === 0 : undefined },
        { label: "Done (24h)", value: queueStats?.completed  ?? "—" },
      ],
    },
  ];

  return (
    <Layout role="operator">
      <div className="opDash" ref={revealRef}>
        <div className="opDash__headerBox">
          <PageHeader title={greeting} />
          <LiveClock />
        </div>

        <section className="opDash__kpiRow">
          {topKpis.map((k) => (
            <KpiCard key={k.label} label={k.label} value={k.value} />
          ))}
        </section>

        <div className="opDash__moduleCol">
          {modules.map((m) => (
            <ModuleCard key={m.title} {...m} />
          ))}
        </div>
      </div>
    </Layout>
  );
}