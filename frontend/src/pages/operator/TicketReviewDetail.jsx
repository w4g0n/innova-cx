import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import "./TicketReviewDetail.css";
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

const C = {
  purple: "#401c51", mid: "#6b3a8a", light: "#9b71a3",
  green: "#22c55e", amber: "#f59e0b", red: "#ef4444", blue: "#3b82f6",
  muted: "rgba(26,26,46,0.55)", border: "rgba(64,28,81,0.12)",
};

const fmtTs  = (ts) => ts ? new Date(ts).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—";
const fmtDur = (ms) => !ms ? "—" : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;

const PRIORITY_COLOR  = { Critical: "danger", High: "red", Medium: "amber", Low: "green" };
const STATUS_COLOR    = { Open: "blue", "In Progress": "amber", Resolved: "green", Escalated: "red", Overdue: "red", Assigned: "blue", Unassigned: "muted" };
const SENTIMENT_COLOR = { "Very Negative": "danger", Negative: "red", Neutral: "muted", Positive: "green" };
const APPROVAL_COLOR  = { Approved: "green", Rejected: "red", Pending: "amber" };
const EXEC_COLOR      = { success: "green", failed: "red", running: "amber", skipped: "muted" };
const AGENT_ICONS     = { sentiment: "🧠", feature: "⚙️", routing: "🔀", priority: "⚖️", resolution: "💡", sla: "⏱️" };
const UPDATE_ICONS    = { status_change: "🔄", assignment: "👤", override: "✏️", resolution: "✅", comment: "💬" };

function transformTicket(raw) {
  const approvalRequests = (raw.approvalRequests ?? raw.approval_requests ?? []).map((ar) => ({
    requestCode:    ar.requestCode   ?? ar.request_code,
    requestType:    ar.requestType   ?? ar.request_type,
    currentValue:   ar.currentValue  ?? ar.current_value,
    requestedValue: ar.requestedValue ?? ar.requested_value,
    requestReason:  ar.requestReason ?? ar.request_reason ?? "",
    status:         ar.status,
    submittedAt:    ar.submittedAt   ?? ar.submitted_at,
    decidedAt:      ar.decidedAt     ?? ar.decided_at,
    decisionNotes:  ar.decisionNotes ?? ar.decision_notes ?? "",
  }));

  const executionLog = (raw.executionLog ?? raw.execution_log ?? []).map((e) => ({
    agent:        e.agentName    ?? e.agent_name ?? e.agent,
    modelVersion: e.modelVersion ?? e.model_version,
    startedAt:    e.startedAt    ?? e.started_at,
    durationMs:   e.durationMs   ?? e.duration_ms,
    status:       e.status,
  }));

  const ticketUpdates = (raw.ticketUpdates ?? raw.ticket_updates ?? []).map((u) => ({
    updateType:  u.updateType  ?? u.update_type,
    fromStatus:  u.fromStatus  ?? u.from_status,
    toStatus:    u.toStatus    ?? u.to_status,
    message:     u.message,
    createdAt:   u.createdAt   ?? u.created_at,
  }));

  const chatSentimentSeries = (raw.chatSentimentSeries ?? raw.chat_sentiment_series ?? []).map((p, i) => ({
    msg:   p.msg ?? p.message_index ?? i + 1,
    score: typeof p.score === "number" ? p.score : parseFloat(p.sentiment_score ?? 0),
  }));

  return {
    ticketCode:          raw.ticketCode         ?? raw.ticket_code,
    subject:             raw.subject,
    details:             raw.details,
    status:              raw.status,
    priority:            raw.priority,
    modelPriority:       raw.modelPriority       ?? raw.model_priority,
    priorityConfidence:  raw.priorityConfidence  ?? raw.model_confidence ?? raw.priority_confidence,
    sentimentLabel:      raw.sentimentLabel      ?? raw.sentiment_label,
    sentimentScore:      raw.sentimentScore      ?? raw.sentiment_score  ?? 0,
    sentimentConfidence: raw.sentimentConfidence ?? raw.sentiment_confidence,
    modelDept:           raw.modelDept           ?? raw.model_dept       ?? raw.model_department_name,
    routingConfidence:   raw.routingConfidence   ?? raw.routing_confidence,
    finalDept:           raw.finalDept           ?? raw.final_dept       ?? raw.department_name,
    routingReason:       raw.routingReason       ?? raw.routing_reason   ?? "",
    humanOverridden:     raw.humanOverridden     ?? raw.human_overridden ?? false,
    overrideReason:      raw.overrideReason      ?? raw.override_reason  ?? "",
    isRecurring:         raw.isRecurring         ?? raw.is_recurring     ?? false,
    respondBreached:     raw.respondBreached     ?? raw.respond_breached ?? false,
    resolveBreached:     raw.resolveBreached     ?? raw.resolve_breached ?? false,
    createdAt:           raw.createdAt           ?? raw.created_at,
    resolvedAt:          raw.resolvedAt          ?? raw.resolved_at,
    firstResponseAt:     raw.firstResponseAt     ?? raw.first_response_at,
    respondDueAt:        raw.respondDueAt        ?? raw.respond_due_at,
    resolveDueAt:        raw.resolveDueAt        ?? raw.resolve_due_at,
    tags:                raw.tags               ?? [],
    channel:             raw.channel            ?? "web",
    suggestedResolution: raw.suggestedResolution ?? raw.suggested_resolution ?? "",
    resolutionModel:     raw.resolutionModel     ?? raw.suggested_resolution_model ?? "",
    finalResolution:     raw.finalResolution     ?? raw.final_resolution,
    feedbackDecision:    raw.feedbackDecision    ?? raw.feedback_decision,
    assetCategory:       raw.assetCategory       ?? raw.asset_type ?? "",
    topicLabels:         raw.topicLabels         ?? raw.topic_labels ?? [],
    featureConfidence:   raw.featureConfidence   ?? raw.feature_confidence,
    assignedToName:      raw.assignedToName      ?? raw.assigned_to_name  ?? "Unassigned",
    assignedToTitle:     raw.assignedToTitle     ?? raw.assigned_to_title ?? "",
    createdByName:       raw.createdByName       ?? raw.created_by_name   ?? "Unknown",
    createdByRole:       raw.createdByRole       ?? raw.created_by_role   ?? "",
    approvalRequests,
    executionLog,
    ticketUpdates,
    chatSentimentSeries,
  };
}

const Badge = ({ variant, children }) => (
  <span className={`trd-badge trd-badge--${variant}`}>{children}</span>
);

const ConfBar = ({ value, warn = 0.65 }) => {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const cls = value < warn ? "warn" : "ok";
  return (
    <div className="trd-conf-bar">
      <div className="trd-conf-bar__track">
        <div className={`trd-conf-bar__fill trd-conf-bar__fill--${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`trd-conf-bar__label trd-conf-bar__label--${cls}`}>{pct}%</span>
    </div>
  );
};

const TabPanel = ({ id, active, children }) =>
  active === id ? <div className="trd-tab-panel">{children}</div> : null;

function Spinner() {
  return (
    <Layout role="operator">
      <div style={{ padding: "3rem", textAlign: "center", color: C.muted }}>
        Loading ticket…
      </div>
    </Layout>
  );
}

function ErrorView({ ticketId, message, onRetry }) {
  const navigate = useNavigate();
  return (
    <Layout role="operator">
      <div className="trd-not-found">
        <div className="trd-not-found__icon">🔍</div>
        <h2>Could not load ticket</h2>
        <p>{message || `No ticket matching ${ticketId} was found.`}</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <button className="trd-back-btn" onClick={() => navigate(-1)} type="button">
            ← Back to Quality Control
          </button>
          {onRetry && (
            <button className="trd-back-btn" onClick={onRetry} type="button">
              Retry
            </button>
          )}
        </div>
      </div>
    </Layout>
  );
}

export default function TicketReviewDetail() {
  const { ticketId } = useParams();
  const navigate     = useNavigate();
  const revealRef    = useScrollReveal();

  const [ticketData,  setTicketData]  = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  const [tab,          setTab]          = useState("overview");
  const [noteText,     setNoteText]     = useState("");
  const [noteSaved,    setNoteSaved]    = useState(false);
  const [feedbackAct,  setFeedbackAct]  = useState(null);

  // FIX: useCallback so the function reference is stable — prevents infinite re-renders
  // and ensures onRetry always calls the latest version.
  const loadTicket = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await apiFetch(`/operator/complaints/${ticketId}`);
      const t   = transformTicket(raw);
      setTicketData(t);
      setFeedbackAct(t.feedbackDecision);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  // FIX: depend on the stable loadTicket reference, not ticketId directly
  useEffect(() => { loadTicket(); }, [loadTicket]);

  if (loading) return <Spinner />;
  if (error || !ticketData) return <ErrorView ticketId={ticketId} message={error} onRetry={loadTicket} />;

  const t = ticketData;

  const responseTimeMins  = t.firstResponseAt ? Math.round((new Date(t.firstResponseAt) - new Date(t.createdAt)) / 60000) : null;
  const resolutionTimeHrs = t.resolvedAt      ? ((new Date(t.resolvedAt) - new Date(t.createdAt)) / 3600000).toFixed(1) : null;
  const routingChanged    = t.modelDept !== t.finalDept;
  const priorityChanged   = t.modelPriority !== t.priority;

  const TABS = [
    { id: "overview",   label: "Overview",    icon: "📋" },
    { id: "ai",         label: "AI Analysis", icon: "🤖" },
    { id: "activity",   label: "Activity",    icon: "🔄" },
    { id: "resolution", label: "Resolution",  icon: "💡" },
  ];

  const saveNote = () => {
    if (noteText.trim()) {
      setNoteSaved(true);
      setTimeout(() => setNoteSaved(false), 2500);
      setNoteText("");
    }
  };

  return (
    <Layout role="operator">
      <div className="trd-page" ref={revealRef}>

        <button className="trd-back-btn" onClick={() => navigate(-1)} type="button">
          ← Quality Control
        </button>

        {/* ── HERO ── */}
        <div className="trd-hero">
          <div className="trd-hero__left">
            <div className="trd-hero__top-row">
              <span className="trd-hero__code">{t.ticketCode}</span>
              <Badge variant={STATUS_COLOR[t.status] || "muted"}>{t.status}</Badge>
              {t.humanOverridden && <Badge variant="amber">✏️ Overridden</Badge>}
              {t.isRecurring     && <Badge variant="amber">🔁 Recurring</Badge>}
              {(t.respondBreached || t.resolveBreached) && <Badge variant="danger">⚠️ SLA Breached</Badge>}
            </div>
            <h1 className="trd-hero__subject">{t.subject}</h1>
            <div className="trd-hero__people">
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon">👤</span>
                <div>
                  <span className="trd-hero__person-role">Submitted by</span>
                  <span className="trd-hero__person-name">{t.createdByName}{t.createdByRole ? ` · ${t.createdByRole}` : ""}</span>
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon">🔧</span>
                <div>
                  <span className="trd-hero__person-role">Assigned to</span>
                  <span className="trd-hero__person-name">{t.assignedToName}</span>
                  {t.assignedToTitle && <span className="trd-hero__person-sub">{t.assignedToTitle}</span>}
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon">🏢</span>
                <div>
                  <span className="trd-hero__person-role">Department</span>
                  <span className="trd-hero__person-name">{t.finalDept}</span>
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon">📅</span>
                <div>
                  <span className="trd-hero__person-role">Created</span>
                  <span className="trd-hero__person-name">{fmtTs(t.createdAt)}</span>
                </div>
              </div>
            </div>
          </div>
          <div className={`trd-hero__priority trd-hero__priority--${PRIORITY_COLOR[t.priority] || "muted"}`}>
            <span className="trd-hero__priority-label">Priority</span>
            <span className="trd-hero__priority-val">{t.priority}</span>
            {priorityChanged && <span className="trd-hero__priority-model">was {t.modelPriority}</span>}
          </div>
        </div>

        {/* ── TABS ── */}
        <div className="trd-tabs">
          {TABS.map((tb) => (
            <button
              key={tb.id} type="button"
              className={`trd-tab ${tab === tb.id ? "trd-tab--active" : ""}`}
              onClick={() => setTab(tb.id)}
            >
              <span className="trd-tab__icon">{tb.icon}</span>
              {tb.label}
            </button>
          ))}
        </div>

        {/* ── TAB: OVERVIEW ── */}
        <TabPanel id="overview" active={tab}>
          <div className="trd-overview">
            <div className="trd-card trd-card--full">
              <div className="trd-card__label">Description</div>
              <p className="trd-card__body">{t.details}</p>
              {t.tags?.length > 0 && (
                <div className="trd-tags">
                  {t.tags.map((tag) => <span key={tag} className="trd-tag">#{tag}</span>)}
                </div>
              )}
            </div>

            <div className="trd-card trd-card--full">
              <div className="trd-card__label">SLA Timeline</div>
              <div className="trd-timeline">
                {[
                  { label: "Created",        ts: t.createdAt,       done: true },
                  { label: "First Response", ts: t.firstResponseAt, done: !!t.firstResponseAt, due: t.respondDueAt },
                  { label: "Resolved",       ts: t.resolvedAt,      done: !!t.resolvedAt,      due: t.resolveDueAt },
                ].map((step, i) => (
                  <div key={i} className={`trd-timeline__step ${step.done ? "trd-timeline__step--done" : ""}`}>
                    <div className="trd-timeline__dot" />
                    <div className="trd-timeline__content">
                      <span className="trd-timeline__label">{step.label}</span>
                      <span className="trd-timeline__ts">{step.ts ? fmtTs(step.ts) : "Pending"}</span>
                      {!step.done && step.due && (
                        <span className="trd-timeline__due">Due {fmtTs(step.due)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {(responseTimeMins != null || resolutionTimeHrs != null) && (
                <div className="trd-timing-row">
                  {responseTimeMins  != null && <span className="trd-timing-chip">⚡ Response: <strong>{responseTimeMins} min</strong></span>}
                  {resolutionTimeHrs != null && <span className="trd-timing-chip">✅ Resolved in: <strong>{resolutionTimeHrs}h</strong></span>}
                </div>
              )}
            </div>

            <div className="trd-card">
              <div className="trd-card__label">Asset &amp; Category</div>
              <div className="trd-infolist">
                <div className="trd-infolist__row"><span>Category</span><strong>{t.assetCategory || "—"}</strong></div>
                <div className="trd-infolist__row"><span>Channel</span><strong>{t.channel}</strong></div>
                <div className="trd-infolist__row"><span>Recurring</span><strong>{t.isRecurring ? "Yes" : "No"}</strong></div>
              </div>
              {t.topicLabels?.length > 0 && (
                <div className="trd-tags trd-tags--sm" style={{ marginTop: 12 }}>
                  {t.topicLabels.map((l) => <span key={l} className="trd-tag trd-tag--muted">{l}</span>)}
                </div>
              )}
            </div>

            {t.sentimentLabel && (
              <div className="trd-card">
                <div className="trd-card__label">Sentiment Snapshot</div>
                <div className="trd-sentiment-snap">
                  <span className={`trd-sentiment-dot trd-sentiment-dot--${SENTIMENT_COLOR[t.sentimentLabel] || "muted"}`} />
                  <span className="trd-sentiment-label">{t.sentimentLabel}</span>
                  <span className="trd-sentiment-score">{Number(t.sentimentScore).toFixed(2)}</span>
                </div>
                {t.sentimentConfidence != null && (
                  <div className="trd-infolist" style={{ marginTop: 12 }}>
                    <div className="trd-infolist__row">
                      <span>Confidence</span>
                      <strong>{Math.round(t.sentimentConfidence * 100)}%</strong>
                    </div>
                  </div>
                )}
                {t.chatSentimentSeries.length > 0 && (
                  <div className="trd-chart-mini" style={{ marginTop: 12 }}>
                    <ResponsiveContainer width="100%" height={80}>
                      <LineChart data={t.chatSentimentSeries} margin={{ top: 4, right: 8, left: -28, bottom: 0 }}>
                        <XAxis dataKey="msg" hide />
                        <YAxis domain={[-1, 0.5]} tick={{ fill: "rgba(26,26,46,0.35)", fontSize: 9 }} />
                        <Tooltip contentStyle={{ borderRadius: 8, fontSize: 11 }} formatter={(v) => v.toFixed(2)} labelFormatter={(v) => `Msg ${v}`} />
                        <ReferenceLine y={0} stroke={C.border} strokeDasharray="3 3" />
                        <Line type="monotone" dataKey="score" stroke={C.purple} strokeWidth={2} dot={{ r: 3, fill: C.purple }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}
          </div>
        </TabPanel>

        {/* ── TAB: AI ANALYSIS ── */}
        <TabPanel id="ai" active={tab}>
          <div className="trd-ai">
            {t.humanOverridden && (
              <div className="trd-override-banner">
                <span className="trd-override-banner__icon">✏️</span>
                <div>
                  <span className="trd-override-banner__title">Human Override Applied</span>
                  <span className="trd-override-banner__text">{t.overrideReason}</span>
                </div>
              </div>
            )}

            <div className="trd-decisions-grid">
              <div className={`trd-decision-card ${routingChanged ? "trd-decision-card--changed" : "trd-decision-card--ok"}`}>
                <div className="trd-decision-card__header">
                  <span className="trd-decision-card__icon">🔀</span>
                  <span className="trd-decision-card__title">Routing</span>
                  {routingChanged ? <Badge variant="amber">Overridden</Badge> : <Badge variant="green">Correct</Badge>}
                </div>
                <div className="trd-decision-card__compare">
                  <div className="trd-decision-card__side">
                    <span className="trd-decision-card__side-label">Model suggested</span>
                    <span className="trd-decision-card__side-val trd-decision-card__side-val--model">{t.modelDept || "—"}</span>
                  </div>
                  {routingChanged && <span className="trd-decision-card__arrow">→</span>}
                  <div className="trd-decision-card__side">
                    <span className="trd-decision-card__side-label">Final decision</span>
                    <span className={`trd-decision-card__side-val ${routingChanged ? "trd-decision-card__side-val--final" : "trd-decision-card__side-val--ok"}`}>{t.finalDept}</span>
                  </div>
                </div>
                {t.routingConfidence != null && (
                  <div className="trd-decision-card__conf">
                    <span>Confidence</span>
                    <ConfBar value={t.routingConfidence} />
                  </div>
                )}
                {t.routingReason && <p className="trd-decision-card__reason">{t.routingReason}</p>}
              </div>

              {t.modelPriority && (
                <div className={`trd-decision-card ${priorityChanged ? "trd-decision-card--changed" : "trd-decision-card--ok"}`}>
                  <div className="trd-decision-card__header">
                    <span className="trd-decision-card__icon">⚖️</span>
                    <span className="trd-decision-card__title">Priority</span>
                    {priorityChanged ? <Badge variant="amber">Rescored</Badge> : <Badge variant="green">Correct</Badge>}
                  </div>
                  <div className="trd-decision-card__compare">
                    <div className="trd-decision-card__side">
                      <span className="trd-decision-card__side-label">Model suggested</span>
                      <span className="trd-decision-card__side-val trd-decision-card__side-val--model">{t.modelPriority}</span>
                    </div>
                    {priorityChanged && <span className="trd-decision-card__arrow">→</span>}
                    <div className="trd-decision-card__side">
                      <span className="trd-decision-card__side-label">Final decision</span>
                      <span className={`trd-decision-card__side-val ${priorityChanged ? "trd-decision-card__side-val--final" : "trd-decision-card__side-val--ok"}`}>{t.priority}</span>
                    </div>
                  </div>
                  {t.priorityConfidence != null && (
                    <div className="trd-decision-card__conf">
                      <span>Confidence</span>
                      <ConfBar value={t.priorityConfidence} />
                    </div>
                  )}
                </div>
              )}
            </div>

            {t.approvalRequests.length > 0 && (
              <div className="trd-card trd-card--full">
                <div className="trd-card__label">Approval Requests</div>
                <div className="trd-approvals">
                  {t.approvalRequests.map((ar) => (
                    <div key={ar.requestCode} className="trd-approval">
                      <div className="trd-approval__left">
                        <Badge variant={ar.requestType === "Rescoring" ? "amber" : "blue"}>{ar.requestType}</Badge>
                        <span className="trd-approval__change">{ar.currentValue} → <strong>{ar.requestedValue}</strong></span>
                      </div>
                      <div className="trd-approval__mid">
                        <p className="trd-approval__reason">{ar.requestReason}</p>
                        {ar.decisionNotes && <p className="trd-approval__notes">"{ar.decisionNotes}"</p>}
                      </div>
                      <div className="trd-approval__right">
                        <Badge variant={APPROVAL_COLOR[ar.status] || "muted"}>{ar.status}</Badge>
                        <span className="trd-approval__ts">{fmtTs(ar.decidedAt)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {t.executionLog.length > 0 && (
              <div className="trd-card trd-card--full">
                <div className="trd-card__label">Agent Pipeline</div>
                <div className="trd-pipeline">
                  {t.executionLog.map((entry, i) => (
                    <div key={i} className="trd-pipeline__step">
                      <div className={`trd-pipeline__dot trd-pipeline__dot--${EXEC_COLOR[entry.status] || "muted"}`} />
                      <div className="trd-pipeline__content">
                        <span className="trd-pipeline__name">{AGENT_ICONS[entry.agent] || "🔹"} {entry.agent}</span>
                        <span className="trd-pipeline__dur">{fmtDur(entry.durationMs)}</span>
                      </div>
                      <span className="trd-pipeline__version">{entry.modelVersion}</span>
                      {i < t.executionLog.length - 1 && <div className="trd-pipeline__connector" />}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </TabPanel>

        {/* ── TAB: ACTIVITY ── */}
        <TabPanel id="activity" active={tab}>
          <div className="trd-activity">
            {t.ticketUpdates.length === 0 ? (
              <p style={{ color: C.muted, padding: "1rem" }}>No activity recorded yet.</p>
            ) : (
              <div className="trd-timeline trd-timeline--full">
                {t.ticketUpdates.map((u, i) => (
                  <div
                    key={i}
                    className={`trd-timeline__step trd-timeline__step--done ${u.updateType === "override" ? "trd-timeline__step--override" : ""}`}
                  >
                    <div className="trd-timeline__dot" />
                    <div className="trd-timeline__content trd-timeline__content--wide">
                      <div className="trd-timeline__top-row">
                        <span className="trd-timeline__update-type">
                          {UPDATE_ICONS[u.updateType] || "•"} {u.updateType.replace(/_/g, " ")}
                        </span>
                        {u.fromStatus && u.toStatus && (
                          <span className="trd-timeline__status-chip">{u.fromStatus} → {u.toStatus}</span>
                        )}
                        <span className="trd-timeline__ts trd-timeline__ts--right">{fmtTs(u.createdAt)}</span>
                      </div>
                      <p className="trd-timeline__message">{u.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabPanel>

        {/* ── TAB: RESOLUTION ── */}
        <TabPanel id="resolution" active={tab}>
          <div className="trd-resolution">
            <div className="trd-card trd-card--full">
              <div className="trd-card__label-row">
                <span className="trd-card__label">AI Suggested Resolution</span>
                {t.resolutionModel && <span className="trd-card__sub-label">{t.resolutionModel}</span>}
              </div>
              {t.suggestedResolution
                ? <p className="trd-suggested">{t.suggestedResolution}</p>
                : <p style={{ color: C.muted }}>No AI suggestion generated for this ticket.</p>
              }

              {t.finalResolution ? (
                <div className="trd-final-resolution">
                  <div className="trd-final-resolution__header">
                    <span>✅</span>
                    <strong>Final Resolution Applied</strong>
                    {t.feedbackDecision && (
                      <Badge variant={t.feedbackDecision === "accepted" ? "green" : "amber"}>
                        {t.feedbackDecision === "accepted" ? "Suggestion accepted" : "Custom resolution used"}
                      </Badge>
                    )}
                    <span className="trd-final-resolution__ts">{fmtTs(t.resolvedAt)}</span>
                  </div>
                  <p className="trd-final-resolution__text">{t.finalResolution}</p>
                </div>
              ) : t.suggestedResolution ? (
                <div className="trd-feedback-row">
                  <span className="trd-feedback-row__label">Mark this suggestion:</span>
                  <button
                    type="button"
                    className={`trd-feedback-btn trd-feedback-btn--accept ${feedbackAct === "accept" ? "trd-feedback-btn--active" : ""}`}
                    onClick={() => setFeedbackAct("accept")}
                  >
                    ✓ Accept
                  </button>
                  <button
                    type="button"
                    className={`trd-feedback-btn trd-feedback-btn--reject ${feedbackAct === "reject" ? "trd-feedback-btn--active" : ""}`}
                    onClick={() => setFeedbackAct("reject")}
                  >
                    ✕ Override
                  </button>
                </div>
              ) : null}
            </div>

            <div className="trd-card trd-card--full">
              <div className="trd-card__label">Analyst Note</div>
              <p className="trd-card__hint">Document override rationale or model failure mode. Saved to ticket_updates.</p>
              <textarea
                className="trd-textarea"
                placeholder="e.g. Model missed 'VPN' vocabulary — route to IT was obvious from the subject. Flagging for retraining dataset."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={4}
              />
              <div className="trd-note-footer">
                <button type="button" className="trd-save-btn" onClick={saveNote}>Save Note</button>
                {noteSaved && <span className="trd-note-saved">✓ Saved</span>}
              </div>
            </div>
          </div>
        </TabPanel>

      </div>
    </Layout>
  );
}