import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import ticketsData from "../../mock-data/employeeAllTickets.json"; // Local JSON import
import "./TicketDetails.css";

export default function ComplaintDetails() {
  const { id } = useParams(); // Get ticket ID from URL
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalType, setModalType] = useState(null); // "reroute", "rescore", "escalate", "resolve"

  const closeModal = () => setModalType(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    try {
      const allTickets = ticketsData.tickets || [];
      const foundTicket = allTickets.find((t) => t.ticketId === id || t.id === id);
      if (!foundTicket) throw new Error("Ticket not found");
      setTicket(foundTicket);
    } catch (err) {
      console.error(err);
      setError(err.message || "Could not load ticket details.");
      setTicket(null);
    } finally {
      setLoading(false);
    }
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
      type === "resolve"
        ? "Resolve"
        : type === "escalate"
        ? "Escalate"
        : "Submit";

    const renderBody = () => {
      switch (type) {
        case "reroute":
          return (
            <>
              <label>New Department</label>
              <div className="select-wrapper modal-dropdown">
                <select>
                  <option>Select Department</option>
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
                <select>
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
                <select>
                  <option>Select Level</option>
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
              <textarea
                className="modal-textarea"
                placeholder="Any extra context..."
              />
            </>
          );
        case "resolve":
          return (
            <>
              <label>Model’s Suggested Resolution</label>
              <div className="model-suggestion">{ticket.modelSuggestion}</div>
              <label>Suggested Resolution</label>
              <textarea
                className="modal-textarea"
                placeholder="Describe the final resolution provided..."
              />
              <label>Steps Taken to Resolve</label>
              <textarea
                className="modal-textarea"
                placeholder="List the steps taken to resolve this issue..."
              />
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
            <span className="modal-close" onClick={closeModal}>
              ✕
            </span>
          </div>
          <div className="modal-body">{renderBody()}</div>
          <div className="modal-footer">
            <button className="modal-btn cancel" onClick={closeModal}>
              Cancel
            </button>
            <button
              className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}
            >
              {submitText}
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
            <button className="back-btn" onClick={() => window.history.back()}>
              ← Back
            </button>
            <h1 className="ticket-title">Ticket ID: {ticket.ticketId}</h1>
            <div className="status-row">
              <span className={`header-pill ${ticket.priority.toLowerCase()}-pill`}>
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
            <div>
              <span className="label">Issue Date:</span> {ticket.issueDate}
            </div>
            <div>
              <span className="label">Mean Time To Respond:</span>{" "}
              {ticket.metrics?.meanTimeToRespond}
            </div>
            <div>
              <span className="label">Mean Time To Resolve:</span>{" "}
              {ticket.metrics?.meanTimeToResolve}
            </div>
            <div>
              <span className="label">Submitted By:</span> {ticket.submittedBy?.name}
            </div>
            <div>
              <span className="label">Contact:</span> {ticket.submittedBy?.contact}
            </div>
            <div>
              <span className="label">Location:</span> {ticket.submittedBy?.location}
            </div>
            <div>
              <span className="label">Description:</span> {ticket.description?.details}
            </div>
          </div>
        </section>

        
        <section className="details-grid">
          <div className="card-section">
            <h2 className="section-title">Complaint Details</h2>
            <div className="subject">{ticket.description?.subject}</div>
            <p className="description">{ticket.description?.details}</p>
            {ticket.attachments && ticket.attachments.length > 0 && (
              <div className="attachments">
                {ticket.attachments.map((att, i) => (
                  <div key={i} className="attachment-thumb">{att}</div>
                ))}
              </div>
            )}
          </div>

          {ticket.stepsTaken && ticket.stepsTaken.length > 0 && (
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