import { useState, useEffect, useCallback, useRef } from "react";

import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";

import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";

import "./ModelHealth.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";
import {
  ALLOWED_TIME_FILTERS,
  ALLOWED_DEPARTMENTS,
  ALLOWED_MODEL_AGENTS,
} from "./Operatorsanitize";

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

async function apiFetch(path, params = {}) {
  const token = getStoredToken();
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== "" && v != null)
  );
  const qs = new URLSearchParams(clean).toString();
  const url = apiUrl(`/api${path}${qs ? `?${qs}` : ""}`);
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 401 || res.status === 403) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

const C = {
  purple: "#401c51", mid: "#6b3a8a", light: "#9b71a3", pale: "#cfc3d7",
  green:  "#22c55e", amber: "#f59e0b", red: "#ef4444", blue: "#3b82f6",
  text:   "#1a1a2e", muted: "rgba(26,26,46,0.55)", border: "rgba(64,28,81,0.12)",
};

// ── Date Range Picker (identical style to QualityControl) ──────────────────
function DateRangePicker({ dateRange, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const fmt = (d) =>
    d
      ? new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
      : "—";

  const label =
    dateRange.from || dateRange.to
      ? `${fmt(dateRange.from)} → ${fmt(dateRange.to)}`
      : "Custom range";

  return (
    <div className="qc-datepicker" ref={ref}>
      <button type="button" className="qc-datepicker__btn" onClick={() => setOpen((v) => !v)}>
        {label}
        <span className="qc-datepicker__icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
        </span>
      </button>
      {open && (
        <div className="qc-datepicker__dropdown">
          <div className="qc-datepicker__row">
            <label className="qc-datepicker__label">From</label>
            <input
              type="date" className="qc-datepicker__input"
              value={dateRange.from || ""}
              onChange={(e) => onChange({ ...dateRange, from: e.target.value })}
            />
          </div>
          <div className="qc-datepicker__row">
            <label className="qc-datepicker__label">To</label>
            <input
              type="date" className="qc-datepicker__input"
              value={dateRange.to || ""}
              onChange={(e) => onChange({ ...dateRange, to: e.target.value })}
            />
          </div>
          <button
            type="button" className="qc-datepicker__clear"
            onClick={() => { onChange({ from: "", to: "" }); setOpen(false); }}
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}

// ── Shared sub-components ──────────────────────────────────────────────────
function KpiCard({ label, value, pill, sub, flag }) {
  return (
    <article className={`ma-kpi ${flag ? `ma-kpi--${flag}` : ""}`}>
      <div className="ma-kpi__top">
        <span className="ma-kpi__label">{label}</span>
        {pill && <span className="ma-kpi__pill">{pill}</span>}
      </div>
      <div className="ma-kpi__value">{value}</div>
      {sub && <div className="ma-kpi__sub">{sub}</div>}
    </article>
  );
}

function Card({ title, subtitle, children, wide }) {
  return (
    <article className={`ma-card${wide ? " ma-card--wide" : ""}`}>
      <h2 className="ma-card__title">{title}</h2>
      {subtitle && <p className="ma-card__sub">{subtitle}</p>}
      {children}
    </article>
  );
}

function EmptyState({ message = "No data for this period." }) {
  return (
    <div style={{ padding: "1.5rem", color: C.muted, textAlign: "center", fontSize: 14 }}>
      {message}
    </div>
  );
}

function LoadingOrError({ loading, error, onRetry }) {
  if (loading) return (
    <div style={{ padding: "2rem", textAlign: "center", color: C.muted }}>Loading…</div>
  );
  if (error) return (
    <div style={{ padding: "2rem", textAlign: "center", color: C.red }}>
      {error}
      {onRetry && (
        <>
          <br />
          <button type="button" style={{ marginTop: 10, cursor: "pointer" }} onClick={onRetry}>
            Retry
          </button>
        </>
      )}
    </div>
  );
  return null;
}

const renderPctLabel = ({ percent }) => `${(percent * 100).toFixed(0)}%`;

// ── Chatbot Agent View ─────────────────────────────────────────────────────
function ChatbotAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, escalationTrend } = data;

  const sentimentAtEscalation = [
    { bucket: "Very Negative", count: escalationTrend.reduce((s, r) => s + (r.escVeryNegative ?? 0), 0) },
    { bucket: "Negative",      count: escalationTrend.reduce((s, r) => s + (r.escNegative    ?? 0), 0) },
    { bucket: "Neutral",       count: escalationTrend.reduce((s, r) => s + (r.escNeutral     ?? 0), 0) },
    { bucket: "Positive",      count: escalationTrend.reduce((s, r) => s + (r.escPositive    ?? 0), 0) },
  ];

  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard label="Escalation Rate" value={`${kpis.escalationRate}%`} pill="escalated_to_human" sub="Sessions ending in human handoff" flag={kpis.escalationRate > 20 ? "warn" : undefined} />
        <KpiCard label="Avg Session Length" value={kpis.avgMessagesPerSession ?? "—"} pill="Messages / session" sub="Average messages exchanged per conversation" />
        <KpiCard label="Total Sessions" value={kpis.totalSessions.toLocaleString()} pill="Period" sub="From sessions + user_chat_logs" />
      </div>
      <div className="ma-cards-row">
        <Card title="Sentiment at Escalation" subtitle="Distribution of user sentiment at the moment of escalation. Consistent negative sentiment means the bot worsens the experience before failing.">
          <div className="ma-chart-box">
            {sentimentAtEscalation.every((d) => d.count === 0)
              ? <EmptyState message="No sentiment data for escalated sessions in this period." />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={sentimentAtEscalation} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="bucket" tick={{ fill: C.muted, fontSize: 11 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                    <Bar dataKey="count" name="Sessions" fill={C.purple} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
        <Card title="Escalation Rate Trend" subtitle="Daily escalation rate. A week-long upward trend indicates model degradation, not a one-off spike.">
          <div className="ma-chart-box">
            {escalationTrend.length === 0
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={escalationTrend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 11 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 12 }} unit="%" />
                    <Tooltip contentStyle={{ borderRadius: 10 }} formatter={(v) => `${v}%`} />
                    <ReferenceLine y={20} stroke={C.red} strokeDasharray="4 3"
                      label={{ value: "20% threshold", fill: C.red, fontSize: 11 }} />
                    <Line type="monotone" dataKey="escalationRate" name="Escalation %"
                      stroke={C.purple} strokeWidth={2.5} dot={{ r: 4, fill: C.purple }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ── Sentiment Agent View ───────────────────────────────────────────────────
function SentimentAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, distribution, scoreOverTime, sentimentByDept } = data;
  const distColors = { Positive: C.light, Neutral: C.pale, Negative: C.purple, "Very Negative": C.mid };

  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard label="Low Confidence Rate" value={`${kpis.lowConfidenceRate}%`} pill="confidence < 0.60" sub="Inferences below threshold" flag={kpis.lowConfidenceRate > 10 ? "warn" : undefined} />
        <KpiCard label="Avg Sentiment Score" value={kpis.avgSentimentScore?.toFixed(2) ?? "—"} pill="−1.0 to +1.0" sub="Mean score across all tickets in period" flag={kpis.avgSentimentScore < -0.1 ? "warn" : undefined} />
        <KpiCard label="Total Scored Tickets" value={kpis.totalScoredTickets.toLocaleString()} pill="Period" sub="Rows in sentiment_outputs (is_current = TRUE)" />
      </div>
      <div className="ma-cards-row">
        <Card title="Sentiment Distribution" subtitle="Breakdown of all tickets by sentiment label. A sudden negative shift is an early warning of a service incident.">
          <div className="ma-chart-box">
            {distribution.every((d) => d.value === 0)
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={distribution} dataKey="value" nameKey="label" innerRadius={55} outerRadius={90} stroke="none" label={renderPctLabel} labelLine={false}>
                      {distribution.map((d) => <Cell key={d.label} fill={distColors[d.label] ?? C.pale} />)}
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
        <Card title="Average Sentiment Score Over Time" subtitle="Daily average of sentiment_score (−1.0 to +1.0). Correlates service changes with mood shifts.">
          <div className="ma-chart-box">
            {scoreOverTime.length === 0
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={scoreOverTime} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10 }} interval={2} />
                    <YAxis domain={[-0.6, 0.6]} tick={{ fill: C.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                    <ReferenceLine y={0} stroke={C.muted} strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="score" name="Avg Score" stroke={C.purple} strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>
      <Card title="Sentiment by Department" subtitle="Average sentiment score per department. Consistent negative sentiment in one area often points to a product or process issue." wide>
        <div className="ma-chart-box">
          {sentimentByDept.length === 0
            ? <EmptyState />
            : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={sentimentByDept} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="department" tick={{ fill: C.muted, fontSize: 12 }} />
                  <YAxis domain={[-0.6, 0.6]} tick={{ fill: C.muted, fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 10 }} />
                  <ReferenceLine y={0} stroke={C.muted} strokeDasharray="3 3" />
                  <Bar dataKey="avg" name="Avg Sentiment" radius={[4, 4, 0, 0]}>
                    {sentimentByDept.map((d) => <Cell key={d.department} fill={d.avg < 0 ? C.purple : C.light} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
        </div>
      </Card>
    </div>
  );
}

// ── Feature Agent View ─────────────────────────────────────────────────────
function FeatureAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, businessImpact, recurringTrend, featureByDept } = data;

  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard label="Safety Flag Rate" value={`${kpis.safetyFlagRate}%`} pill="safety_concern = true" sub="All flagged tickets require human review." flag={kpis.safetyFlagRate > 0 ? "danger" : undefined} />
        <KpiCard label="Recurring Issue Rate" value={`${kpis.recurringIssueRate}%`} pill="is_recurring = true" sub="Tickets flagged as recurring in the period" flag={kpis.recurringIssueRate > 12 ? "warn" : undefined} />
        <KpiCard label="Severity vs Urgency Mismatch" value={`${kpis.severityUrgencyMismatch}%`} pill="2+ levels apart" sub="issue_severity and issue_urgency at opposite ends" flag={kpis.severityUrgencyMismatch > 7 ? "warn" : undefined} />
        <KpiCard label="Low Confidence Rate" value={`${kpis.lowConfidenceRate}%`} pill="confidence < 0.60" sub="Extractions below threshold" flag={kpis.lowConfidenceRate > 10 ? "warn" : undefined} />
      </div>
      <div className="ma-cards-row">
        <Card title="Business Impact Distribution" subtitle="Breakdown of all tickets by business_impact level (from raw_features JSONB). A growing high-impact segment signals under-addressed issues.">
          <div className="ma-chart-box">
            {businessImpact.every((d) => d.value === 0)
              ? <EmptyState message="No business_impact data in raw_features for this period." />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={businessImpact} dataKey="value" nameKey="label" innerRadius={55} outerRadius={90} stroke="none" label={renderPctLabel} labelLine={false}>
                      <Cell fill={C.purple} />
                      <Cell fill={C.mid} />
                      <Cell fill={C.light} />
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
        <Card title="Recurring Issue Rate — Daily Trend" subtitle="Daily % of tickets flagged as is_recurring. A rising rate means resolution quality is low or root causes are not being addressed.">
          <div className="ma-chart-box">
            {recurringTrend.length === 0
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={recurringTrend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="recGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.light} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={C.light} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 12 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 12 }} unit="%" />
                    <Tooltip contentStyle={{ borderRadius: 10 }} formatter={(v) => `${v}%`} />
                    <Area type="monotone" dataKey="rate" name="Recurring %" stroke={C.light} fill="url(#recGrad)" strokeWidth={2.5} dot={{ r: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>
      <Card title="Feature Distribution by Department" subtitle="Business impact breakdown per department. A low-stakes department generating many high-impact tickets may indicate misclassification." wide>
        <div className="ma-chart-box">
          {featureByDept.length === 0
            ? <EmptyState />
            : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={featureByDept} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="department" tick={{ fill: C.muted, fontSize: 12 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 12 }} unit="%" />
                  <Tooltip contentStyle={{ borderRadius: 10 }} formatter={(v) => `${v}%`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="high"   name="High Impact"   stackId="a" fill={C.purple} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="medium" name="Medium Impact" stackId="a" fill={C.mid}    radius={[0, 0, 0, 0]} />
                  <Bar dataKey="low"    name="Low Impact"    stackId="a" fill={C.light}  radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
        </div>
      </Card>
    </div>
  );
}

// ── Agent tabs config ──────────────────────────────────────────────────────
const AGENTS = [
  { id: "chatbot",   label: "Chatbot Agent",              endpoint: "/operator/analytics/model-health/chatbot"   },
  { id: "sentiment", label: "Sentiment Agent",            endpoint: "/operator/analytics/model-health/sentiment" },
  { id: "feature",   label: "Feature Engineering Agent",  endpoint: "/operator/analytics/model-health/feature"   },
];

// ── Main component ─────────────────────────────────────────────────────────
export default function ModelHealth() {
  const revealRef = useScrollReveal();

  const [activeAgent,  setActiveAgent]  = useState("chatbot");
  const [timeFilter,   setTimeFilter]   = useState("last30days");
  const [deptFilter,   setDeptFilter]   = useState("All Departments");
  const [dateRange,    setDateRange]    = useState({ from: "", to: "" });

  const [agentData,    setAgentData]    = useState({});
  const [agentLoading, setAgentLoading] = useState({});
  const [agentError,   setAgentError]   = useState({});

  // Custom date range overrides pill selector when both from+to are set.
  // Chatbot endpoint does not accept a department parameter.
  const buildParams = useCallback((agentId) => {
    const base = agentId === "chatbot" ? {} : { department: deptFilter };
    if (dateRange.from && dateRange.to) {
      return { ...base, dateFrom: dateRange.from, dateTo: dateRange.to };
    }
    return { ...base, timeRange: timeFilter };
  }, [timeFilter, deptFilter, dateRange]);

  const loadAgent = useCallback(async (agentId) => {
    const agent = AGENTS.find((a) => a.id === agentId);
    if (!agent) return;
    setAgentLoading((prev) => ({ ...prev, [agentId]: true }));
    setAgentError((prev)   => ({ ...prev, [agentId]: null }));
    try {
      const data = await apiFetch(agent.endpoint, buildParams(agentId));
      setAgentData((prev) => ({ ...prev, [agentId]: data }));
    } catch (err) {
      setAgentError((prev) => ({ ...prev, [agentId]: "Failed to load agent data. Please try again." }));
    } finally {
      setAgentLoading((prev) => ({ ...prev, [agentId]: false }));
    }
  }, [buildParams]);

  useEffect(() => {
    loadAgent(activeAgent);
  }, [activeAgent, loadAgent]);

  const handleFilterChange = useCallback((setter) => (value) => {
    setter(value);
    setAgentData({});
  }, []);

  const handleDateRangeChange = useCallback((newRange) => {
    setDateRange(newRange);
    if ((newRange.from && newRange.to) || (!newRange.from && !newRange.to)) {
      setAgentData({});
    }
  }, []);

  return (
    <Layout role="operator">
      <div className="modelAnalysis" ref={revealRef}>
        <PageHeader
          title="Model Health"
          subtitle="Agent-level diagnostics: chatbot session quality, sentiment scoring accuracy, and feature extraction analytics."
          actions={
            <div className="ma-top-actions">
              <PillSelect
                value={timeFilter}
                onChange={handleFilterChange((v) => { if (ALLOWED_TIME_FILTERS.includes(v)) setTimeFilter(v); })}
                ariaLabel="Filter by time range"
                options={[
                  { label: "Last 7 days",  value: "last7days"  },
                  { label: "Last 30 days", value: "last30days" },
                  { label: "This quarter", value: "quarter"    },
                ]}
              />
              <PillSelect
                value={deptFilter}
                onChange={handleFilterChange((v) => { if (ALLOWED_DEPARTMENTS.includes(v)) setDeptFilter(v); })}
                ariaLabel="Filter by department"
                options={[
                  { label: "All Departments",       value: "All Departments"       },
                  { label: "Facilities Management", value: "Facilities Management" },
                  { label: "Legal & Compliance",    value: "Legal & Compliance"    },
                  { label: "Safety & Security",     value: "Safety & Security"     },
                  { label: "HR",                    value: "HR"                    },
                  { label: "Leasing",               value: "Leasing"               },
                  { label: "Maintenance",           value: "Maintenance"           },
                  { label: "IT",                    value: "IT"                    },
                ]}
              />
              <DateRangePicker dateRange={dateRange} onChange={handleDateRangeChange} />
            </div>
          }
        />

        <div className="ma-nav">
          {AGENTS.map((a) => (
            <button
              key={a.id}
              className={`ma-nav__btn ${activeAgent === a.id ? "ma-nav__btn--active" : ""}`}
              onClick={() => { if (ALLOWED_MODEL_AGENTS.includes(a.id)) setActiveAgent(a.id); }}
              type="button"
            >
              {a.label}
            </button>
          ))}
        </div>

        {activeAgent === "chatbot" && (
          <ChatbotAgentView data={agentData.chatbot} loading={!!agentLoading.chatbot} error={agentError.chatbot} onRetry={() => loadAgent("chatbot")} />
        )}
        {activeAgent === "sentiment" && (
          <SentimentAgentView data={agentData.sentiment} loading={!!agentLoading.sentiment} error={agentError.sentiment} onRetry={() => loadAgent("sentiment")} />
        )}
        {activeAgent === "feature" && (
          <FeatureAgentView data={agentData.feature} loading={!!agentLoading.feature} error={agentError.feature} onRetry={() => loadAgent("feature")} />
        )}
      </div>
    </Layout>
  );
}