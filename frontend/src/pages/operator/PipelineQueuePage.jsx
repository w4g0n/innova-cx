import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import "./PipelineQueuePage.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";

/* ─── Auth helper ──────────────────────────────────────────────────────────── */
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

async function apiFetch(path, opts = {}) {
  const token = getStoredToken();
  const url = apiUrl(`/api${path}`);
  const res = await fetch(url, {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, ...opts.headers },
  });
  if (res.status === 401 || res.status === 403) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  if (!res.ok) {
    const d = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${d}`);
  }
  return res.json();
}

/* ─── Formatters ───────────────────────────────────────────────────────────── */
const fmtTs = (ts) =>
  ts
    ? new Date(ts).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })
    : "—";

function fmtAge(ts) {
  if (!ts) return "—";
  const ms = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/* ─── Config ───────────────────────────────────────────────────────────────── */
const AUTO_REFRESH_INTERVAL_MS = 20_000;
const REASON_TRUNCATE_LENGTH = 140;

const STATUS_TABS = ["Active", "Held", "Queued", "Processing"];

const STATUS_PILL = {
  queued:     { label: "Queued",     cls: "pq-pill--blue"   },
  processing: { label: "Processing", cls: "pq-pill--amber"  },
  held:       { label: "Held",       cls: "pq-pill--red"    },
};

const PRIORITY_PILL = {
  critical: { cls: "pq-pill--red"   },
  high:     { cls: "pq-pill--amber" },
  medium:   { cls: "pq-pill--blue"  },
  low:      { cls: "pq-pill--green" },
};

const PRIORITY_RANK = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function getPriorityMeta(priority) {
  const normalized = String(priority || "").trim().toLowerCase();
  if (!normalized) {
    return { key: "", label: "—", cls: "pq-pill--muted" };
  }
  const pill = PRIORITY_PILL[normalized] || { cls: "pq-pill--muted" };
  return {
    key: normalized,
    label: normalized.charAt(0).toUpperCase() + normalized.slice(1),
    cls: pill.cls,
  };
}

/* ─── Small components ─────────────────────────────────────────────────────── */
function Pill({ label, cls }) {
  return <span className={`pq-pill ${cls || ""}`}>{label}</span>;
}

function StatCard({ label, value, flag, loading }) {
  return (
    <div className={`pq-stat ${flag ? `pq-stat--${flag}` : ""}`}>
      <span className="pq-stat__val">{loading ? "…" : (value ?? "—")}</span>
      <span className="pq-stat__label">{label}</span>
    </div>
  );
}

/* ─── SVG icons ────────────────────────────────────────────────────────────── */
function Ico({ name, size = 15 }) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor", strokeWidth: "2",
    strokeLinecap: "round", strokeLinejoin: "round",
    "aria-hidden": "true",
    style: { display: "inline-block", verticalAlign: "middle", flexShrink: 0 },
  };
  switch (name) {
    case "alert":
      return <svg {...p}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
    case "refresh":
      return <svg {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>;
    case "arrow-right":
      return <svg {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>;
    case "search":
      return <svg {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
    case "check":
      return <svg {...p}><polyline points="20 6 9 17 4 12"/></svg>;
    case "x-circle":
      return <svg {...p}><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>;
    case "clock":
      return <svg {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
    case "pause":
      return <svg {...p}><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>;
    case "play":
      return <svg {...p} fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>;
    default:
      return null;
  }
}

/* ─── Action Required Card ─────────────────────────────────────────────────── */
function ActionCard({ item }) {
  const navigate = useNavigate();
  const priorityMeta = getPriorityMeta(item.priority);
  const ageStr   = fmtAge(item.held_at || item.entered_at);
  const reason   = item.failure_reason || "Operator correction required";
  const stage    = item.failed_stage || "ReviewAgent";
  const entered  = fmtTs(item.entered_at);
  const heldAt   = fmtTs(item.held_at);
  const retryCount = item.display_retry_count ?? item.retry_count ?? 0;
  const failureType = {
    timeout: "Timeout",
    model_error: "Model Error",
    connection_error: "Connection Error",
    manual_pause: "Paused",
    recovered_restart: "Recovered Restart",
    unknown: "Unknown",
  }[String(item.failure_category || "").toLowerCase()] || "Pipeline Failure";

  return (
    <div className="pq-action-card">
      <div className="pq-action-card__header">
        <Link
          to={`/operator/pipeline-queue/${item.id}`}
          className="pq-action-card__code pq-action-card__code--link"
          onClick={(e) => e.stopPropagation()}
        >
          {item.ticket_code || "—"}
        </Link>
        <Pill label={priorityMeta.label} cls={priorityMeta.cls} />
        <Pill label={item.ticket_type || "—"} cls="pq-pill--muted" />
      </div>

      <p className="pq-action-card__subject">
        {item.subject || <em>No subject</em>}
      </p>

      <div className="pq-action-card__meta">
        <span className="pq-action-card__stage">
          <Ico name="x-circle" size={13} />
          &nbsp;Held at <strong>{stage}</strong>
        </span>
        <span className="pq-action-card__age">
          <Ico name="clock" size={13} />
          &nbsp;{ageStr}
        </span>
        {retryCount > 0 && (
          <span className="pq-action-card__retries">
            {retryCount} retr{retryCount === 1 ? "y" : "ies"}
          </span>
        )}
      </div>

      <div className="pq-action-card__details">
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Failure Type</span>
          <span className="pq-action-card__detail-value">{failureType}</span>
        </div>
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Status</span>
          <span className="pq-action-card__detail-value">{String(item.status || "held").replace(/^./, (c) => c.toUpperCase())}</span>
        </div>
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Entered Queue</span>
          <span className="pq-action-card__detail-value">{entered}</span>
        </div>
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Held At</span>
          <span className="pq-action-card__detail-value">{heldAt}</span>
        </div>
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Queue Position</span>
          <span className="pq-action-card__detail-value">{item.display_position ?? item.queue_position ?? "—"}</span>
        </div>
        <div className="pq-action-card__detail">
          <span className="pq-action-card__detail-label">Current Stage</span>
          <span className="pq-action-card__detail-value">{(item.current_stage || item.failed_stage || "—").replace("Agent", "")}</span>
        </div>
      </div>

      {reason && (
        <p className="pq-action-card__reason" title={reason}>
          {reason.length > REASON_TRUNCATE_LENGTH ? reason.slice(0, REASON_TRUNCATE_LENGTH) + "…" : reason}
        </p>
      )}

      <div className="pq-action-card__footer">
        <button
          type="button"
          className="pq-action-card__btn"
          onClick={() => navigate(`/operator/pipeline-queue/${item.id}`)}
        >
          View &amp; Correct <Ico name="arrow-right" size={13} />
        </button>
      </div>
    </div>
  );
}

/* ─── Stage indicator for processing rows ──────────────────────────────────── */
const STAGE_SHORT = {
  SubjectGenerationAgent:   "Subject",
  SuggestedResolutionAgent: "Resolution",
  ClassificationAgent:      "Classify",
  SentimentAgent:           "Sentiment",
  AudioAnalysisAgent:       "Audio",
  SentimentCombinerAgent:   "Combiner",
  RecurrenceAgent:          "Recurrence",
  FeatureEngineeringAgent:  "Features",
  PrioritizationAgent:      "Priority",
  DepartmentRoutingAgent:   "Routing",
  ReviewAgent:              "Review",
};
const TOTAL_PIPELINE_STEPS = 11;

/* ─── Derived data constants (module-level to avoid re-creation on render) ── */
const STATUS_ORDER = { processing: 0, queued: 1, held: 2 };
const ACTIVE_STATUSES = new Set(["processing", "queued", "held"]);

function normalizeQueueStatus(status) {
  const normalized = String(status || "").toLowerCase();
  return normalized === "failed" ? "held" : normalized;
}

function StageBar({ currentStage, currentStep }) {
  if (!currentStage) return <span className="pq-muted">—</span>;
  const label = STAGE_SHORT[currentStage] || currentStage.replace("Agent", "");
  const pct   = Math.round(((currentStep ?? 1) / TOTAL_PIPELINE_STEPS) * 100);
  return (
    <div className="pq-stage-bar">
      <div className="pq-stage-bar__track">
        <div className="pq-stage-bar__fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="pq-stage-bar__label">{label}</span>
    </div>
  );
}

/* ─── Queue Table Row ──────────────────────────────────────────────────────── */
// ClassificationAgent is step_order=4; only show ticket type after it has run
const CLASSIFICATION_STEP = 4;

function QueueRow({ item, index, rerunBusy, onRerun }) {
  const navigate = useNavigate();
  const normalizedStatus = normalizeQueueStatus(item.status);
  const sConf  = STATUS_PILL[normalizedStatus] || { label: item.status, cls: "pq-pill--muted" };
  const priorityMeta = getPriorityMeta(item.priority);
  const isHeld       = normalizedStatus === "held";
  const isProcessing = normalizedStatus === "processing";
  const canRerun = item.status !== "completed";
  const noSuggestedResolution =
    String(item.suggested_resolution_mode || "").toLowerCase() === "timeout_background" &&
    !item.suggested_resolution;
  // Show the classified type only once Classification has actually run
  const classificationDone =
    item.status === "completed" ||
    (item.current_step != null && item.current_step >= CLASSIFICATION_STEP);
  const typeLabel = classificationDone ? (item.ticket_type || "—") : "—";
  return (
    <tr
      className={`pq-row${isHeld ? " pq-row--held" : ""}${isProcessing ? " pq-row--processing" : ""}`}
      onClick={() => navigate(`/operator/pipeline-queue/${item.id}`)}
      title={isHeld ? "Click to view and correct" : "Click to view details"}
    >
      <td className="pq-row__pos">
        {item.display_position ?? index + 1}
      </td>
      <td className="pq-row__code">
        <span className="pq-row__code-val">{item.ticket_code || "—"}</span>
        {isHeld && <span className="pq-row__held-dot" title="Held — requires action" />}
      </td>
      <td className="pq-row__subject">
        <div className="pq-row__subject-main">
          {item.subject || <em className="pq-muted">No subject</em>}
        </div>
        {noSuggestedResolution && (
          <div className="pq-row__note">
            <span className="pq-row__note-badge">No suggested resolution</span>
          </div>
        )}
      </td>
      <td>
        <Pill label={typeLabel} cls="pq-pill--muted" />
      </td>
      <td>
        <Pill label={priorityMeta.label} cls={priorityMeta.cls} />
      </td>
      <td>
        <Pill label={sConf.label} cls={sConf.cls} />
      </td>
      <td className="pq-row__stage pq-muted">
        {isProcessing
          ? <StageBar currentStage={item.current_stage} currentStep={item.current_step} />
          : (item.failed_stage || "—")
        }
      </td>
      <td className="pq-row__ts pq-muted">
        {fmtAge(item.entered_at)}
      </td>
      <td className="pq-row__action" onClick={(e) => e.stopPropagation()}>
        <div className="pq-row__action-inner">
          {canRerun && (
            <button
              type="button"
              className="pq-row__link"
              onClick={(e) => {
                e.stopPropagation();
                onRerun(item);
              }}
              disabled={rerunBusy}
            >
              {rerunBusy ? "Rerunning…" : "Rerun"}
            </button>
          )}
          {item.ticket_id && (
            <Link
              to={`/operator/pipeline-queue/${item.id}`}
              className="pq-row__link"
            >
              View <Ico name="arrow-right" size={12} />
            </Link>
          )}
        </div>
      </td>
    </tr>
  );
}

/* ─── Main Page ────────────────────────────────────────────────────────────── */
export default function PipelineQueuePage() {
  const revealRef = useScrollReveal();

  const [items,       setItems]       = useState([]);
  const [itemsLoading,setItemsLoading]= useState(true);
  const [error,       setError]       = useState(null);
  const [activeTab,   setActiveTab]   = useState("Active");
  const [search,      setSearch]      = useState("");
  const [refreshing,  setRefreshing]  = useState(false);
  const [rerunId,     setRerunId]     = useState(null);
  const [pipelineControl, setPipelineControl] = useState(null);
  const [pipelineToggleBusy, setPipelineToggleBusy] = useState(false);
  const intervalRef   = useRef(null);

  /* Load data */
  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setItemsLoading(true);
    setError(null);
    try {
      const q = await apiFetch("/operator/pipeline-queue");
      const control = await apiFetch("/operator/pipeline-queue/control");
      setItems(Array.isArray(q) ? q : []);
      setPipelineControl(control || { is_paused: false });
    } catch (err) {
      setError(err.message);
    } finally {
      setItemsLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    // Auto-refresh every 20s
    intervalRef.current = setInterval(() => loadAll(true), AUTO_REFRESH_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [loadAll]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadAll(true);
  };

  const handleRerun = useCallback(async (item) => {
    if (!item?.id) return;
    setRerunId(item.id);
    setError(null);
    try {
      await apiFetch(`/operator/pipeline-queue/${item.id}/rerun`, { method: "POST" });
      await loadAll(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setRerunId(null);
    }
  }, [loadAll]);

  const handlePipelineToggle = useCallback(async () => {
    const isPaused = Boolean(pipelineControl?.is_paused);
    if (!isPaused) {
      const confirmed = window.confirm(
        "Pause the pipeline? The current in-flight ticket will be checkpoint-held and will resume from its current stage when you play again."
      );
      if (!confirmed) return;
    }
    setPipelineToggleBusy(true);
    setError(null);
    try {
      await apiFetch(`/operator/pipeline-queue/control/${isPaused ? "resume" : "pause"}`, { method: "POST" });
      await loadAll(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setPipelineToggleBusy(false);
    }
  }, [loadAll, pipelineControl]);

  /* Derived data */
  const queueItems = items.filter((item) => String(item.status || "").toLowerCase() !== "completed");

  const sortedItems = [...queueItems].sort((a, b) => {
    const aStatus = normalizeQueueStatus(a.status);
    const bStatus = normalizeQueueStatus(b.status);
    const aOrder  = STATUS_ORDER[aStatus] ?? 99;
    const bOrder  = STATUS_ORDER[bStatus] ?? 99;
    if (aOrder !== bOrder) return aOrder - bOrder;

    const aPriority = PRIORITY_RANK[String(a.priority || "").toLowerCase()] ?? 99;
    const bPriority = PRIORITY_RANK[String(b.priority || "").toLowerCase()] ?? 99;
    if (aPriority !== bPriority) return aPriority - bPriority;

    return new Date(a.entered_at || 0).getTime() - new Date(b.entered_at || 0).getTime();
  });

  const heldItems = sortedItems.filter(
    (i) => normalizeQueueStatus(i.status) === "held" && i.failure_category !== "manual_pause"
  );

  const filteredItems = sortedItems.filter((item) => {
    const status = normalizeQueueStatus(item.status);
    const tabMatch =
      activeTab === "Active"
        ? ACTIVE_STATUSES.has(status)
        : status === activeTab.toLowerCase();

    const q = search.trim().toLowerCase();
    const searchMatch =
      !q ||
      (item.ticket_code || "").toLowerCase().includes(q) ||
      (item.subject || "").toLowerCase().includes(q) ||
      (item.ticket_type || "").toLowerCase().includes(q);

    return tabMatch && searchMatch;
  });

  const tabCounts = STATUS_TABS.reduce((acc, tab) => {
    if (tab === "Active") {
      acc[tab] = queueItems.filter((i) => ACTIVE_STATUSES.has((i.status || "").toLowerCase())).length;
      return acc;
    }
    acc[tab] = queueItems.filter((i) => (i.status || "").toLowerCase() === tab.toLowerCase()).length;
    return acc;
  }, {});

  /* Stats derived from items so they always match the table */
  const stats = {
    queued:     tabCounts["Queued"]     ?? 0,
    processing: tabCounts["Processing"] ?? 0,
    held:       tabCounts["Held"]       ?? 0,
  };

  return (
    <Layout role="operator">
      <div className="pq" ref={revealRef}>
        <PageHeader
          title="Pipeline Queue"
          subtitle="Override-first queue for operator intervention. Tickets that need your action stay at the top."
          actions={
            <div className="pq-header-actions">
              <button
                type="button"
                className={`pq-refresh-btn pq-pipeline-toggle${pipelineControl?.is_paused ? " pq-pipeline-toggle--paused" : ""}`}
                onClick={handlePipelineToggle}
                disabled={pipelineToggleBusy}
                title={pipelineControl?.is_paused ? "Resume pipeline" : "Pause pipeline"}
              >
                {pipelineToggleBusy ? (
                  <Ico name="refresh" size={15} />
                ) : pipelineControl?.is_paused ? (
                  <Ico name="play" size={15} />
                ) : (
                  <Ico name="pause" size={15} />
                )}
                {pipelineToggleBusy
                  ? (pipelineControl?.is_paused ? "Resuming…" : "Pausing…")
                  : (pipelineControl?.is_paused ? "Resume Pipeline" : "Pause Pipeline")}
              </button>
              <button
                type="button"
                className={`pq-refresh-btn${refreshing ? " pq-refresh-btn--spinning" : ""}`}
                onClick={handleRefresh}
                disabled={refreshing}
                title="Refresh"
              >
                <Ico name="refresh" size={15} />
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          }
        />

        {/* Stats strip */}
        <section className="pq-stats">
          <StatCard label="Queued"     value={stats.queued}     loading={itemsLoading} />
          <StatCard label="Processing" value={stats.processing}  loading={itemsLoading} flag="amber" />
          <StatCard label="Held"       value={stats.held}        loading={itemsLoading} flag={stats.held > 0 ? "red" : undefined} />
        </section>

        {!itemsLoading && pipelineControl?.is_paused && (
          <div className="pq-clear-banner pq-clear-banner--warn">
            <Ico name="clock" size={16} />
            &nbsp; Pipeline paused — current work is checkpoint-held and no new tickets will be picked up
          </div>
        )}

        {/* ── Action Required ──────────────────────────────────────────────── */}
        {(heldItems.length > 0 || itemsLoading) && (
          <section className="pq-actions">
            <div className="pq-section-header pq-section-header--warn">
              <span className="pq-section-header__icon">
                <Ico name="alert" size={16} />
              </span>
              <h2 className="pq-section-header__title">
                Override Queue
              </h2>
              {!itemsLoading && (
                <span className="pq-section-header__badge">
                  {heldItems.length}
                </span>
              )}
              <p className="pq-section-header__sub">
                {itemsLoading
                  ? "Loading…"
                  : `${heldItems.length} ticket${heldItems.length !== 1 ? "s" : ""} waiting for operator override before the pipeline can continue`}
              </p>
            </div>

            {itemsLoading ? (
              <div className="pq-loading">Loading held tickets…</div>
            ) : (
              <div className="pq-action-grid">
                {heldItems.map((item) => (
                  <ActionCard key={item.id} item={item} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* Empty state when nothing held */}
        {!itemsLoading && heldItems.length === 0 && (
          <div className="pq-clear-banner">
            <Ico name="check" size={16} />
            &nbsp; No tickets currently held — pipeline is running smoothly
          </div>
        )}

        {/* ── Full Queue ───────────────────────────────────────────────────── */}
        <section className="pq-queue">
          <div className="pq-queue__toolbar">
            <div className="pq-tabs">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`pq-tab${activeTab === tab ? " pq-tab--active" : ""}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab}
                  {tabCounts[tab] > 0 && (
                    <span className="pq-tab__count">{tabCounts[tab]}</span>
                  )}
                </button>
              ))}
            </div>

            <div className="pq-search">
              <span className="pq-search__icon"><Ico name="search" size={14} /></span>
              <input
                type="search"
                className="pq-search__input"
                placeholder="Search by code or subject…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          {error ? (
            <div className="pq-error">
              {error}
              <button type="button" className="pq-retry-btn" onClick={() => loadAll()}>
                Retry
              </button>
            </div>
          ) : itemsLoading ? (
            <div className="pq-loading">Loading queue…</div>
          ) : filteredItems.length === 0 ? (
            <div className="pq-empty">
              {search ? "No tickets match your search." : `No ${activeTab.toLowerCase()} tickets.`}
            </div>
          ) : (
            <div className="pq-table-wrap">
              <table className="pq-table">
                <thead>
                  <tr>
                    <th className="pq-th pq-th--pos">#</th>
                    <th className="pq-th">Code</th>
                    <th className="pq-th pq-th--subject">Subject</th>
                    <th className="pq-th">Type</th>
                    <th className="pq-th">Priority</th>
                    <th className="pq-th">Status</th>
                    <th className="pq-th pq-th--stage">Current Stage</th>
                    <th className="pq-th">Entered</th>
                    <th className="pq-th pq-th--action" />
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const SECTION_LABELS = {
                      processing: "Now Processing",
                      queued:     "In Queue",
                      held:       "Held — Requires Action",
                    };
                    let lastSection = null;
                    const rows = [];
                    filteredItems.forEach((item, idx) => {
                      const section = normalizeQueueStatus(item.status);
                      if (section !== lastSection) {
                        lastSection = section;
                        rows.push(
                          <tr key={`section-${section}-${idx}`} className="pq-section-divider">
                            <td colSpan={9} className="pq-section-divider__cell">
                              {SECTION_LABELS[section] || section}
                            </td>
                          </tr>
                        );
                      }
                      rows.push(
                  <QueueRow
                    key={item.id}
                    item={item}
                    index={idx}
                    rerunBusy={rerunId === item.id}
                    onRerun={handleRerun}
                  />
                      );
                    });
                    return rows;
                  })()}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </Layout>
  );
}
