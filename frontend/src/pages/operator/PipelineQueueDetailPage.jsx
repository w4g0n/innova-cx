import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import { apiUrl } from "../../config/apiBase";
import { getCsrfToken } from "../../services/api";
import "./PipelineQueuePage.css";

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

async function apiFetch(path, opts = {}) {
  const token = getStoredToken();
  const res = await fetch(apiUrl(`/api${path}`), {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, ...opts.headers },
  });
  if (res.status === 401 || res.status === 403) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "Request failed");
    throw new Error(detail || "Request failed");
  }
  return res.json();
}

const QUEUE_STATUS_LABEL = { queued: "Queued", processing: "Processing", held: "Held", completed: "Completed", failed: "Failed" };
const QUEUE_STATUS_COLOR = { queued: "#3b82f6", processing: "#f59e0b", held: "#ef4444", completed: "#22c55e", failed: "#6b7280" };
const CRITICAL_STAGES = new Set([
  "ClassificationAgent", "SentimentAgent", "AudioAnalysisAgent", "SentimentCombinerAgent",
  "FeatureEngineeringAgent", "PrioritizationAgent", "DepartmentRoutingAgent",
]);
const DEPARTMENT_OPTIONS = [
  "Facilities Management",
  "Legal & Compliance",
  "Safety & Security",
  "HR",
  "Leasing",
  "Maintenance",
  "IT",
];
const STAGE_OUTPUT_NOISE = new Set([
  "text", "details", "ticket_id", "created_by_user_id", "ticket_source",
  "audio_features", "ticket_code", "name", "email", "asset_type",
  "ticket_type", "label", "status", "has_audio", "_pipeline_total_steps",
  "is_recurring_checked", "audio_analysis_mode", "audio_sentiment",
  "recurrence_branch",
]);
const MAX_PIPELINE_RETRIES = 3;
const TOTAL_PIPELINE_STAGES = 11;
const DETAIL_POLL_INTERVAL_MS = 5_000;
const REFRESH_SPIN_DURATION_MS = 600;

function formatStageVal(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) {
    if (v.length === 0) return "—";
    if (typeof v[0] === "object") {
      return v.map((item) => item.department || item.label || JSON.stringify(item, null, 2)).join(", ");
    }
    return v.join(", ");
  }
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  return String(v);
}

function renderStageVal(v, kind = "default") {
  if (kind === "review_summary" && Array.isArray(v)) {
    return (
      <div className="pq-review-summary-list">
        {v.map((line, idx) => (
          <div key={`${idx}-${line}`} className="pq-review-summary-item">{line}</div>
        ))}
      </div>
    );
  }
  if (kind === "reason") {
    return <div className="pq-stage-output-text">{formatStageVal(v)}</div>;
  }
  if (kind === "multiline") {
    return <pre className="pq-stage-output-pre">{formatStageVal(v)}</pre>;
  }
  return <span>{formatStageVal(v)}</span>;
}

function formatStageKey(key) {
  return String(key || "")
    .replace(/^review_agent_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function summarizeReviewStageResults(results) {
  if (!Array.isArray(results) || results.length === 0) return [];
  return results
    .map((item) => {
      const stage = String(item?.stage || "Unknown").replace("Agent", "");
      const status = String(item?.status || "unknown");
      const fix = String(item?.fix_applied || "").trim();
      const issue = String(item?.issue || "").trim();

      if (status === "flagged") {
        return `${stage}: blocking issue${issue ? ` — ${issue}` : ""}`;
      }
      if (status === "fixed") {
        return `${stage}: corrected${fix ? ` — ${fix}` : issue ? ` — ${issue}` : ""}`;
      }
      if (status === "success") {
        return `${stage}: passed${issue ? ` — ${issue}` : ""}`;
      }
      return `${stage}: ${status}${fix ? ` — ${fix}` : issue ? ` — ${issue}` : ""}`;
    });
}

function getPrimaryReviewIssue(results, verdictReason) {
  const flagged = Array.isArray(results)
    ? results.find((item) => String(item?.status || "").toLowerCase() === "flagged")
    : null;
  if (flagged) {
    const stage = String(flagged?.stage || "Unknown").replace("Agent", "");
    const issue = String(flagged?.issue || "").trim();
    return issue ? `${stage}: ${issue}` : `${stage}: requires operator review`;
  }
  return verdictReason ? String(verdictReason) : "—";
}

function getSecondaryReviewNote(results, overrideStages) {
  const notes = [];
  if (Array.isArray(overrideStages) && overrideStages.length > 0) {
    notes.push(
      `Operator override note: ${overrideStages.map((name) => String(name).replace("Agent", "")).join(", ")}`
    );
  }
  const timeoutSuccesses = Array.isArray(results)
    ? results
        .filter((item) => String(item?.status || "").toLowerCase() === "success" && String(item?.issue || "").trim())
        .map((item) => `${String(item?.stage || "Unknown").replace("Agent", "")}: ${String(item?.issue || "").trim()}`)
    : [];
  notes.push(...timeoutSuccesses);
  return notes;
}

function getStageOutputRows(stage) {
  const inp = stage?.input_state || {};
  const out = stage?.output_state || {};

  if (stage?.stage_name === "ReviewAgent") {
    const rows = [];
    if (out.review_agent_verdict) {
      rows.push(["Verdict", out.review_agent_verdict]);
    }
    if (out.review_agent_verdict_reason) {
      rows.push(["Reason", out.review_agent_verdict_reason, "reason"]);
    }
    if (Array.isArray(out.review_agent_stage_results) && out.review_agent_stage_results.length > 0) {
      rows.push(["Stage Review Summary", summarizeReviewStageResults(out.review_agent_stage_results), "review_summary"]);
    }
    if (out.review_agent_operator_override_required !== undefined) {
      rows.push(["Operator Override Required", out.review_agent_operator_override_required]);
    }
    if (Array.isArray(out.review_agent_operator_override_stages) && out.review_agent_operator_override_stages.length > 0) {
      rows.push([
        "Operator Override Stages",
        out.review_agent_operator_override_stages.map((name) => String(name).replace("Agent", "")).join(", "),
      ]);
    }
    return rows;
  }

  if (stage?.stage_name === "SuggestedResolutionAgent") {
    const rows = [];
    if ("suggested_resolution" in out) {
      rows.push(["Suggested Resolution", out.suggested_resolution || "—", out.suggested_resolution ? "default" : "reason"]);
    }
    if (out.suggested_resolution_mode) {
      rows.push(["Suggested Resolution Mode", out.suggested_resolution_mode]);
    }
    if (out.suggested_resolution_model !== undefined) {
      rows.push(["Suggested Resolution Model", out.suggested_resolution_model || "—"]);
    }
    if (
      String(out.suggested_resolution_mode || "").toLowerCase() === "timeout_background" &&
      !out.suggested_resolution
    ) {
      rows.push([
        "Operator Note",
        "This ticket did not get a suggested resolution during the pipeline run because generation timed out. The operator and employee had no suggestion available at decision time.",
        "reason",
      ]);
    }
    return rows;
  }

  if (stage?.stage_name === "ClassificationAgent") {
    const confidence = out.class_confidence ?? out.classification_confidence;
    const classificationLabel = out.label || out.ticket_type || "—";
    return [
      [
        "Class Confidence",
        confidence !== null && confidence !== undefined ? confidence : "—",
      ],
      ["Classification Source", out.classification_source || "—"],
      ["Classification Output", classificationLabel],
    ];
  }

  if (stage?.stage_name === "PrioritizationAgent") {
    const details = out.priority_details || {};
    const confidence = details?.confidence;
    const engine = details?.engine || out.priority_mode || "—";
    const rows = [
      ["Final Priority", out.priority_label || "—"],
      [
        "Confidence",
        confidence !== null && confidence !== undefined
          ? `${(Number(confidence) * 100).toFixed(1)}%`
          : "—",
      ],
      ["Model Used", engine || "—"],
    ];
    if (out.respond_due_at) rows.push(["Respond Due", out.respond_due_at]);
    if (out.resolve_due_at) rows.push(["Resolve Due", out.resolve_due_at]);
    return rows;
  }

  if (stage?.stage_name === "DepartmentRoutingAgent") {
    const confidence = out.department_confidence ?? out.model_confidence;
    return [
      ["Department", out.department_selected || out.department || "—"],
      [
        "Confidence",
        confidence !== null && confidence !== undefined
          ? `${(Number(confidence) * 100).toFixed(1)}%`
          : "—",
      ],
      ["Model Used", out.department_routing_source || "—"],
    ];
  }

  return Object.entries(out).filter(([k, v]) => {
    if (k.startsWith("_") || STAGE_OUTPUT_NOISE.has(k)) return false;
    return JSON.stringify(v) !== JSON.stringify(inp[k]);
  }).map(([k, v]) => {
    const kind =
      Array.isArray(v) || (v && typeof v === "object") || String(v).length > 120
        ? "multiline"
        : "default";
    return [formatStageKey(k), v, kind];
  });
}

function renderReviewOutput(stage) {
  const out = stage?.output_state || {};
  const verdict = String(out.review_agent_verdict || "").toLowerCase();
  const summaryItems = summarizeReviewStageResults(out.review_agent_stage_results);
  const overrideStages = Array.isArray(out.review_agent_operator_override_stages)
    ? out.review_agent_operator_override_stages.map((name) => String(name).replace("Agent", ""))
    : [];
  const primaryIssue = getPrimaryReviewIssue(out.review_agent_stage_results, out.review_agent_verdict_reason);
  const secondaryNotes =
    verdict === "held_operator_review"
      ? getSecondaryReviewNote(
          out.review_agent_stage_results,
          []
        )
      : getSecondaryReviewNote(out.review_agent_stage_results, overrideStages);
  const isHeldForReview = verdict === "held_operator_review";
  const showOverrideCard =
    !isHeldForReview && out.review_agent_operator_override_required !== undefined;
  const operatorActionLabel = isHeldForReview
    ? "Operator Review Required"
    : "Operator Override Required";
  const operatorActionValue = isHeldForReview
    ? "Yes"
    : formatStageVal(out.review_agent_operator_override_required);

  return (
    <div className="pq-review-output">
      <div className="pq-review-output-grid">
        <div className="pq-review-output-card">
          <div className="pq-review-output-label">Verdict</div>
          <div className="pq-review-output-value">{formatStageVal(out.review_agent_verdict)}</div>
        </div>
        <div className="pq-review-output-card pq-review-output-card--wide">
          <div className="pq-review-output-label">Primary Issue</div>
          <div className="pq-review-output-text">{formatStageVal(primaryIssue)}</div>
        </div>
        <div className="pq-review-output-card pq-review-output-card--wide">
          <div className="pq-review-output-label">Stage Review Summary</div>
          {summaryItems.length > 0 ? (
            <div className="pq-review-summary-list">
              {summaryItems.map((line, idx) => (
                <div key={`${idx}-${line}`} className="pq-review-summary-item">{line}</div>
              ))}
            </div>
          ) : (
            <div className="pq-review-output-text">—</div>
          )}
        </div>
        {(isHeldForReview || showOverrideCard) && (
          <div className="pq-review-output-card">
            <div className="pq-review-output-label">{operatorActionLabel}</div>
            <div className="pq-review-output-value">{operatorActionValue}</div>
          </div>
        )}
        {secondaryNotes.length > 0 && (
          <div className="pq-review-output-card pq-review-output-card--wide">
            <div className="pq-review-output-label">Secondary Notes</div>
            <div className="pq-review-summary-list">
              {secondaryNotes.map((line, idx) => (
                <div key={`${idx}-${line}`} className="pq-review-summary-item">{line}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function isAudioStageWithoutInput(stage) {
  if (stage?.stage_name !== "AudioAnalysisAgent") return false;
  const inp = stage?.input_state || {};
  const hasAudio = Boolean(inp.has_audio);
  const audioFeatures = inp.audio_features;
  const hasAudioFeatures =
    !!audioFeatures &&
    ((Array.isArray(audioFeatures) && audioFeatures.length > 0) ||
      (typeof audioFeatures === "object" && Object.keys(audioFeatures).length > 0));
  return !hasAudio && !hasAudioFeatures;
}

function getNonBlockingStageWarning(stage) {
  if (stage?.stage_name === "SuggestedResolutionAgent") {
    const out = stage?.output_state || {};
    const mode = String(out.suggested_resolution_mode || "").toLowerCase();
    const suggestion = out.suggested_resolution;
    if (mode === "timeout_background" && !suggestion) {
      return "No suggested resolution was available during the run.";
    }
  }
  return null;
}

function hasPendingBackgroundSuggestedResolution(queueDetail) {
  const stages = Array.isArray(queueDetail?.stages) ? queueDetail.stages : [];
  return stages.some((stage) => {
    if (stage?.stage_name !== "SuggestedResolutionAgent") return false;
    const out = stage?.output_state || {};
    return (
      String(out.suggested_resolution_mode || "").toLowerCase() === "timeout_background" &&
      !out.suggested_resolution
    );
  });
}

function Ico({ name, size = 15 }) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor", strokeWidth: "2",
    strokeLinecap: "round", strokeLinejoin: "round",
    "aria-hidden": "true",
    style: { display: "inline-block", verticalAlign: "middle", flexShrink: 0 },
  };
  switch (name) {
    case "arrow-right":
      return <svg {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>;
    default:
      return null;
  }
}

export default function PipelineQueueDetailPage() {
  const navigate = useNavigate();
  const { queueId } = useParams();

  const [queueDetail, setQueueDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [spinning, setSpinning] = useState(false);
  const [error, setError] = useState("");
  const [corrections, setCorrections] = useState({});
  const [expandedStage, setExpandedStage] = useState(null);
  const [releaseBusy, setReleaseBusy] = useState(false);
  const [rerunBusy, setRerunBusy] = useState(false);
  const [fullRerunBusy, setFullRerunBusy] = useState(false);
  const [releaseMsg, setReleaseMsg] = useState("");
  const [releaseErr, setReleaseErr] = useState("");
  const intervalRef = useRef(null);

  const loadQueueDetail = useCallback(async (silent = false) => {
    if (!queueId) return;
    if (!silent) setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/operator/pipeline-queue/${queueId}`);
      setQueueDetail(res);
      setCorrections(res.operator_corrections || {});
      // Keep polling briefly for background suggested resolution completion so
      // the detail view can swap the timeout snapshot for the final result.
      if (
        ["completed", "failed", "held"].includes(res.status) &&
        !hasPendingBackgroundSuggestedResolution(res)
      ) {
        clearInterval(intervalRef.current);
      }
    } catch (e) {
      setError(e?.message || "Failed to load queue item.");
      setQueueDetail(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [queueId]);

  useEffect(() => {
    loadQueueDetail();
    // Auto-poll every 5s while processing/queued
    intervalRef.current = setInterval(() => loadQueueDetail(true), DETAIL_POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [loadQueueDetail]);

  function handleManualRefresh() {
    setRefreshing(true);
    setSpinning(true);
    setTimeout(() => setSpinning(false), REFRESH_SPIN_DURATION_MS);
    loadQueueDetail(true);
  }

  async function rerunStage() {
    if (!queueId) return;
    setRerunBusy(true);
    setReleaseMsg("");
    setReleaseErr("");
    setQueueDetail((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        status: "processing",
        current_stage: prev.failed_stage || prev.current_stage,
        current_step: prev.failed_at_step || prev.current_step,
        failure_reason: null,
      };
    });
    try {
      const token = getStoredToken();
      const csrf = await getCsrfToken();
      const res = await fetch(apiUrl(`/api/operator/pipeline-queue/${queueId}/rerun-stage`), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      });
      if (!res.ok) {
        const msg = await res.text().catch(() => "Failed");
        throw new Error(msg);
      }
      const data = await res.json();
      if (data.succeeded) {
        navigate("/operator/pipeline-queue");
        return;
      }
      setReleaseErr(`Stage still failing: ${data.reason || "unknown error"}. You can manually correct the output below.`);
      await loadQueueDetail();
    } catch (e) {
      setReleaseErr(e?.message || "Rerun failed.");
      await loadQueueDetail();
    } finally {
      setRerunBusy(false);
    }
  }

  async function rerunTicket() {
    if (!queueId) return;
    setFullRerunBusy(true);
    setReleaseMsg("");
    setReleaseErr("");
    try {
      const token = getStoredToken();
      const csrf = await getCsrfToken();
      const res = await fetch(apiUrl(`/api/operator/pipeline-queue/${queueId}/rerun`), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      });
      if (!res.ok) {
        const msg = await res.text().catch(() => "Failed");
        throw new Error(msg);
      }
      navigate("/operator/pipeline-queue");
    } catch (e) {
      setReleaseErr(e?.message || "Ticket rerun failed.");
    } finally {
      setFullRerunBusy(false);
    }
  }

  async function releaseTicket() {
    if (!queueId) return;
    setReleaseBusy(true);
    setReleaseMsg("");
    setReleaseErr("");
    try {
      const token = getStoredToken();
      const res = await fetch(apiUrl(`/api/operator/pipeline-queue/${queueId}/release`), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ corrections }),
      });
      if (!res.ok) {
        const msg = await res.text().catch(() => "Failed");
        throw new Error(msg);
      }
      navigate("/operator/pipeline-queue");
    } catch (e) {
      setReleaseErr(e?.message || "Release failed.");
    } finally {
      setReleaseBusy(false);
    }
  }

  const title = queueDetail?.ticket_code || "Queue Detail";

  return (
    <Layout role="operator">
      <div className="pq-detail-page">
        <div className="pq-detail-header">
          <PageHeader title={title} />
        </div>

        <div className="pq-detail-topbar">
          <button type="button" className="pq-back-btn" onClick={() => navigate("/operator/pipeline-queue")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="pq-btn-icon"><polyline points="15 18 9 12 15 6"/></svg>
            Back to Queue
          </button>
          <button type="button" className="pq-refresh-btn" onClick={handleManualRefresh} disabled={refreshing} title="Refresh">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={spinning ? "pq-spin" : ""} aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Refresh
          </button>
        </div>

        <div className="pq-detail-shell">
          {loading ? (
            <div className="pq-loading">Loading queue detail…</div>
          ) : error ? (
            <div className="pq-msg pq-msg--err">{error}</div>
          ) : !queueDetail ? (
            <div className="pq-empty">Queue item not found.</div>
          ) : (
            <>
              <div className="pq-detail-topbar">
                <div className="pq-detail-header-group">
                  <div className="pq-detail-subject">{queueDetail.subject || "—"}</div>
                </div>
                <div className="pq-detail-actions">
                  {queueDetail.status !== "completed" && (
                    <button
                      type="button"
                      className="pq-rerun-btn"
                      disabled={fullRerunBusy || rerunBusy || releaseBusy}
                      onClick={rerunTicket}
                    >
                      {fullRerunBusy ? "Rerunning..." : "Rerun Ticket"}
                    </button>
                  )}
                  {queueDetail.ticket_id && (
                    <button
                      type="button"
                      className="pq-action-ghost"
                      onClick={() => navigate(`/operator/complaints/${queueDetail.ticket_id}`)}
                    >
                      Open Ticket <Ico name="arrow-right" size={13} />
                    </button>
                  )}
                </div>
              </div>

              <div className="pq-detail-summary">
                <div className="pq-detail-summary-card">
                  <div className="pq-detail-summary-label">Status</div>
                  <div className="pq-detail-summary-value">
                    <span className="pq-status-badge" style={{ background: QUEUE_STATUS_COLOR[queueDetail.status] || "#6b7280" }}>
                      {QUEUE_STATUS_LABEL[queueDetail.status] || queueDetail.status || "—"}
                    </span>
                  </div>
                </div>
                <div className="pq-detail-summary-card">
                  <div className="pq-detail-summary-label">
                    {queueDetail.status === "processing"
                      ? "Current Stage"
                      : queueDetail.status === "held" && queueDetail.failure_category === "manual_pause"
                        ? "Paused After"
                        : queueDetail.status === "queued" && ["manual_pause", "recovered_restart"].includes(queueDetail.failure_category)
                          ? "Resume From"
                        : "Failed Stage"}
                  </div>
                  <div className="pq-detail-summary-value">
                    {(queueDetail.status === "processing"
                      ? (queueDetail.current_stage || queueDetail.failed_stage)
                      : queueDetail.failed_stage
                    )?.replace("Agent", "") || "—"}
                  </div>
                </div>
                <div className="pq-detail-summary-card">
                  <div className="pq-detail-summary-label">Retries</div>
                  <div className="pq-detail-summary-value">{queueDetail.display_retry_count ?? queueDetail.retry_count ?? 0}</div>
                </div>
                <div className="pq-detail-summary-card">
                  <div className="pq-detail-summary-label">Queue Position</div>
                  <div className="pq-detail-summary-value">{queueDetail.display_position ?? "—"}</div>
                </div>
              </div>

              {queueDetail.failure_reason && (queueDetail.status === "held" || queueDetail.status === "failed") && (
                <div className="pq-failure-banner">
                  <div className="pq-failure-top">
                    <span className={`pq-failure-cat pq-failure-cat--${queueDetail.failure_category || "unknown"}`}>
                      {{ timeout: "Timeout", model_error: "Model Error", connection_error: "Connection Error", manual_pause: "Paused", unknown: "Error" }[queueDetail.failure_category] || "Error"}
                    </span>
                    <span className="pq-failure-stage">
                      {queueDetail.failure_category === "manual_pause"
                        ? `After ${queueDetail.failed_stage?.replace("Agent", "") || "queue start"}`
                        : (queueDetail.failed_stage?.replace("Agent", "") || "Unknown stage")}
                    </span>
                  </div>
                  <div className="pq-failure-reason">{queueDetail.failure_reason}</div>
                </div>
              )}

              <div className="pq-inline-msgs">
                {releaseMsg && <div className="pq-msg pq-msg--ok">{releaseMsg}</div>}
                {releaseErr && <div className="pq-msg pq-msg--err">{releaseErr}</div>}
              </div>

              {(queueDetail.stages || []).length === 0 ? (
                <div className="pq-empty">No stage data yet for this run.</div>
              ) : (
                <>
                  <div className="pq-stages-header">
                    <span className="pq-stages-title">Pipeline Stages</span>
                    <span className="pq-stages-progress">
                      <span className="pq-stages-progress-count">
                        {queueDetail.stages.filter((s) => !(queueDetail.failure_category !== "manual_pause" && s.stage_name === queueDetail.failed_stage)).length}
                      </span>
                      <span className="pq-stages-progress-sep">/</span>
                      <span className="pq-stages-progress-total">{TOTAL_PIPELINE_STAGES}</span>
                      <span className="pq-stages-progress-label">completed</span>
                    </span>
                  </div>
                  <div className="pq-stages-grid">
                    {queueDetail.stages.map((stage, stageIdx) => {
                      const stageWarning = getNonBlockingStageWarning(stage);
                      const stageStatus = String(stage.status || "").toLowerCase();
                      const isProcessingRun = queueDetail.status === "processing";
                      const isCurrentStage =
                        isProcessingRun &&
                        stage.stage_name === (queueDetail.current_stage || queueDetail.failed_stage);
                      const hasRealStageFailure =
                        stageStatus === "failed" ||
                        (Boolean(stage.error_message) && stageStatus !== "success" && stageStatus !== "fixed");
                      const hasStageFailureSignal =
                        !isCurrentStage &&
                        (
                          hasRealStageFailure ||
                          Boolean(stageWarning)
                        );
                      const isFailed =
                        (
                          (queueDetail.status === "held" || queueDetail.status === "failed") &&
                          !isProcessingRun &&
                          queueDetail.failure_category !== "manual_pause" &&
                          stage.stage_name === queueDetail.failed_stage
                        ) || hasStageFailureSignal;
                      const statusClass = isFailed
                        ? "pq-stage--failed"
                        : isCurrentStage
                          ? "pq-stage--warn"
                          : "pq-stage--ok";
                      const isExpanded = expandedStage === stage.stage_name;
                      const isLast = stageIdx === queueDetail.stages.length - 1;
                      return (
                        <div key={stage.stage_name} className="pq-stage-flow-item">
                          <div className={`pq-stage-row ${statusClass} ${isFailed ? "pq-stage-row--failed" : ""} ${isExpanded ? "pq-stage-row--expanded" : ""}`}>
                            <button
                              type="button"
                              className="pq-stage-summary"
                              onClick={() => setExpandedStage(isExpanded ? null : stage.stage_name)}
                            >
                              <div className="pq-stage-icon-wrap">
                                <div className="pq-stage-num">{stageIdx + 1}</div>
                              </div>
                              <div className="pq-stage-summary-body">
                                <div className="pq-stage-name">
                                  {stage.stage_name.replace("Agent", "")}
                                  {CRITICAL_STAGES.has(stage.stage_name) && <span className="pq-critical-badge">Critical</span>}
                                  {stageWarning && <span className="pq-stage-note-badge">Operator Note</span>}
                                </div>
                                <div className="pq-stage-explain">
                                  {stage.explanation}
                                  {stageWarning && <span className="pq-stage-explain-note"> {stageWarning}</span>}
                                </div>
                              </div>
                              <div className="pq-stage-meta">
                                {stage.inference_time_ms && <span className="pq-stage-time">{(stage.inference_time_ms / 1000).toFixed(1)}s</span>}
                              </div>
                            </button>

                            {isExpanded && (
                              <div className="pq-stage-detail">
                                <div className="pq-stage-desc">{stage.description}</div>
                                {(() => {
                                  if (isAudioStageWithoutInput(stage)) {
                                    return (
                                      <div className="pq-stage-output">
                                        <div className="pq-stage-output-title">Input</div>
                                        <div className="pq-stage-input-text">null</div>
                                      </div>
                                    );
                                  }
                                  const inp = stage.input_state || {};
                                  const inputText = inp.details || inp.text || "";
                                  if (!inputText) return null;
                                  return (
                                    <div className="pq-stage-output">
                                      <div className="pq-stage-output-title">Input</div>
                                      <div className="pq-stage-input-text">{String(inputText)}</div>
                                    </div>
                                  );
                                })()}
                                {(() => {
                                  if (isAudioStageWithoutInput(stage)) {
                                    return (
                                      <div className="pq-stage-output">
                                        <div className="pq-stage-output-title">Output</div>
                                        <div className="pq-stage-input-text">null</div>
                                      </div>
                                    );
                                  }
                                  if (stage.stage_name === "ReviewAgent") {
                                    return (
                                      <div className="pq-stage-output">
                                        <div className="pq-stage-output-title">Output</div>
                                        {renderReviewOutput(stage)}
                                      </div>
                                    );
                                  }
                                  const outputRows = getStageOutputRows(stage);
                                  if (outputRows.length === 0) return null;
                                  return (
                                    <div className="pq-stage-output">
                                      <div className="pq-stage-output-title">Output</div>
                                        <div className="pq-stage-output-grid">
                                          {outputRows.map(([k, v, kind]) => (
                                          <div key={k} className="pq-stage-output-row">
                                            <span className="pq-stage-output-key">{k}</span>
                                            <div className={`pq-stage-output-val${stage.stage_name === "ReviewAgent" ? " pq-stage-output-val--review" : ""}`}>
                                              {String(k).toLowerCase() === "similar ticket code" && v && v !== "—" ? (
                                                <button
                                                  type="button"
                                                  className="pq-inline-ticket-link"
                                                  onClick={() => navigate(`/operator/ai-explainability/${encodeURIComponent(String(v))}`)}
                                                >
                                                  {String(v)}
                                                </button>
                                              ) : (
                                                renderStageVal(v, kind)
                                              )}
                                            </div>
                                          </div>
                                          ))}
                                        </div>
                                      </div>
                                  );
                                })()}
                                {isFailed && queueDetail.status === "held" && (stage.correctable_fields || []).length > 0 && (
                                  <div className="pq-correction-form">
                                    <div className="pq-correction-title">Correct this stage output</div>
                                    {stage.correctable_fields.map((field) => {
                                      const val = corrections[field] !== undefined ? corrections[field] : (stage.output_state?.[field] ?? "");
                                      const isLevel = ["issue_severity", "issue_urgency", "business_impact"].includes(field);
                                      const isPriority = field === "priority_label";
                                      const isLabel = field === "label";
                                      const isBool = field === "safety_concern";
                                      const isDepartment = field === "department";
                                      return (
                                        <label key={field} className="pq-correction-field">
                                          <span>{field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
                                          {isLevel ? (
                                            <select value={val} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value }))}>
                                              {["low", "medium", "high"].map((o) => <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>)}
                                            </select>
                                          ) : isPriority ? (
                                            <select value={val} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value }))}>
                                              {["Low", "Medium", "High", "Critical"].map((o) => <option key={o} value={o}>{o}</option>)}
                                            </select>
                                          ) : isLabel ? (
                                            <select value={val} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value }))}>
                                              {["complaint", "inquiry"].map((o) => <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>)}
                                            </select>
                                          ) : isBool ? (
                                            <select value={String(val)} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value === "true" }))}>
                                              <option value="false">No</option>
                                              <option value="true">Yes</option>
                                            </select>
                                          ) : isDepartment ? (
                                            <select value={val} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value }))}>
                                              {DEPARTMENT_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                                            </select>
                                          ) : (
                                            <input type="text" value={String(val)} onChange={(e) => setCorrections((c) => ({ ...c, [field]: e.target.value }))} />
                                          )}
                                        </label>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          {!isLast && (
                            <div className="pq-stage-arrow">
                              <svg width="20" height="28" viewBox="0 0 20 28" fill="none">
                                <line x1="10" y1="0" x2="10" y2="18" stroke="#c4b5fd" strokeWidth="2" />
                                <path d="M3 16 L10 26 L17 16" stroke="#c4b5fd" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {queueDetail.status === "held" && queueDetail.failure_category !== "manual_pause" && (
                <div className="pq-release-row">
                  <div className="pq-action-row">
                    <button type="button" className="pq-rerun-btn" disabled={rerunBusy || releaseBusy || fullRerunBusy} onClick={rerunStage}>
                      {rerunBusy ? "Running..." : "Rerun Stage"}
                    </button>
                    <button type="button" className="pq-release-btn" disabled={releaseBusy || rerunBusy || fullRerunBusy} onClick={releaseTicket}>
                      {releaseBusy ? "Releasing..." : "Apply Corrections & Release"}
                    </button>
                  </div>
                  <div className="pq-release-hint">
                    {(queueDetail.display_retry_count ?? queueDetail.retry_count ?? 0) >= MAX_PIPELINE_RETRIES - 1
                      ? "Final retry — permanently held if this run fails."
                      : `Retry ${(queueDetail.display_retry_count ?? queueDetail.retry_count ?? 0) + 1} of ${MAX_PIPELINE_RETRIES}`}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
