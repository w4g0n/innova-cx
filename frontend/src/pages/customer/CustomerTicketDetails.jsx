import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PriorityPill from "../../components/common/PriorityPill";
import "./CustomerTicketDetails.css";

export default function CustomerTicketDetails() {
  const navigate = useNavigate();
  const { id } = useParams();

  // Dummy data (same IDs as History demo)
  const tickets = useMemo(
    () => [
      {
        id: "INC-1024",
        title: "Unable to access my account",
        type: "Inquiry",
        status: "Open",
        date: "Aug 16, 2025",
        priority: "Low",
        description:
          "I tried logging in with my email but it keeps saying my credentials are invalid. Please help me regain access.",
        updates: [
          { date: "Aug 16, 2025", text: "Ticket created and assigned to support." },
          { date: "Aug 16, 2025", text: "We are reviewing your login activity (demo)." },
        ],
      },
      {
        id: "CMP-2219",
        title: "Delivery was delayed and support did not respond",
        type: "Complaint",
        status: "In Progress",
        date: "Aug 12, 2025",
        priority: "High",
        description:
          "My order arrived late and I could not get a response from support. I would like an explanation and resolution.",
        updates: [
          { date: "Aug 12, 2025", text: "Ticket created and assigned to an agent." },
          { date: "Aug 13, 2025", text: "Agent requested delivery timeline from vendor (demo)." },
        ],
      },
      {
        id: "CMP-2144",
        title: "Incorrect billing amount on my invoice",
        type: "Complaint",
        status: "Resolved",
        date: "Aug 02, 2025",
        priority: "Medium",
        description:
          "The amount shown on my invoice is higher than expected. Please verify and correct the billing details.",
        updates: [
          { date: "Aug 02, 2025", text: "Ticket created." },
          { date: "Aug 03, 2025", text: "Billing team reviewed invoice and issued correction (demo)." },
          { date: "Aug 03, 2025", text: "Ticket marked as Resolved." },
        ],
      },
      {
        id: "INC-0997",
        title: "How can I update my email address?",
        type: "Inquiry",
        status: "Resolved",
        date: "Jul 28, 2025",
        priority: "Low",
        description:
          "I want to change the email linked to my account. Please guide me on the correct steps.",
        updates: [
          { date: "Jul 28, 2025", text: "Ticket created." },
          { date: "Jul 28, 2025", text: "Provided steps to update email in settings (demo)." },
          { date: "Jul 29, 2025", text: "Ticket marked as Resolved." },
        ],
      },
      {
        id: "CMP-2050",
        title: "App keeps crashing when I submit the form",
        type: "Complaint",
        status: "Open",
        date: "Jul 21, 2025",
        priority: "Critical",
        description:
          "Every time I submit the complaint form, the app freezes and closes. This is blocking me from completing my request.",
        updates: [
          { date: "Jul 21, 2025", text: "Ticket created and flagged as Critical." },
          { date: "Jul 21, 2025", text: "Engineering team notified (demo)." },
        ],
      },
    ],
    []
  );

  const ticket = tickets.find((t) => t.id === id);

  const statusClass = (s) => {
    const key = (s || "").replaceAll(" ", "");
    return `statusPill status-${key}`;
  };

  return (
    <Layout role="customer">
      <div className="custTicketDetails">
        <PageHeader
          title="Ticket Details"
          subtitle="View ticket information, status, and updates."
          actions={
            <button
              type="button"
              className="primaryPillBtn"
              onClick={() => navigate("/customer/history")}
            >
              Back to History
            </button>
          }
        />

        {!ticket ? (
          <div className="ticketEmpty">
            <h3 className="ticketEmptyTitle">Ticket not found</h3>
            <p className="ticketEmptySub">
              We couldn’t find a ticket with ID <strong>{id}</strong>.
            </p>

            <button
              type="button"
              className="primaryPillBtn"
              onClick={() => navigate("/customer/history")}
            >
              Go to History
            </button>
          </div>
        ) : (
          <>
            {/* Top summary card */}
            <section className="ticketCard">
              <div className="ticketTop">
                <div className="ticketTopLeft">
                  <div className="ticketMeta">
                    <span className="ticketId">{ticket.id}</span>
                    <span className="dot">•</span>
                    <span className="ticketType">{ticket.type}</span>
                    <span className="dot">•</span>
                    <span className={statusClass(ticket.status)}>{ticket.status}</span>
                  </div>

                  <h2 className="ticketTitle">{ticket.title}</h2>

                  <div className="ticketBadges">
                    <div className="badgeBlock">
                      <span className="badgeLabel">Priority</span>
                      <PriorityPill priority={ticket.priority} />
                    </div>

                    <div className="badgeBlock">
                      <span className="badgeLabel">Created</span>
                      <span className="badgeValue">{ticket.date}</span>
                    </div>
                  </div>
                </div>

                <div className="ticketTopRight">
                  <button
                    type="button"
                    className="primaryPillBtn"
                    onClick={() => alert(`Download / Share ticket ${ticket.id} (demo)`)}
                  >
                    Share
                  </button>
                </div>
              </div>

              <div className="ticketDivider" />

              <div className="ticketBody">
                <h3 className="sectionTitle">Description</h3>
                <p className="ticketDesc">{ticket.description}</p>
              </div>
            </section>

            {/* Updates */}
            <section className="updatesCard">
              <h3 className="sectionTitle">Updates</h3>

              <div className="updatesList">
                {ticket.updates.map((u, idx) => (
                  <div key={idx} className="updateRow">
                    <div className="updateDot" />
                    <div className="updateContent">
                      <div className="updateDate">{u.date}</div>
                      <div className="updateText">{u.text}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </Layout>
  );
}
