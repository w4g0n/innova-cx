import { useState, useEffect, useCallback } from "react";

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

async function apiFetch(path, params = {}) {
  const token = getStoredToken();
  const qs = new URLSearchParams(params).toString();
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


/* ─────────────────────────────────────────────────────────────
   Palette
───────────────────────────────────────────────────────────── */
const C = {
  purple: "#401c51", mid: "#6b3a8a", light: "#9b71a3", pale: "#cfc3d7",
  green:  "#22c55e", amber: "#f59e0b", red: "#ef4444", blue: "#3b82f6",
  text:   "#1a1a2e", muted: "rgba(26,26,46,0.55)", border: "rgba(64,28,81,0.12)",
};

/* ─────────────────────────────────────────────────────────────
   API fetch helper
───────────────────────────────────────────────────────────── */


/* ─────────────────────────────────────────────────────────────
   Sub-components
───────────────────────────────────────────────────────────── */
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

function SectionHeading({ icon, label, accent }) {
  return (
    <div className={`ma-section-heading ma-section-heading--${accent}`}>
      <span className="ma-section-heading__icon">{icon}</span>
      <span className="ma-section-heading__label">{label}</span>
    </div>
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
        <><br />
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

/* ─────────────────────────────────────────────────────────────
   Agent views — each receives live data prop
───────────────────────────────────────────────────────────── */
function ChatbotAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, escalationTrend } = data;

  // Build sentiment-at-escalation bar chart data from aggregated daily buckets
  const sentimentAtEscalation = [
    { bucket: "Very Negative", count: escalationTrend.reduce((s, r) => s + (r.escVeryNegative ?? 0), 0) },
    { bucket: "Negative",      count: escalationTrend.reduce((s, r) => s + (r.escNegative    ?? 0), 0) },
    { bucket: "Neutral",       count: escalationTrend.reduce((s, r) => s + (r.escNeutral     ?? 0), 0) },
    { bucket: "Positive",      count: escalationTrend.reduce((s, r) => s + (r.escPositive    ?? 0), 0) },
  ];

  return (
    <div className="ma-view">
      <SectionHeading icon="💬" label="Chatbot Agent — Session Analytics" accent="purple" />

      <div className="ma-kpi-row">
        <KpiCard
          label="Containment Rate"
          value={`${kpis.containmentRate}%`}
          pill="resolved_without_ticket"
          sub="Sessions resolved without creating a ticket or escalating"
        />
        <KpiCard
          label="Escalation Rate"
          value={`${kpis.escalationRate}%`}
          pill="escalated_to_human"
          sub="Sessions ending in human handoff"
          flag={kpis.escalationRate > 20 ? "warn" : undefined}
        />
        <KpiCard
          label="Avg Session Length"
          value={kpis.avgMessagesPerSession ?? "—"}
          pill="Messages / session"
          sub="Average messages exchanged per conversation"
        />
        <KpiCard
          label="Total Sessions"
          value={kpis.totalSessions.toLocaleString()}
          pill="Period"
          sub="From sessions + user_chat_logs"
        />
      </div>

      <div className="ma-cards-row">
        <Card
          title="Sentiment at Escalation"
          subtitle="Distribution of user sentiment at the moment of escalation. Consistent negative sentiment means the bot worsens the experience before failing."
        >
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

        <Card
          title="Escalation Rate Trend"
          subtitle="Daily escalation rate. A week-long upward trend indicates model degradation, not a one-off spike."
        >
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

      <div className="ma-info-banner">
        <span className="ma-info-banner__icon">ℹ️</span>
        <span>
          Sourced from <code>mv_chatbot_daily</code> (sessions + user_chat_logs).
          Containment = sessions where <code>escalated_to_human = FALSE</code> and <code>linked_ticket_id IS NULL</code>.
        </span>
      </div>
    </div>
  );
}

function SentimentAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, distribution, scoreOverTime, sentimentByDept } = data;

  const distColors = { Positive: C.green, Neutral: C.pale, Negative: C.red, "Very Negative": "#7f1d1d" };

  return (
    <div className="ma-view">
      <SectionHeading icon="🧠" label="Sentiment Agent — Scoring Analytics" accent="purple" />

      <div className="ma-kpi-row">
        <KpiCard
          label="Low Confidence Rate"
          value={`${kpis.lowConfidenceRate}%`}
          pill="confidence < 0.60"
          sub="Inferences below threshold"
          flag={kpis.lowConfidenceRate > 10 ? "warn" : undefined}
        />
        <KpiCard
          label="Avg Sentiment Score"
          value={kpis.avgSentimentScore?.toFixed(2) ?? "—"}
          pill="−1.0 to +1.0"
          sub="Mean score across all tickets in period"
          flag={kpis.avgSentimentScore < -0.1 ? "warn" : undefined}
        />
        <KpiCard
          label="Total Scored Tickets"
          value={kpis.totalScoredTickets.toLocaleString()}
          pill="Period"
          sub="Rows in sentiment_outputs (is_current = TRUE)"
        />
      </div>

      <div className="ma-cards-row">
        <Card
          title="Sentiment Distribution"
          subtitle="Breakdown of all tickets by sentiment label. A sudden negative shift is an early warning of a service incident."
        >
          <div className="ma-chart-box">
            {distribution.every((d) => d.value === 0)
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={distribution} dataKey="value" nameKey="label"
                      innerRadius={55} outerRadius={90}
                      stroke="none" label={renderPctLabel} labelLine={false}
                    >
                      {distribution.map((d) => (
                        <Cell key={d.label} fill={distColors[d.label] ?? C.pale} />
                      ))}
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>

        <Card
          title="Average Sentiment Score Over Time"
          subtitle="Daily average of sentiment_score (−1.0 to +1.0). Correlates service changes with mood shifts."
        >
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
                    <Line type="monotone" dataKey="score" name="Avg Score"
                      stroke={C.purple} strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>

      <Card
        title="Sentiment by Department"
        subtitle="Average sentiment score per department. Consistent negative sentiment in one area often points to a product or process issue."
        wide
      >
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
                    {sentimentByDept.map((d) => (
                      <Cell key={d.department} fill={d.avg < 0 ? C.red : C.green} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
        </div>
      </Card>

      <div className="ma-info-banner">
        <span className="ma-info-banner__icon">ℹ️</span>
        <span>
          Sourced from <code>mv_sentiment_daily</code> (sentiment_outputs joined to tickets + departments,
          <code> is_current = TRUE</code>). Low confidence uses <code>confidence_score &lt; 0.60</code>.
        </span>
      </div>
    </div>
  );
}

function FeatureAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, businessImpact, recurringTrend, featureByDept } = data;

  return (
    <div className="ma-view">
      <SectionHeading icon="⚙️" label="Feature Engineering Agent — Extraction Analytics" accent="purple" />

      <div className="ma-kpi-row">
        <KpiCard
          label="Safety Flag Rate"
          value={`${kpis.safetyFlagRate}%`}
          pill="safety_concern = true"
          sub="All flagged tickets require human review."
          flag={kpis.safetyFlagRate > 0 ? "danger" : undefined}
        />
        <KpiCard
          label="Recurring Issue Rate"
          value={`${kpis.recurringIssueRate}%`}
          pill="is_recurring = true"
          sub="Tickets flagged as recurring in the period"
          flag={kpis.recurringIssueRate > 12 ? "warn" : undefined}
        />
        <KpiCard
          label="Severity vs Urgency Mismatch"
          value={`${kpis.severityUrgencyMismatch}%`}
          pill="2+ levels apart"
          sub="issue_severity and issue_urgency at opposite ends"
          flag={kpis.severityUrgencyMismatch > 7 ? "warn" : undefined}
        />
        <KpiCard
          label="Low Confidence Rate"
          value={`${kpis.lowConfidenceRate}%`}
          pill="confidence < 0.60"
          sub="Extractions below threshold"
          flag={kpis.lowConfidenceRate > 10 ? "warn" : undefined}
        />
      </div>

      <div className="ma-cards-row">
        <Card
          title="Business Impact Distribution"
          subtitle="Breakdown of all tickets by business_impact level (from raw_features JSONB). A growing high-impact segment signals under-addressed issues."
        >
          <div className="ma-chart-box">
            {businessImpact.every((d) => d.value === 0)
              ? <EmptyState message="No business_impact data in raw_features for this period." />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={businessImpact} dataKey="value" nameKey="label"
                      innerRadius={55} outerRadius={90}
                      stroke="none" label={renderPctLabel} labelLine={false}
                    >
                      <Cell fill={C.red} />
                      <Cell fill={C.amber} />
                      <Cell fill={C.green} />
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>

        <Card
          title="Recurring Issue Rate — Daily Trend"
          subtitle="Daily % of tickets flagged as is_recurring. A rising rate means resolution quality is low or root causes are not being addressed."
        >
          <div className="ma-chart-box">
            {recurringTrend.length === 0
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={recurringTrend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="recGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.amber} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={C.amber} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 12 }} />
                    <YAxis tick={{ fill: C.muted, fontSize: 12 }} unit="%" />
                    <Tooltip contentStyle={{ borderRadius: 10 }} formatter={(v) => `${v}%`} />
                    <Area type="monotone" dataKey="rate" name="Recurring %"
                      stroke={C.amber} fill="url(#recGrad)" strokeWidth={2.5} dot={{ r: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>

      <Card
        title="Feature Distribution by Department"
        subtitle="Business impact breakdown per department. A low-stakes department generating many high-impact tickets may indicate misclassification."
        wide
      >
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
                  <Bar dataKey="high"   name="High Impact"   stackId="a" fill={C.red}   radius={[0, 0, 0, 0]} />
                  <Bar dataKey="medium" name="Medium Impact" stackId="a" fill={C.amber} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="low"    name="Low Impact"    stackId="a" fill={C.green} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
        </div>
      </Card>

      <div className="ma-info-banner">
        <span className="ma-info-banner__icon">ℹ️</span>
        <span>
          Sourced from <code>mv_feature_daily</code> (feature_outputs joined to tickets + departments,{" "}
          <code>is_current = TRUE</code>). <code>business_impact</code>, <code>safety_concern</code>,{" "}
          <code>issue_severity</code>, <code>issue_urgency</code> are extracted from{" "}
          <code>feature_outputs.raw_features</code> JSONB.
        </span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Agent tabs config
───────────────────────────────────────────────────────────── */
const AGENTS = [
  { id: "chatbot",   label: "Chatbot Agent",             icon: "💬", endpoint: "/operator/analytics/model-health/chatbot"   },
  { id: "sentiment", label: "Sentiment Agent",           icon: "🧠", endpoint: "/operator/analytics/model-health/sentiment" },
  { id: "feature",   label: "Feature Engineering Agent", icon: "⚙️", endpoint: "/operator/analytics/model-health/feature"   },
];

/* ─────────────────────────────────────────────────────────────
   Main component
───────────────────────────────────────────────────────────── */
export default function ModelHealth() {
  const revealRef = useScrollReveal();

  const [activeAgent, setActiveAgent] = useState("chatbot");
  const [timeFilter,  setTimeFilter]  = useState("last30days");
  const [deptFilter,  setDeptFilter]  = useState("All Departments");

  // Per-agent data state so switching tabs doesn't re-fetch unnecessarily
  const [agentData, setAgentData]     = useState({});
  const [agentLoading, setAgentLoading] = useState({});
  const [agentError,   setAgentError]   = useState({});

  const loadAgent = useCallback(async (agentId) => {
    const agent = AGENTS.find((a) => a.id === agentId);
    if (!agent) return;

    setAgentLoading((prev) => ({ ...prev, [agentId]: true }));
    setAgentError((prev)   => ({ ...prev, [agentId]: null }));

    try {
      const data = await apiFetch(agent.endpoint, {
        timeRange:  timeFilter,
        department: deptFilter,
      });
      setAgentData((prev) => ({ ...prev, [agentId]: data }));
    } catch (err) {
      setAgentError((prev) => ({ ...prev, [agentId]: err.message }));
    } finally {
      setAgentLoading((prev) => ({ ...prev, [agentId]: false }));
    }
  }, [timeFilter, deptFilter]);

  // Load active agent on mount and whenever filters change
  useEffect(() => {
    loadAgent(activeAgent);
  }, [activeAgent, loadAgent]);

  // When filters change, clear cached data so all agents reload fresh
  const handleFilterChange = useCallback((setter) => (value) => {
    setter(value);
    setAgentData({});
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
                onChange={handleFilterChange(setTimeFilter)}
                ariaLabel="Filter by time range"
                options={[
                  { label: "Last 7 days",  value: "last7days"  },
                  { label: "Last 30 days", value: "last30days" },
                  { label: "This quarter", value: "quarter"    },
                ]}
              />
              <PillSelect
                value={deptFilter}
                onChange={handleFilterChange(setDeptFilter)}
                ariaLabel="Filter by department"
                options={[
                  { label: "All departments", value: "All Departments" },
                  { label: "Warehouse",        value: "Warehouse"      },
                  { label: "Office",           value: "Office"         },
                  { label: "Retail Store",     value: "Retail Store"   },
                ]}
              />
            </div>
          }
        />

        {/* Agent tabs */}
        <div className="ma-nav">
          {AGENTS.map((a) => (
            <button
              key={a.id}
              className={`ma-nav__btn ${activeAgent === a.id ? "ma-nav__btn--active" : ""}`}
              onClick={() => setActiveAgent(a.id)}
              type="button"
            >
              <span>{a.icon}</span> {a.label}
            </button>
          ))}
        </div>

        {/* Agent views */}
        {activeAgent === "chatbot" && (
          <ChatbotAgentView
            data={agentData.chatbot}
            loading={!!agentLoading.chatbot}
            error={agentError.chatbot}
            onRetry={() => loadAgent("chatbot")}
          />
        )}
        {activeAgent === "sentiment" && (
          <SentimentAgentView
            data={agentData.sentiment}
            loading={!!agentLoading.sentiment}
            error={agentError.sentiment}
            onRetry={() => loadAgent("sentiment")}
          />
        )}
        {activeAgent === "feature" && (
          <FeatureAgentView
            data={agentData.feature}
            loading={!!agentLoading.feature}
            error={agentError.feature}
            onRetry={() => loadAgent("feature")}
          />
        )}
      </div>
    </Layout>
  );
}
