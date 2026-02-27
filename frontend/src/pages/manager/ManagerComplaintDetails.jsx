import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ManagerComplaintDetails.css";
import { apiUrl } from "../../config/apiBase";


export default function ManagerComplaintDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [ticket, setTicket] = useState(location.state?.ticket || null);
  const [loading, setLoading] = useState(!location.state?.ticket);
  const [error, setError] = useState(null);

  const [modalType, setModalType] = useState(null);
  const closeModal = () => setModalType(null);

  useEffect(() => {
    if (ticket) return;

    setLoading(true);
    setError(null);

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
        setTicket(data);
      })
      .catch((e) => {
        setError(e.message || "Could not load ticket details.");
        setTicket(null);
      })
      .finally(() => setLoading(false));
  }, [id, ticket]);

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
              <label className="mvd-modalLabel">New Department</label>
              <div className="mvd-modalDropdown">
                <select>
                  <option>Select Department</option>
                  <option>IT</option>
                  <option>Facilities</option>
                  <option>Security</option>
                  <option>HR</option>
                  <option>Admin</option>
                </select>
              </div>

              <label className="mvd-modalLabel">Reason for rerouting</label>
              <textarea
                className="mvd-modalTextarea"
                placeholder="Explain why this ticket should be rerouted..."
              />
            </>
          );

        case "rescore":
          return (
            <>
              <label className="mvd-modalLabel">New Priority</label>
              <div className="mvd-modalDropdown">
                <select defaultValue={ticket.priorityText || "Medium"}>
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
              />
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
              <label className="mvd-modalLabel">Resolution</label>
              <textarea
                className="mvd-modalTextarea"
                placeholder="Describe the final resolution provided..."
              />

              <label className="mvd-modalLabel">Steps Taken</label>
              <textarea
                className="mvd-modalTextarea"
                placeholder="List the steps taken to resolve this issue..."
              />

              <label className="mvd-modalLabel">Attachments (optional)</label>
              <div className="mvd-uploadBox">
                <input type="file" multiple />
              </div>
            </>
          );

        default:
          return null;
      }
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
            <div style={{ gridColumn: "1 / -1" }}>
              <span className="mvd-label">Subject:</span> {ticket.subject}
            </div>
          </div>
        </section>

        <section className="mvd-twoCol">
          <div className="mvd-card">
            <h2 className="mvd-sectionTitle">Complaint Details</h2>
            <div className="mvd-subject">{ticket.subject}</div>
            <p className="mvd-desc">
              This is a placeholder description. When you connect to your backend/DB, replace this with the real complaint text.
            </p>
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

      <Modal type={modalType} />
    </Layout>
  );
}