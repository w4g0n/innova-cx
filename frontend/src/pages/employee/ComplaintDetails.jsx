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

// ─── AttachmentThumb ────────────────────────────────────────────────────────
function AttachmentThumb({ url, fileName }) {
  const isImage = /\.(jpe?g|png|gif|webp|bmp|svg)$/i.test(fileName || "");
  const [imgError, setImgError] = useState(false);

  if (!url) return null;

  if (isImage && !imgError) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" title={fileName}
         style={{ display:"block", width:80, height:80, borderRadius:10,
                  overflow:"hidden", flexShrink:0,
                  border:"1px solid rgba(0,0,0,0.1)" }}>
        <img
          src={url}
          alt={fileName}
          style={{ width:"100%", height:"100%", objectFit:"cover" }}
          onError={() => setImgError(true)}
        />
      </a>
    );
  }

  return (
    <a href={url} download={fileName} target="_blank" rel="noopener noreferrer"
       className="attachment-thumb" title={fileName}
       style={{ display:"flex", flexDirection:"column", alignItems:"center",
                justifyContent:"center", width:80, height:80, fontSize:11,
                color:"#5b21b6", textDecoration:"none", wordBreak:"break-all",
                padding:4, textAlign:"center", background:"#f5f3ff",
                borderRadius:10, border:"1px solid rgba(89,36,180,0.15)",
                flexShrink:0 }}>
      <span style={{ fontSize:26 }}>{imgError ? "🖼️" : "📎"}</span>
      <span style={{ marginTop:4, lineHeight:1.2 }}>{fileName}</span>
    </a>
  );
}

// ─── Modal (outside ComplaintDetails so it never remounts on parent re-render)
function TicketModal({
  type, ticket, id,
  // reroute
  rerouteDepartment, setRerouteDepartment,
  rerouteReason, setRerouteReason,
  rerouteError, setRerouteError,
  // rescore
  rescoreNewPriority, setRescoreNewPriority,
  rescoreReason, setRescoreReason,
  rescoreError, setRescoreError,
  // resolve
  resolveDecision, setResolveDecision,
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
                <option>Maintenance</option>
                <option>IT Support</option>
                <option>Cleaning</option>
                <option>Security</option>
                <option>Facilities</option>
                <option>HR</option>
                <option>Admin</option>
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
            <label>Model Suggested Resolution (Falcon)</label>
            <div className="model-suggestion">
              {suggestionBusy ? "Generating..." : (resolutionSuggestion || "No suggestion available.")}
            </div>

            <label>Resolution Decision</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={resolveDecision}
                onChange={(e) => {
                  const next = e.target.value;
                  setResolveDecision(next);
                  if (next === "accepted") setFinalResolution(resolutionSuggestion || "");
                }}
              >
                <option value="accepted">Accept Suggested Resolution</option>
                <option value="declined_custom">Decline and Write My Own</option>
              </select>
            </div>

            <label>Final Resolution</label>
            <textarea
              className="modal-textarea"
              value={finalResolution}
              onChange={(e) => setFinalResolution(e.target.value)}
              placeholder="Describe the final resolution provided..."
              disabled={resolveDecision === "accepted"}
            />

            <label>Steps Taken to Resolve</label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => setStepsTaken(e.target.value)}
              placeholder="List the steps taken to resolve this issue..."
            />

            {resolveError && (
              <div style={{ color: "#b42318", marginTop: 8, whiteSpace: "pre-wrap" }}>
                {resolveError}
              </div>
            )}

            <label>Attachments (optional)</label>
            <div className="modal-upload-box">
              <input
                type="file"
                multiple
                onChange={(e) => setResolveFiles(Array.from(e.target.files || []))}
              />
              {resolveFiles.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 13, color: "#5b21b6" }}>
                  {resolveFiles.length} file(s) selected: {resolveFiles.map((f) => f.name).join(", ")}
                </div>
              )}
            </div>

            {resolveFiles.length > 0 && (
              <button
                type="button"
                className="modal-btn cancel"
                style={{ marginTop: 10 }}
                onClick={() => setResolveFiles([])}
                disabled={resolveBusy || suggestionBusy}
              >
                Clear selected files
              </button>
            )}
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
    if (resolveDecision === "declined_custom" && !finalResolution.trim()) {
      setResolveError("Final Resolution is required when declining suggestion.");
      return;
    }

    setResolveBusy(true);
    setResolveError("");
    try {
      await uploadAttachmentsOrThrow({ ticketCode: id, token, files: resolveFiles });

      const payload = {
        decision: resolveDecision,
        final_resolution: resolveDecision === "declined_custom" ? finalResolution.trim() : undefined,
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
        className={`modal-card ${type === "escalate" ? "modal-red" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>{titles[type]}</h2>
          <span className="modal-close" onClick={closeModal}>✕</span>
        </div>

        <div className="modal-body">{renderBody()}</div>

        <div className="modal-footer">
          <button className="modal-btn cancel" onClick={closeModal}>Cancel</button>
          <button
            className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
            onClick={handleSubmit}
            disabled={resolveBusy || suggestionBusy}
          >
            {resolveBusy ? "Saving..." : submitText}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────
export default function ComplaintDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalType, setModalType] = useState(null);

  const [resolveDecision, setResolveDecision] = useState("accepted");
  const [resolutionSuggestion, setResolutionSuggestion] = useState("");
  const [finalResolution, setFinalResolution] = useState("");
  const [stepsTaken, setStepsTaken] = useState("");
  const [resolveBusy, setResolveBusy] = useState(false);
  const [resolveError, setResolveError] = useState("");
  const [resolveFiles, setResolveFiles] = useState([]);
  const [suggestionBusy, setSuggestionBusy] = useState(false);

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

  const closeModal = () => {
    setModalType(null);
    setRerouteError("");
    setRescoreError("");
  };

  useEffect(() => {
    if (modalType !== "resolve") return;
    setResolveDecision("accepted");
    setFinalResolution("");
    setStepsTaken("");
    setResolveError("");
  }, [modalType]);

  useEffect(() => {
    async function loadSuggestion() {
      if (modalType !== "resolve" || !id) return;
      const token = getAuthToken();
      if (!token) return;
      setResolveError("");
      setSuggestionBusy(true);
      try {
        const res = await fetch(
          `${API_BASE}/employee/tickets/${encodeURIComponent(id)}/resolution-suggestion`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
        const data = await res.json();
        const suggestion = (data?.suggestedResolution || "").trim();
        setResolutionSuggestion(suggestion);
        setFinalResolution(suggestion);
      } catch (e) {
        setResolveError(e?.message || "Could not fetch suggested resolution.");
      } finally {
        setSuggestionBusy(false);
      }
    }
    loadSuggestion();
  }, [modalType, id]);

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
              <span className="header-pill empStatusPill">{ticket.status}</span>
            </div>
          </div>

          <div className="header-actions">
            <button className="btn-outline" onClick={() => setModalType("rescore")}>Rescore</button>
            <button className="btn-outline" onClick={() => setModalType("reroute")}>Reroute</button>
            <button className="btn-primary" onClick={() => setModalType("resolve")}>Resolve</button>
          </div>
        </div>

        <section className="card-section">
          <h2 className="section-title">Summary</h2>
          <div className="summary-grid">
            <div><span className="label">Issue Date:</span> {ticket.issueDate}</div>
            <div><span className="label">Mean Time To Respond:</span> {ticket.metrics?.meanTimeToRespond}</div>
            <div><span className="label">Mean Time To Resolve:</span> {ticket.metrics?.meanTimeToResolve}</div>
            <div><span className="label">Submitted By:</span> {ticket.submittedBy?.name}</div>
            <div><span className="label">Contact:</span> {ticket.submittedBy?.contact}</div>
            <div><span className="label">Location:</span> {ticket.submittedBy?.location}</div>
            <div><span className="label">Description:</span> {ticket.description?.details}</div>
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
                  return <AttachmentThumb key={i} url={fileUrl} fileName={fileName} />;
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
        rerouteDepartment={rerouteDepartment} setRerouteDepartment={setRerouteDepartment}
        rerouteReason={rerouteReason} setRerouteReason={setRerouteReason}
        rerouteError={rerouteError} setRerouteError={setRerouteError}
        rescoreNewPriority={rescoreNewPriority} setRescoreNewPriority={setRescoreNewPriority}
        rescoreReason={rescoreReason} setRescoreReason={setRescoreReason}
        rescoreError={rescoreError} setRescoreError={setRescoreError}
        resolveDecision={resolveDecision} setResolveDecision={setResolveDecision}
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
