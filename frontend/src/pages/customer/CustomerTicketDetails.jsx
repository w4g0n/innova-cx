import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PriorityPill from "../../components/common/PriorityPill";
import { authHeader } from "../../utils/auth";
import "./CustomerTicketDetails.css";

export default function CustomerTicketDetails() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`http://localhost:8000/api/customer/tickets/${id}`, {
      headers: authHeader(),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then((data) => {
        const t = data.ticket;

        setTicket({
          id: t.ticketId,
          title: t.description?.subject,
          type: "Ticket",
          status: t.status,
          date: t.issueDate,
          priority: t.priority,
          description: t.description?.details,
          updates:
            t.updates?.map((u) => ({
              date: new Date(u.date).toLocaleString(),
              text: `${u.author}: ${u.message}`,        
            })) || [],
        });

        setLoading(false);
      })
      .catch(() => {
        setTicket(null);
        setLoading(false);
      });
  }, [id]);

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
              onClick={() => navigate("/customer/mytickets")}
            >
              Back to My Tickets
            </button>
          }
        />

        {!loading && !ticket ? (
          <div className="ticketEmpty">
            <h3 className="ticketEmptyTitle">Ticket not found</h3>
            <p className="ticketEmptySub">
              We couldn’t find a ticket with ID <strong>{id}</strong>.
            </p>

            <button
              type="button"
              className="primaryPillBtn"
              onClick={() => navigate("/customer/mytickets")}
            >
              Go to My Tickets
            </button>
          </div>
        ) : ticket ? (
          <>
            <section className="ticketCard">
              <div className="ticketTop">
                <div className="ticketTopLeft">
                  <div className="ticketMeta">
                    <span className="ticketId">{ticket.id}</span>
                    <span className="dot">•</span>
                    <span className="ticketType">{ticket.type}</span>
                    <span className="dot">•</span>
                    <span className={statusClass(ticket.status)}>
                      {ticket.status}
                    </span>
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
                    onClick={() =>
                      alert(`Download / Share ticket ${ticket.id} (demo)`)
                    }
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
        ) : (
          <p>Loading ticket...</p>
        )}
      </div>
    </Layout>
  );
}
