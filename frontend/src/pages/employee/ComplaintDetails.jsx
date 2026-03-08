import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import { apiUrl } from "../../config/apiBase";
import "./TicketDetails.css";

const API_BASE = apiUrl("/api");

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

function formatTicketSource(value) {
  return String(value || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
}

// --- AttachmentThumb --------------------------------------------------------
// FIX (Issue 1): Non-image attachments are downloaded via fetch+blob so that
// the request includes the auth token and the Content-Disposition header is
// respected in production (cross-origin). Images still render inline with a
// direct URL because <img> loads are not blocked by CORS for display.
function AttachmentThumb({ url, fileName, token }) {
  const isImage = /\.(jpe?g|png|gif|webp|bmp|svg)$/i.test(fileName || "");
  const [imgError, setImgError] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!url) return null;

  if (isImage && !imgError) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer"
         title={fileName} className="attachment-thumb attachment-thumb--image">
        <img
          src={url}
          alt={fileName}
          className="attachment-thumb__img"
          onError={() => setImgError(true)}
        />
      </a>
    );
  }

  // For all non-image files (and images that fail to load), use fetch+blob
  // download so it works reliably in cross-origin production environments.
  const handleDownload = async (e) => {
    e.preventDefault();
    if (downloading) return;
    setDownloading(true);
    try {
      const headers = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = fileName || "download";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      // Revoke after a short delay to allow the download to start
      setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
    } catch {
      // Fallback: open in new tab if blob download fails
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
      <svg className="attachment-thumb__icon" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </svg>
      <span className="attachment-thumb__name">
        {downloading ? "Downloading…" : fileName}
      </span>
    </a>
  );
}

// ─── Modal (outside ComplaintDetails so it never remounts on parent re-render)
// FIX (Issues 2 & 3): `confirming` state is now LIFTED into the parent
// (ComplaintDetails) and passed as a prop, so it is always reset to false
// when the modal is opened or closed. Previously it lived here as local
// useState, which meant it persisted across modal open/close cycles.
function TicketModal({
  type, ticket, id,
  // confirming — now controlled by parent to guarantee clean reset on open
  confirming, setConfirming,
  // reroute
  rerouteDepartment, setRerouteDepartment,
  rerouteReason, setRerouteReason,
  rerouteError, setRerouteError,
  // rescore
  rescoreNewPriority, setRescoreNewPriority,
  rescoreReason, setRescoreReason,
  rescoreError, setRescoreError,
  // resolve
  resolveReviewAction, setResolveReviewAction,
  resolutionSuggestion, suggestionBusy,
  finalResolution, setFinalResolution,
  stepsTaken, setStepsTaken,
  resolveError, setResolveError,
  resolveFiles, setResolveFiles,
  resolveBusy, setResolveBusy,
  // shared
  closeModal, loadTicket, uploadAttachmentsOrThrow, onSuccess,
}) {
  if (!type || !ticket) return null;

  const titles = {
    reroute: "Reroute Ticket",
    rescore: "Rescore Ticket",
    escalate: "Escalate Ticket",
    resolve: "Resolve Ticket",
  };

  const submitText =
    type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit";

  // ── Confirmation summary for reroute / rescore / resolve ──
  const renderConfirmation = () => {
    if (type === "reroute") {
      return (
        <div className="modal-confirm-body">
          <div className="modal-confirm-icon">↗</div>
          <p className="modal-confirm-heading">Confirm Reroute Request</p>
          <p className="modal-confirm-sub">
            Please review the details below before submitting. This will be sent for manager approval.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Department</span>
              <span className="modal-confirm-value">{rerouteDepartment}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Reason</span>
              <span className="modal-confirm-value modal-confirm-reason">{rerouteReason}</span>
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
            Please review the details below before submitting. This will be sent for manager approval.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Current Priority</span>
              <span className="modal-confirm-value">{ticket.priority ?? "—"}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Priority</span>
              <span className="modal-confirm-value">{rescoreNewPriority}</span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Reason</span>
              <span className="modal-confirm-value modal-confirm-reason">{rescoreReason}</span>
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
            Please review the details below before submitting. This action will mark the ticket as resolved.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Resolution Decision</span>
              <span className="modal-confirm-value">
                {resolveReviewAction === "accepted" ? "AI Suggestion Accepted" : "Custom Resolution"}
              </span>
            </div>
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">Final Resolution</span>
              <span className="modal-confirm-value modal-confirm-reason">{finalResolution || "—"}</span>
            </div>
            {resolveFiles.length > 0 && (
              <div className="modal-confirm-row">
                <span className="modal-confirm-label">Attachments</span>
                <span className="modal-confirm-value">{resolveFiles.length} file(s): {resolveFiles.map(f => f.name).join(", ")}</span>
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
                onChange={(e) => setRerouteDepartment(e.target.value)}
              >
                <option value="" disabled>Select Department</option>
                <option>Facilities Management</option>
                <option>Legal &amp; Compliance</option>
                <option>Safety &amp; Security</option>
                <option>HR</option>
                <option>Leasing</option>
                <option>Maintenance</option>
                <option>IT</option>
              </select>
            </div>
            <label>Reason for rerouting</label>
            <textarea
              className="modal-textarea"
              value={rerouteReason}
              onChange={(e) => { setRerouteReason(e.target.value); setRerouteError(""); }}
              placeholder="Explain why this ticket should be rerouted..."
            />
            {rerouteError && <div className="modal-inline-error">{rerouteError}</div>}
          </>
        );

      case "rescore":
        return (
          <>
            <label>New Priority</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={rescoreNewPriority}
                onChange={(e) => setRescoreNewPriority(e.target.value)}
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>
            <label>Reason for rescoring</label>
            <textarea
              className="modal-textarea"
              value={rescoreReason}
              onChange={(e) => { setRescoreReason(e.target.value); setRescoreError(""); }}
              placeholder="Explain why the model score should be adjusted..."
            />
            {rescoreError && <div className="modal-inline-error">{rescoreError}</div>}
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
            />
            <label>Additional Notes (optional)</label>
            <textarea className="modal-textarea" placeholder="Any extra context..." />
          </>
        );

      case "resolve":
        return (
          <>
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
                  setFinalResolution(next);
                  if ((resolutionSuggestion || "").trim() !== next.trim()) {
                    setResolveReviewAction("edited");
                  }
                }}
                placeholder={suggestionBusy ? "Generating..." : "No suggestion available."}
                disabled={suggestionBusy}
              />

              <div className="resolution-review-box__actions">
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--decline ${resolveReviewAction === "declined" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("declined")}
                  disabled={suggestionBusy}
                  aria-label="Decline suggestion"
                  title="Decline suggestion"
                >
                  ✕
                </button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--accept ${resolveReviewAction === "accepted" ? "is-active" : ""}`}
                  onClick={() => {
                    setResolveReviewAction("accepted");
                    setFinalResolution(resolutionSuggestion || "");
                  }}
                  disabled={suggestionBusy}
                  aria-label="Accept suggestion"
                  title="Accept suggestion"
                >
                  ✓
                </button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--edit ${resolveReviewAction === "edited" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("edited")}
                  disabled={suggestionBusy}
                  aria-label="Edit suggestion"
                  title="Edit suggestion"
                >
                  ✎
                </button>
              </div>
            </div>

            {resolveError && (
              <div style={{ color: "#b42318", marginTop: 8, whiteSpace: "pre-wrap" }}>
                {resolveError}
              </div>
            )}

            <label>Steps Taken <span className="modal-label-optional">optional</span></label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => setStepsTaken(e.target.value)}
              placeholder="List the steps taken to resolve this issue..."
              disabled={suggestionBusy}
            />

            <label>Attachments <span className="modal-label-optional">optional</span></label>
            <div className="modal-upload-box">
              <label className="modal-upload-box__label">
                <div className="modal-upload-box__inner">
                  <div className="modal-upload-box__icon-wrap">
                    <svg viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
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
                  onChange={(e) => setResolveFiles(prev => [...prev, ...Array.from(e.target.files || [])])}
                />
              </label>
              {resolveFiles.length > 0 && (
                <div className="modal-upload-box__files">
                  {resolveFiles.map((f, i) => (
                    <div key={i} className="modal-upload-box__file">
                      <div className="modal-upload-box__file-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                             strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
                          <path d="M14 2v6h6" />
                        </svg>
                      </div>
                      <div className="modal-upload-box__file-info">
                        <span className="modal-upload-box__file-name">{f.name}</span>
                        <span className="modal-upload-box__file-size">
                          {f.size < 1024 * 1024
                            ? `${Math.round(f.size / 1024)} KB`
                            : `${(f.size / (1024 * 1024)).toFixed(1)} MB`}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="modal-upload-box__remove"
                        onClick={() => setResolveFiles((prev) => prev.filter((_, j) => j !== i))}
                        disabled={resolveBusy}
                        aria-label="Remove file"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                             strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
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
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ new_priority: rescoreNewPriority, reason: rescoreReason.trim() }),
          }
        );
        if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
        setRescoreReason("");
        closeModal();
        onSuccess("Rescore request submitted for manager approval.");
      } catch (e) {
        setRescoreError(e?.message || "Failed to submit rescore request.");
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
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ new_department: rerouteDepartment, reason: rerouteReason.trim() }),
          }
        );
        if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
        setRerouteDepartment("");
        setRerouteReason("");
        closeModal();
        onSuccess("Reroute request submitted for manager approval.");
      } catch (e) {
        setRerouteError(e?.message || "Failed to submit reroute request.");
      }
      return;
    }

    if (type === "escalate") {
      closeModal();
      onSuccess("Escalate saved (UI only for now).");
      return;
    }

    // ── resolve ──
    const token = getAuthToken();
    if (!token) { setResolveError("Missing auth token. Please log in again."); return; }
    const suggestedTrimmed = (resolutionSuggestion || "").trim();
    const finalTrimmed = finalResolution.trim();

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
        final_resolution: decision === "declined_custom" ? finalTrimmed : undefined,
        steps_taken: stepsTaken.trim() || undefined,
      };

      const res = await fetch(
        `${API_BASE}/employee/tickets/${encodeURIComponent(id)}/resolve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) throw new Error((await res.text()) || `Failed to resolve ticket (${res.status})`);

      await loadTicket();
      setResolveFiles([]);
      setStepsTaken("");
      closeModal();
      onSuccess("Ticket resolved successfully.");
    } catch (e) {
      setResolveError(e?.message || "Could not resolve ticket.");
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
                {resolveBusy ? "Saving..." : type === "resolve" ? "Confirm & Resolve" : "Confirm & Submit"}
              </button>
            </>
          ) : (
            <>
              <button className="modal-btn cancel" onClick={closeModal}>Cancel</button>
              <button
                className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
                onClick={() => {
                  // reroute / rescore → show confirmation first
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
                  // all other types submit directly
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
  const { id } = useParams();
  const navigate = useNavigate();

  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalType, setModalType] = useState(null);

  // FIX (Issues 2 & 3): `confirming` is now owned by the parent so we can
  // reset it to false every time a modal is opened or closed. Previously this
  // lived inside TicketModal as local state, and since TicketModal never
  // unmounts (it just returns null when type is null), the stale `true` value
  // persisted across open/close cycles, causing the confirmation screen to
  // appear immediately on the next open.
  const [confirming, setConfirming] = useState(false);

  const [resolveReviewAction, setResolveReviewAction] = useState("accepted");
  const [resolutionSuggestion, setResolutionSuggestion] = useState("");
  const [finalResolution, setFinalResolution] = useState("");
  const [stepsTaken, setStepsTaken] = useState("");
  const [resolveBusy, setResolveBusy] = useState(false);
  const [resolveError, setResolveError] = useState("");
  const [resolveFiles, setResolveFiles] = useState([]);
  const suggestionBusy = false;

  const [rescoreNewPriority, setRescoreNewPriority] = useState("Medium");
  const [rescoreReason, setRescoreReason] = useState("");

  const [rerouteDepartment, setRerouteDepartment] = useState("");
  const [rerouteReason, setRerouteReason] = useState("");
  const [rerouteError, setRerouteError] = useState("");
  const [rescoreError, setRescoreError] = useState("");
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  // FIX (Issues 2 & 3): openModal always resets confirming to false so the
  // form is always shown first, regardless of what happened in a previous
  // modal session.
  const openModal = (type) => {
    setConfirming(false);
    setModalType(type);
  };

  const closeModal = () => {
    setModalType(null);
    // FIX (Issues 2 & 3): also reset confirming on close so next open is clean
    setConfirming(false);
    setRerouteError("");
    setRescoreError("");
  };

  useEffect(() => {
    if (modalType !== "resolve") return;
    const preGenerated = (ticket?.suggestedResolution || "").trim();
    setResolveReviewAction("accepted");
    setResolutionSuggestion(preGenerated);
    setFinalResolution(preGenerated);
    setResolveError("");
  }, [modalType, ticket]);

  const loadTicket = useCallback(async () => {
    const token = getAuthToken();
    if (!token) { setError("Missing auth token."); setLoading(false); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/employee/tickets/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
      const data = await res.json();
      setTicket(data?.ticket || null);
    } catch (e) {
      setError(e?.message || "Could not load ticket details.");
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
        { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd }
      );
      if (!upRes.ok) throw new Error((await upRes.text()) || `Upload failed (${upRes.status})`);
    }
  }

  if (loading) return <Layout role="employee"><div className="empTicketDetail">Loading ticket details...</div></Layout>;
  if (error) return <Layout role="employee"><div className="empTicketDetail">{error}</div></Layout>;
  if (!ticket) return null;

  // FIX (Issue 1): pass auth token to AttachmentThumb so it can include it
  // in the fetch-based blob download, which is required in cross-origin prod.
  const authToken = getAuthToken();

  return (
    <Layout role="employee">
      <div className="empTicketDetail">
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" onClick={() => navigate(-1)}>← Back</button>
            <h1 className="ticket-title">Ticket ID: {ticket.ticketId}</h1>
            <div className="status-row">
              <span className={`header-pill ${(ticket.priority || "").toLowerCase()}-pill`}>
                {ticket.priority}
              </span>
              <span className={`header-pill empStatusPill ${statusPillClass(ticket.status)}`}>{ticket.status}</span>
            </div>
          </div>

          <div className="header-actions">
            {/* FIX (Issues 2 & 3): use openModal() instead of setModalType() directly */}
            <button className="btn-outline" onClick={() => openModal("rescore")}>Rescore</button>
            <button className="btn-outline" onClick={() => openModal("reroute")}>Reroute</button>
            <button className="btn-primary" onClick={() => openModal("resolve")}>Resolve</button>
          </div>
        </div>

        <section className="card-section">
          <h2 className="section-title">Summary</h2>
          <div className="summary-grid">
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Issue Date:</div>
              <div>{ticket.issueDate || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Min Time To Respond:</div>
              <div>{ticket.metrics?.minTimeToRespond || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Min Time To Resolve:</div>
              <div>{ticket.metrics?.minTimeToResolve || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Submitted By:</div>
              <div>{ticket.submittedBy?.name || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Contact:</div>
              <div>{ticket.submittedBy?.contact || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Location:</div>
              <div>{ticket.submittedBy?.location || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Ticket Source:</div>
              <div>{formatTicketSource(ticket.ticketSource)}</div>
            </div>
          </div>
        </section>

        <section className="details-grid">
          <div className="card-section">
            <h2 className="section-title">Ticket Details</h2>
            <div className="subject">{ticket.description?.subject}</div>
            <p className="description">{ticket.description?.details}</p>

            {ticket.attachments?.length > 0 && (
              <div className="attachments">
                {ticket.attachments.map((att, i) => {
                  const fileName = att?.fileName ?? (typeof att === "string" ? att : "");
                  const rawUrl   = att?.fileUrl ?? null;
                  const fileUrl  = rawUrl
                    ? apiUrl(rawUrl)
                    : fileName ? apiUrl("/uploads/" + fileName) : null;
                  return (
                    <AttachmentThumb
                      key={i}
                      url={fileUrl}
                      fileName={fileName}
                      token={authToken}
                    />
                  );
                })}
              </div>
            )}
          </div>

          {ticket.stepsTaken?.length > 0 && (
            <div className="card-section">
              <h2 className="section-title">Steps Taken</h2>
              {ticket.stepsTaken.map((step) => (
                <div key={step.step} className="step">
                  <div className="step-title">Step {step.step}</div>
                  <div className="step-text">
                    Technician assigned: {step.technician}<br />
                    Time: {step.time}<br />
                    Notes: {step.notes}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

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
        rerouteDepartment={rerouteDepartment} setRerouteDepartment={setRerouteDepartment}
        rerouteReason={rerouteReason} setRerouteReason={setRerouteReason}
        rerouteError={rerouteError} setRerouteError={setRerouteError}
        rescoreNewPriority={rescoreNewPriority} setRescoreNewPriority={setRescoreNewPriority}
        rescoreReason={rescoreReason} setRescoreReason={setRescoreReason}
        rescoreError={rescoreError} setRescoreError={setRescoreError}
        resolveReviewAction={resolveReviewAction} setResolveReviewAction={setResolveReviewAction}
        resolutionSuggestion={resolutionSuggestion} suggestionBusy={suggestionBusy}
        finalResolution={finalResolution} setFinalResolution={setFinalResolution}
        stepsTaken={stepsTaken} setStepsTaken={setStepsTaken}
        resolveError={resolveError} setResolveError={setResolveError}
        resolveFiles={resolveFiles} setResolveFiles={setResolveFiles}
        resolveBusy={resolveBusy} setResolveBusy={setResolveBusy}
        closeModal={closeModal}
        loadTicket={loadTicket}
        uploadAttachmentsOrThrow={uploadAttachmentsOrThrow}
        onSuccess={showToast}
      />
    </Layout>
  );
}
