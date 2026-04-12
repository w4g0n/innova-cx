import { useState, useEffect, useCallback, useRef } from "react";

import Layout from "../../components/Layout";
import PillSelect from "../../components/common/PillSelect";

import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
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
  purple: "#401c51", mid: "#6b3a8a", light: "#9b71a3", pale: "#a882b8",
  green:  "#22c55e", amber: "#f59e0b", red: "#ef4444", blue: "#3b82f6",
  text:   "#1a1a2e", muted: "rgba(26,26,46,0.55)", border: "rgba(64,28,81,0.12)",
};

// ── Date Range Picker ──────────────────────────────────────────────────────
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
function KpiCard({ label, value, flag }) {
  return (
    <article className={`ma-kpi ${flag ? `ma-kpi--${flag}` : ""}`}>
      <div className="ma-kpi__top">
        <span className="ma-kpi__label">{label}</span>
      </div>
      <div className="ma-kpi__value">{value}</div>
    </article>
  );
}

function Card({ title, children, wide }) {
  return (
    <article className={`ma-card${wide ? " ma-card--wide" : ""}`}>
      <h2 className="ma-card__title">{title}</h2>
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

// ── Consistent color mapping for Feature Engineering charts ───────────────
const CHART_COLORS = ["#401c51", "#6b3a8a", "#9b71a3", "#a882b8", "#c4a8ce"];

// Canonical label order: Critical → High → Medium → Low → Unknown
const FE_LABEL_ORDER = ["Critical", "High", "Medium", "Low", "Unknown"];
const FE_COLOR_MAP = {
  Critical: "#401c51",
  High:     "#6b3a8a",
  Medium:   "#9b71a3",
  Low:      "#a882b8",
  Unknown:  "#c4a8ce",
};

function sortFeData(data) {
  if (!data) return [];
  return [...data].sort((a, b) => {
    const ai = FE_LABEL_ORDER.indexOf(a.label);
    const bi = FE_LABEL_ORDER.indexOf(b.label);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
}

// ── Chatbot Agent View ─────────────────────────────────────────────────────
// KPI 1: Escalation to Ticket Creation Rate (% sessions that escalated / linked to ticket)
// KPI 2: Average Messages Per Session (renamed)
// KPI 3: Total Sessions (unchanged)
// KPI 4: Containment Rate (NEW — % sessions resolved without escalation)
function ChatbotAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, escalationTrend } = data;

  const ticketCreationRate = kpis.escalationRate ?? 0;
  const containmentRate    = kpis.containmentRate ?? 0;
  const avgMessages        = kpis.avgMessagesPerSession ?? "—";
  const totalSessions      = kpis.totalSessions ?? 0;

  const sentimentAtEscalation = [
    { bucket: "Negative",  count: escalationTrend.reduce((s, r) => s + (r.escNegative ?? 0), 0) },
    { bucket: "Neutral",   count: escalationTrend.reduce((s, r) => s + (r.escNeutral  ?? 0), 0) },
    { bucket: "Positive",  count: escalationTrend.reduce((s, r) => s + (r.escPositive ?? 0), 0) },
  ];

  // Zero-state trend: use today at 0 so chart always renders with axes (no blank box)
  const trendData = escalationTrend.length > 0
    ? escalationTrend
    : [{ day: new Date().toISOString().slice(0, 10), escalationRate: 0 }];

  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard
          label="Escalation to Ticket Creation Rate"
          value={`${ticketCreationRate}%`}
          flag={ticketCreationRate > 20 ? "warn" : undefined}
        />
        <KpiCard
          label="Average Messages Per Session"
          value={avgMessages}
        />
        <KpiCard
          label="Total Sessions"
          value={totalSessions.toLocaleString()}
        />
        <KpiCard
          label="Containment Rate"
          value={`${containmentRate}%`}
          flag={containmentRate < 70 ? "warn" : undefined}
        />
      </div>

      {/* Escalation Rate Trend — always renders with axes; zero dot if no real data */}
      <Card title="Escalation Rate Trend" wide>
        <div className="ma-chart-box">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendData} margin={{ top: 14, right: 24, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 11 }} />
              <YAxis tick={{ fill: C.muted, fontSize: 12 }} unit="%" domain={[0, 100]} />
              <Tooltip contentStyle={{ borderRadius: 10 }} formatter={(v) => `${v}%`} />
              <ReferenceLine y={20} stroke={C.red} strokeDasharray="4 3"
                label={{ value: "20% threshold", fill: C.red, fontSize: 11, position: "insideTopRight" }} />
              <Line type="monotone" dataKey="escalationRate" name="Escalation %"
                stroke={C.purple} strokeWidth={2.5} dot={{ r: 5, fill: C.purple }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Sentiment at Escalation — always renders; zero bars if no escalated sessions */}
      <Card title="Sentiment at Escalation" wide>
        <div className="ma-chart-box">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={sentimentAtEscalation} margin={{ top: 14, right: 24, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="bucket" tick={{ fill: C.muted, fontSize: 13 }} />
              <YAxis tick={{ fill: C.muted, fontSize: 12 }} allowDecimals={false} />
              <Tooltip contentStyle={{ borderRadius: 10 }} />
              <Bar dataKey="count" name="Sessions" fill={C.purple} radius={[6, 6, 0, 0]} maxBarSize={90} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

// ── Canonical 7 departments — always shown, in this order ─────────────────
const CANONICAL_DEPTS = [
  "Facilities Management",
  "HR",
  "IT",
  "Legal & Compliance",
  "Leasing",
  "Maintenance",
  "Safety & Security",
];

function normalizeDeptData(data, valueKey = "avg") {
  const map = {};
  (data || []).forEach((d) => { map[d.department] = d; });
  return CANONICAL_DEPTS.map((dept) => ({
    department: dept,
    [valueKey]: map[dept]?.[valueKey] ?? 0,
  }));
}
// KPI 1: Agent Confidence Rate (% above threshold, inverted from lowConfidenceRate)
// KPI 2: Avg Sentiment Score (unchanged)
// KPI 3: High Negative Rate (% of tickets that are Negative, replaces Total Scored Tickets)
// Distribution: 3 buckets only — Positive, Neutral, Negative (Very Negative merged into Negative)
// Legend: numeric range labels shown
// Sentiment distribution — 3 buckets, colors assigned darkest=Negative, mid=Neutral, lightest=Positive
const SENTIMENT_DIST_COLORS = {
  Negative: "#401c51",
  Neutral:  "#9b71a3",
  Positive: "#c4a8ce",
};
// Clean legend labels — threshold note shown separately below chart
const SENTIMENT_RANGE_LABELS = {
  Negative: "Negative",
  Neutral:  "Neutral",
  Positive: "Positive",
};
function SentimentAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, distribution, scoreOverTime, sentimentByDept } = data;

  // Always show all 7 canonical departments, even if value = 0
  const sentimentByDeptNorm = normalizeDeptData(sentimentByDept, "avg");

  // KPI 1: confidence rate = 100 - lowConfidenceRate
  const confidenceRate = kpis.lowConfidenceRate != null
    ? Math.max(0, Math.round((100 - kpis.lowConfidenceRate) * 10) / 10)
    : null;

  // Distribution: merge Very Negative into Negative
  const negativeCount    = distribution.find((d) => d.label === "Negative")?.value     ?? 0;
  const veryNegCount     = distribution.find((d) => d.label === "Very Negative")?.value ?? 0;
  const totalDist        = distribution.reduce((s, d) => s + (d.value ?? 0), 0);
  const mergedNeg        = negativeCount + veryNegCount;
  const highNegativeRate = totalDist > 0 ? Math.round(mergedNeg / totalDist * 1000) / 10 : 0;

  // dist3: ordered Negative → Neutral → Positive to match legend and color assignment
  const dist3 = [
    { label: "Negative", value: mergedNeg },
    { label: "Neutral",  value: distribution.find((d) => d.label === "Neutral")?.value  ?? 0 },
    { label: "Positive", value: distribution.find((d) => d.label === "Positive")?.value ?? 0 },
  ];

  return (
    <div className="ma-view">
      <div className="ma-kpi-row" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        <KpiCard
          label="Agent Confidence Rate"
          value={confidenceRate != null ? `${confidenceRate}%` : "—"}
         
          flag={confidenceRate != null && confidenceRate < 85 ? "warn" : undefined}
        />
        <KpiCard
          label="Avg Sentiment Score"
          value={kpis.avgSentimentScore?.toFixed(2) ?? "—"}
         
          flag={kpis.avgSentimentScore < -0.1 ? "warn" : undefined}
        />
        <KpiCard
          label="High Negative Rate"
          value={`${highNegativeRate}%`}
         
          flag={highNegativeRate > 40 ? "warn" : undefined}
        />
      </div>
      <div className="ma-cards-row">
        <Card title="Sentiment Distribution">

          <div className="ma-chart-box">
            {dist3.every((d) => d.value === 0)
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={dist3}
                      dataKey="value"
                      nameKey="label"
                      innerRadius={70}
                      outerRadius={115}
                      stroke="none"
                      label={renderPctLabel}
                      labelLine={false}
                    >
                      {dist3.map((d) => (
                        <Cell key={d.label} fill={SENTIMENT_DIST_COLORS[d.label] ?? C.pale} />
                      ))}
                    </Pie>
                    <Legend
                      layout="vertical"
                      align="right"
                      verticalAlign="middle"
                      wrapperStyle={{ fontSize: 13, paddingLeft: 20, lineHeight: "1.2" }}
                      formatter={(value) => {
                        const rangeMap = {
                          Negative: "score < −0.1",
                          Neutral:  "−0.1 to +0.1",
                          Positive: "score > +0.1",
                        };
                        return (
                          <span style={{ display: "inline-flex", flexDirection: "column", lineHeight: 1.3 }}>
                            <span style={{ fontWeight: 700, fontSize: 13, color: "rgba(26,26,46,0.80)" }}>{value}</span>
                            <span style={{ fontSize: 11, color: "rgba(26,26,46,0.45)", marginTop: 1 }}>{rangeMap[value] ?? ""}</span>
                          </span>
                        );
                      }}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 10 }}
                      formatter={(v, name) => [`${v}% of scored tickets`, name]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
        <Card title="Average Sentiment Score Over Time">
          <div className="ma-chart-box" style={{ height: 340 }}>
            {(() => {
              const timeData = scoreOverTime.length > 0
                ? scoreOverTime
                : [{ date: new Date().toISOString().slice(0, 10), score: null }];
              return (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timeData} margin={{ top: 16, right: 36, left: -4, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                    <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10 }} interval={0} />
                    <YAxis domain={[-1, 1]} tick={{ fill: C.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                    <ReferenceLine y={0}    stroke={C.muted}  strokeDasharray="3 3" />
                    <ReferenceLine y={-0.1} stroke={C.red}   strokeDasharray="2 3"
                      label={({ viewBox }) => (
                        <text
                          x={(viewBox.x || 0) + (viewBox.width || 0) - 6}
                          y={(viewBox.y || 0) + 12}
                          fill={C.red} fontSize={11} fontWeight={600} textAnchor="end">
                          −0.1
                        </text>
                      )} />
                    <ReferenceLine y={0.1}  stroke={C.green} strokeDasharray="2 3"
                      label={({ viewBox }) => (
                        <text
                          x={(viewBox.x || 0) + (viewBox.width || 0) - 6}
                          y={(viewBox.y || 0) - 4}
                          fill={C.green} fontSize={11} fontWeight={600} textAnchor="end">
                          +0.1
                        </text>
                      )} />
                    {scoreOverTime.length > 0 && (
                      <Line type="monotone" dataKey="score" name="Avg Score" stroke={C.purple} strokeWidth={2.5} dot={{ r: 4 }} connectNulls={false} />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              );
            })()}
          </div>
        </Card>
      </div>
      <Card title="Sentiment by Department" wide>
        <div className="ma-chart-box">
          {sentimentByDeptNorm.every((d) => d.avg === 0)
            ? <EmptyState />
            : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={sentimentByDeptNorm} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="department"
                    tick={{ fill: C.muted, fontSize: 11 }}
                    interval={0}
                    tickFormatter={(v) => {
                      const abbr = {
                        "Facilities Management": "Facilities",
                        "Legal & Compliance":    "Legal & Comp.",
                        "Safety & Security":     "Safety & Sec.",
                        "Maintenance":           "Maintenance",
                        "Leasing":               "Leasing",
                        "HR":                    "HR",
                        "IT":                    "IT",
                      };
                      return abbr[v] ?? v;
                    }}
                    height={36}
                  />
                  <YAxis domain={[-1, 1]} tick={{ fill: C.muted, fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ borderRadius: 10 }}
                    formatter={(value) => [value?.toFixed(2), "Avg Sentiment"]}
                    labelFormatter={(label) => label}
                  />
                  <ReferenceLine y={0} stroke={C.muted} strokeDasharray="3 3" />
                  <Bar dataKey="avg" name="Avg Sentiment" radius={[4, 4, 0, 0]} maxBarSize={60}>
                    {sentimentByDeptNorm.map((d) => <Cell key={d.department} fill={d.avg < 0 ? C.purple : C.light} />)}
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
// KPIs: Safety Flag Rate, Correlation Rate, Avg Confidence Score, Low Confidence Rate
// Recurring Issue Rate: REMOVED from UI (backend logic kept intact)
// Charts: Business Impact (keep), Urgency (new), Severity (new), Category (new)
// Feature Distribution by Department: REMOVED
// Custom legend for FE charts — always renders ALL 5 FE_LABEL_ORDER items
// Labels with data show full opacity; missing labels are shown at reduced opacity
function FELegend({ data }) {
  const present = new Set((data || []).map((d) => d.label));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 16, justifyContent: "center", minWidth: 90 }}>
      {FE_LABEL_ORDER.map((label) => (
        <div key={label} style={{
          display: "flex", alignItems: "center", gap: 7, fontSize: 13,
          color: present.has(label) ? "rgba(26,26,46,0.70)" : "rgba(26,26,46,0.30)",
          whiteSpace: "nowrap"
        }}>
          <span style={{
            display: "inline-block", width: 12, height: 12, borderRadius: 3,
            background: FE_COLOR_MAP[label] ?? "#c4a8ce",
            flexShrink: 0,
            opacity: present.has(label) ? 1 : 0.35
          }} />
          {label}
        </div>
      ))}
    </div>
  );
}

// Legend specifically for Business Impact Distribution (High / Medium / Low only)
const BI_LABEL_ORDER = ["High", "Medium", "Low"];
function BiLegend({ data }) {
  const present = new Set((data || []).map((d) => d.label));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 16, justifyContent: "center", minWidth: 80 }}>
      {BI_LABEL_ORDER.map((label) => (
        <div key={label} style={{
          display: "flex", alignItems: "center", gap: 7, fontSize: 13,
          color: present.has(label) ? "rgba(26,26,46,0.70)" : "rgba(26,26,46,0.30)",
          whiteSpace: "nowrap"
        }}>
          <span style={{
            display: "inline-block", width: 12, height: 12, borderRadius: 3,
            background: FE_COLOR_MAP[label] ?? "#c4a8ce",
            flexShrink: 0,
            opacity: present.has(label) ? 1 : 0.35
          }} />
          {label}
        </div>
      ))}
    </div>
  );
}

function FeatureAgentView({ data, loading, error, onRetry }) {
  if (loading || error) return <LoadingOrError loading={loading} error={error} onRetry={onRetry} />;
  if (!data) return null;

  const { kpis, businessImpact, urgencyDist, severityDist, categoryDist } = data;

  const avgConfScore = kpis.avgConfidenceScore != null
    ? kpis.avgConfidenceScore.toFixed(3)
    : "—";

  // correlationRate: backend returns this field directly.
  // Fallback: invert severityUrgencyMismatch as a proxy if correlationRate not yet present.
  const correlationRaw = kpis.correlationRate ?? (
    kpis.severityUrgencyMismatch != null
      ? Math.max(0, Math.round((100 - kpis.severityUrgencyMismatch) * 10) / 10)
      : null
  );
  const correlationDisplay = correlationRaw != null ? `${correlationRaw}%` : "—";
  const correlationFlag    = correlationRaw != null && correlationRaw < 70 ? "warn" : undefined;

  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard
          label="Safety Flag Rate"
          value={`${kpis.safetyFlagRate}%`}
         
          flag={kpis.safetyFlagRate > 0 ? "danger" : undefined}
        />
        <KpiCard
          label="Correlation Rate"
          value={correlationDisplay}
         
          flag={correlationFlag}
        />
        <KpiCard
          label="Avg Confidence Score"
          value={avgConfScore}
         
          flag={kpis.avgConfidenceScore != null && kpis.avgConfidenceScore < 0.60 ? "warn" : undefined}
        />
        <KpiCard
          label="Low Confidence Rate"
          value={`${kpis.lowConfidenceRate}%`}
         
          flag={kpis.lowConfidenceRate > 10 ? "warn" : undefined}
        />
      </div>

      {/* Row 1: Business Impact + Urgency */}
      <div className="ma-cards-row" style={{ alignItems: "stretch" }}>
        <Card title="Business Impact Distribution">
          <div className="ma-chart-box" style={{ height: 300 }}>
            {businessImpact.every((d) => d.value === 0)
              ? <EmptyState message="No business_impact data for this period." />
              : (() => { const sorted = sortFeData(businessImpact); return (
                <div style={{ display: "flex", alignItems: "center", width: "100%", height: "100%" }}>
                  <ResponsiveContainer width="72%" height="100%">
                    <PieChart margin={{ top: 20, right: 0, bottom: 20, left: 0 }}>
                      <Pie data={sorted} dataKey="value" nameKey="label" innerRadius={58} outerRadius={92} stroke="none" label={renderPctLabel} labelLine={false}>
                        {sorted.map((d) => (
                          <Cell key={d.label} fill={FE_COLOR_MAP[d.label] ?? "#c4a8ce"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <BiLegend data={sorted} />
                </div>
              ); })()}
          </div>
        </Card>

        <Card title="Urgency Distribution">
          <div className="ma-chart-box" style={{ height: 300 }}>
            {!urgencyDist || urgencyDist.every((d) => d.value === 0)
              ? <EmptyState />
              : (() => { const sorted = sortFeData(urgencyDist); return (
                <div style={{ display: "flex", alignItems: "center", width: "100%", height: "100%" }}>
                  <ResponsiveContainer width="72%" height="100%">
                    <PieChart margin={{ top: 20, right: 0, bottom: 20, left: 0 }}>
                      <Pie data={sorted} dataKey="value" nameKey="label" innerRadius={58} outerRadius={92} stroke="none" label={renderPctLabel} labelLine={false}>
                        {sorted.map((d) => (
                          <Cell key={d.label} fill={FE_COLOR_MAP[d.label] ?? "#c4a8ce"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <FELegend data={sorted} />
                </div>
              ); })()}
          </div>
        </Card>
      </div>

      {/* Row 2: Severity + Category */}
      <div className="ma-cards-row">
        <Card title="Severity Distribution">
          <div className="ma-chart-box" style={{ height: Math.max(300, (categoryDist || []).length * 34 + 40) }}>
            {!severityDist || severityDist.every((d) => d.value === 0)
              ? <EmptyState />
              : (() => { const sorted = sortFeData(severityDist); return (
                <div style={{ display: "flex", alignItems: "center", width: "100%", height: "100%" }}>
                  <ResponsiveContainer width="72%" height="100%">
                    <PieChart margin={{ top: 24, right: 0, bottom: 24, left: 0 }}>
                      <Pie data={sorted} dataKey="value" nameKey="label" innerRadius={62} outerRadius={96} stroke="none" label={renderPctLabel} labelLine={false}>
                        {sorted.map((d) => (
                          <Cell key={d.label} fill={FE_COLOR_MAP[d.label] ?? "#c4a8ce"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 10 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <FELegend data={sorted} />
                </div>
              ); })()}
          </div>
        </Card>

        <Card title="Category Distribution">
          <div className="ma-chart-box">
            {!categoryDist || categoryDist.length === 0
              ? <EmptyState />
              : (
                <ResponsiveContainer width="100%" height={Math.max(300, categoryDist.length * 34 + 40)}>
                  <BarChart data={categoryDist} layout="vertical" margin={{ top: 8, right: 30, left: 10, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
                    <XAxis type="number" tick={{ fill: C.muted, fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      tick={{ fill: C.muted, fontSize: 12 }}
                      width={130}
                      interval={0}
                    />
                    <Tooltip contentStyle={{ borderRadius: 10 }} />
                    <Bar dataKey="value" name="Tickets" fill={C.purple} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
          </div>
        </Card>
      </div>
      {/* Feature Distribution by Department — REMOVED per spec */}
    </div>
  );
}

// ── Agent tabs ─────────────────────────────────────────────────────────────
const AGENTS = [
  { id: "chatbot",   label: "Chatbot Agent",             endpoint: "/operator/analytics/model-health/chatbot"   },
  { id: "sentiment", label: "Sentiment Agent",           endpoint: "/operator/analytics/model-health/sentiment" },
  { id: "feature",   label: "Feature Engineering Agent", endpoint: "/operator/analytics/model-health/feature"   },
];

export default function ModelHealth() {
  const revealRef = useScrollReveal();

  const [activeAgent,  setActiveAgent]  = useState("chatbot");
  const [timeFilter,   setTimeFilter]   = useState("last30days");
  const [deptFilter,   setDeptFilter]   = useState("All Departments");
  const [dateRange,    setDateRange]    = useState({ from: "", to: "" });

  const [agentData,    setAgentData]    = useState({});
  const [agentLoading, setAgentLoading] = useState({});
  const [agentError,   setAgentError]   = useState({});

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
    } catch {
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
        <div className="ma-hero">
          <div className="ma-hero__title">Model Health</div>
        </div>

        <div className="ma-toolbar">
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
