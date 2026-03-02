import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PriorityPill from "../../components/common/PriorityPill";
import { apiUrl } from "../../config/apiBase";
import { authHeader } from "../../utils/auth";
import "./CustomerTicketDetails.css";

const AI_PIPELINE_STAGES = [
  { id: "orchestrator",  label: "Orchestrator",           icon: "⚙️", explain: "Starts the AI workflow and routes ticket data to downstream agents." },
  { id: "classification",label: "Classification",         icon: "🏷️", conditional: true, explain: "Determines inquiry vs complaint if type was not already provided." },
  { id: "sentiment",     label: "Sentiment Analysis",     icon: "💬", explain: "Reads the message tone to estimate customer sentiment from text." },
  { id: "audio",         label: "Audio Analysis",         icon: "🎙️", conditional: true, explain: "Analyzes voice signals when an audio submission exists." },
  { id: "combiner",      label: "Sentiment Combiner",     icon: "🔀", conditional: true, explain: "Merges text and audio sentiment into one unified score." },
  { id: "feature",       label: "Feature Engineering",    icon: "🧪", explain: "Builds risk and business-impact features used for prioritization." },
  { id: "priority",      label: "Prioritization",         icon: "📊", explain: "Assigns the ticket's urgency level (Low to Critical)." },
  { id: "sla",           label: "SLA Check",              icon: "⏱️", explain: "Applies SLA rules and escalation thresholds based on priority." },
  { id: "routing",       label: "Department Routing",     icon: "🔀", explain: "Assigns the ticket to the right team and responsible employee." },
  { id: "resolution",    label: "Suggested Resolution",   icon: "💡", explain: "Generates a recommended action plan for fast resolution." },
  { id: "feedback",      label: "Feedback Loop",          icon: "🔄", conditional: true, explain: "Learns from employee outcomes to improve future decisions." },
];

const AI_STAGE_INDEX = AI_PIPELINE_STAGES.reduce((acc, stage, idx) => {
  acc[stage.id] = idx;
  return acc;
}, {});

function getCurrentAiStageIndex(status) {
  const key = String(status || "").toLowerCase().replaceAll(" ", "");
  switch (key) {
    case "open":       return 0;
    case "inprogress": return 5;
    case "escalated":
    case "overdue":    return 7;
    case "assigned":   return 8;
    case "resolved":   return AI_PIPELINE_STAGES.length - 1;
    case "reopened":   return 8;
    default:           return 0;
  }
}

function StatusBadge({ status }) {
  const colorMap = {
    Open:       { bg: "rgba(124,58,237,0.1)",  color: "#7c3aed", dot: "#7c3aed" },
    InProgress: { bg: "rgba(234,88,12,0.1)",   color: "#c2410c", dot: "#f97316" },
    Escalated:  { bg: "rgba(220,38,38,0.1)",   color: "#dc2626", dot: "#ef4444" },
    Overdue:    { bg: "rgba(220,38,38,0.1)",   color: "#dc2626", dot: "#ef4444" },
    Assigned:   { bg: "rgba(37,99,235,0.1)",   color: "#1d4ed8", dot: "#3b82f6" },
    Resolved:   { bg: "rgba(22,163,74,0.1)",   color: "#15803d", dot: "#22c55e" },
    Reopened:   { bg: "rgba(234,179,8,0.1)",   color: "#a16207", dot: "#eab308" },
  };
  const s = String(status || "").replaceAll(" ", "");
  const style = colorMap[s] || { bg: "rgba(0,0,0,0.06)", color: "#444", dot: "#888" };

  return (
    <span className="ctd-status-badge" style={{ background: style.bg, color: style.color }}>
      <span className="ctd-status-dot" style={{ background: style.dot }} />
      {status}
    </span>
  );
}

function PipelineTracker({ currentAiStageIndex }) {
  const total = AI_PIPELINE_STAGES.length;
  const progress = Math.round((currentAiStageIndex / (total - 1)) * 100);
  const currentStage = AI_PIPELINE_STAGES[currentAiStageIndex];
  const nextStage = AI_PIPELINE_STAGES[currentAiStageIndex + 1] || null;

  return (
    <div className="ctd-pipeline-wrap">
      {/* Header row */}
      <div className="ctd-pipeline-header">
        <div>
          <div className="ctd-pipeline-eyebrow">AI Processing Pipeline</div>
          <div className="ctd-pipeline-current-label">{currentStage.icon} {currentStage.label}</div>
        </div>
        <div className="ctd-pipeline-fraction">
          <span className="ctd-pipeline-fraction-num">{currentAiStageIndex + 1}</span>
          <span className="ctd-pipeline-fraction-sep">/</span>
          <span className="ctd-pipeline-fraction-total">{total}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="ctd-progress-track">
        <div className="ctd-progress-fill" style={{ width: `${progress}%` }} />
      </div>

      {/* Stage dots — compact row */}
      <div className="ctd-stage-dots">
        {AI_PIPELINE_STAGES.map((stage, idx) => {
          const done    = idx < currentAiStageIndex;
          const current = idx === currentAiStageIndex;
          return (
            <div key={stage.id} className="ctd-stage-dot-wrap" title={stage.label}>
              <div className={`ctd-stage-dot ${done ? "done" : ""} ${current ? "current" : ""}`}>
                {done && <span className="ctd-dot-check">✓</span>}
                {current && <span className="ctd-dot-pulse" />}
              </div>
              <div className={`ctd-stage-dot-label ${current ? "active" : ""}`}>
                {stage.label}
                {stage.conditional && <span className="ctd-dot-cond">cond</span>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Current + Next explanation cards */}
      <div className="ctd-stage-cards">
        <div className="ctd-stage-card ctd-stage-card--current">
          <div className="ctd-stage-card-eyebrow">Current Stage</div>
          <div className="ctd-stage-card-title">{currentStage.icon} {currentStage.label}</div>
          <p className="ctd-stage-card-text">{currentStage.explain}</p>
        </div>
        <div className="ctd-stage-card ctd-stage-card--next">
          <div className="ctd-stage-card-eyebrow">What Happens Next</div>
          <div className="ctd-stage-card-title">
            {nextStage ? `${nextStage.icon} ${nextStage.label}` : "✅ Pipeline Complete"}
          </div>
          <p className="ctd-stage-card-text">
            {nextStage
              ? nextStage.explain
              : "AI processing is complete. The ticket is now in the hands of your support team."}
          </p>
        </div>
      </div>
    </div>
  );
}

function ActivityLog({ updates }) {
  if (!updates.length) {
    return (
      <div className="ctd-log-empty">
        <span className="ctd-log-empty-icon">📭</span>
        <span>No activity yet — updates will appear here as your ticket progresses.</span>
      </div>
    );
  }

  const typeStyle = (type) => {
    switch ((type || "").toLowerCase()) {
      case "system":   return { dot: "#7c3aed", label: "System" };
      case "agent":    return { dot: "#2563eb", label: "Agent" };
      case "resolved": return { dot: "#16a34a", label: "Resolved" };
      default:         return { dot: "#9ca3af", label: "Update" };
    }
  };

  return (
    <div className="ctd-log-list">
      {updates.map((u, idx) => {
        const ts = typeStyle(u.type);
        return (
          <div key={idx} className="ctd-log-row">
            <div className="ctd-log-spine">
              <div className="ctd-log-dot" style={{ background: ts.dot }} />
              {idx < updates.length - 1 && <div className="ctd-log-line" />}
            </div>
            <div className="ctd-log-body">
              <div className="ctd-log-meta">
                <span className="ctd-log-author">{u.author}</span>
                <span className="ctd-log-type-tag" style={{ color: ts.dot, background: `${ts.dot}18` }}>{ts.label}</span>
                <span className="ctd-log-date">{u.date}</span>
              </div>
              <div className="ctd-log-text">{u.message || u.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CustomerTicketDetails() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const loadTicket = async (silent = false) => {
      if (!silent && isMounted) setLoading(true);
      try {
        const res = await fetch(apiUrl(`/api/customer/tickets/${id}`), { headers: authHeader() });
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        const t = data.ticket;
        if (!isMounted) return;
        setTicket({
          id: t.ticketId,
          title: t.description?.subject,
          type: "Ticket",
          status: t.status,
          date: t.issueDate,
          priority: t.priority,
          description: t.description?.details,
          updates: t.updates?.map((u) => ({
            date: u.date ? new Date(u.date).toLocaleString() : "",
            text: `${u.author || "System"}: ${u.message}`,
            message: u.message,
            type: u.type,
            author: u.author || "System",
            meta: u.meta || {},
          })) || [],
        });
      } catch {
        if (isMounted) setTicket(null);
      } finally {
        if (!silent && isMounted) setLoading(false);
      }
    };

    loadTicket(false);
    const pollId = window.setInterval(() => loadTicket(true), 5000);
    return () => { isMounted = false; window.clearInterval(pollId); };
  }, [id]);

  const latestOrchestratorUpdate = [...(ticket?.updates || [])]
    .reverse()
    .find((u) => u.type === "system" && u.meta?.source === "orchestrator" && u.meta?.stage_id);

  const orchestratorStageIndex = latestOrchestratorUpdate
    ? AI_STAGE_INDEX[latestOrchestratorUpdate.meta.stage_id]
    : undefined;

  const currentAiStageIndex = Number.isInteger(orchestratorStageIndex)
    ? orchestratorStageIndex
    : getCurrentAiStageIndex(ticket?.status);

  if (loading) {
    return (
      <Layout role="customer">
        <div className="ctd-loading">
          <div className="ctd-loading-spinner" />
          <span>Loading ticket…</span>
        </div>
      </Layout>
    );
  }

  if (!ticket) {
    return (
      <Layout role="customer">
        <div className="ctd-not-found">
          <div className="ctd-not-found-icon">🔍</div>
          <h3>Ticket not found</h3>
          <p>We couldn't find a ticket with ID <strong>{id}</strong>.</p>
          <button type="button" className="ctd-back-btn" onClick={() => navigate("/customer/mytickets")}>
            Go to My Tickets
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout role="customer">
      <div className="ctd-page">
        <PageHeader
          title="Ticket Details"
          subtitle="View ticket information, status, and updates."
          actions={
            <button type="button" className="ctd-back-btn" onClick={() => navigate("/customer/mytickets")}>
              ← Back to My Tickets
            </button>
          }
        />

        <div className="ctd-layout">
          {/* ── Left column: ticket info + pipeline ── */}
          <div className="ctd-main">

            {/* Ticket card */}
            <section className="ctd-card">
              <div className="ctd-card-topbar">
                <div className="ctd-ticket-id-row">
                  <span className="ctd-ticket-id">{ticket.id}</span>
                  <span className="ctd-divider-dot">·</span>
                  <StatusBadge status={ticket.status} />
                </div>
              </div>

              <h2 className="ctd-ticket-title">{ticket.title}</h2>

              <div className="ctd-meta-row">
                <div className="ctd-meta-item">
                  <span className="ctd-meta-label">Priority</span>
                  <PriorityPill priority={ticket.priority} />
                </div>
                <div className="ctd-meta-item">
                  <span className="ctd-meta-label">Created</span>
                  <span className="ctd-meta-value">{ticket.date}</span>
                </div>
                <div className="ctd-meta-item">
                  <span className="ctd-meta-label">Type</span>
                  <span className="ctd-meta-value">{ticket.type}</span>
                </div>
              </div>

              <div className="ctd-divider" />

              <div>
                <div className="ctd-section-label">Description</div>
                <p className="ctd-description">{ticket.description}</p>
              </div>
            </section>

            {/* AI Pipeline tracker */}
            <section className="ctd-card">
              <PipelineTracker currentAiStageIndex={currentAiStageIndex} />
            </section>

          </div>

          {/* ── Right column: activity log ── */}
          <aside className="ctd-aside">
            <section className="ctd-card ctd-card--aside">
              <div className="ctd-section-label" style={{ marginBottom: 20 }}>Activity Log</div>
              <ActivityLog updates={ticket.updates} />
            </section>
          </aside>
        </div>
      </div>
    </Layout>
  );
}