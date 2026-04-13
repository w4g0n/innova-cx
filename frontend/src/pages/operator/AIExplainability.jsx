import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import { apiUrl } from "../../config/apiBase";
import { getCsrfToken } from "../../services/api";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import FilterPillButton from "../../components/common/FilterPillButton";
import PriorityPill from "../../components/common/PriorityPill";
import {
  sanitizeId,
  sanitizeSearchQuery,
  MAX_SEARCH_LEN,
} from "./Operatorsanitize";
import "./AIExplainability.css";

function getStoredToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

async function apiFetch(path) {
  const token = getStoredToken();
  const res = await fetch(apiUrl(`/api${path}`), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
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

function unwrapValue(v) {
  if (v && typeof v === "object" && "value" in v) return v.value;
  return v;
}

function asLevel(v, fallback = "medium") {
  const s = String(unwrapValue(v) ?? "").trim().toLowerCase();
  return ["low", "medium", "high"].includes(s) ? s : fallback;
}

function asTicketType(v, fallback = "complaint") {
  const s = String(unwrapValue(v) ?? "").trim().toLowerCase();
  return s === "inquiry" ? "inquiry" : fallback;
}

function asBool(v, fallback = false) {
  const val = unwrapValue(v);
  if (typeof val === "boolean") return val;
  if (typeof val === "number") return val !== 0;
  const s = String(val ?? "").trim().toLowerCase();
  if (["true", "1", "yes", "y"].includes(s)) return true;
  if (["false", "0", "no", "n"].includes(s)) return false;
  return fallback;
}

function parseModelSuggestion(value) {
  if (value && typeof value === "object") return value;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }
  return {};
}

function formatFieldLabel(key) {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function renderFieldValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    if (value.every((v) => v === null || ["string", "number", "boolean"].includes(typeof v))) {
      return value.map((v) => String(v)).join(", ");
    }
    return value.map((v) => JSON.stringify(v)).join("\n");
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function getRecurrenceDecision(branch, isRecurring) {
  if (!isRecurring || !branch || branch === "none") return "Not recurring";
  if (branch === "A" || branch === "B") return "Matched to an open ticket";
  if (branch === "C") return "Matched to a recently resolved ticket";
  if (branch === "D") return "Matched to an older resolved ticket";
  return "Recurring match found";
}

function getRecurrenceActionTaken(branch, isRecurring) {
  if (!isRecurring || !branch || branch === "none") {
    return "Continued as a new ticket because no similar prior ticket from the same user was found.";
  }
  if (branch === "A") {
    return "Sent a reminder on the existing open ticket and stopped this duplicate submission from continuing in the pipeline.";
  }
  if (branch === "B") {
    return "Sent a reminder on the existing open ticket, increased its priority, and stopped this duplicate submission from continuing in the pipeline.";
  }
  if (branch === "C") {
    return "Reopened the previous ticket with its existing context and resolution history, and stopped this duplicate submission from continuing in the pipeline.";
  }
  if (branch === "D") {
    return "Allowed a new ticket to continue through the pipeline while carrying over context from the older resolved ticket.";
  }
  return "Recurring issue handling was applied.";
}

function KeyValueBlock({ data }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <div className="aix-kv-empty">No data</div>;

  return (
    <div className="aix-kv-list">
      {entries.map(([key, value]) => {
        const rendered = renderFieldValue(value);
        const multiline = typeof rendered === "string" && rendered.includes("\n");
        return (
          <div key={key} className="aix-kv-row">
            <div className="aix-kv-key">{formatFieldLabel(key)}</div>
            <div className={`aix-kv-value ${multiline ? "aix-kv-value--multiline" : ""}`}>{rendered}</div>
          </div>
        );
      })}
    </div>
  );
}

function normalizeStageIO(stage, ticket) {
  const inputState = stage?.inputState || {};
  const outputState = stage?.outputState || {};
  const ticketDetails = ticket?.description?.details || "";
  const ticketSubject = ticket?.description?.subject || "";
  const modelSuggestion = parseModelSuggestion(ticket?.modelSuggestion);
  const overrides =
    modelSuggestion?.operator_overrides && typeof modelSuggestion.operator_overrides === "object"
      ? modelSuggestion.operator_overrides
      : {};
  const stageName = String(stage?.stageName || "");
  const ticketDetailsInput = { ticket_details: inputState.text || ticketDetails || "" };

  if (stageName === "SubjectGenerationAgent") {
    return {
      input: ticketDetailsInput,
      output: { subject: outputState.subject || ticketSubject || "" },
    };
  }

  if (stageName === "SuggestedResolutionAgent") {
    return {
      input: ticketDetailsInput,
      output: { suggested_resolution: outputState.suggested_resolution || ticket?.suggestedResolution || "" },
    };
  }

  if (stageName === "ClassificationAgent") {
    return {
      input: ticketDetailsInput,
      output: {
        ticket_type: asTicketType(overrides.ticket_type ?? outputState.label ?? outputState.ticket_type, "complaint"),
        confidence_score:
          outputState.class_confidence ??
          outputState.classification_confidence ??
          stage?.confidenceScore ??
          null,
      },
    };
  }

  if (stageName === "SentimentAgent") {
    const score = Number(outputState.text_sentiment ?? 0);
    return {
      input: ticketDetailsInput,
      output: {
        text_sentiment: Number.isFinite(score) ? Number(score.toFixed(3)) : 0,
      },
    };
  }

  if (stageName === "AudioAnalysisAgent") {
    const audioProvided =
      asBool(inputState.has_audio, false) ||
      (inputState.audio_features &&
        typeof inputState.audio_features === "object" &&
        Object.keys(inputState.audio_features).length > 0);
    return {
      input: ticketDetailsInput,
      output: {
        audio_provided: audioProvided,
        audio_sentiment: outputState.audio_sentiment ?? null,
      },
    };
  }

  if (stageName === "SentimentCombinerAgent") {
    return {
      input: {
        ticket_details: inputState.text || ticketDetails || "",
        text_sentiment: inputState.text_sentiment ?? 0,
        audio_sentiment: inputState.audio_sentiment ?? null,
      },
      output: {
        combined_sentiment_score: outputState.sentiment_score_numeric ?? null,
        sentiment: outputState.sentiment_score ?? "",
      },
    };
  }

  if (stageName === "RecurrenceAgent") {
    const isRecurring = asBool(overrides.is_recurring ?? outputState.is_recurring, false);
    const branch = String(unwrapValue(outputState.recurrence_branch) || "").trim().toUpperCase() || "none";
    const linkedCode =
      unwrapValue(outputState.similar_ticket_code) ||
      unwrapValue(outputState.recurrence_similar_ticket_code) ||
      unwrapValue(outputState.matched_ticket_code) ||
      unwrapValue(outputState.similar_ticket?.ticket_code) ||
      null;
    const linkedSubject =
      unwrapValue(outputState.similar_ticket_subject) ||
      unwrapValue(outputState.recurrence_similar_ticket_subject) ||
      unwrapValue(outputState.matched_ticket_subject) ||
      unwrapValue(outputState.similar_ticket?.subject) ||
      null;
    const linkedScore =
      unwrapValue(outputState.similarity_score) ??
      unwrapValue(outputState.recurrence_similarity_score) ??
      unwrapValue(outputState.similar_ticket?.similarity_score) ??
      null;
    return {
      input: ticketDetailsInput,
      output: {
        decision: getRecurrenceDecision(branch, isRecurring),
        action_taken: getRecurrenceActionTaken(branch, isRecurring),
        is_recurring: isRecurring,
        similar_ticket_code: isRecurring ? (overrides.similar_ticket_code || linkedCode) : null,
        similar_ticket_subject: isRecurring ? linkedSubject : null,
        similarity_score: isRecurring ? linkedScore : null,
        recurrence_reason: unwrapValue(outputState.recurrence_reason) || "",
      },
    };
  }

  if (stageName === "FeatureEngineeringAgent") {
    return {
      input: ticketDetailsInput,
      output: {
        business_impact: asLevel(overrides.business_impact ?? outputState.business_impact, "medium"),
        issue_severity: asLevel(overrides.issue_severity ?? outputState.issue_severity, "medium"),
        issue_urgency: asLevel(overrides.issue_urgency ?? outputState.issue_urgency, "medium"),
        safety_concern: asBool(overrides.safety_concern ?? outputState.safety_concern, false),
      },
    };
  }

  if (stageName === "PrioritizationAgent") {
    const sentimentRaw =
      inputState.sentiment_score ??
      inputState.sentiment_score_numeric ??
      inputState.text_sentiment ??
      "neutral";
    const sentimentNormalized = normalizeSentimentLabel(sentimentRaw);
    const effectiveInput = {
      Safety_Concern: asBool(overrides.safety_concern ?? inputState.safety_concern, false),
      Issue_Severity: asLevel(overrides.issue_severity ?? inputState.issue_severity, "medium"),
      Issue_Urgency: asLevel(overrides.issue_urgency ?? inputState.issue_urgency, "medium"),
      Business_Impact: asLevel(overrides.business_impact ?? inputState.business_impact, "medium"),
      Sentiment_Score: sentimentNormalized,
      ticket_type: asTicketType(overrides.ticket_type ?? inputState.ticket_type ?? inputState.label, "complaint"),
      Is_Recurring: false, // always false — recurrence handled separately, not a model input
    };
    return {
      input: effectiveInput,
      output: {
        final_priority:
          (overrides && Object.keys(overrides).length > 0 ? ticket?.priority : null) ||
          unwrapValue(outputState.priority_label) ||
          unwrapValue(outputState.priority_details?.final_priority) ||
          "",
      },
    };
  }

  if (stageName === "DepartmentRoutingAgent") {
    const candidateList = Array.isArray(outputState.department_routing_candidates)
      ? outputState.department_routing_candidates
      : [];
    const calibration = outputState.department_routing_calibration || {};
    const fromCalibration = Object.entries(calibration).map(([department, confidence]) => ({
      department,
      confidence_score: unwrapValue(confidence) ?? null,
    }));
    const candidates = (candidateList.length ? candidateList : fromCalibration).map((c) => ({
      department: unwrapValue(c?.department) || "",
      confidence_score: unwrapValue(c?.confidence ?? c?.confidence_score) ?? null,
    }));
    return {
      input: ticketDetailsInput,
      output: {
        selected_department:
          unwrapValue(outputState.department_selected) ||
          unwrapValue(outputState.department) ||
          null,
        department_confidences: candidates,
      },
    };
  }

  return {
    input: { ticket_details: inputState.text || ticketDetails || "" },
    output: {},
  };
}

const SENTIMENT_NEGATIVE_THRESHOLD = -0.25;
const SENTIMENT_POSITIVE_THRESHOLD = 0.25;

function normalizeSentimentLabel(value) {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "negative") return "Negative";
  if (s === "positive") return "Positive";
  if (s === "neutral") return "Neutral";
  const n = Number(value);
  if (!Number.isNaN(n)) {
    if (n < SENTIMENT_NEGATIVE_THRESHOLD) return "Negative";
    if (n > SENTIMENT_POSITIVE_THRESHOLD) return "Positive";
  }
  return "Neutral";
}

function computePriorityFormulaLines(priorityInput) {
  const toLevel = (v, d = "medium") => {
    const s = String(v || "").toLowerCase();
    return ["low", "medium", "high"].includes(s) ? s : d;
  };
  const sentiment = String(priorityInput?.Sentiment_Score || "Neutral").toLowerCase();
  const safety = Boolean(priorityInput?.Safety_Concern);
  const ticketType = String(priorityInput?.ticket_type || "complaint").toLowerCase() === "inquiry" ? "inquiry" : "complaint";
  const impact = toLevel(priorityInput?.Business_Impact);
  const severity = toLevel(priorityInput?.Issue_Severity);
  const urgency = toLevel(priorityInput?.Issue_Urgency);

  const levels = [impact, severity, urgency];
  const highCount = levels.filter((x) => x === "high").length;
  const mediumCount = levels.filter((x) => x === "medium").length;

  let base = "low";
  if (highCount >= 2) base = "critical";
  else if (highCount === 1) base = "medium";
  else if (mediumCount === 3) base = "high";
  else if (mediumCount === 2) base = "medium";

  const order = ["low", "medium", "high", "critical"];
  let idx = order.indexOf(base);
  const lines = [`Base priority from impact/severity/urgency: ${base.toUpperCase()}`];

  if (safety) {
    const highIdx = order.indexOf("high");
    if (idx < highIdx) idx = highIdx;
    lines.push("Safety Concern = TRUE -> enforce minimum HIGH");
  } else {
    lines.push("Safety Concern = FALSE -> no safety floor");
  }

  if (ticketType === "inquiry") {
    idx -= 1;
    lines.push("ticket_type = inquiry -> -1 level");
  } else {
    lines.push("ticket_type = complaint -> +0");
  }

  if (sentiment === "negative") {
    idx += 1;
    lines.push("Sentiment_Score = Negative -> +1 level");
  } else if (sentiment === "positive") {
    idx -= 1;
    lines.push("Sentiment_Score = Positive -> -1 level");
  } else {
    lines.push("Sentiment_Score = Neutral -> +0");
  }

  idx = Math.max(0, Math.min(3, idx));
  if (safety && idx < 2) idx = 2;
  const finalPriority = order[idx];
  lines.push(`Final priority after modifiers: ${finalPriority.toUpperCase()}`);
  return lines;
}

function inferStageMode(stage) {
  const stageName = String(stage?.stageName || "");
  const out = stage?.outputState || {};

  const read = (...keys) => {
    for (const key of keys) {
      const value = out?.[key];
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        return String(value).toLowerCase();
      }
    }
    return "";
  };

  const stageSpecific = {
    SubjectGenerationAgent: read("subject_generation_mode"),
    SuggestedResolutionAgent: read("suggested_resolution_mode", "suggested_resolution_model"),
    ClassificationAgent: read("classification_source"),
    SentimentAgent: read("sentiment_mode"),
    AudioAnalysisAgent: read("audio_analysis_mode"),
    SentimentCombinerAgent: read("sentiment_combiner_source", "sentiment_combiner_mode"),
    RecurrenceAgent: read("is_recurring_source"),
    FeatureEngineeringAgent: read("feature_labeler_mode", "feature_labels_source"),
    PrioritizationAgent: read("priority_mode"),
    DepartmentRoutingAgent: read("department_routing_source"),
  };

  const hint = stageSpecific[stageName] || read(
    "mode",
    "source",
    "model_mode",
    "model_source",
    "classification_source",
    "priority_mode",
    "feature_labels_source",
    "feature_labeler_mode",
    "department_routing_source",
    "subject_generation_mode",
    "sentiment_mode",
    "audio_analysis_mode",
  );

  if (
    stageName === "SubjectGenerationAgent" &&
    !hint &&
    typeof out?.subject === "string" &&
    out.subject.trim() !== ""
  ) {
    return "Real";
  }

  if (!hint) return stageName === "RecurrenceAgent" ? "Heuristic" : "Mock";
  if (hint.includes("deterministic")) {
    return "Deterministic";
  }
  if (stageName === "RecurrenceAgent" && hint.includes("search")) {
    return "Search";
  }
  if (hint.includes("heuristic") || hint.includes("fallback") || hint.includes("rule") || hint.includes("text_only")) {
    return stageName === "RecurrenceAgent" ? "Heuristic" : "Mock";
  }
  if (hint.includes("mock")) {
    return "Mock";
  }
  if (
    hint.includes("qwen") ||
    hint.includes("generation") ||
    hint.includes("model") ||
    hint.includes("ml") ||
    hint.includes("neural") ||
    hint.includes("transformer") ||
    hint.includes("bert") ||
    hint.includes("nli")
  ) {
    return "Real";
  }
  return stageName === "RecurrenceAgent" ? "Heuristic" : "Mock";
}

function getStageConfidence(stage) {
  const out = stage?.outputState || {};
  const name = String(stage?.stageName || "");
  if (name === "ClassificationAgent") {
    return out.class_confidence ?? out.classification_confidence ?? stage?.confidenceScore ?? null;
  }
  if (name === "DepartmentRoutingAgent") {
    return out.department_confidence ?? stage?.confidenceScore ?? null;
  }
  return null;
}

function formatProcessingTimeSeconds(inferenceTimeMs) {
  const value = Number(inferenceTimeMs);
  if (!Number.isFinite(value) || value < 0) return "—";
  return `${(value / 1000).toFixed(1)}s`;
}

function stageUsesFallback(stage) {
  const out = stage?.outputState || {};
  const values = Object.values(out).map((value) => String(unwrapValue(value) ?? "").toLowerCase());
  return values.some(
    (value) =>
      value.includes("mock_fallback") ||
      value.includes("heuristic_fallback"),
  );
}

function getStageVisualStatus(stage) {
  if (stageUsesFallback(stage)) return "failed";
  const status = String(stage?.status || "").toLowerCase();
  if (status) return status;
  const eventType = String(stage?.eventType || "").toLowerCase();
  return eventType || "success";
}

function getStageStatusLabel(stage) {
  if (stageUsesFallback(stage)) return "Fallback Used";
  return String(stage?.status || stage?.eventType || "Success");
}

function compareTicketsByDate(a, b) {
  const leftTime = new Date(a?.pipelineCompletedAt || a?.createdAt || 0).getTime();
  const rightTime = new Date(b?.pipelineCompletedAt || b?.createdAt || 0).getTime();
  if (rightTime !== leftTime) return rightTime - leftTime;
  const leftCode = String(a?.ticketCode || "");
  const rightCode = String(b?.ticketCode || "");
  return leftCode.localeCompare(rightCode, undefined, { numeric: true, sensitivity: "base" });
}

function stageHasAudio(stage) {
  const inputState = stage?.inputState || {};
  const outputState = stage?.outputState || {};
  if (inputState.has_audio !== undefined) return asBool(inputState.has_audio, false);
  if (inputState.audio_features && typeof inputState.audio_features === "object") {
    return Object.keys(inputState.audio_features).length > 0;
  }
  if (outputState.audio_sentiment !== null && outputState.audio_sentiment !== undefined) {
    return true;
  }
  return false;
}


const STATUS_CLASS = {
  Open: "ev-status-open",
  Assigned: "ev-status-assigned",
  "In Progress": "ev-status-inprogress",
  Escalated: "ev-status-escalated",
  Overdue: "ev-status-overdue",
  Resolved: "ev-status-resolved",
  Completed: "ev-status-resolved",
};

export default function AIExplainability() {
  const navigate = useNavigate();
  const { ticketCode: rawTicketCode } = useParams();
  const ticketCode = sanitizeId(rawTicketCode);
  const detailMode = Boolean(ticketCode);

  const [ticketList, setTicketList] = useState([]);
  const [, setStatusCounts] = useState({});
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [ticketSearch, setTicketSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");

  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [data, setData] = useState(null);
  const [, setSelectedExecutionId] = useState("");
  const [selectedStageKey, setSelectedStageKey] = useState("");
  const [overrideForm, setOverrideForm] = useState({
    ticketType: "complaint",
    businessImpact: "medium",
    issueSeverity: "medium",
    issueUrgency: "medium",
    safetyConcern: false,
    isRecurring: false,
    similarTicketCode: "",
  });
  const [overrideBusy, setOverrideBusy] = useState(false);
  const [rerunBusy, setRerunBusy] = useState(false);
  const [overrideMsg, setOverrideMsg] = useState("");
  const [overrideErr, setOverrideErr] = useState("");
  const [recurrenceQuery, setRecurrenceQuery] = useState("");
  const [recurrenceResults, setRecurrenceResults] = useState([]);
  const [recurrenceLoading, setRecurrenceLoading] = useState(false);

  async function loadTicketList() {
    setListLoading(true);
    setListError("");
    try {
      const res = await apiFetch("/operator/ai-explainability/tickets");
      setTicketList(Array.isArray(res?.items) ? res.items : []);
      setStatusCounts(res?.statusCounts || {});
    } catch {
      setListError("Failed to load tickets. Please try again.");
      setTicketList([]);
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    if (detailMode) return;
    loadTicketList();
  }, [detailMode]);

  const stages = useMemo(() => {
    const arr = Array.isArray(data?.pipelineStages) ? data.pipelineStages : [];
    return [...arr]
      .filter((s) => String(s?.stageName || "") !== "TicketCreationGate")
      .sort((a, b) => {
        const sa = Number(a?.stepOrder || 0);
        const sb = Number(b?.stepOrder || 0);
        if (sa !== sb) return sa - sb;
        const ta = new Date(a?.createdAt || 0).getTime();
        const tb = new Date(b?.createdAt || 0).getTime();
        return ta - tb;
      });
  }, [data]);

  const stageMenu = useMemo(() => {
    const byStage = new Map();
    const weight = { output: 3, error: 2, start: 1 };
    const stageOrder = [
      "RecurrenceAgent",
      "SubjectGenerationAgent",
      "ClassificationAgent",
      "SentimentAgent",
      "AudioAnalysisAgent",
      "SentimentCombinerAgent",
      "FeatureEngineeringAgent",
      "PrioritizationAgent",
      "DepartmentRoutingAgent",
      "SuggestedResolutionAgent",
      "ReviewAgent",
    ];
    for (const s of stages) {
      const key = String(s.stageName || "");
      const current = byStage.get(key);
      if (!current) {
        byStage.set(key, s);
        continue;
      }
      const currentWeight = weight[current.eventType] || 0;
      const nextWeight = weight[s.eventType] || 0;
      const currentTime = new Date(current.createdAt || 0).getTime();
      const nextTime = new Date(s.createdAt || 0).getTime();
      if (nextWeight > currentWeight || (nextWeight === currentWeight && nextTime >= currentTime)) {
        byStage.set(key, s);
      }
    }
    return [...byStage.values()].sort((a, b) => {
      const ia = stageOrder.indexOf(String(a.stageName || ""));
      const ib = stageOrder.indexOf(String(b.stageName || ""));
      const va = ia === -1 ? 999 : ia;
      const vb = ib === -1 ? 999 : ib;
      if (va !== vb) return va - vb;
      const ta = new Date(a.createdAt || 0).getTime();
      const tb = new Date(b.createdAt || 0).getTime();
      return ta - tb;
    });
  }, [stages]);

  const selectedStage = useMemo(() => {
    if (!stageMenu.length) return null;
    const found = stageMenu.find((s) => `${s.stepOrder}-${s.stageName}` === selectedStageKey);
    return found || stageMenu[0];
  }, [stageMenu, selectedStageKey]);

  const selectedStageDisplayOrder = useMemo(() => {
    if (!selectedStage) return null;
    const idx = stageMenu.findIndex(
      (s) => `${s.stepOrder}-${s.stageName}` === `${selectedStage.stepOrder}-${selectedStage.stageName}`,
    );
    return idx >= 0 ? idx + 1 : null;
  }, [selectedStage, stageMenu]);

  const selectedStageVisualStatus = useMemo(
    () => getStageVisualStatus(selectedStage),
    [selectedStage],
  );
  const selectedStageStatusLabel = useMemo(
    () => getStageStatusLabel(selectedStage),
    [selectedStage],
  );

  useEffect(() => {
    if (!data) {
      setSelectedExecutionId("");
      setSelectedStageKey("");
      return;
    }
    if (stageMenu.length > 0) {
      setSelectedStageKey((prev) => {
        const exists = stageMenu.some((s) => `${s.stepOrder}-${s.stageName}` === prev);
        return exists ? prev : `${stageMenu[0].stepOrder}-${stageMenu[0].stageName}`;
      });
    } else {
      setSelectedStageKey("");
    }
  }, [data, stageMenu]);

  async function rerunPipeline() {
    if (!detailTicket?.ticketId) return;
    setRerunBusy(true);
    setOverrideErr("");
    setOverrideMsg("");
    try {
      const csrf = await getCsrfToken();
      const response = await fetch(
        apiUrl(`/api/operator/ai-explainability/tickets/${encodeURIComponent(detailTicket.ticketId)}/pipeline-rerun`),
        {
          method: "POST",
          headers: { ...(getStoredToken() ? { Authorization: `Bearer ${getStoredToken()}` } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
        },
      );
      if (!response.ok) {
        const msg = await response.text().catch(() => "Failed to rerun pipeline");
        throw new Error(msg || "Failed to rerun pipeline");
      }
      const result = await response.json();
      const refreshed = await apiFetch(`/operator/ai-explainability/tickets/${encodeURIComponent(detailTicket.ticketId)}`);
      setData(refreshed);
      const nextExecutionId = result?.orchestratorExecutionId || result?.executionId || "";
      if (nextExecutionId) {
        setSelectedExecutionId(nextExecutionId);
      }
      setOverrideMsg("Pipeline rerun completed from the beginning.");
    } catch {
      setOverrideErr("Failed to rerun pipeline. Please try again.");
    } finally {
      setRerunBusy(false);
    }
  }

  async function loadTicket(code) {
    const q = sanitizeId(String(code || "").trim());
    if (!q) return;
    setDetailLoading(true);
    setDetailError("");
    try {
      const res = await apiFetch(`/operator/ai-explainability/tickets/${encodeURIComponent(q)}`);
      setData(res);
    } catch {
      setDetailError("Failed to load explainability data. Please try again.");
      setData(null);
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    if (!detailMode) {
      setData(null);
      setDetailError("");
      return;
    }
    loadTicket(ticketCode);
  }, [detailMode, ticketCode]);

  const detailTicket = useMemo(() => data?.ticket || {}, [data]);
  const selectedStageIO = useMemo(() => normalizeStageIO(selectedStage, detailTicket), [selectedStage, detailTicket]);
  const stageOutputMap = useMemo(() => {
    const map = {};
    for (const stage of stageMenu) {
      map[stage.stageName] = stage.outputState || {};
    }
    return map;
  }, [stageMenu]);

  useEffect(() => {
    if (!detailTicket?.ticketId) return;
    const classificationOut = stageOutputMap.ClassificationAgent || {};
    const featureOut = stageOutputMap.FeatureEngineeringAgent || {};
    const recurrenceOut = stageOutputMap.RecurrenceAgent || {};
    const modelSuggestion = parseModelSuggestion(detailTicket?.modelSuggestion);
    const overrides = (modelSuggestion.operator_overrides && typeof modelSuggestion.operator_overrides === "object")
      ? modelSuggestion.operator_overrides
      : {};
    const recurrenceSimilarCode =
      unwrapValue(overrides.similar_ticket_code) ||
      unwrapValue(recurrenceOut.similar_ticket_code) ||
      unwrapValue(recurrenceOut.recurrence_similar_ticket_code) ||
      unwrapValue(recurrenceOut.matched_ticket_code) ||
      "";
    setOverrideForm({
      ticketType: asTicketType(
        overrides.ticket_type ?? classificationOut.ticket_type ?? classificationOut.label,
        "complaint",
      ),
      businessImpact: asLevel(overrides.business_impact ?? featureOut.business_impact, "medium"),
      issueSeverity: asLevel(overrides.issue_severity ?? featureOut.issue_severity, "medium"),
      issueUrgency: asLevel(overrides.issue_urgency ?? featureOut.issue_urgency, "medium"),
      safetyConcern: asBool(overrides.safety_concern ?? featureOut.safety_concern, false),
      isRecurring: asBool(overrides.is_recurring ?? recurrenceOut.is_recurring, false),
      similarTicketCode: recurrenceSimilarCode,
    });
    setRecurrenceQuery("");
    setRecurrenceResults([]);
  }, [detailTicket, stageOutputMap]);

  useEffect(() => {
    setOverrideMsg("");
    setOverrideErr("");
  }, [ticketCode]);

  useEffect(() => {
    async function runSearch() {
      const q = recurrenceQuery.trim();
      if (!q || !detailTicket?.ticketId) {
        setRecurrenceResults([]);
        return;
      }
      setRecurrenceLoading(true);
      try {
        const res = await apiFetch(
          `/operator/ai-explainability/ticket-search?q=${encodeURIComponent(q)}&exclude_ticket_code=${encodeURIComponent(
            detailTicket.ticketId || "",
          )}`,
        );
        setRecurrenceResults(Array.isArray(res?.items) ? res.items : []);
      } catch {
        setRecurrenceResults([]);
      } finally {
        setRecurrenceLoading(false);
      }
    }
    if (!overrideForm.isRecurring) return;
    const t = setTimeout(runSearch, 250);
    return () => clearTimeout(t);
  }, [recurrenceQuery, overrideForm.isRecurring, detailTicket]);

  async function applyOverrides() {
    if (!detailTicket?.ticketId) return;
    if (overrideForm.isRecurring && !overrideForm.similarTicketCode) {
      setOverrideErr("Select a similar ticket when recurring is true.");
      return;
    }
    setOverrideBusy(true);
    setOverrideErr("");
    setOverrideMsg("");
    try {
      const csrf = await getCsrfToken();
      const response = await fetch(apiUrl(`/api/operator/ai-explainability/tickets/${encodeURIComponent(detailTicket.ticketId)}/pipeline-overrides`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(getStoredToken() ? { Authorization: `Bearer ${getStoredToken()}` } : {}),
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body: JSON.stringify({
          ticket_type: overrideForm.ticketType,
          business_impact: overrideForm.businessImpact,
          issue_severity: overrideForm.issueSeverity,
          issue_urgency: overrideForm.issueUrgency,
          safety_concern: overrideForm.safetyConcern,
          is_recurring: overrideForm.isRecurring,
          similar_ticket_code: overrideForm.isRecurring ? overrideForm.similarTicketCode : null,
        }),
      });
      if (!response.ok) {
        const msg = await response.text().catch(() => "Failed to apply overrides");
        throw new Error(msg || "Failed to apply overrides");
      }
      const result = await response.json();
      const refreshed = await apiFetch(`/operator/ai-explainability/tickets/${encodeURIComponent(detailTicket.ticketId)}`);
      setData(refreshed);
      const beforePriority = result?.previousPriority || "—";
      const afterPriority = result?.priority || "—";
      setOverrideMsg(
        result?.priorityChanged
          ? `Overrides applied. Priority changed: ${beforePriority} -> ${afterPriority}.`
          : `Overrides applied. Prioritization rerun completed (priority unchanged: ${afterPriority}).`,
      );
    } catch {
      setOverrideErr("Failed to apply overrides. Please try again.");
    } finally {
      setOverrideBusy(false);
    }
  }

  async function deleteTicket(ticketId, e) {
    e?.stopPropagation();
    if (!window.confirm("Permanently delete this ticket and all its data? This cannot be undone.")) return;
    try {
      const token = getStoredToken();
      const csrf = await getCsrfToken();
      const res = await fetch(apiUrl(`/api/operator/tickets/${ticketId}`), {
        method: "DELETE",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      });
      if (!res.ok) { const d = await res.text().catch(() => "Failed"); throw new Error(d); }
      await loadTicketList();
    } catch (e) {
      alert(`Failed to delete ticket: ${e?.message}`);
    }
  }
  const modelSelectedSummary = useMemo(() => {
    const classificationOut = stageOutputMap.ClassificationAgent || {};
    const featureOut = stageOutputMap.FeatureEngineeringAgent || {};
    const recurrenceOut = stageOutputMap.RecurrenceAgent || {};
    const modelSuggestion = parseModelSuggestion(detailTicket?.modelSuggestion);
    const overrides = (modelSuggestion.operator_overrides && typeof modelSuggestion.operator_overrides === "object")
      ? modelSuggestion.operator_overrides
      : {};
    const sentimentSource =
      stageOutputMap.SentimentCombinerAgent?.outputState?.sentiment_score ??
      stageOutputMap.SentimentCombinerAgent?.outputState?.sentiment_score_numeric ??
      stageOutputMap.SentimentAgent?.outputState?.text_sentiment ??
      "neutral";
    return {
      ticketType: asTicketType(
        overrides.ticket_type ?? classificationOut.ticket_type ?? classificationOut.label,
        "complaint",
      ),
      businessImpact: asLevel(overrides.business_impact ?? featureOut.business_impact, "medium"),
      issueSeverity: asLevel(overrides.issue_severity ?? featureOut.issue_severity, "medium"),
      issueUrgency: asLevel(overrides.issue_urgency ?? featureOut.issue_urgency, "medium"),
      safetyConcern: asBool(overrides.safety_concern ?? featureOut.safety_concern, false),
      isRecurring: asBool(overrides.is_recurring ?? recurrenceOut.is_recurring, false),
      sentimentScore: normalizeSentimentLabel(sentimentSource),
    };
  }, [stageOutputMap, detailTicket]);

  const visibleTicketList = useMemo(() => {
    const search = ticketSearch.trim().toLowerCase();
    return [...ticketList]
      .sort(compareTicketsByDate)
      .filter((t) => {
        const blob = `${t.ticketCode || ""} ${t.subject || ""}`.toLowerCase();
        return !search || blob.includes(search);
      })
      .filter((t) => priorityFilter === "all" || String(t.priority || "").trim().toLowerCase() === priorityFilter)
      .filter((t) => statusFilter === "all" || String(t.status || "Completed").trim().toLowerCase() === statusFilter)
      .filter((t) => departmentFilter === "all" || String(t.department || "").trim().toLowerCase() === departmentFilter);
  }, [ticketList, ticketSearch, priorityFilter, statusFilter, departmentFilter]);

  const priorityOptions = useMemo(() => [
    { value: "all", label: "All Priorities" },
    ...Array.from(new Set(ticketList.map((t) => String(t.priority || "").trim()).filter(Boolean)))
      .sort()
      .map((value) => ({ value: value.toLowerCase(), label: value })),
  ], [ticketList]);

  const statusOptions = useMemo(() => [
    { value: "all", label: "All Statuses" },
    ...Array.from(new Set(ticketList.map((t) => String(t.status || "Completed").trim()).filter(Boolean)))
      .sort()
      .map((value) => ({ value: value.toLowerCase(), label: value })),
  ], [ticketList]);

  const departmentOptions = useMemo(() => [
    { value: "all", label: "All Departments" },
    ...Array.from(new Set(ticketList.map((t) => String(t.department || "").trim()).filter(Boolean)))
      .sort((a, b) => a.localeCompare(b))
      .map((value) => ({ value: value.toLowerCase(), label: value })),
  ], [ticketList]);


  return (
    <Layout role="operator">
      <section className="aix-wrap">
        {!detailMode && (
          <article className="aix-list">
            <div className="aix-hero">
              <h1 className="aix-hero__title">AI Explainability</h1>
            </div>

            {listError ? <p className="aix-error">{listError}</p> : null}

            <section className="aix-list-controls">
              <PillSearch
                className="aix-list-search"
                value={ticketSearch}
                onChange={(v) => {
                  const raw = typeof v === "string" ? v : (v?.target?.value ?? "");
                  setTicketSearch(sanitizeSearchQuery(raw));
                }}
                placeholder="Search by ticket code..."
                maxLength={MAX_SEARCH_LEN}
              />
              <div className="aix-filter-bar">
                <PillSelect
                  className="aix-filter-select"
                  value={priorityFilter}
                  onChange={setPriorityFilter}
                  options={priorityOptions}
                  ariaLabel="Filter by priority"
                  minWidth={156}
                />
                <PillSelect
                  className="aix-filter-select"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  options={statusOptions}
                  ariaLabel="Filter by status"
                  minWidth={150}
                />
                <PillSelect
                  className="aix-filter-select"
                  value={departmentFilter}
                  onChange={setDepartmentFilter}
                  options={departmentOptions}
                  ariaLabel="Filter by department"
                  minWidth={176}
                />
                <FilterPillButton
                  onClick={() => {
                    setPriorityFilter("all");
                    setStatusFilter("all");
                    setDepartmentFilter("all");
                    setTicketSearch("");
                  }}
                  label="Reset"
                />
              </div>
            </section>

            <div className="table-wrapper-EV-VAC">
              <table className="complaints-table-EV-VAC">
                <thead>
                  <tr>
                    <th>Ticket</th>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Department</th>
                    <th>Assignee</th>
                    <th>Created</th>
                    <th></th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {listLoading ? (
                    <tr><td colSpan={9}>Loading tickets...</td></tr>
                  ) : visibleTicketList.length === 0 ? (
                    <tr><td colSpan={9}>No completed pipeline tickets yet.</td></tr>
                  ) : (
                    visibleTicketList.map((t) => (
                        <tr key={t.ticketId}>
                          <td>
                            <button
                              type="button"
                              className="aix-row-ticket"
                              onClick={() => navigate(`/operator/ai-explainability/${encodeURIComponent(t.ticketCode)}`)}
                            >
                              {t.ticketCode}
                            </button>
                          </td>
                          <td>{t.subject || "—"}</td>
                          <td>
                            <span className={`ev-status-badge ${STATUS_CLASS.Completed || "ev-status-assigned"}`}>
                              Completed
                            </span>
                          </td>
                          <td>{t.priority ? <PriorityPill priority={t.priority} /> : "—"}</td>
                          <td>{t.department}</td>
                          <td>{t.assignedTo}</td>
                          <td>{t.pipelineCompletedAt ? new Date(t.pipelineCompletedAt).toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium", timeStyle: "short" }) : (t.createdAt ? new Date(t.createdAt).toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium", timeStyle: "short" }) : "—")}</td>
                          <td>
                            <button
                              type="button"
                              className="aix-open-btn"
                              onClick={() => navigate(`/operator/ai-explainability/${encodeURIComponent(t.ticketCode)}`)}
                            >
                              View Pipeline
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="aix-delete-btn"
                              title="Delete ticket"
                              aria-label={`Delete ${t.ticketCode}`}
                              onClick={e => deleteTicket(t.ticketId, e)}
                            >
                              <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                <path d="M10 11v6" />
                                <path d="M14 11v6" />
                                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                              </svg>
                            </button>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </article>
        )}

        {detailMode && (
          <>
            <div className="aix-detail-actions">
              <button
                type="button"
                className="aix-back-btn"
                onClick={() => navigate("/operator/ai-explainability")}
              >
                Back to Ticket List
              </button>
            </div>

            {detailLoading ? (
              <article className="aix-stage">
                <h3>Loading ticket pipeline...</h3>
              </article>
            ) : null}
            {detailError ? <p className="aix-error">{detailError}</p> : null}

            {data ? (
              <>
                <article className="aix-detail-header">
                  <div>
                    <h1 className="aix-ticket-title">Ticket ID: {detailTicket.ticketId || data.ticketCode}</h1>
                    <div className="aix-status-row">
                      {detailTicket.priority ? (
                        <span className="header-pill">{detailTicket.priority}</span>
                      ) : null}
                      <span className={`header-pill ev-status-badge ${STATUS_CLASS[detailTicket.status || data.status] || "ev-status-assigned"}`}>
                        {detailTicket.status || data.status || "—"}
                      </span>
                    </div>
                  </div>
                </article>

                <section className="aix-card-section">
                  <h2 className="aix-section-title">Summary</h2>
                  <div className="aix-summary-grid">
                    <div><span className="aix-label">Issue Date</span><div>{detailTicket.issueDate || "—"}</div></div>
                    <div><span className="aix-label">Submitted By</span><div>{detailTicket.submittedBy?.name || "Unknown"}</div></div>
                    <div><span className="aix-label">Contact</span><div>{detailTicket.submittedBy?.contact || "—"}</div></div>
                    <div><span className="aix-label">Location</span><div>{detailTicket.submittedBy?.location || "—"}</div></div>
                    <div><span className="aix-label">Department</span><div>{detailTicket.department || "Unassigned"}</div></div>
                    <div><span className="aix-label">Pipeline Runs</span><div>{data.pipelineExecutions?.length || 0}</div></div>
                  </div>
                  <div className="aix-summary-text">
                    <span className="aix-label">Ticket Subject</span>
                    <div>{detailTicket.description?.subject || data.subject || "—"}</div>
                  </div>
                  <div className="aix-summary-text">
                    <span className="aix-label">Ticket Details</span>
                    <div className="aix-description">{detailTicket.description?.details || data.details || "—"}</div>
                  </div>
                </section>

                <section className="aix-details-grid">
                  {(detailTicket.stepsTaken || []).length > 0 ? (
                    <article className="aix-card-section">
                      <h2 className="aix-section-title">Steps Taken</h2>
                      {(detailTicket.stepsTaken || []).map((step) => (
                        <div key={step.step} className="aix-step-card">
                          <div className="aix-step-title">Step {step.step}</div>
                          <div className="aix-step-text">
                            Technician: {step.technician || "—"}<br />
                            Time: {step.time || "—"}<br />
                            Notes: {step.notes || "—"}
                          </div>
                        </div>
                      ))}
                    </article>
                  ) : null}
                </section>

                <section className="aix-card-section">
                  <h2 className="aix-section-title">Pipeline Controls</h2>
                  <div className="aix-subtle">
                    Current model-selected: type={modelSelectedSummary.ticketType}, impact={modelSelectedSummary.businessImpact}, severity={modelSelectedSummary.issueSeverity}, urgency={modelSelectedSummary.issueUrgency}, safety={modelSelectedSummary.safetyConcern ? "true" : "false"}, sentiment={modelSelectedSummary.sentimentScore}.
                  </div>
                  <div className="aix-controls-grid">
                    <label className="aix-field">
                      <span>Ticket Type</span>
                      <select
                        value={overrideForm.ticketType}
                        onChange={(e) => setOverrideForm((p) => ({ ...p, ticketType: e.target.value }))}
                      >
                        <option value="complaint">Complaint</option>
                        <option value="inquiry">Inquiry</option>
                      </select>
                    </label>
                    <label className="aix-field">
                      <span>Business Impact</span>
                      <select
                        value={overrideForm.businessImpact}
                        onChange={(e) => setOverrideForm((p) => ({ ...p, businessImpact: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                    <label className="aix-field">
                      <span>Issue Severity</span>
                      <select
                        value={overrideForm.issueSeverity}
                        onChange={(e) => setOverrideForm((p) => ({ ...p, issueSeverity: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                    <label className="aix-field">
                      <span>Issue Urgency</span>
                      <select
                        value={overrideForm.issueUrgency}
                        onChange={(e) => setOverrideForm((p) => ({ ...p, issueUrgency: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </label>
                  </div>

                  <div className="aix-toggles">
                    <label className="aix-check">
                      <input
                        type="checkbox"
                        checked={overrideForm.safetyConcern}
                        onChange={(e) => setOverrideForm((p) => ({ ...p, safetyConcern: e.target.checked }))}
                      />
                      <span>Safety Concern</span>
                    </label>
                    <label className="aix-check">
                      <input
                        type="checkbox"
                        checked={overrideForm.isRecurring}
                        onChange={(e) =>
                          setOverrideForm((p) => ({
                            ...p,
                            isRecurring: e.target.checked,
                            similarTicketCode: e.target.checked ? p.similarTicketCode : "",
                          }))
                        }
                      />
                      <span>Recurring Ticket</span>
                    </label>
                  </div>

                  {overrideForm.isRecurring ? (
                    <div className="aix-recurrence-box">
                      <label className="aix-field">
                        <span>Search Similar Ticket ID</span>
                        <input
                          type="text"
                          value={recurrenceQuery}
                          onChange={(e) => setRecurrenceQuery(sanitizeSearchQuery(e.target.value))}
                          placeholder="Type ticket code or subject..."
                          maxLength={MAX_SEARCH_LEN}
                        />
                      </label>
                      {recurrenceLoading ? <div className="aix-subtle">Searching tickets...</div> : null}
                      <div className="aix-search-results">
                        {recurrenceResults.map((item) => (
                          <button
                            key={item.ticketCode}
                            type="button"
                            className={`aix-result-btn ${
                              overrideForm.similarTicketCode === item.ticketCode ? "aix-result-btn--active" : ""
                            }`}
                            onClick={() =>
                              setOverrideForm((p) => ({
                                ...p,
                                similarTicketCode: item.ticketCode,
                              }))
                            }
                          >
                            <strong>{item.ticketCode}</strong> {item.subject ? `- ${item.subject}` : ""}
                          </button>
                        ))}
                      </div>
                      {overrideForm.similarTicketCode ? (
                        <div className="aix-subtle">Selected: {overrideForm.similarTicketCode}</div>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="aix-controls-actions">
                    <button type="button" className="aix-open-btn" disabled={rerunBusy || overrideBusy} onClick={rerunPipeline}>
                      {rerunBusy ? "Re-running..." : "Re-run Full Pipeline"}
                    </button>
                    <button type="button" className="aix-open-btn" disabled={overrideBusy} onClick={applyOverrides}>
                      {overrideBusy ? "Applying..." : "Apply & Re-run Prioritization"}
                    </button>
                  </div>
                  {overrideErr ? <p className="aix-error">{overrideErr}</p> : null}
                  {overrideMsg ? <p className="aix-subtle">{overrideMsg}</p> : null}
                </section>

                <article className="aix-stage-menu">
                  <h3>Pipeline Stages</h3>
                  <div className="aix-stage-chips">
                    {stageMenu.map((s) => {
                      const key = `${s.stepOrder}-${s.stageName}`;
                      const active = key === selectedStageKey;
                      return (
                        <button
                          key={key}
                          type="button"
                          className={`aix-stage-chip ${active ? "aix-stage-chip--active" : ""}`}
                          onClick={() => setSelectedStageKey(key)}
                        >
                          {stageMenu.findIndex((x) => `${x.stepOrder}-${x.stageName}` === key) + 1}. {s.stageName}
                        </button>
                      );
                    })}
                  </div>
                </article>

                {selectedStage ? (
                  <article className={`aix-stage ${selectedStageVisualStatus === "failed" ? "aix-stage--failed" : ""}`}>
                    <header className="aix-stage-head">
                      <h3>
                        Step {selectedStageDisplayOrder ?? selectedStage.stepOrder}: {selectedStage.stageName}
                      </h3>
                      <div className={`aix-pill aix-pill--${selectedStageVisualStatus}`}>
                        {selectedStage.eventType} · {selectedStageStatusLabel}
                      </div>
                    </header>
                    <div className="aix-meta">
                      <span>Execution: {selectedStage.executionId}</span>
                      <span>Time: {selectedStage.createdAt || "—"}</span>
                      <span>Processing time: {formatProcessingTimeSeconds(selectedStage.inferenceTimeMs)}</span>
                      <span>Confidence: {getStageConfidence(selectedStage) ?? "—"}</span>
                      <span>Mode: {inferStageMode(selectedStage)}</span>
                      {selectedStage.stageName === "AudioAnalysisAgent" ? (
                        <span>Audio Provided: {stageHasAudio(selectedStage) ? "Yes" : "No"}</span>
                      ) : null}
                    </div>
                    {selectedStage.description || selectedStage.explanation ? (
                      <div className="aix-stage-explainer">
                        {selectedStage.description ? (
                          <div className="aix-stage-explainer__description">{selectedStage.description}</div>
                        ) : null}
                        {selectedStage.explanation ? (
                          <div className="aix-stage-explainer__explanation">{selectedStage.explanation}</div>
                        ) : null}
                      </div>
                    ) : null}
                    {selectedStage.errorMessage ? <p className="aix-error">Error: {selectedStage.errorMessage}</p> : null}
                    {selectedStage.stageName === "PrioritizationAgent" ? (
                      <div className="aix-formula">
                        <h4>Priority Formula</h4>
                        {computePriorityFormulaLines(selectedStageIO.input).map((line, i) => (
                          <div key={`${i}-${line}`} className="aix-formula-line">{line}</div>
                        ))}
                      </div>
                    ) : null}
                    {selectedStage.stageName === "RecurrenceAgent" &&
                    selectedStageIO?.output?.similar_ticket_code ? (
                      <div className="aix-linked-ticket">
                        <span className="aix-label">Linked Similar Ticket</span>
                        <button
                          type="button"
                          className="aix-open-btn"
                          onClick={() =>
                            navigate(
                              `/operator/ai-explainability/${encodeURIComponent(
                                selectedStageIO.output.similar_ticket_code,
                              )}`,
                            )
                          }
                        >
                          {selectedStageIO.output.similar_ticket_code}
                        </button>
                        {selectedStageIO.output.similar_ticket_subject ? (
                          <span>{selectedStageIO.output.similar_ticket_subject}</span>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="aix-io-grid">
                      <div>
                        <h4>Input State</h4>
                        <div className="aix-io-box">
                          <KeyValueBlock data={selectedStageIO.input} />
                        </div>
                      </div>
                      <div>
                        <h4>Output State</h4>
                        <div className="aix-io-box">
                          <KeyValueBlock data={selectedStageIO.output} />
                        </div>
                      </div>
                    </div>
                  </article>
                ) : (
                  <article className="aix-stage">
                    <h3>No pipeline stage logs found</h3>
                    <p>This ticket has no stage-level explainability rows yet.</p>
                  </article>
                )}
              </>
            ) : null}
          </>
        )}
      </section>
    </Layout>
  );
}
