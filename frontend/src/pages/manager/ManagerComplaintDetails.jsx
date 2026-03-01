import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
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

// ─── Modal ────────────────────────────────────────────────────────────────────
function ManagerTicketModal({ type, ticket, closeModal, onSuccess }) {
  if (!type || !ticket) return null;

  return (
    <ManagerTicketModalInner
      key={type}
      type={type}
      ticket={ticket}
      closeModal={closeModal}
      onSuccess={onSuccess}
    />
  );
}

function ManagerTicketModalInner({ type, ticket, closeModal, onSuccess }) {
  // Controlled fields
  const [department, setDepartment] = useState("");
  const [rerouteReason, setRerouteReason] = useState("");
  const [rerouteError, setRerouteError] = useState("");

  const [priority, setPriority] = useState(ticket.priorityText || ticket.priority || "Medium");
  const [rescoreReason, setRescoreReason] = useState("");
  const [rescoreError, setRescoreError] = useState("");

  const [escalateLevel, setEscalateLevel] = useState("");
  const [escalateReason, setEscalateReason] = useState("");

  const [resolution, setResolution] = useState("");
  const [stepsTaken, setStepsTaken] = useState("");
  const [resolveError, setResolveError] = useState("");

  const [busy, setBusy] = useState(false);

  const titles = {
    reroute: "Reroute Ticket",
    rescore: "Rescore Ticket",
    escalate: "Escalate Ticket",
    resolve: "Resolve Ticket",
  };

  const submitText =
    type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit";

  const handleSubmit = async () => {
    const token = getAuthToken();

    // ── Reroute ──
    if (type === "reroute") {
      if (!department || !rerouteReason.trim()) {
        setRerouteError("Please select a department and provide a reason.");
        return;
      }
      setBusy(true);
      try {
        const res = await fetch(
          apiUrl(`/manager/complaints/${ticket.id || ticket.ticket_code}/reroute`),
          {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ new_department: department, reason: rerouteReason.trim() }),
          }
        );
        if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
        closeModal();
        onSuccess("Reroute request submitted successfully.");
      } catch (e) {
        setRerouteError(e?.message || "Failed to submit reroute request.");
      } finally {
        setBusy(false);
      }
      return;
    }

    // ── Rescore ──
    if (type === "rescore") {
      if (!priority || !rescoreReason.trim()) {
        setRescoreError("Please select a priority and provide a reason.");
        return;
      }
      setBusy(true);
      try {
        const res = await fetch(
          apiUrl(`/manager/complaints/${ticket.id || ticket.ticket_code}/rescore`),
          {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ new_priority: priority, reason: rescoreReason.trim() }),
          }
        );
        if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
        closeModal();
        onSuccess("Rescore request submitted successfully.");
      } catch (e) {
        setRescoreError(e?.message || "Failed to submit rescore request.");
      } finally {
        setBusy(false);
      }
      return;
    }

    // ── Escalate (UI only) ──
    if (type === "escalate") {
      closeModal();
      onSuccess("Escalation submitted.");
      return;
    }

    // ── Resolve ──
    if (!resolution.trim()) {
      setResolveError("Please describe the resolution.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(
        apiUrl(`/manager/complaints/${ticket.id || ticket.ticket_code}/resolve`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            final_resolution: resolution.trim(),
            steps_taken: stepsTaken.trim() || undefined,
          }),
        }
      );
      if (!res.ok) throw new Error((await res.text()) || `Failed (${res.status})`);
      closeModal();
      onSuccess("Ticket resolved successfully.");
    } catch (e) {
      setResolveError(e?.message || "Failed to resolve ticket.");
    } finally {
      setBusy(false);
    }
  };

  const renderBody = () => {
    switch (type) {
      case "reroute":
        return (
          <>
            <label>New Department</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={department}
                onChange={(e) => { setDepartment(e.target.value); setRerouteError(""); }}
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
                value={priority}
                onChange={(e) => { setPriority(e.target.value); setRescoreError(""); }}
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
              placeholder="Explain why the priority should be adjusted..."
            />
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
                <option value="" disabled>Select Level</option>
                <option>Supervisor</option>
                <option>Department Head</option>
                <option>Management</option>
              </select>
            </div>
            <label>Reason for Escalation</label>
            <textarea
              className="modal-textarea"
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value)}
              placeholder="Explain why this ticket must be escalated..."
            />
            <label>Additional Notes (optional)</label>
            <textarea className="modal-textarea" placeholder="Any extra context..." />
          </>
        );

      case "resolve":
        return (
          <>
            <label>Resolution</label>
            <textarea
              className="modal-textarea"
              value={resolution}
              onChange={(e) => { setResolution(e.target.value); setResolveError(""); }}
              placeholder="Describe the final resolution provided..."
            />
            <label>Steps Taken</label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => setStepsTaken(e.target.value)}
              placeholder="List the steps taken to resolve this issue..."
            />
            {resolveError && <div className="modal-inline-error">{resolveError}</div>}
            <label>Attachments (optional)</label>
            <div className="modal-upload-box">
              <input type="file" multiple />
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
        className={`modal-card ${type === "escalate" ? "modal-red" : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <h2>{titles[type]}</h2>
          <span className="modal-close" onClick={closeModal} role="button" tabIndex={0}>✕</span>
        </div>

        <div className="modal-body">{renderBody()}</div>

        <div className="modal-footer">
          <button className="modal-btn cancel" type="button" onClick={closeModal} disabled={busy}>
            Cancel
          </button>
          <button
            className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
            type="button"
            onClick={handleSubmit}
            disabled={busy}
          >
            {busy ? "Saving…" : submitText}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────
export default function ManagerComplaintDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [ticket, setTicket] = useState(location.state?.ticket || null);
  const [loading, setLoading] = useState(!location.state?.ticket);
  const [error, setError] = useState(null);
  const [modalType, setModalType] = useState(null);
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });

  const closeModal = () => setModalType(null);

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  useEffect(() => {
    if (ticket) return;
    const token = getAuthToken();
    fetch(apiUrl(`/manager/complaints/${id}`), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Ticket not found");
        return res.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setTicket(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "Could not load ticket details.");
        setLoading(false);
      });
  }, [id, ticket]);

  if (loading)
    return (
      <Layout role="manager">
        <div className="empTicketDetail">Loading ticket details…</div>
      </Layout>
    );

  if (error)
    return (
      <Layout role="manager">
        <div className="empTicketDetail">{error}</div>
      </Layout>
    );

  if (!ticket) return null;

  const priorityText = ticket.priorityText || ticket.priority || "Medium";

  return (
    <Layout role="manager">
      <div className="empTicketDetail">

        {/* ── Header ── */}
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" type="button" onClick={() => navigate(-1)}>
              ← Back
            </button>
            <h1 className="ticket-title">
              Ticket ID: {ticket.ticket_code || ticket.id}
            </h1>
            <div className="status-row">
              <span className={`header-pill ${priorityText.toLowerCase()}-pill`}>
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

        {/* ── Summary ── */}
        <section className="card-section">
          <h2 className="section-title">Summary</h2>
          <div className="summary-grid">
            <div>
              <span className="label">Issue Date</span>
              {ticket.issueDate || "—"}
            </div>
            <div>
              <span className="label">Response Time</span>
              {ticket.respondTime || "—"}
            </div>
            <div>
              <span className="label">Resolve Time</span>
              {ticket.resolveTime || "—"}
            </div>
            <div>
              <span className="label">Assignee</span>
              {ticket.assignee || "—"}
            </div>
            <div>
              <span className="label">Submitted By</span>
              {ticket.submittedBy || "—"}
            </div>
            <div>
              <span className="label">Department</span>
              {ticket.department || "—"}
            </div>
          </div>
        </section>

        {/* ── Details + Activity ── */}
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
      </div>

      {/* ── Toast ── */}
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
        onSuccess={showToast}
      />
    </Layout>
  );
}
