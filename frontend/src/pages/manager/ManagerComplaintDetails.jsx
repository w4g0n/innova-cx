import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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

  useEffect(() => {
    if (type !== "reroute") return;
    const token = getAuthToken();

    fetch(apiUrl("/manager/departments"), {
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

  const submitText =
    type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit";

  const handleRerouteSubmit = async () => {
    if (!selectedDept) {
      setRerouteError("Please select a department.");
      return;
    }
    if (!rerouteReason.trim()) {
      setRerouteError("Please provide a reason for rerouting.");
      return;
    }

    setBusy(true);
    setRerouteError("");

    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/department`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ department: selectedDept, reason: rerouteReason.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      onRerouteSuccess?.(selectedDept);
      onSuccess?.("Reroute request submitted successfully.");
      closeModal();
    } catch (e) {
      setRerouteError(e.message || "Failed to reroute ticket.");
    } finally {
      setBusy(false);
    }
  };

  const handleRescoreSubmit = async () => {
    if (!rescoreReason.trim()) {
      setRescoreError("Please provide a reason for rescoring.");
      return;
    }

    setBusy(true);
    setRescoreError("");

    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/priority`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          new_priority: selectedPriority,
          reason: rescoreReason.trim(),
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      onRescoreSuccess?.(selectedPriority);
      onSuccess?.("Rescore request submitted successfully.");
      closeModal();
    } catch (e) {
      setRescoreError(e.message || "Failed to rescore ticket.");
    } finally {
      setBusy(false);
    }
  };

  const handleResolveSubmit = async () => {
    if (!resolution.trim()) {
      setResolveError("Please provide a resolution description.");
      return;
    }

    setBusy(true);
    setResolveError("");

    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/resolve`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          final_resolution: resolution.trim(),
          steps_taken: stepsTaken.trim() || null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      onResolveSuccess?.();
      onSuccess?.("Ticket resolved successfully.");
      closeModal();
    } catch (e) {
      setResolveError(e.message || "Failed to resolve ticket.");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = () => {
    if (type === "reroute") return handleRerouteSubmit();
    if (type === "rescore") return handleRescoreSubmit();
    if (type === "resolve") return handleResolveSubmit();

    // Escalate placeholder (if backend endpoint not implemented yet)
    if (type === "escalate") {
      onSuccess?.(
        `Escalation submitted${escalateLevel ? ` to ${escalateLevel}` : ""}${
          escalateReason ? "." : " (no reason provided)."
        }`
      );
      closeModal();
    }
  };

  const renderBody = () => {
    switch (type) {
      case "reroute":
        return (
          <>
            <label className="mvd-modalLabel">New Department</label>
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

            <label className="mvd-modalLabel">Reason for rerouting</label>
            <textarea
              className="modal-textarea"
              value={rerouteReason}
              onChange={(e) => {
                setRerouteReason(e.target.value);
                setRerouteError("");
              }}
              placeholder="Explain why this ticket should be rerouted..."
            />

            {rerouteError && <div className="modal-inline-error">{rerouteError}</div>}
          </>
        );

      case "rescore":
        return (
          <>
            <label className="mvd-modalLabel">New Priority</label>
            <div className="select-wrapper modal-dropdown">
              <select
                value={selectedPriority}
                onChange={(e) => {
                  setSelectedPriority(e.target.value);
                  setRescoreError("");
                }}
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>

            <label className="mvd-modalLabel">Reason for rescoring</label>
            <textarea
              className="modal-textarea"
              value={rescoreReason}
              onChange={(e) => {
                setRescoreReason(e.target.value);
                setRescoreError("");
              }}
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
              onChange={(e) => setEscalateReason(e.target.value)}
              placeholder="Explain why this ticket must be escalated..."
            />
          </>
        );

      case "resolve":
        return (
          <>
            <label className="mvd-modalLabel">
              Resolution <span style={{ color: "red" }}>*</span>
            </label>
            <textarea
              className="modal-textarea"
              value={resolution}
              onChange={(e) => {
                setResolution(e.target.value);
                setResolveError("");
              }}
              placeholder="Describe the final resolution provided..."
            />

            <label className="mvd-modalLabel">Steps Taken (optional)</label>
            <textarea
              className="modal-textarea"
              value={stepsTaken}
              onChange={(e) => setStepsTaken(e.target.value)}
              placeholder="List the steps taken to resolve this issue..."
            />

            {resolveError && <div className="modal-inline-error">{resolveError}</div>}
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
          <span className="modal-close" onClick={closeModal} role="button" tabIndex={0}>
            ✕
          </span>
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
            {busy ? "Saving..." : submitText}
          </button>
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

  const handleResolveSuccess = () => {
    setTicket((prev) => ({ ...prev, status: "Resolved" }));
  };

  useEffect(() => {
    const token = getAuthToken();

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(apiUrl(`/manager/complaints/${id}`), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Ticket not found");
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        setTicket(data);
      } catch (e) {
        setError(e.message || "Could not load ticket details.");
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
              <span className="label">Department</span>
              {ticket.department || "—"}
            </div>
            <div>
              <span className="label">Submitted By</span>
              {ticket.submittedBy || "—"}
            </div>
            <div>
              <span className="label">Ticket Source</span>
              {formatTicketSource(ticket.ticketSource)}
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
