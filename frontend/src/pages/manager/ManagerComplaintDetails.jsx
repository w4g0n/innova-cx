import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerComplaintDetails.css";
import { apiUrl } from "../../config/apiBase";


function Modal({ type, ticket, closeModal, onRerouteSuccess, onRescoreSuccess, onResolveSuccess }) {  
  if (!type || !ticket) return null;

  const titles = {
    reroute: "Reroute Ticket",
    rescore: "Rescore Ticket",
    escalate: "Escalate Ticket",
    resolve: "Resolve Ticket",
  };

  const submitText =
    type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit";

  // ── Reroute state ──────────────────────────────────────────
  const [departments, setDepartments] = useState([]);
  const [selectedDept, setSelectedDept] = useState("");
  const [rerouteLoading, setRerouteLoading] = useState(false);
  const [rerouteError, setRerouteError] = useState("");

  // ── Rescore state ──────────────────────────────────────────
  const [selectedPriority, setSelectedPriority] = useState(ticket.priorityText || "Medium");
  const [rescoreReason, setRescoreReason] = useState("");
  const [rescoreLoading, setRescoreLoading] = useState(false);
  const [rescoreError, setRescoreError] = useState("");

  // ── Resolve state ──────────────────────────────────────────
  const [resolveText, setResolveText] = useState("");
  const [resolveSteps, setResolveSteps] = useState("");
  const [resolveLoading, setResolveLoading] = useState(false);
  const [resolveError, setResolveError] = useState("");

  useEffect(() => {
    if (type !== "reroute") return;
    const token = localStorage.getItem("access_token");
    fetch(apiUrl("/manager/departments"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        // API returns a plain array of strings
        const list = Array.isArray(data) ? data : [];
        setDepartments(list);
        // Pre-select current department if it exists in the list
        if (ticket.department && list.includes(ticket.department)) {
          setSelectedDept(ticket.department);
        }
      })
      .catch(() => setDepartments([]));
  }, [type, ticket.department]);

  const handleRerouteSubmit = async () => {
    if (!selectedDept) {
      setRerouteError("Please select a department.");
      return;
    }
    setRerouteLoading(true);
    setRerouteError("");
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/department`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ department: selectedDept }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      // Notify parent to update displayed ticket
      onRerouteSuccess(selectedDept);
      closeModal();
    } catch (e) {
      setRerouteError(e.message || "Failed to reroute ticket.");
    } finally {
      setRerouteLoading(false);
    }
  };

  const handleRescoreSubmit = async () => {
    if (!rescoreReason.trim()) {
      setRescoreError("Please provide a reason for rescoring.");
      return;
    }
    setRescoreLoading(true);
    setRescoreError("");
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/priority`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ new_priority: selectedPriority, reason: rescoreReason }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onRescoreSuccess(selectedPriority);
      closeModal();
    } catch (e) {
      setRescoreError(e.message || "Failed to rescore ticket.");
    } finally {
      setRescoreLoading(false);
    }
  };

  const handleResolveSubmit = async () => {
    if (!resolveText.trim()) {
      setResolveError("Please provide a resolution description.");
      return;
    }
    setResolveLoading(true);
    setResolveError("");
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(apiUrl(`/manager/complaints/${ticket.id}/resolve`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          final_resolution: resolveText,
          steps_taken: resolveSteps || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      onResolveSuccess();
      closeModal();
    } catch (e) {
      setResolveError(e.message || "Failed to resolve ticket.");
    } finally {
      setResolveLoading(false);
    }
  };
  // ──────────────────────────────────────────────────────────

  const renderBody = () => {
    switch (type) {
      case "reroute":
        return (
          <>
            <label className="mvd-modalLabel">New Department</label>
            <div className="mvd-modalDropdown">
              <select
                value={selectedDept}
                onChange={(e) => setSelectedDept(e.target.value)}
              >
                <option value="">Select Department</option>
                {departments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                    {d === ticket.department ? " (current)" : ""}
                  </option>
                ))}
              </select>
            </div>
            {rerouteError && (
              <p style={{ color: "red", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                {rerouteError}
              </p>
            )}
          </>
        );

      case "rescore":
        return (
          <>
            <label className="mvd-modalLabel">New Priority</label>
            <div className="mvd-modalDropdown">
              <select
                value={selectedPriority}
                onChange={(e) => setSelectedPriority(e.target.value)}
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>

            <label className="mvd-modalLabel">Reason for rescoring</label>
            <textarea
              className="mvd-modalTextarea"
              placeholder="Explain why the priority should be adjusted..."
              value={rescoreReason}
              onChange={(e) => setRescoreReason(e.target.value)}
            />
            {rescoreError && (
              <p style={{ color: "red", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                {rescoreError}
              </p>
            )}
          </>
        );

      case "escalate":
        return (
          <>
            <label className="mvd-modalLabel">Escalation Level</label>
            <div className="mvd-modalDropdown">
              <select>
                <option>Select Level</option>
                <option>Supervisor</option>
                <option>Department Head</option>
                <option>Management</option>
              </select>
            </div>

            <label className="mvd-modalLabel">Reason for escalation</label>
            <textarea
              className="mvd-modalTextarea"
              placeholder="Explain why this ticket must be escalated..."
            />

            <label className="mvd-modalLabel">Additional Notes (optional)</label>
            <textarea className="mvd-modalTextarea mvd-modalTextareaSmall" placeholder="Any extra context..." />
          </>
        );

      case "resolve":
        return (
          <>
            <label className="mvd-modalLabel">Resolution <span style={{ color: "red" }}>*</span></label>
            <textarea
              className="mvd-modalTextarea"
              placeholder="Describe the final resolution provided..."
              value={resolveText}
              onChange={(e) => setResolveText(e.target.value)}
            />

            <label className="mvd-modalLabel">Steps Taken (optional)</label>
            <textarea
              className="mvd-modalTextarea"
              placeholder="List the steps taken to resolve this issue..."
              value={resolveSteps}
              onChange={(e) => setResolveSteps(e.target.value)}
            />

            {resolveError && (
              <p style={{ color: "red", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                {resolveError}
              </p>
            )}
          </>
        );

      default:
        return null;
    }
  };

  const handleSubmit = () => {
    if (type === "reroute") handleRerouteSubmit();
    if (type === "rescore") handleRescoreSubmit();
    if (type === "resolve") handleResolveSubmit();
  };

  return (
    <div className="mvd-overlay" onClick={closeModal} role="presentation">
      <div
        className={`mvd-modalCard ${type === "escalate" ? "mvd-modalRed" : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="mvd-modalHeader">
          <h2 className="mvd-modalTitle">{titles[type]}</h2>
          <button className="mvd-close" type="button" onClick={closeModal}>
            ✕
          </button>
        </div>

        <div className="mvd-modalBody">{renderBody()}</div>

        <div className="mvd-modalFooter">
          <button className="mvd-btn mvd-btnCancel" type="button" onClick={closeModal}>
            Cancel
          </button>
          <button
            className={`mvd-btn ${type === "escalate" ? "mvd-btnEscalate" : "mvd-btnSubmit"}`}
            type="button"
            onClick={["reroute", "rescore", "resolve"].includes(type) ? handleSubmit : undefined}
            disabled={
              (type === "reroute" && rerouteLoading) ||
              (type === "rescore" && rescoreLoading) ||
              (type === "resolve" && resolveLoading)
            }
          >
            {(type === "reroute" && rerouteLoading) ||
             (type === "rescore" && rescoreLoading) ||
             (type === "resolve" && resolveLoading)
              ? "Saving..."
              : submitText}
          </button>
        </div>
      </div>
    </div>
  );
}


export default function ManagerComplaintDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [modalType, setModalType] = useState(null);
  const closeModal = () => setModalType(null);

  // Called by Modal after a successful reroute PATCH
  const handleRerouteSuccess = (newDepartment) => {
    setTicket((prev) => ({ ...prev, department: newDepartment }));
  };

  const handleRescoreSuccess = (newPriority) => {
    const priorityMap = { low: "Low", medium: "Medium", high: "High", critical: "Critical" };
    const priorityText = newPriority;
    const priorityRaw = newPriority.toLowerCase();
    setTicket((prev) => ({ ...prev, priority: priorityRaw, priorityText }));
  };

  const handleResolveSuccess = () => {
    setTicket((prev) => ({ ...prev, status: "Resolved" }));
  };

  useEffect(() => {
    if (ticket) return;
    const token = localStorage.getItem("access_token");
    fetch(apiUrl(`/manager/complaints/${id}`), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Ticket not found");
        return res.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setLoading(false);
        setTicket(data);
      })
      .catch((e) => {
        setError(e.message || "Could not load ticket details.");
        setLoading(false);
      });
  }, [id, ticket]);

  if (loading)
    return (
      <Layout role="manager">
        <main className="mvd-main">Loading ticket details...</main>
      </Layout>
    );

  if (error)
    return (
      <Layout role="manager">
        <main className="mvd-main">{error}</main>
      </Layout>
    );

  if (!ticket) return null;

  return (
    <Layout role="manager">
      <main className="mvd-main">
        <div className="mvd-header">
          <div className="mvd-headerLeft">
            <button className="mvd-back" type="button" onClick={() => navigate(-1)}>
              ← Back
            </button>

            <h1 className="mvd-title">Ticket ID: {ticket.ticket_code || ticket.id}</h1>

            <div className="mvd-pills">
              <span className={`mvd-pill mvd-pill--${(ticket.priorityText || "Medium").toLowerCase()}`}>
                {ticket.priorityText}
              </span>
              <span className="mvd-pill mvd-pill--status">{ticket.status}</span>
            </div>
          </div>

          <div className="mvd-actions">
            <button className="mvd-outline" type="button" onClick={() => setModalType("rescore")}>
              Rescore
            </button>
            <button className="mvd-outline" type="button" onClick={() => setModalType("reroute")}>
              Reroute
            </button>
            <button className="mvd-primary" type="button" onClick={() => setModalType("resolve")}>
              Resolve
            </button>
          </div>
        </div>

        <section className="mvd-card">
          <h2 className="mvd-sectionTitle">Summary</h2>
          <div className="mvd-grid">
            <div>
              <span className="mvd-label">Issue Date:</span> {ticket.issueDate}
            </div>
            <div>
              <span className="mvd-label">Respond Time:</span> {ticket.respondTime}
            </div>
            <div>
              <span className="mvd-label">Resolve Time:</span> {ticket.resolveTime}
            </div>
            <div>
              <span className="mvd-label">Assignee:</span> {ticket.assignee}
            </div>
            <div>
              <span className="mvd-label">Department:</span>{" "}
              {ticket.department || <span style={{ color: "#aaa" }}>Unassigned</span>}
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <span className="mvd-label">Subject:</span> {ticket.subject}
            </div>
          </div>
        </section>

        <section className="mvd-twoCol">
          <div className="mvd-card">
            <h2 className="mvd-sectionTitle">Complaint Details</h2>
            <div className="mvd-subject">{ticket.subject}</div>
            <p className="mvd-desc">{ticket.details}</p>
          </div>

          <div className="mvd-card">
            <h2 className="mvd-sectionTitle">Activity</h2>
            <div className="mvd-activity">
              <div className="mvd-activityItem">
                <div className="mvd-dot" />
                <div>
                  <div className="mvd-activityTitle">Ticket created</div>
                  <div className="mvd-activityText">{ticket.issueDate}</div>
                </div>
              </div>
              {ticket.department && (
                <div className="mvd-activityItem">
                  <div className="mvd-dot" />
                  <div>
                    <div className="mvd-activityTitle">Department</div>
                    <div className="mvd-activityText">{ticket.department}</div>
                  </div>
                </div>
              )}
              <div className="mvd-activityItem">
                <div className="mvd-dot" />
                <div>
                  <div className="mvd-activityTitle">Current status</div>
                  <div className="mvd-activityText">{ticket.status}</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Modal
        type={modalType}
        ticket={ticket}
        closeModal={closeModal}
        onRerouteSuccess={handleRerouteSuccess}
        onRescoreSuccess={handleRescoreSuccess}
        onResolveSuccess={handleResolveSuccess}
      />
      
    </Layout>
  );
}