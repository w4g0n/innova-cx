import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import { apiUrl } from "../../config/apiBase";
import "./TicketDetails.css";

const API_BASE = apiUrl("/api");

// Token may be stored under one of these keys
function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

export default function ComplaintDetails() {
  const { id } = useParams(); // ticket code like "CX-4630"
  const navigate = useNavigate();

  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalType, setModalType] = useState(null); // "reroute", "rescore", "escalate", "resolve"
  const [resolveDecision, setResolveDecision] = useState("accepted");
  const [resolutionSuggestion, setResolutionSuggestion] = useState("");
  const [finalResolution, setFinalResolution] = useState("");
  const [stepsTaken, setStepsTaken] = useState("");
  const [resolveBusy, setResolveBusy] = useState(false);
  const [resolveError, setResolveError] = useState("");
  const [suggestionBusy, setSuggestionBusy] = useState(false);

  const closeModal = () => setModalType(null);

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
        if (!res.ok) {
          const msg = await res.text();
          throw new Error(msg || `Failed to get suggested resolution (${res.status})`);
        }
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

  useEffect(() => {
    async function load() {
      const token = getAuthToken();
      if (!token) {
        setError("Missing auth token. Please log in again.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

      try {
        const res = await fetch(`${API_BASE}/employee/tickets/${encodeURIComponent(id)}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          const msg = await res.text();
          throw new Error(msg || `Failed to load ticket (${res.status})`);
        }

        const data = await res.json();
        setTicket(data?.ticket || null);
      } catch (e) {
        setError(e?.message || "Could not load ticket details.");
        setTicket(null);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [id]);

  const Modal = ({ type }) => {
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
                <select defaultValue="">
                  <option value="" disabled>Select Department</option>
                  <option>Maintenance</option>
                  <option>IT Support</option>
                  <option>Cleaning</option>
                  <option>Security</option>
                </select>
              </div>
              <label>Reason for rerouting</label>
              <textarea
                className="modal-textarea"
                placeholder="Explain why this ticket should be rerouted..."
              />
            </>
          );
        case "rescore":
          return (
            <>
              <label>New Priority</label>
              <div className="select-wrapper modal-dropdown">
                <select defaultValue="Medium">
                  <option>Low</option>
                  <option>Medium</option>
                  <option>High</option>
                  <option>Critical</option>
                </select>
              </div>
              <label>Reason for rescoring</label>
              <textarea
                className="modal-textarea"
                placeholder="Explain why the model’s score should be adjusted..."
              />
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
                    if (next === "accepted") {
                      setFinalResolution(resolutionSuggestion || "");
                    }
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
              {resolveError && <div style={{ color: "#b42318", marginTop: 8 }}>{resolveError}</div>}
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
              onClick={async () => {
                if (type !== "resolve") {
                  closeModal();
                  alert("Saved (UI only). Backend action endpoints can be added next.");
                  return;
                }

                const token = getAuthToken();
                if (!token) {
                  setResolveError("Missing auth token. Please log in again.");
                  return;
                }
                setResolveBusy(true);
                setResolveError("");
                try {
                  const payload = {
                    decision: resolveDecision,
                    final_resolution: resolveDecision === "declined_custom" ? finalResolution.trim() : undefined,
                    steps_taken: stepsTaken.trim() || undefined,
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
                  if (!res.ok) {
                    const msg = await res.text();
                    throw new Error(msg || `Failed to resolve ticket (${res.status})`);
                  }
                  const data = await res.json();
                  setTicket((prev) => ({
                    ...prev,
                    status: data?.status || "Resolved",
                    modelSuggestion: resolutionSuggestion || prev?.modelSuggestion,
                  }));
                  closeModal();
                  alert("Ticket resolved successfully.");
                } catch (e) {
                  setResolveError(e?.message || "Could not resolve ticket.");
                } finally {
                  setResolveBusy(false);
                }
              }}
              disabled={resolveBusy || suggestionBusy}
            >
              {resolveBusy ? "Saving..." : submitText}
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (loading)
    return (
      <Layout role="employee">
        <main className="main">Loading ticket details...</main>
      </Layout>
    );

  if (error)
    return (
      <Layout role="employee">
        <main className="main">{error}</main>
      </Layout>
    );

  if (!ticket) return null;

  return (
    <Layout role="employee">
      <main className="main">
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" onClick={() => navigate(-1)}>
              ← Back
            </button>
            <h1 className="ticket-title">Ticket ID: {ticket.ticketId}</h1>
            <div className="status-row">
              <span className={`header-pill ${(ticket.priority || "").toLowerCase()}-pill`}>
                {ticket.priority}
              </span>
              <span className="header-pill status-pill">{ticket.status}</span>
            </div>
          </div>

          <div className="header-actions">
            <button className="btn-outline" onClick={() => setModalType("rescore")}>
              Rescore
            </button>
            <button className="btn-outline" onClick={() => setModalType("reroute")}>
              Reroute
            </button>
            <button className="btn-primary" onClick={() => setModalType("resolve")}>
              Resolve
            </button>
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
            <h2 className="section-title">Complaint Details</h2>
            <div className="subject">{ticket.description?.subject}</div>
            <p className="description">{ticket.description?.details}</p>

            {ticket.attachments?.length > 0 && (
              <div className="attachments">
                {ticket.attachments.map((att, i) => (
                  <div key={i} className="attachment-thumb">{att}</div>
                ))}
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
      </main>

      <Modal type={modalType} />
    </Layout>
  );
}
