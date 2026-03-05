import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PriorityPill from "../../components/common/PriorityPill";
import { apiUrl } from "../../config/apiBase";
import { authHeader } from "../../utils/auth";
import "./CustomerTicketDetails.css";

const AI_PIPELINE_STAGES = [
  { id: "orchestrator", label: "Controller / Orchestrator", explain: "Starts the AI workflow and routes ticket data to downstream agents." },
  { id: "classification", label: "Classification Agent", conditional: true, explain: "Determines inquiry vs complaint if type was not already provided." },
  { id: "sentiment", label: "Sentiment Analysis Agent", explain: "Reads the message tone to estimate customer sentiment from text." },
  { id: "audio", label: "Audio Analysis Agent", conditional: true, explain: "Analyzes voice signals when an audio submission exists." },
  { id: "combiner", label: "Sentiment Combiner", conditional: true, explain: "Merges text and audio sentiment into one unified score." },
  { id: "feature", label: "Feature Engineering Agent", explain: "Builds risk and business-impact features used for prioritization." },
  { id: "priority", label: "Prioritization Agent", explain: "Assigns the ticket’s urgency level (Low to Critical)." },
  { id: "sla", label: "SLA Check", explain: "Applies SLA rules and escalation thresholds based on priority." },
  { id: "routing", label: "Department Routing", explain: "Assigns the ticket to the right team and responsible employee." },
  { id: "resolution", label: "Suggested Resolution Agent", explain: "Generates a recommended action plan for fast resolution." },
  { id: "feedback", label: "Employee Feedback Loop", conditional: true, explain: "Learns from employee outcomes to improve future decisions." },
];
const AI_STAGE_INDEX = AI_PIPELINE_STAGES.reduce((acc, stage, idx) => {
  acc[stage.id] = idx;
  return acc;
}, {});

function getCurrentAiStageIndex(status) {
  const key = String(status || "").toLowerCase().replaceAll(" ", "");
  switch (key) {
    case "open":
      return 0;
    case "inprogress":
      return 5;
    case "escalated":
    case "overdue":
      return 7;
    case "assigned":
      return 8;
    case "resolved":
      return AI_PIPELINE_STAGES.length - 1;
    case "reopened":
      return 8;
    default:
      return 0;
  }
}

function formatTicketSource(value) {
  return String(value || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
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
        const res = await fetch(apiUrl(`/api/customer/tickets/${id}`), {
          headers: authHeader(),
        });
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        const t = data.ticket;
        if (!isMounted) return;

        setTicket({
          id: t.ticketId,
          title: t.description?.subject,
          type: "Ticket",
          source: formatTicketSource(t.ticketSource),
          status: t.status,
          date: t.issueDate,
          priority: t.priority,
          description: t.description?.details,
          updates:
            t.updates?.map((u) => ({
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

    return () => {
      isMounted = false;
      window.clearInterval(pollId);
    };
  }, [id]);

  const statusTone = (status) => {
    const s = String(status || "").toLowerCase().replaceAll(" ", "");
    if (s === "resolved") return { color: "#1f7a3a", bg: "rgba(31,122,58,0.12)" };
    if (s === "inprogress") return { color: "#b65a00", bg: "rgba(182,90,0,0.12)" };
    if (s === "escalated" || s === "overdue") return { color: "#b42318", bg: "rgba(180,35,24,0.12)" };
    return { color: "#6d28d9", bg: "rgba(109,40,217,0.12)" };
  };

  const updateTypeTone = (type) => {
    const t = String(type || "").toLowerCase();
    if (t === "system") return { dot: "#6d28d9", bg: "rgba(109,40,217,0.1)", color: "#6d28d9", label: "AI Stage" };
    if (t === "status_change") return { dot: "#1f7a3a", bg: "rgba(31,122,58,0.12)", color: "#1f7a3a", label: "Status" };
    if (t === "priority_change") return { dot: "#b65a00", bg: "rgba(182,90,0,0.12)", color: "#b65a00", label: "Priority" };
    return { dot: "rgba(20,20,20,0.3)", bg: "rgba(20,20,20,0.08)", color: "rgba(20,20,20,0.6)", label: type || "Update" };
  };

  const latestOrchestratorUpdate = [...(ticket?.updates || [])]
    .reverse()
    .find((u) => u.type === "system" && u.meta?.source === "orchestrator" && u.meta?.stage_id);
  const orchestratorStageIndex = latestOrchestratorUpdate
    ? AI_STAGE_INDEX[latestOrchestratorUpdate.meta.stage_id]
    : undefined;
  const currentAiStageIndex = Number.isInteger(orchestratorStageIndex)
    ? orchestratorStageIndex
    : getCurrentAiStageIndex(ticket?.status);
  const currentAiStage = AI_PIPELINE_STAGES[currentAiStageIndex]?.label || "Controller / Orchestrator";
  const currentAiStageObj = AI_PIPELINE_STAGES[currentAiStageIndex] || AI_PIPELINE_STAGES[0];
  const nextAiStageObj = AI_PIPELINE_STAGES[currentAiStageIndex + 1] || null;
  const aiProgress = Math.round((currentAiStageIndex / (AI_PIPELINE_STAGES.length - 1)) * 100);

  const tone = statusTone(ticket?.status);

  return (
    <Layout role="customer">
      <div className="ctd-page">
        <PageHeader
          title="Ticket Details"
          subtitle="View ticket information, status, and updates."
          actions={
            <button
              type="button"
              className="ctd-back-btn"
              onClick={() => navigate("/customer/mytickets")}
            >
              Back to My Tickets
            </button>
          }
        />

        {loading ? (
          <div className="ctd-card ctd-loading">
            <div className="ctd-loading-spinner" />
            <div>Loading ticket...</div>
          </div>
        ) : !ticket ? (
          <div className="ctd-card ctd-not-found">
            <div className="ctd-not-found-icon">🧾</div>
            <h3>Ticket not found</h3>
            <p>We couldn’t find a ticket with ID <strong>{id}</strong>.</p>
            <button
              type="button"
              className="ctd-back-btn"
              onClick={() => navigate("/customer/mytickets")}
            >
              Go to My Tickets
            </button>
          </div>
        ) : (
          <div className="ctd-layout">
            <section className="ctd-card">
              <div className="ctd-card-topbar">
                <div className="ctd-ticket-id-row">
                  <span className="ctd-ticket-id">{ticket.id}</span>
                  <span className="ctd-divider-dot">•</span>
                  <span className="ctd-ticket-id">{ticket.type}</span>
                  <span className="ctd-divider-dot">•</span>
                  <span className="ctd-ticket-id">{ticket.source}</span>
                  <span className="ctd-divider-dot">•</span>
                  <span className="ctd-status-badge" style={{ color: tone.color, background: tone.bg }}>
                    <span className="ctd-status-dot" style={{ background: tone.color }} />
                    {ticket.status}
                  </span>
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
              </div>

              <div className="ctd-divider" />
              <div className="ctd-section-label">Description</div>
              <p className="ctd-description">{ticket.description}</p>
            </section>

            <section className="ctd-card">
              <div className="ctd-section-label">Updates</div>

              {/* ── Status Pipeline Tracker ── */}
              <div className="ctd-pipeline-wrap">
                {(() => {
                  const STATUS_STAGES = [
                    { id: "open",       label: "Opened" },
                    { id: "inprogress", label: "In Progress" },
                    { id: "assigned",   label: "Assigned" },
                    { id: "overdue",    label: "Overdue" },
                    { id: "escalated",  label: "Escalated" },
                    { id: "resolved",   label: "Resolved" },
                  ];

                  const normalise = (s) => String(s || "").toLowerCase().replace(/\s+/g, "");
                  const currentKey = normalise(ticket.status);

                  // Map ticket status → stage index
                  const keyToIdx = {
                    open: 0, inprogress: 1, assigned: 2,
                    overdue: 3, escalated: 4, resolved: 5,
                  };
                  const currentIdx = keyToIdx[currentKey] ?? 0;
                  const progress = Math.round((currentIdx / (STATUS_STAGES.length - 1)) * 100);

                  return (
                    <>
                      <div className="ctd-pipeline-header">
                        <div>
                          <div className="ctd-pipeline-eyebrow">Ticket Status</div>
                          <div className="ctd-pipeline-current-label">{STATUS_STAGES[currentIdx].label}</div>
                        </div>
                        <div className="ctd-pipeline-fraction">
                          <span className="ctd-pipeline-fraction-num">{currentIdx + 1}</span>
                          <span className="ctd-pipeline-fraction-sep">/</span>
                          <span className="ctd-pipeline-fraction-total">{STATUS_STAGES.length}</span>
                        </div>
                      </div>

                      <div className="ctd-progress-track">
                        <div className="ctd-progress-fill" style={{ width: `${progress}%` }} />
                      </div>

                      <div className="ctd-stage-dots">
                        {STATUS_STAGES.map((stage, idx) => (
                          <div
                            key={stage.id}
                            className={`ctd-stage-dot-wrap ${idx < currentIdx ? "done" : ""} ${idx === currentIdx ? "current" : ""}`}
                          >
                            <div className={`ctd-stage-dot ${idx < currentIdx ? "done" : ""} ${idx === currentIdx ? "current" : ""}`}>
                              {idx < currentIdx && <span className="ctd-dot-check">✓</span>}
                              {idx === currentIdx && <span className="ctd-dot-pulse" />}
                            </div>
                            <div className={`ctd-stage-dot-label ${idx === currentIdx ? "active" : ""}`}>
                              {stage.label}
                              {idx === currentIdx && <span className="ctd-dot-cond">Current</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  );
                })()}
              </div>

              <div className="ctd-divider ctd-divider--updates" />
              <div className="ctd-section-label">Activity Log</div>
              {ticket.updates.length ? (
                <div className="ctd-log-list">
                  {ticket.updates.map((u, idx) => {
                    const t = updateTypeTone(u.type);
                    return (
                      <div key={idx} className="ctd-log-row">
                        <div className="ctd-log-spine">
                          <div className="ctd-log-dot" style={{ background: t.dot }} />
                          {idx < ticket.updates.length - 1 && <div className="ctd-log-line" />}
                        </div>
                        <div className="ctd-log-body">
                          <div className="ctd-log-meta">
                            <span className="ctd-log-author">{u.author || "System"}</span>
                            <span className="ctd-log-type-tag" style={{ background: t.bg, color: t.color }}>
                              {t.label}
                            </span>
                            <span className="ctd-log-date">{u.date}</span>
                          </div>
                          <div className="ctd-log-text">{u.message || u.text}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="ctd-log-empty">
                  <div className="ctd-log-empty-icon">💬</div>
                  <div>No activity updates yet.</div>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </Layout>
  );
}