import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import {
  sanitizeText,
  sanitizeId,
  sanitizePriority,
  MAX_REASON_LEN,
  MAX_RESOLUTION_LEN,
  ALLOWED_PRIORITIES,
} from "./ManagerSanitize";
import { apiUrl } from "../../config/apiBase";
import "../employee/TicketDetails.css";

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

function ManagerTicketModal({
  type,
  ticket,
  closeModal,
  onRerouteSuccess,
  onRescoreSuccess,
  onResolveSuccess,
  onSuccess,
}) {
  if (!type || !ticket) return null;

  return (
    <ManagerTicketModalInner
      key={type}
      type={type}
      ticket={ticket}
      closeModal={closeModal}
      onRerouteSuccess={onRerouteSuccess}
      onRescoreSuccess={onRescoreSuccess}
      onResolveSuccess={onResolveSuccess}
      onSuccess={onSuccess}
    />
  );
}

function ManagerTicketModalInner({
  type,
  ticket,
  closeModal,
  onRerouteSuccess,
  onRescoreSuccess,
  onResolveSuccess,
  onSuccess,
}) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Reroute
  const [departments, setDepartments] = useState([]);
  const [selectedDept, setSelectedDept] = useState("");
  const [rerouteReason, setRerouteReason] = useState("");
  const [rerouteError, setRerouteError] = useState("");

  // Rescore
  const [selectedPriority, setSelectedPriority] = useState(
    ticket.priorityText || ticket.priority || "Medium"
  );
  const [rescoreReason, setRescoreReason] = useState("");
  const [rescoreError, setRescoreError] = useState("");

  // Escalate
  const [escalateLevel, setEscalateLevel] = useState("");
  const [escalateReason, setEscalateReason] = useState("");

  // Resolve
  const [resolution, setResolution] = useState("");
  const [stepsTaken, setStepsTaken] = useState("");
  const [resolveError, setResolveError] = useState("");
  const [resolveReviewAction, setResolveReviewAction] = useState("accepted");
  const [resolveFiles, setResolveFiles] = useState([]);

  useEffect(() => {
    if (type !== "reroute") return;
    const token = getAuthToken();

    fetch(apiUrl("/api/manager/departments"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setDepartments(list);
        if (ticket.department && list.includes(ticket.department)) {
          setSelectedDept(ticket.department);
        }
      })
      .catch(() => setDepartments([]));
  }, [type, ticket.department]);

  const titles = {
    reroute: "Reroute Ticket",
    rescore: "Rescore Ticket",
    escalate: "Escalate Ticket",
    resolve: "Resolve Ticket",
  };

  const handleRerouteSubmit = async () => {
    setBusy(true);
    setRerouteError("");
    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/api/manager/complaints/${ticket.id}/department`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ department: sanitizeText(selectedDept, 100), reason: sanitizeText(rerouteReason, MAX_REASON_LEN) }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onRerouteSuccess?.(selectedDept);
      onSuccess?.("Ticket rerouted successfully.");
      closeModal();
    } catch (e) {
      setRerouteError("Failed to reroute ticket. Please try again.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  };

  const handleRescoreSubmit = async () => {
    setBusy(true);
    setRescoreError("");
    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/api/manager/complaints/${ticket.id}/priority`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          new_priority: sanitizePriority(selectedPriority),
          reason: sanitizeText(rescoreReason, MAX_REASON_LEN),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onRescoreSuccess?.(selectedPriority);
      onSuccess?.("Priority updated successfully.");
      closeModal();
    } catch (e) {
      setRescoreError("Failed to update priority. Please try again.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  };

  const handleResolveSubmit = async () => {
    setBusy(true);
    setResolveError("");
    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/api/manager/complaints/${ticket.id}/resolve`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          final_resolution: sanitizeText(resolution, MAX_RESOLUTION_LEN),
          steps_taken: sanitizeText(stepsTaken, MAX_REASON_LEN) || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onResolveSuccess?.();
      onSuccess?.("Ticket resolved successfully.");
      setResolveFiles([]);
      setResolveReviewAction("accepted");
      closeModal();
    } catch (e) {
      setResolveError("Failed to resolve ticket. Please try again.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = () => {
    if (type === "reroute") return handleRerouteSubmit();
    if (type === "rescore") return handleRescoreSubmit();
    if (type === "resolve") return handleResolveSubmit();
    if (type === "escalate") {
      onSuccess?.(
        `Escalation submitted${escalateLevel ? ` to ${escalateLevel}` : ""}${
          escalateReason ? "." : " (no reason provided)."
        }`
      );
      closeModal();
    }
  };

  // Confirmation screen — mirrors employee's renderConfirmation pattern
  const renderConfirmation = () => {
    if (type === "reroute") {
      return (
        <div className="modal-confirm-body">
          <div className="modal-confirm-icon">↗</div>
          <p className="modal-confirm-heading">Confirm Reroute</p>
          <p className="modal-confirm-sub">
            Review the details below before submitting. This will take effect immediately.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Department</span>
              <span className="modal-confirm-value">{selectedDept}</span>
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
          <p className="modal-confirm-heading">Confirm Rescore</p>
          <p className="modal-confirm-sub">
            Review the details below before submitting. This will take effect immediately.
          </p>
          <div className="modal-confirm-rows">
            <div className="modal-confirm-row">
              <span className="modal-confirm-label">New Priority</span>
              <span className="modal-confirm-value">{selectedPriority}</span>
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
              <span className="modal-confirm-label">Final Resolution</span>
              <span className="modal-confirm-value modal-confirm-reason">{resolution}</span>
            </div>
            {stepsTaken.trim() && (
              <div className="modal-confirm-row">
                <span className="modal-confirm-label">Steps Taken</span>
                <span className="modal-confirm-value modal-confirm-reason">{stepsTaken}</span>
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
                value={selectedDept}
                onChange={(e) => {
                  setSelectedDept(e.target.value);
                  setRerouteError("");
                }}
              >
                <option value="" disabled>
                  Select Department
                </option>
                {departments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                    {d === ticket.department ? " (current)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <label>Reason for rerouting</label>
            <textarea
              className="modal-textarea"
              value={rerouteReason}
              onChange={(e) => {
                setRerouteReason(e.target.value.slice(0, MAX_REASON_LEN));
                setRerouteError("");
              }}
              placeholder="Explain why this ticket should be rerouted..."
              maxLength={MAX_REASON_LEN}
            />
            <div style={{ fontSize: 11, color: "rgba(17,17,17,0.4)", textAlign: "right" }}>
              {rerouteReason.length}/{MAX_REASON_LEN}
            </div>

            {rerouteError && <div className="modal-inline-error">{rerouteError}</div>}
          </>
        );

      case "rescore":
        return (
          <>
            <label>New Priority</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={selectedPriority}
                onChange={(e) => {
                  setSelectedPriority(sanitizePriority(e.target.value));
                  setRescoreError("");
                }}
              >
                {ALLOWED_PRIORITIES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            <label>Reason for rescoring</label>
            <textarea
              className="modal-textarea"
              value={rescoreReason}
              onChange={(e) => {
                setRescoreReason(e.target.value.slice(0, MAX_REASON_LEN));
                setRescoreError("");
              }}
              placeholder="Explain why the priority should be adjusted..."
              maxLength={MAX_REASON_LEN}
            />
            <div style={{ fontSize: 11, color: "rgba(17,17,17,0.4)", textAlign: "right" }}>
              {rescoreReason.length}/{MAX_REASON_LEN}
            </div>

            {rescoreError && <div className="modal-inline-error">{rescoreError}</div>}
          </>
        );

      case "escalate":
        return (
          <>
            <label>Escalation Level</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={escalateLevel}
                onChange={(e) => setEscalateLevel(e.target.value)}
              >
                <option value="" disabled>
                  Select Level
                </option>
                <option>Supervisor</option>
                <option>Department Head</option>
                <option>Management</option>
              </select>
            </div>

            <label>Reason for Escalation</label>
            <textarea
              className="modal-textarea"
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value.slice(0, MAX_REASON_LEN))}
              placeholder="Explain why this ticket must be escalated..."
              maxLength={MAX_REASON_LEN}
            />
          </>
        );

      case "resolve":
        return (
          <>
            <label>Suggested Resolution</label>
            <div className="resolution-review-box">
              <div className="resolution-review-box__hint">
                Describe the final resolution provided for this ticket.
              </div>
              <textarea
                className="modal-textarea resolution-review-box__textarea"
                value={resolution}
                onChange={(e) => {
                  setResolution(e.target.value.slice(0, MAX_RESOLUTION_LEN));
                  setResolveError("");
                }}
                placeholder="Describe the final resolution provided..."
                maxLength={MAX_RESOLUTION_LEN}
              />
              <div style={{ fontSize: 11, color: "rgba(17,17,17,0.4)", textAlign: "right", marginTop: 2 }}>
                {resolution.length}/{MAX_RESOLUTION_LEN}
              </div>
              <div className="resolution-review-box__actions">
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--decline ${resolveReviewAction === "declined" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("declined")}
                  aria-label="Decline"
                  title="Decline"
                >
                  ✕
                </button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--accept ${resolveReviewAction === "accepted" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("accepted")}
                  aria-label="Accept"
                  title="Accept"
                >
                  ✓
                </button>
                <button
                  type="button"
                  className={`resolution-icon-btn resolution-icon-btn--edit ${resolveReviewAction === "edited" ? "is-active" : ""}`}
                  onClick={() => setResolveReviewAction("edited")}
                  aria-label="Edit"
                  title="Edit"
                >
                  ✎
                </button>
              </div>
              {resolveError && (
                <div style={{ color: "#b42318", marginTop: 8, whiteSpace: "pre-wrap" }}>
                  {resolveError}
                </div>
              )}
            </div>

            <label>Steps Taken <span className="modal-label-optional">optional</span></label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => setStepsTaken(e.target.value.slice(0, MAX_REASON_LEN))}
              placeholder="List the steps taken to resolve this issue..."
              maxLength={MAX_REASON_LEN}
            />
            <div style={{ fontSize: 11, color: "rgba(17,17,17,0.4)", textAlign: "right" }}>
              {stepsTaken.length}/{MAX_REASON_LEN}
            </div>

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
                        disabled={busy}
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

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div
        className={`modal-card ${type === "escalate" ? "modal-red" : ""} ${type === "resolve" ? "modal-card--resolve" : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <h2>{titles[type]}</h2>
          <span className="modal-close" onClick={closeModal} role="button" tabIndex={0}>
            ✕
          </span>
        </div>

        <div className="modal-body">
          {confirming ? renderConfirmation() : renderBody()}
        </div>

        <div className="modal-footer">
          {confirming ? (
            <>
              <button
                className="modal-btn cancel"
                type="button"
                onClick={() => setConfirming(false)}
                disabled={busy}
              >
                ← Back
              </button>
              <button
                className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
                type="button"
                onClick={handleSubmit}
                disabled={busy}
              >
                {busy ? "Saving..." : type === "resolve" ? "Confirm & Resolve" : "Confirm & Submit"}
              </button>
            </>
          ) : (
            <>
              <button
                className="modal-btn cancel"
                type="button"
                onClick={closeModal}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
                type="button"
                onClick={() => {
                  if (type === "reroute") {
                    if (!selectedDept) { setRerouteError("Please select a department."); return; }
                    if (!rerouteReason.trim()) { setRerouteError("Please provide a reason for rerouting."); return; }
                    setRerouteError("");
                    setConfirming(true);
                    return;
                  }
                  if (type === "rescore") {
                    if (!rescoreReason.trim()) { setRescoreError("Please provide a reason for rescoring."); return; }
                    setRescoreError("");
                    setConfirming(true);
                    return;
                  }
                  if (type === "resolve") {
                    if (!resolution.trim()) { setResolveError("Please provide a resolution description."); return; }
                    setResolveError("");
                    setConfirming(true);
                    return;
                  }
                  handleSubmit();
                }}
                disabled={busy}
              >
                {busy ? "Saving..." : type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ManagerComplaintDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalType, setModalType] = useState(null);
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });

  const closeModal = () => setModalType(null);

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  const handleRerouteSuccess = (newDepartment) => {
    setTicket((prev) => ({ ...prev, department: newDepartment }));
  };

  const handleRescoreSuccess = (newPriority) => {
    const priorityText = newPriority;
    const priorityRaw = String(newPriority).toLowerCase();
    setTicket((prev) => ({ ...prev, priority: priorityRaw, priorityText }));
  };

  const handleResolveSuccess = async () => {
    // Reload full ticket so steps_taken and final_resolution are reflected in UI
    const token = getAuthToken();
    try {
      const res = await fetch(apiUrl(`/api/manager/complaints/${id}`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (!data.error) { setTicket(data); return; }
      }
    } catch {
      // fall through to local update
    }
    setTicket((prev) => ({ ...prev, status: "Resolved" }));
  };

  useEffect(() => {
    const token = getAuthToken();

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(apiUrl(`/api/manager/complaints/${id}`), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Ticket not found");
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        setTicket({
          ...data,
          ticket_code:     sanitizeId(data.ticket_code || data.id),
          subject:         sanitizeText(data.subject, 300),
          status:          sanitizeText(data.status, 50),
          priorityText:    sanitizePriority(data.priorityText || data.priority),
          priority:        sanitizeText(data.priority, 50),
          department:      sanitizeText(data.department, 100),
          assignee:        sanitizeText(data.assignee, 100),
          submittedBy:     sanitizeText(data.submittedBy, 100),
          issueDate:       sanitizeText(data.issueDate, 50),
          respondTime:     sanitizeText(data.respondTime, 50),
          resolveTime:     sanitizeText(data.resolveTime, 50),
          details:         sanitizeText(data.details || data.description, 5000),
          description:     sanitizeText(data.description, 5000),
          finalResolution: sanitizeText(data.finalResolution, 5000),
        });
      } catch (e) {
        setError("Failed to load ticket details. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [id]);

  if (loading) {
    return (
      <Layout role="manager">
        <div className="empTicketDetail">Loading ticket details…</div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout role="manager">
        <div className="empTicketDetail">{error}</div>
      </Layout>
    );
  }

  if (!ticket) return null;

  const priorityText = ticket.priorityText || ticket.priority || "Medium";

  return (
    <Layout role="manager">
      <div className="empTicketDetail">
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" type="button" onClick={() => navigate(-1)}>
              ← Back
            </button>
            <h1 className="ticket-title">Ticket ID: {ticket.ticket_code || ticket.id}</h1>
            <div className="status-row">
              <span className={`header-pill ${String(priorityText).toLowerCase()}-pill`}>
                {priorityText}
              </span>
              <span className="header-pill empStatusPill">{ticket.status}</span>
            </div>
          </div>

          <div className="header-actions">
            <button className="btn-outline" type="button" onClick={() => setModalType("rescore")}>
              Rescore
            </button>
            <button className="btn-outline" type="button" onClick={() => setModalType("reroute")}>
              Reroute
            </button>
            <button className="btn-primary" type="button" onClick={() => setModalType("resolve")}>
              Resolve
            </button>
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
              <div>{ticket.respondTime || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Min Time To Resolve:</div>
              <div>{ticket.resolveTime || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Assignee:</div>
              <div>{ticket.assignee || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Department:</div>
              <div>{ticket.department || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Submitted By:</div>
              <div>{ticket.submittedBy || "—"}</div>
            </div>
            <div>
              <div className="label" style={{display:"block",color:"#374151",fontSize:"11px",fontWeight:700,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:3}}>Ticket Source:</div>
              <div>{formatTicketSource(ticket.ticketSource)}</div>
            </div>
          </div>
        </section>

        <section className="details-grid">
          <div className="card-section">
            <h2 className="section-title">Complaint Details</h2>
            <div className="subject">{ticket.subject || "No subject"}</div>
            <p className="description">
              {ticket.details || ticket.description || "No details provided."}
            </p>
          </div>

          <div className="card-section">
            <h2 className="section-title">Activity</h2>
            <div className="timeline">
              <div className="timeline-item">
                <div className="dot" />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>
                    Ticket created
                  </div>
                  <div style={{ color: "rgba(17,17,17,0.55)", fontSize: 12 }}>
                    {ticket.issueDate || "—"}
                  </div>
                </div>
              </div>

              <div className="timeline-item">
                <div className="dot" />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>
                    Current status
                  </div>
                  <div style={{ color: "rgba(17,17,17,0.55)", fontSize: 12 }}>
                    {ticket.status || "—"}
                  </div>
                </div>
              </div>

              {ticket.respondTime && (
                <div className="timeline-item">
                  <div className="dot" />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2 }}>
                      First response
                    </div>
                    <div style={{ color: "rgba(17,17,17,0.55)", fontSize: 12 }}>
                      {ticket.respondTime}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {ticket.finalResolution && (
          <section className="card-section">
            <h2 className="section-title">Final Resolution</h2>
            <p className="description">{ticket.finalResolution}</p>
          </section>
        )}

        {ticket.stepsTaken?.length > 0 && (
          <section className="card-section">
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

      <ManagerTicketModal
        type={modalType}
        ticket={ticket}
        closeModal={closeModal}
        onRerouteSuccess={handleRerouteSuccess}
        onRescoreSuccess={handleRescoreSuccess}
        onResolveSuccess={handleResolveSuccess}
        onSuccess={showToast}
      />
    </Layout>
  );
}