import { useState } from "react";
import Layout from "../../components/Layout";
import "./TicketDetails.css";

export default function ComplaintDetails() {
  const [modalType, setModalType] = useState(null); // "reroute", "rescore", "escalate", "resolve"

  const closeModal = () => setModalType(null);

  const Modal = ({ type }) => {
    if (!type) return null;

    const titles = {
      reroute: "Reroute Ticket",
      rescore: "Rescore Ticket",
      escalate: "Escalate Ticket",
      resolve: "Resolve Ticket",
    };

    const submitText = type === "resolve" ? "Resolve" : type === "escalate" ? "Escalate" : "Submit";

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
              <textarea className="modal-textarea" placeholder="Explain why this ticket should be rerouted..." />
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
              <textarea class="modal-textarea" placeholder="Explain why the model’s score should be adjusted..." />
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
              <textarea placeholder="Explain why this ticket must be escalated..." />
              <label>Additional Notes (optional)</label>
              <textarea className="modal-textarea" placeholder="Any extra context..." />
            </>
          );
        case "resolve":
          return (
            <>
              <label>Model’s Suggested Resolution</label>
              <div className="model-suggestion">
                Send a technician to reset the AC unit, clean or replace filters, inspect the compressor for overheating,
                and schedule a follow-up check within 24 hours to confirm stable cooling.
              </div>
              <label>Suggested Resolution</label>
              <textarea className="modal-textarea" placeholder="Describe the final resolution provided..." />
              <label>Steps Taken to Resolve</label>
              <textarea className="modal-textarea" placeholder="List the steps taken to resolve this issue..." />
              <label>Attachments (optional)</label>
              <div class="modal-upload-box">
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
        <div className={`modal-card ${type === "escalate" ? "modal-red" : ""}`} onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <h2>{titles[type]}</h2>
            <span className="modal-close" onClick={closeModal}>✕</span>
          </div>
          <div className="modal-body">{renderBody()}</div>
          <div className="modal-footer">
            <button className="modal-btn cancel" onClick={closeModal}>Cancel</button>
            <button className={`modal-btn ${type === "escalate" ? "escalate" : "submit"}`}>{submitText}</button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Layout role="employee">
      {/* MAIN CONTENT */}
      <main className="main">

        {/* HEADER */}
        <div className="details-header">
          <div className="header-left">
            <button className="back-btn" onClick={() => window.history.back()}>← Back</button>
            <h1 className="ticket-title">Ticket ID: CX-1122</h1>
            <div className="status-row">
              <span className="header-pill critical-pill">Critical</span>
              <span className="header-pill status-pill">Submitted</span>
            </div>
          </div>
          <div className="header-actions">
            <button className="btn-outline" onClick={() => setModalType("rescore")}>Rescore</button>
            <button className="btn-outline" onClick={() => setModalType("reroute")}>Reroute</button>
            <button className="btn-primary" onClick={() => setModalType("resolve")}>Resolve</button>
          </div>
        </div>

        {/* SUMMARY */}
        <section className="card-section">
          <h2 className="section-title">Summary</h2>
          <div className="summary-grid">
            <div><span className="label">Issue Date:</span> 18/11/2025</div>
            <div><span className="label">Mean Time To Respond:</span> 6 Hours</div>
            <div><span className="label">Mean Time To Resolve:</span> 30 Minutes</div>
            <div><span className="label">Submitted By:</span> John Smith</div>
            <div><span className="label">Contact:</span> +971 50 123 4567</div>
            <div><span className="label">Location:</span> Building A, Floor 3</div>
          </div>
        </section>

        {/* DETAILS */}
        <section className="details-grid">

          <div className="card-section">
            <h2 className="section-title">Complaint Details</h2>
            <div className="subject">Air conditioning not working</div>
            <p className="description">
              The AC unit in the main office stopped cooling around 11 AM. Room temperature rose significantly, affecting employees. Issue may be related to compressor or electrical supply.
            </p>
            <div className="attachments">
              <div className="attachment-thumb">IMG 1</div>
              <div className="attachment-thumb">IMG 2</div>
            </div>
          </div>

          <div className="card-section">
            <h2 className="section-title">Steps Taken</h2>
            <div className="step">
              <div className="step-title">Step 1</div>
              <div className="step-text">
                Technician assigned: Ahmed Khan<br />
                Time: 18/11/2025 – 10:15 AM<br />
                Notes: Technician informed and en route.
              </div>
            </div>
            <div className="step">
              <div className="step-title">Step 2</div>
              <div className="step-text">
                Technician arrived on-site<br />
                Time: 18/11/2025 – 10:45 AM<br />
                Notes: Compressor overheating.
              </div>
            </div>
          </div>

        </section>

      </main>

      {/* MODAL */}
      <Modal type={modalType} />

    </Layout>
  );
}
