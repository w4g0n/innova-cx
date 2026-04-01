import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import { apiUrl } from "../../config/apiBase";
import TicketChat from "../../components/common/TicketChat";
import {
  sanitizeText,
  sanitizeId,
  sanitizeFilename,
  sanitizePriority,
  sanitizeDepartment,
  sanitizeTicketSource,
  ALLOWED_PRIORITIES,
  ALLOWED_DEPARTMENTS,
  MAX_REASON_LEN,
  MAX_RESOLUTION_LEN,
} from "./EmployeeSanitize";
import "./TicketDetails.css";

const API_BASE = apiUrl("/api");

// File upload constraints for resolve attachments
const MAX_RESOLVE_FILES      = 10;
const MAX_RESOLVE_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_MIME_PREFIXES  = ["image/", "application/pdf"];
const ALLOWED_EXTENSIONS     = [".doc", ".docx", ".xls", ".xlsx", ".txt"];

function isAllowedFile(file) {
  const name = (file.name || "").toLowerCase();
  const ext  = name.substring(name.lastIndexOf("."));
  return (
    ALLOWED_MIME_PREFIXES.some((p) => (file.type || "").startsWith(p)) ||
    ALLOWED_EXTENSIONS.includes(ext)
  );
}

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token")        ||
    localStorage.getItem("jwt")          ||
    localStorage.getItem("authToken")    ||
    ""
  );
}

// formatTicketSource returns only "Chatbot" or "User" — safe
function formatTicketSource(value) {
  return sanitizeTicketSource(value);
}

// --- AttachmentThumb --------------------------------------------------------
function AttachmentThumb({ url, fileName, token }) {
  const isImage = /\.(jpe?g|png|gif|webp|bmp|svg)$/i.test(fileName || "");
  const [imgError,     setImgError]     = useState(false);
  const [downloading,  setDownloading]  = useState(false);

  if (!url) return null;

  if (isImage && !imgError) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        // sanitizeFilename already applied before this component receives fileName
        title={fileName}
        className="attachment-thumb attachment-thumb--image"
      >
        <img
          src={url}
          alt={fileName}
          className="attachment-thumb__img"
          onError={() => setImgError(true)}
        />
      </a>
    );
  }

  const handleDownload = async (e) => {
    e.preventDefault();
    if (downloading) return;
    setDownloading(true);
    try {
      const headers = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob    = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const anchor  = document.createElement("a");
      anchor.href     = blobUrl;
      anchor.download = fileName || "download";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
    } catch {
      window.open(url, "_blank", "noopener,noreferrer");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <a
      href={url}
      onClick={handleDownload}
      className="attachment-thumb attachment-thumb--file"
      title={fileName}
      aria-disabled={downloading}
    >
      <svg
        className="attachment-thumb__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </svg>
      <span className="attachment-thumb__name">
        {downloading ? "Downloading…" : fileName}
      </span>
    </a>
  );
}

// ─── Modal ──────────────────────────────────────────────────────────────────
function TicketModal({
  type,
  ticket,
  id,
  confirming,
  setConfirming,
  rerouteDepartment,
  setRerouteDepartment,
  rerouteReason,
  setRerouteReason,
  rerouteError,
  setRerouteError,
  rescoreNewPriority,
  setRescoreNewPriority,
  rescoreReason,
  setRescoreReason,
  rescoreError,
  setRescoreError,
  resolveReviewAction,
  setResolveReviewAction,
  resolutionSuggestion,
  suggestionBusy,
  finalResolution,
  setFinalResolution,
  stepsTaken,
  setStepsTaken,
  resolveError,
  setResolveError,
  resolveFiles,
  setResolveFiles,
  resolveFileError,
  setResolveFileError,
  resolveBusy,
  setResolveBusy,
  closeModal,
  loadTicket,
  uploadAttachmentsOrThrow,
  onSuccess,
}) {
  if (!type || !ticket) return null;

  const titles = {
    reroute:  "Reroute Ticket",
    rescore:  "Rescore Ticket",
    escalate: "Escalate Ticket",
    resolve:  "Resolve Ticket",
  };

  const submitText =
    type === "resolve"  ? "Resolve" :
    type === "escalate" ? "Escalate" : "Submit";

  const renderConfirmation = () => {
    if (type === "reroute") {
      return (
        <div className="modal-confirm-body">
          <div className="modal-confirm-icon">↗</div>
          <p className="modal-confirm-heading">Confirm Reroute Request</p>
          <p className="modal-confirm-sub">
            Please review the details below before submitting. This will be sent
            for manager approval.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Department</span>
              {/* rerouteDepartment is validated against allowlist before confirm is shown */}
              <span className="modal-confirm-value">{rerouteDepartment}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Reason</span>
              <span className="modal-confirm-value modal-confirm-reason">
                {rerouteReason}
              </span>
            </div>
          </div>
        </div>
      );
    }
    if (type === "rescore") {
      return (
        <div className="modal-confirm-body">
          <div className="modal-confirm-icon">⚖</div>
          <p className="modal-confirm-heading">Confirm Rescore Request</p>
          <p className="modal-confirm-sub">
            Please review the details below before submitting. This will be sent
            for manager approval.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Current Priority</span>
              {/* ticket.priority is sanitizePriority'd before reaching modal props */}
              <span className="modal-confirm-value">{ticket.priority ?? "—"}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Priority</span>
              <span className="modal-confirm-value">{rescoreNewPriority}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Reason</span>
              <span className="modal-confirm-value modal-confirm-reason">
                {rescoreReason}
              </span>
            </div>
          </div>
        </div>
      );
    }
    if (type === "resolve") {
      return (
        <div className="modal-confirm-body">
          <div className="modal-confirm-icon">✓</div>
          <p className="modal-confirm-heading">Confirm Resolution</p>
          <p className="modal-confirm-sub">
            Please review the details below before submitting. This action will
            mark the ticket as resolved.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Resolution Decision</span>
              <span className="modal-confirm-value">
                {resolveReviewAction === "accepted"
                  ? "AI Suggestion Accepted"
                  : "Custom Resolution"}
              </span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Final Resolution</span>
              <span className="modal-confirm-value modal-confirm-reason">
                {finalResolution || "—"}
              </span>
            </div>
            {resolveFiles.length > 0 && (
              <div className="modal-confirm-row">
                <span className="modal-confirm-label">Attachments</span>
                <span className="modal-confirm-value">
                  {resolveFiles.length} file(s):{" "}
                  {/* sanitizeFilename applied before files enter resolveFiles state */}
                  {resolveFiles.map((f) => sanitizeFilename(f.name, 60)).join(", ")}
                </span>
              </div>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  const renderBody = () => {
    switch (type) {
      case "reroute":
        return (
          <>
            <label>New Department</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={rerouteDepartment}
                onChange={(e) => {
                  // Validate against allowlist — never accept arbitrary department strings
                  const safe = sanitizeDepartment(e.target.value);
                  setRerouteDepartment(safe);
                }}
              >
                <option value="" disabled>Select Department</option>
                {ALLOWED_DEPARTMENTS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </div>
            <label>Reason for rerouting</label>
            <textarea
              className="modal-textarea"
              value={rerouteReason}
              onChange={(e) => {
                // Cap reason length client-side
                const v = e.target.value;
                if (v.length <= MAX_REASON_LEN) {
                  setRerouteReason(v);
                  setRerouteError("");
                }
              }}
              placeholder="Explain why this ticket should be rerouted..."
              maxLength={MAX_REASON_LEN}
            />
            <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#888" }}>
              {rerouteReason.length} / {MAX_REASON_LEN}
            </div>
            {rerouteError && (
              <div className="modal-inline-error">{rerouteError}</div>
            )}
          </>
        );

      case "rescore":
        return (
          <>
            <label>New Priority</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={rescoreNewPriority}
                onChange={(e) => {
                  // Validate against allowlist — reject unknown priority values
                  const safe = sanitizePriority(e.target.value);
                  setRescoreNewPriority(safe);
                }}
              >
                {ALLOWED_PRIORITIES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <label>Reason for rescoring</label>
            <textarea
              className="modal-textarea"
              value={rescoreReason}
              onChange={(e) => {
                const v = e.target.value;
                if (v.length <= MAX_REASON_LEN) {
                  setRescoreReason(v);
                  setRescoreError("");
                }
              }}
              placeholder="Explain why the model score should be adjusted..."
              maxLength={MAX_REASON_LEN}
            />
            <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#888" }}>
              {rescoreReason.length} / {MAX_REASON_LEN}
            </div>
            {rescoreError && (
              <div className="modal-inline-error">{rescoreError}</div>
            )}
          </>
        );

      case "escalate":
        return (
          <>
            <label>Escalation Level</label>
            <div className="select-wrapper modal-dropdown">
              <select defaultValue="">
                <option value="" disabled>Select Level</option>
                <option>Supervisor</option>
                <option>Department Head</option>
                <option>Management</option>
              </select>
            </div>
            <label>Reason for Escalation</label>
            <textarea
              className="modal-textarea"
              placeholder="Explain why this ticket must be escalated..."
              maxLength={MAX_REASON_LEN}
            />
            <label>Additional Notes (optional)</label>
            <textarea
              className="modal-textarea"
              placeholder="Any extra context..."
              maxLength={MAX_REASON_LEN}
            />
          </>
        );

      case "resolve":
        return (
          <>
            {!(resolutionSuggestion || "").trim() && (
              <div style={{
                display: "flex", alignItems: "flex-start", gap: "10px",
                padding: "12px 14px", marginBottom: "14px", borderRadius: "12px",
                background: "rgba(234,179,8,0.08)", border: "1.5px solid rgba(234,179,8,0.28)",
                fontSize: "13px", fontWeight: "600", color: "#92400e", lineHeight: "1.45",
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0, marginTop: "1px" }}>
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>No AI suggestion available for this ticket. Please write the resolution manually below.</span>
              </div>
            )}
            <label>Suggested Resolution</label>
            <div className="resolution-review-box">
              <div className="resolution-review-box__hint">
                Mark as correct, decline, or edit. Your action trains the model.
              </div>

              <textarea
                className="modal-textarea resolution-review-box__textarea"
                value={finalResolution}
                onChange={(e) => {
                  const next = e.target.value;
                  // Cap resolution length
                  if (next.length <= MAX_RESOLUTION_LEN) {
                    setFinalResolution(next);
                    if ((resolutionSuggestion || "").trim() !== next.trim()) {
                      setResolveReviewAction("edited");
                    }
                  }
                }}
                placeholder={suggestionBusy ? "Generating..." : "No suggestion available."}
                disabled={suggestionBusy}
                maxLength={MAX_RESOLUTION_LEN}
              />
              <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#888" }}>
                {finalResolution.length} / {MAX_RESOLUTION_LEN}
              </div>

              <div className="resolution-review-box__actions">
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--decline ${resolveReviewAction === "declined" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("declined")}
                  disabled={suggestionBusy}
                  aria-label="Decline suggestion"
                  title="Decline suggestion"
                >✕</button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--accept ${resolveReviewAction === "accepted" ? "is-active" : ""}`}
                  onClick={() => {
                    setResolveReviewAction("accepted");
                    setFinalResolution(resolutionSuggestion || "");
                  }}
                  disabled={suggestionBusy || !(resolutionSuggestion || "").trim()}
                  aria-label="Accept suggestion"
                  title={!(resolutionSuggestion || "").trim() ? "No suggestion to accept" : "Accept suggestion"}
                >✓</button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--edit ${resolveReviewAction === "edited" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("edited")}
                  disabled={suggestionBusy}
                  aria-label="Edit suggestion"
                  title="Edit suggestion"
                >✎</button>
              </div>
            </div>

            {resolveError && (
              <div style={{ color: "#b42318", marginTop: 8, whiteSpace: "pre-wrap" }}>
                {/* resolveError is set from fixed internal strings only */}
                {resolveError}
              </div>
            )}

            <label>
              Steps Taken <span className="modal-label-optional">optional</span>
            </label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => {
                const v = e.target.value;
                if (v.length <= MAX_REASON_LEN) setStepsTaken(v);
              }}
              placeholder="List the steps taken to resolve this issue..."
              disabled={suggestionBusy}
              maxLength={MAX_REASON_LEN}
            />

            <label>
              Attachments <span className="modal-label-optional">optional</span>
            </label>
            <div className="modal-upload-box">
              <label className="modal-upload-box__label">
                <div className="modal-upload-box__inner">
                  <div className="modal-upload-box__icon-wrap">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <span className="modal-upload-box__title">
                    {resolveFiles.length > 0
                      ? `${resolveFiles.length} file${resolveFiles.length > 1 ? "s" : ""} attached`
                      : "Click to upload files"}
                  </span>
                </div>
                <input
                  type="file"
                  multiple
                  className="modal-upload-box__input"
                  accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx,.txt"
                  onChange={(e) => {
                    const incoming = Array.from(e.target.files || []);
                    const fileErrors = [];

                    setResolveFiles((prev) => {
                      const next = [...prev];
                      for (const f of incoming) {
                        // Enforce count cap
                        if (next.length >= MAX_RESOLVE_FILES) {
                          fileErrors.push(`Maximum ${MAX_RESOLVE_FILES} attachments allowed.`);
                          break;
                        }
                        // Enforce per-file size cap
                        if (f.size > MAX_RESOLVE_FILE_BYTES) {
                          fileErrors.push(`"${sanitizeFilename(f.name, 40)}" exceeds 10 MB.`);
                          continue;
                        }
                        // Enforce MIME / extension allowlist
                        if (!isAllowedFile(f)) {
                          fileErrors.push(`"${sanitizeFilename(f.name, 40)}" is not an allowed file type.`);
                          continue;
                        }
                        // Deduplicate
                        const exists = next.some(
                          (x) => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified
                        );
                        if (!exists) next.push(f);
                      }
                      return next;
                    });

                    if (fileErrors.length) setResolveFileError(fileErrors[0]);
                    e.target.value = "";
                  }}
                />
              </label>

              {resolveFileError && (
                <div className="modal-inline-error" role="alert">
                  {/* resolveFileError is set from a fixed internal template */}
                  {resolveFileError}
                </div>
              )}

              {resolveFiles.length > 0 && (
                <div className="modal-upload-box__files">
                  {resolveFiles.map((f, i) => (
                    <div key={i} className="modal-upload-box__file">
                      <div className="modal-upload-box__file-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
                          <path d="M14 2v6h6" />
                        </svg>
                      </div>
                      <div className="modal-upload-box__file-info">
                        {/* sanitizeFilename prevents overlong/malformed names in the UI */}
                        <span className="modal-upload-box__file-name">{sanitizeFilename(f.name, 60)}</span>
                        <span className="modal-upload-box__file-size">
                          {f.size < 1024 * 1024
                            ? `${Math.round(f.size / 1024)} KB`
                            : `${(f.size / (1024 * 1024)).toFixed(1)} MB`}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="modal-upload-box__remove"
                        onClick={() => {
                          setResolveFiles((prev) => prev.filter((_, j) => j !== i));
                          setResolveFileError("");
                        }}
                        disabled={resolveBusy}
                        aria-label={`Remove ${sanitizeFilename(f.name, 40)}`}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6"  y2="18" />
                          <line x1="6"  y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        );

      default:
        return null;
    }
  };

  const handleSubmit = async () => {
    if (type === "rescore") {
      // Both values are allowlist-validated before reaching here
      if (!rescoreNewPriority || !rescoreReason.trim()) {
        setRescoreError("Please select a priority and provide a reason.");
        return;
      }
      const token = getAuthToken();
      try {
        const res = await fetch(
          `${API_BASE}/employee/tickets/${encodeURIComponent(id)}/rescore`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              // sanitizeText applied as final trim before API call
              new_priority: sanitizePriority(rescoreNewPriority),
              reason:       sanitizeText(rescoreReason, MAX_REASON_LEN),
            }),
          }
        );
        if (!res.ok) throw new Error("rescore_failed");
        setRescoreReason("");
        closeModal();
        onSuccess("Rescore request submitted for manager approval.");
      } catch {
        setRescoreError("Failed to submit rescore request. Please try again.");
      }
      return;
    }

    if (type === "reroute") {
      if (!rerouteDepartment || !rerouteReason.trim()) {
        setRerouteError("Please select a department and provide a reason.");
        return;
      }
      const token = getAuthToken();
      try {
        const res = await fetch(
          `${API_BASE}/employee/tickets/${encodeURIComponent(id)}/reroute`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              new_department: sanitizeDepartment(rerouteDepartment),
              reason:         sanitizeText(rerouteReason, MAX_REASON_LEN),
            }),
          }
        );
        if (!res.ok) throw new Error("reroute_failed");
        setRerouteDepartment("");
        setRerouteReason("");
        closeModal();
        onSuccess("Reroute request submitted for manager approval.");
      } catch {
        setRerouteError("Failed to submit reroute request. Please try again.");
      }
      return;
    }

    if (type === "escalate") {
      closeModal();
      onSuccess("Escalate saved (UI only for now).");
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setResolveError("Missing auth token. Please log in again.");
      return;
    }

    const suggestedTrimmed = (resolutionSuggestion || "").trim();
    const finalTrimmed     = finalResolution.trim();

    if (resolveReviewAction !== "accepted" && !finalTrimmed) {
      setResolveError("Please provide an edited final resolution.");
      return;
    }

    if (resolveReviewAction === "declined" && finalTrimmed === suggestedTrimmed) {
      setResolveError("Please edit the resolution so the model can learn the correction.");
      return;
    }

    setResolveBusy(true);
    setResolveError("");
    try {
      await uploadAttachmentsOrThrow({ ticketCode: id, token, files: resolveFiles });

      const decision = resolveReviewAction === "accepted" ? "accepted" : "declined_custom";

      const payload = {
        decision,
        final_resolution: decision === "declined_custom"
          ? sanitizeText(finalTrimmed, MAX_RESOLUTION_LEN)
          : undefined,
        steps_taken: stepsTaken.trim()
          ? sanitizeText(stepsTaken.trim(), MAX_REASON_LEN)
          : undefined,
      };

      const res = await fetch(
        `${API_BASE}/employee/tickets/${encodeURIComponent(id)}/resolve`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) throw new Error("resolve_failed");

      await loadTicket();
      setResolveFiles([]);
      setStepsTaken("");
      closeModal();
      onSuccess("Ticket resolved successfully.");
    } catch {
      setResolveError("Could not resolve ticket. Please try again.");
    } finally {
      setResolveBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div
        className={`modal-card ${type === "escalate" ? "modal-red" : ""} ${type === "resolve" ? "modal-card--resolve" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          {/* titles is a static map — never API-derived */}
          <h2>{titles[type]}</h2>
          <span className="modal-close" onClick={closeModal}>✕</span>
        </div>

        <div className="modal-body">
          {confirming ? renderConfirmation() : renderBody()}
        </div>

        <div className="modal-footer">
          {confirming ? (
            <>
              <button className="modal-btn cancel" onClick={() => setConfirming(false)}>← Back</button>
              <button
                className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
                onClick={handleSubmit}
                disabled={resolveBusy || suggestionBusy}
              >
                {resolveBusy
                  ? "Saving..."
                  : type === "resolve"
                  ? "Confirm & Resolve"
                  : "Confirm & Submit"}
              </button>
            </>
          ) : (
            <>
              <button className="modal-btn cancel" onClick={closeModal}>Cancel</button>
              <button
                className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
                onClick={() => {
                  if (type === "reroute") {
                    if (!rerouteDepartment || !rerouteReason.trim()) {
                      setRerouteError("Please select a department and provide a reason.");
                      return;
                    }
                    setRerouteError("");
                    setConfirming(true);
                    return;
                  }
                  if (type === "rescore") {
                    if (!rescoreNewPriority || !rescoreReason.trim()) {
                      setRescoreError("Please select a priority and provide a reason.");
                      return;
                    }
                    setRescoreError("");
                    setConfirming(true);
                    return;
                  }
                  if (type === "resolve") {
                    if (resolveReviewAction !== "accepted" && !finalResolution.trim()) {
                      setResolveError("Please provide an edited final resolution.");
                      return;
                    }
                    setResolveError("");
                    setConfirming(true);
                    return;
                  }
                  handleSubmit();
                }}
                disabled={resolveBusy || suggestionBusy}
              >
                {resolveBusy ? "Saving..." : submitText}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function statusPillClass(status) {
  switch ((status || "").toLowerCase().replace(/\s+/g, "")) {
    case "open":       return "empStatusPill--open";
    case "assigned":   return "empStatusPill--assigned";
    case "inprogress": return "empStatusPill--inprogress";
    case "escalated":  return "empStatusPill--escalated";
    case "overdue":    return "empStatusPill--overdue";
    case "resolved":   return "empStatusPill--resolved";
    default:           return "";
  }
}

// ─── Main Component ─────────────────────────────────────────────────────────
export default function ComplaintDetails() {
  const { id: rawId } = useParams();
  const navigate      = useNavigate();

  // Sanitize the URL param immediately — rawId is never used directly after this
  const id = sanitizeId(rawId, 48);

  const [ticket,  setTicket]  = useState(null);
  const [loading, setLoading] = useState(true);
  // Fixed internal error messages only — raw API error text is never rendered
  const [error,   setError]   = useState("");
  const [modalType, setModalType] = useState(null);

  const [confirming,           setConfirming]           = useState(false);
  const [resolveReviewAction,  setResolveReviewAction]  = useState("accepted");
  const [resolutionSuggestion, setResolutionSuggestion] = useState("");
  const [finalResolution,      setFinalResolution]      = useState("");
  const [stepsTaken,           setStepsTaken]           = useState("");
  const [resolveBusy,          setResolveBusy]          = useState(false);
  const [resolveError,         setResolveError]         = useState("");
  const [resolveFiles,         setResolveFiles]         = useState([]);
  const [resolveFileError,     setResolveFileError]     = useState("");
  const suggestionBusy = false;

  const [rescoreNewPriority, setRescoreNewPriority] = useState("Medium");
  const [rescoreReason,      setRescoreReason]      = useState("");
  const [rerouteDepartment,  setRerouteDepartment]  = useState("");
  const [rerouteReason,      setRerouteReason]      = useState("");
  const [rerouteError,       setRerouteError]       = useState("");
  const [rescoreError,       setRescoreError]       = useState("");
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  const openModal = (type) => {
    if (String(ticket?.status || "").toLowerCase() === "resolved") return;
    setConfirming(false);
    setModalType(type);
  };

  const closeModal = () => {
    setModalType(null);
    setConfirming(false);
    setRerouteError("");
    setRescoreError("");
    setResolveFileError("");
  };

  useEffect(() => {
    if (modalType !== "resolve") return;
    // resolutionSuggestion is sanitized when the ticket is loaded
    const preGenerated = (ticket?.suggestedResolution || "").trim();
    setResolutionSuggestion(preGenerated);
    setFinalResolution(preGenerated);
    setResolveError("");
    setResolveReviewAction(preGenerated ? "accepted" : "declined_custom");
  }, [modalType, ticket]);

  const loadTicket = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setError("Missing auth token. Please log in again.");
      setLoading(false);
      return;
    }

    // Reject obviously invalid IDs before making a network request
    if (!id) {
      setError("Invalid ticket ID.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      // id is sanitizeId'd — encodeURIComponent as final layer
      const res = await fetch(
        `${API_BASE}/employee/tickets/${encodeURIComponent(id)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("fetch_failed");
      const data = await res.json();
      const t    = data?.ticket || null;

      if (!t) {
        setTicket(null);
        return;
      }

      // Sanitize every field from the API before storing in state
      setTicket({
        ticketId:            sanitizeId(t.ticketId, 48),
        status:              sanitizeText(t.status,   40),
        priority:            sanitizePriority(t.priority),
        issueDate:           sanitizeText(t.issueDate, 40),
        ticketSource:        formatTicketSource(t.ticketSource),
        suggestedResolution: sanitizeText(t.suggestedResolution || "", MAX_RESOLUTION_LEN),
        finalResolution:     sanitizeText(t.finalResolution     || "", MAX_RESOLUTION_LEN),
        description: {
          subject: sanitizeText(t.description?.subject, 200),
          details: sanitizeText(t.description?.details, MAX_RESOLUTION_LEN),
        },
        submittedBy: {
          name:     sanitizeText(t.submittedBy?.name     || "", 100),
          contact:  sanitizeText(t.submittedBy?.contact  || "", 100),
          location: sanitizeText(t.submittedBy?.location || "", 200),
        },
        metrics: {
          minTimeToRespond: sanitizeText(t.metrics?.minTimeToRespond || "", 40),
          minTimeToResolve: sanitizeText(t.metrics?.minTimeToResolve || "", 40),
        },
        stepsTaken: Array.isArray(t.stepsTaken)
          ? t.stepsTaken.map((s) => ({
              step:       Number(s.step)                      || 0,
              technician: sanitizeText(s.technician || "", 100),
              time:       sanitizeText(s.time       || "",  40),
              notes:      sanitizeText(s.notes      || "", 500),
            }))
          : [],
        attachments: Array.isArray(t.attachments)
          ? t.attachments.map((att) => ({
              fileName: sanitizeFilename(att?.fileName ?? (typeof att === "string" ? att : ""), 255),
              fileUrl:  att?.fileUrl ?? null,
            }))
          : [],
      });
    } catch {
      // Fixed internal message — raw error.message never rendered
      setError("Could not load ticket details. Please try again.");
      setTicket(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadTicket();
  }, [loadTicket]);

  async function uploadAttachmentsOrThrow({ ticketCode, token, files }) {
    if (!files || files.length === 0) return;

    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      const upRes = await fetch(
        `${API_BASE}/employee/tickets/${encodeURIComponent(ticketCode)}/attachments`,
        {
          method:  "POST",
          headers: { Authorization: `Bearer ${token}` },
          body:    fd,
        }
      );
      if (!upRes.ok) {
        throw new Error(`Upload failed (${upRes.status})`);
      }
    }
  }

  if (loading) {
    return (
      <Layout role="employee">
        <div className="empTicketDetail">Loading ticket details...</div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout role="employee">
        {/* error is always a fixed internal string */}
        <div className="empTicketDetail">{error}</div>
      </Layout>
    );
  }

  if (!ticket) return null;

  const isResolved = ticket.status.toLowerCase() === "resolved";
  const authToken  = getAuthToken();

  return (
    <Layout role="employee">
      <div className="empTicketDetail">
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" onClick={() => navigate(-1)}>← Back</button>
            {/* ticket.ticketId is sanitizeId'd when stored in state */}
            <h1 className="ticket-title">Ticket ID: {ticket.ticketId}</h1>
            <div className="status-row">
              <span className={`header-pill ${ticket.priority.toLowerCase()}-pill`}>
                {ticket.priority}
              </span>
              <span className={`header-pill empStatusPill ${statusPillClass(ticket.status)}`}>
                {ticket.status}
              </span>
            </div>
          </div>

          {!isResolved && (
            <div className="header-actions">
              <button className="btn-outline" onClick={() => openModal("rescore")}>Rescore</button>
              <button className="btn-outline" onClick={() => openModal("reroute")}>Reroute</button>
              <button className="btn-primary" onClick={() => openModal("resolve")}>Resolve</button>
            </div>
          )}
        </div>

        <section className="card-section">
          <h2 className="section-title">Summary</h2>
          <div className="summary-grid">
            {[
              { label: "Issue Date:",        value: ticket.issueDate                        },
              { label: "Min Time To Respond:", value: ticket.metrics.minTimeToRespond || "—" },
              { label: "Min Time To Resolve:", value: ticket.metrics.minTimeToResolve || "—" },
              { label: "Submitted By:",      value: ticket.submittedBy.name     || "—"      },
              { label: "Contact:",           value: ticket.submittedBy.contact  || "—"      },
              { label: "Location:",          value: ticket.submittedBy.location || "—"      },
              { label: "Ticket Source:",     value: ticket.ticketSource                     },
            ].map(({ label, value }) => (
              <div key={label}>
                <div className="label" style={{
                  display: "block", color: "#374151", fontSize: "11px",
                  fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.08em", marginBottom: 3,
                }}>
                  {label}
                </div>
                {/* All values are sanitized when ticket state is set */}
                <div>{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="details-grid">
          <div className="card-section">
            <h2 className="section-title">Ticket Details</h2>
            <div className="subject">{ticket.description.subject}</div>
            <p className="description">{ticket.description.details}</p>

            {ticket.attachments.length > 0 && (
              <div className="attachments">
                {ticket.attachments.map((att, i) => {
                  const fileUrl = att.fileUrl
                    ? apiUrl(att.fileUrl)
                    : att.fileName
                    ? apiUrl("/uploads/" + att.fileName)
                    : null;

                  return (
                    <AttachmentThumb
                      key={i}
                      url={fileUrl}
                      // fileName is sanitizeFilename'd when ticket state is set
                      fileName={att.fileName}
                      token={authToken}
                    />
                  );
                })}
              </div>
            )}
          </div>

          {ticket.stepsTaken.length > 0 && (
            <div className="card-section">
              <h2 className="section-title">Steps Taken</h2>
              {ticket.stepsTaken.map((step) => (
                <div key={step.step} className="step">
                  <div className="step-title">Step {step.step}</div>
                  <div className="step-text">
                    {/* All step fields sanitized when ticket state is set */}
                    Technician assigned: {step.technician}
                    <br />
                    Time: {step.time}
                    <br />
                    Notes: {step.notes}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <TicketChat
          ticketId={ticket.ticketId}
          role="employee"
          authHeader={() => ({ Authorization: `Bearer ${authToken}` })}
          disabled={isResolved}
        />

        {ticket.finalResolution && (
          <section className="card-section">
            <h2 className="section-title">Final Resolution</h2>
            <p className="description">{ticket.finalResolution}</p>
          </section>
        )}
      </div>

      {toast.show && (
        <div className={`ticket-toast ticket-toast--${toast.type}`}>
          <span className="ticket-toast__msg">{toast.message}</span>
          <button
            className="ticket-toast__close"
            onClick={() => setToast((t) => ({ ...t, show: false }))}
          >
            ✕
          </button>
        </div>
      )}

      <TicketModal
        type={modalType}
        ticket={ticket}
        id={id}
        confirming={confirming}
        setConfirming={setConfirming}
        rerouteDepartment={rerouteDepartment}
        setRerouteDepartment={setRerouteDepartment}
        rerouteReason={rerouteReason}
        setRerouteReason={setRerouteReason}
        rerouteError={rerouteError}
        setRerouteError={setRerouteError}
        rescoreNewPriority={rescoreNewPriority}
        setRescoreNewPriority={setRescoreNewPriority}
        rescoreReason={rescoreReason}
        setRescoreReason={setRescoreReason}
        rescoreError={rescoreError}
        setRescoreError={setRescoreError}
        resolveReviewAction={resolveReviewAction}
        setResolveReviewAction={setResolveReviewAction}
        resolutionSuggestion={resolutionSuggestion}
        suggestionBusy={suggestionBusy}
        finalResolution={finalResolution}
        setFinalResolution={setFinalResolution}
        stepsTaken={stepsTaken}
        setStepsTaken={setStepsTaken}
        resolveError={resolveError}
        setResolveError={setResolveError}
        resolveFiles={resolveFiles}
        setResolveFiles={setResolveFiles}
        resolveFileError={resolveFileError}
        setResolveFileError={setResolveFileError}
        resolveBusy={resolveBusy}
        setResolveBusy={setResolveBusy}
        closeModal={closeModal}
        loadTicket={loadTicket}
        uploadAttachmentsOrThrow={uploadAttachmentsOrThrow}
        onSuccess={showToast}
      />
    </Layout>
  );
}