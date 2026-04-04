import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import "./TicketReviewDetail.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";
import {
  sanitizeText,
  sanitizeId,
  MAX_NOTE_LEN,
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
const AGENT_ICONS     = { sentiment: "brain", feature: "settings", routing: "shuffle", priority: "sliders", resolution: "zap", sla: "clock" };
const UPDATE_ICONS    = { status_change: "refresh-cw", assignment: "user", override: "edit", resolution: "check-circle", comment: "message-circle" };

// ── Inline SVG icon component ─────────────────────────────────────────────────
function Ico({ name, size = 14, style = {} }) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor", strokeWidth: "2",
    strokeLinecap: "round", strokeLinejoin: "round",
    style: { display: "inline-block", verticalAlign: "middle", flexShrink: 0, ...style },
    "aria-hidden": "true",
  };
  switch (name) {
    case "brain":
      return <svg {...p}><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.14"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.14"/></svg>;
    case "cpu":
      return <svg {...p}><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>;
    case "settings":
      return <svg {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
    case "shuffle":
      return <svg {...p}><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>;
    case "sliders":
      return <svg {...p}><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>;
    case "zap":
      return <svg {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
    case "clock":
      return <svg {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
    case "refresh-cw":
      return <svg {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>;
    case "user":
      return <svg {...p}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
    case "edit":
      return <svg {...p}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
    case "check-circle":
      return <svg {...p}><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>;
    case "message-circle":
      return <svg {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>;
    case "search":
      return <svg {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
    case "file-text":
      return <svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>;
    case "activity":
      return <svg {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
    case "repeat":
      return <svg {...p}><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>;
    case "alert-triangle":
      return <svg {...p}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
    case "tool":
      return <svg {...p}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>;
    case "briefcase":
      return <svg {...p}><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>;
    case "calendar":
      return <svg {...p}><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>;
    case "dot":
      return <svg {...p} fill="currentColor" stroke="none"><circle cx="12" cy="12" r="5"/></svg>;
    default:
      return null;
  }
}

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
        <div className="trd-not-found__icon"><Ico name="search" size={36} /></div>
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
  const { ticketId: rawTicketId } = useParams();
  const ticketId  = sanitizeId(rawTicketId);
  const navigate     = useNavigate();
  const revealRef    = useScrollReveal();

  const [ticketData,  setTicketData]  = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  const [tab,          setTab]          = useState("overview");
  const [noteText,     setNoteText]     = useState("");
  const [noteSaved,    setNoteSaved]    = useState(false);
  const [feedbackAct,  setFeedbackAct]  = useState(null);
  const [pendingFeedback, setPendingFeedback] = useState(null); // "accept" | "reject" | null

  // FIX: useCallback so the function reference is stable — prevents infinite re-renders
  // and ensures onRetry always calls the latest version.
  const loadTicket = useCallback(async () => {
    if (!ticketId) { setError("Invalid ticket ID."); setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const raw = await apiFetch(`/operator/complaints/${encodeURIComponent(ticketId)}`);
      const t   = transformTicket(raw);
      // Sanitize string fields at the load boundary
      t.ticketCode   = sanitizeId(t.ticketCode);
      t.subject      = sanitizeText(t.subject, 300);
      t.details      = sanitizeText(t.details, 5000);
      t.status       = sanitizeText(t.status, 50);
      t.priority     = sanitizeText(t.priority, 50);
      t.finalDept    = sanitizeText(t.finalDept, 100);
      t.assignedToName  = sanitizeText(t.assignedToName, 100);
      t.assignedToTitle = sanitizeText(t.assignedToTitle, 100);
      t.createdByName   = sanitizeText(t.createdByName, 100);
      t.createdByRole   = sanitizeText(t.createdByRole, 100);
      t.suggestedResolution = sanitizeText(t.suggestedResolution, 5000);
      t.finalResolution     = sanitizeText(t.finalResolution, 5000);
      t.routingReason       = sanitizeText(t.routingReason, 1000);
      t.overrideReason      = sanitizeText(t.overrideReason, 1000);
      setTicketData(t);
      setFeedbackAct(t.feedbackDecision);
    } catch {
      setError("Failed to load ticket details. Please try again.");
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
    { id: "overview",   label: "Overview",    icon: "file-text" },
    { id: "ai",         label: "AI Analysis", icon: "cpu" },
    { id: "activity",   label: "Activity",    icon: "activity" },
    { id: "resolution", label: "Resolution",  icon: "zap" },
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
              {t.humanOverridden && <Badge variant="amber"><Ico name="edit" size={11} /> Overridden</Badge>}
              {t.isRecurring     && <Badge variant="amber"><Ico name="repeat" size={11} /> Recurring</Badge>}
              {(t.respondBreached || t.resolveBreached) && <Badge variant="danger"><Ico name="alert-triangle" size={11} /> SLA Breached</Badge>}
            </div>
            <h1 className="trd-hero__subject">{t.subject}</h1>
            <div className="trd-hero__people">
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon"><Ico name="user" size={16} /></span>
                <div>
                  <span className="trd-hero__person-role">Submitted by</span>
                  <span className="trd-hero__person-name">{t.createdByName}{t.createdByRole ? ` · ${t.createdByRole}` : ""}</span>
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon"><Ico name="tool" size={16} /></span>
                <div>
                  <span className="trd-hero__person-role">Assigned to</span>
                  <span className="trd-hero__person-name">{t.assignedToName}</span>
                  {t.assignedToTitle && <span className="trd-hero__person-sub">{t.assignedToTitle}</span>}
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon"><Ico name="briefcase" size={16} /></span>
                <div>
                  <span className="trd-hero__person-role">Department</span>
                  <span className="trd-hero__person-name">{t.finalDept}</span>
                </div>
              </div>
              <div className="trd-hero__divider" />
              <div className="trd-hero__person">
                <span className="trd-hero__person-icon"><Ico name="calendar" size={16} /></span>
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
              <span className="trd-tab__icon"><Ico name={tb.icon} size={15} /></span>
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
                  {responseTimeMins  != null && <span className="trd-timing-chip"><Ico name="zap" size={13} /> Response: <strong>{responseTimeMins} min</strong></span>}
                  {resolutionTimeHrs != null && <span className="trd-timing-chip"><Ico name="check-circle" size={13} /> Resolved in: <strong>{resolutionTimeHrs}h</strong></span>}
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
                <span className="trd-override-banner__icon"><Ico name="edit" size={16} /></span>
                <div>
                  <span className="trd-override-banner__title">Human Override Applied</span>
                  <span className="trd-override-banner__text">{t.overrideReason}</span>
                </div>
              </div>
            )}

            <div className="trd-decisions-grid">
              <div className={`trd-decision-card ${routingChanged ? "trd-decision-card--changed" : "trd-decision-card--ok"}`}>
                <div className="trd-decision-card__header">
                  <span className="trd-decision-card__icon"><Ico name="shuffle" size={16} /></span>
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
                    <span className="trd-decision-card__icon"><Ico name="sliders" size={16} /></span>
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
                        <span className="trd-pipeline__name"><Ico name={AGENT_ICONS[entry.agent] || "dot"} size={14} /> {entry.agent}</span>
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
                          <Ico name={UPDATE_ICONS[u.updateType] || "dot"} size={14} /> {u.updateType.replace(/_/g, " ")}
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
                    <Ico name="check-circle" size={16} />
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
                    onClick={() => setPendingFeedback("accept")}
                  >
                    ✓ Accept
                  </button>
                  <button
                    type="button"
                    className={`trd-feedback-btn trd-feedback-btn--reject ${feedbackAct === "reject" ? "trd-feedback-btn--active" : ""}`}
                    onClick={() => setPendingFeedback("reject")}
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
                onChange={(e) => setNoteText(e.target.value.slice(0, MAX_NOTE_LEN))}
                maxLength={MAX_NOTE_LEN}
                rows={4}
              />
              <div style={{ fontSize: 11, color: "rgba(26,26,46,0.4)", textAlign: "right", marginTop: 2 }}>
                {noteText.length}/{MAX_NOTE_LEN}
              </div>
              <div className="trd-note-footer">
                <button type="button" className="trd-save-btn" onClick={saveNote}>Save Note</button>
                {noteSaved && <span className="trd-note-saved">✓ Saved</span>}
              </div>
            </div>
          </div>
        </TabPanel>

      </div>
    
      <ConfirmDialog
        open={pendingFeedback !== null}
        icon={pendingFeedback === "accept" ? "✓" : "✕"}
        title={pendingFeedback === "accept" ? "Accept suggestion?" : "Override suggestion?"}
        message={pendingFeedback === "accept"
          ? "Mark the AI suggestion as correct. This will be recorded as accepted."
          : "Mark the AI suggestion as incorrect. This will be recorded as a human override."}
        confirmLabel={pendingFeedback === "accept" ? "Accept" : "Override"}
        cancelLabel="Cancel"
        variant={pendingFeedback === "accept" ? "success" : "warning"}
        onConfirm={() => { setFeedbackAct(pendingFeedback); setPendingFeedback(null); }}
        onCancel={() => setPendingFeedback(null)}
      />
    </Layout>
  );
}