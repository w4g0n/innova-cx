import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import { apiUrl } from "../../config/apiBase";
import "./ApprovalRequestDetails.css";

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

function getPriorityClass(val = "") {
  const v = val.toLowerCase();
  if (v.includes("critical")) return "ard-val--critical";
  if (v.includes("high"))     return "ard-val--high";
  if (v.includes("medium"))   return "ard-val--medium";
  if (v.includes("low"))      return "ard-val--low";
  return "";
}

function StatusBadge({ status }) {
  const cls =
    status === "Approved" ? "ard-badge ard-badge--approved" :
    status === "Rejected" ? "ard-badge ard-badge--rejected" :
                            "ard-badge ard-badge--pending";
  const icon = status === "Approved" ? "✓" : status === "Rejected" ? "✕" : "●";
  return <span className={cls}>{icon} {status}</span>;
}

function TypeIcon({ type }) {
  return (
    <div className="ard-typeIcon">
      {type === "Rescoring" ? (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      ) : (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
        </svg>
      )}
    </div>
  );
}

export default function ApprovalRequestDetails() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const heroRef = useRef(null);

  const [approval, setApproval] = useState(null);
  const [ticket, setTicket]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [deciding, setDeciding] = useState(false);
  const [flashClass, setFlashClass] = useState("");
  const [showConfetti, setShowConfetti] = useState(false);
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });
  const [confirm, setConfirm] = useState({ open: false, decision: null });
  const closeConfirm = () => setConfirm({ open: false, decision: null });

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  useEffect(() => {
    const token = getAuthToken();
    if (!token) { navigate("/login"); return; }

    setLoading(true);
    setError(null);

    fetch(apiUrl("/api/manager/approvals"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401) { navigate("/login"); return null; }
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        const found = data.find((a) => String(a.requestId) === String(requestId));
        if (!found) { setError("Approval request not found."); setLoading(false); return; }
        setApproval(found);

        if (found.ticketCode) {
          return fetch(apiUrl(`/api/manager/complaints/${found.ticketCode}`), {
            headers: { Authorization: `Bearer ${token}` },
          })
            .then((r) => r.json())
            .then((t) => { if (!t.error) setTicket(t); })
            .catch(() => null);
        }
      })
      .catch((e) => setError(e.message || "Failed to load request."))
      .finally(() => setLoading(false));
  }, [requestId, navigate]);

  const triggerAnimation = (decision) => {
    if (decision === "Approved") {
      setShowConfetti(true);
      setFlashClass("ard-flash--approved");
      setTimeout(() => { setShowConfetti(false); setFlashClass(""); }, 900);
    } else {
      setFlashClass("ard-flash--rejected");
      setTimeout(() => setFlashClass(""), 900);
    }
  };

  const decide = async (decision) => {
    const token = getAuthToken();
    if (!token) { navigate("/login"); return; }

    setDeciding(true);
    triggerAnimation(decision);

    try {
      const res = await fetch(apiUrl(`/api/manager/approvals/${requestId}`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ decision }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }

      setApproval((prev) => ({ ...prev, status: decision }));
      showToast(
        decision === "Approved" ? "✓ Request approved successfully." : "Request rejected.",
        decision === "Approved" ? "success" : "error"
      );
    } catch (e) {
      showToast(e.message || "Failed to save decision.", "error");
    } finally {
      setDeciding(false);
    }
  };

  if (loading) {
    return (
      <Layout role="manager">
        <div className="ard-loading">
          <div className="ard-spinner" />
          <p>Loading request…</p>
        </div>
      </Layout>
    );
  }

  if (error || !approval) {
    return (
      <Layout role="manager">
        <div className="ard-error">
          <div className="ard-errorIcon">⚠</div>
          <h2>{error || "Request not found"}</h2>
          <button className="ard-backBtn" onClick={() => navigate(-1)}>← Go Back</button>
        </div>
      </Layout>
    );
  }

  const isPending    = approval.status === "Pending";
  const currentVal   = approval.current   || "—";
  const requestedVal = approval.requested || "—";

  const stripPrefix = (val) => val.replace(/^(Priority:|Dept:)\s*/i, "").trim();
  const beforeLabel = stripPrefix(currentVal);
  const afterLabel  = stripPrefix(requestedVal);

  const submittedDate = approval.submittedOn
    ? new Date(approval.submittedOn).toLocaleString("en-US", {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : "—";

  const decisionDate = approval.decisionDate
    ? new Date(approval.decisionDate).toLocaleString("en-US", {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : null;

  const daysOpen = approval.submittedOn
    ? Math.floor((Date.now() - new Date(approval.submittedOn)) / 86400000)
    : null;

  // Description / reason fields — check multiple possible field names
  const description =
    approval.description ||
    approval.requestReason ||
    approval.reason ||
    approval.notes ||
    approval.comment ||
    null;

  const decisionNotes =
    approval.decisionNotes ||
    approval.managerNotes ||
    null;

  return (
    <Layout role="manager">
      <div className="ard-page">

        {/* Back */}
        <div className="ard-topBar">
          <button className="ard-backBtn" type="button" onClick={() => navigate(-1)}>
            ← Back to Approvals
          </button>
        </div>

        {/* Hero */}
        <div className={`ard-hero ${flashClass}`} ref={heroRef}>
          <div className="ard-heroGlow" />

          {/* Confetti burst */}
          <div className={`ard-confettiWrap ${showConfetti ? "" : "hidden"}`}>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="ard-particle" />
            ))}
          </div>

          <div className="ard-heroContent">
            <div className="ard-heroLeft">
              <TypeIcon type={approval.type} />
              <div>
                <div className="ard-heroSub">Approval Request</div>
                <h1 className="ard-heroTitle">{approval.ticketCode ? `Request · ${approval.ticketCode}` : "Approval Request"}</h1>
                <div className="ard-heroMeta">
                  <span className="ard-typePill">{approval.type}</span>
                  <StatusBadge status={approval.status} />
                  {approval.ticketCode && (
                    <span
                      className="ard-typePill"
                      style={{ cursor: "pointer" }}
                      onClick={() => navigate(`/manager/complaints/${ticket?.id || approval.ticketCode}`)}
                    >
                      {approval.ticketCode}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="ard-heroRight">
              {/* Stats strip */}
              <div className="ard-heroStats">
                <div className="ard-heroStat">
                  <span className="ard-heroStatVal">{approval.submittedBy || "—"}</span>
                  <span className="ard-heroStatLabel">Submitted By</span>
                </div>
                <div className="ard-heroStatDivider" />
                <div className="ard-heroStat">
                  <span className="ard-heroStatVal">{daysOpen !== null ? `${daysOpen}d` : "—"}</span>
                  <span className="ard-heroStatLabel">Days Open</span>
                </div>
                <div className="ard-heroStatDivider" />
                <div className="ard-heroStat">
                  <span className="ard-heroStatVal">{approval.type}</span>
                  <span className="ard-heroStatLabel">Type</span>
                </div>
              </div>

              {isPending && (
                <div className="ard-heroActions">
                  <button className="ard-btnReject" type="button" onClick={() => setConfirm({ open: true, decision: "Rejected" })} disabled={deciding}>
                    {deciding ? "…" : "✕  Reject"}
                  </button>
                  <button className="ard-btnApprove" type="button" onClick={() => setConfirm({ open: true, decision: "Approved" })} disabled={deciding}>
                    {deciding ? "…" : "✓  Approve"}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Main grid */}
        <div className="ard-grid">
          {/* LEFT */}
          <div className="ard-leftCol">

            {/* Change card */}
            <div className="ard-changeCard">
              <div className="ard-changeHeader">
                <span className="ard-changeHeaderIcon">⇄</span>
                <h2 className="ard-changeTitle">Requested Change</h2>
              </div>

              <div className="ard-changeBody">
                <div className="ard-changePane ard-changePane--before">
                  <div className="ard-changePaneLabel">Current</div>
                  <div className={`ard-changePaneValue ${getPriorityClass(beforeLabel)}`}>
                    {beforeLabel}
                  </div>
                  <div className="ard-changePaneFull">{currentVal}</div>
                </div>

                <div className="ard-changeArrow">
                  <svg viewBox="0 0 24 24" width="30" height="30">
                    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.5"
                      strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                  </svg>
                </div>

                <div className={`ard-changePane ard-changePane--after ${approval.status === "Approved" ? "ard-changePane--applied" : ""}`}>
                  <div className="ard-changePaneLabel">Requested</div>
                  <div className={`ard-changePaneValue ${getPriorityClass(afterLabel)}`}>
                    {afterLabel}
                  </div>
                  <div className="ard-changePaneFull">{requestedVal}</div>
                  {approval.status === "Approved" && (
                    <div className="ard-appliedBadge">✓ Applied</div>
                  )}
                </div>
              </div>

              {/* Reason for request */}
              {description && (
                <div className="ard-reasonBox">
                  <div className="ard-reasonLabel">Reason for Request</div>
                  <p className="ard-reasonText">{description}</p>
                </div>
              )}

              {/* Decision notes (if manager left notes) */}
              {decisionNotes && (
                <div className="ard-reasonBox" style={{ borderLeftColor: approval.status === "Rejected" ? "#f87171" : "#34d399" }}>
                  <div className="ard-reasonLabel">
                    {approval.status === "Rejected" ? "Rejection Reason" : "Approval Notes"}
                  </div>
                  <p className="ard-reasonText">{decisionNotes}</p>
                </div>
              )}

              {/* Fallback if no description at all */}
              {!description && !decisionNotes && (
                <div className="ard-reasonBox" style={{ borderLeftColor: "#c4b5fd" }}>
                  <div className="ard-reasonLabel">Reason for Request</div>
                  <p className="ard-reasonText" style={{ color: "#9e8cc4", fontStyle: "italic" }}>
                    No reason provided for this request.
                  </p>
                </div>
              )}
            </div>

            {/* Detail chips */}
            <div className="ard-detailsRow">
              <div className="ard-detailChip">
                <span className="ard-detailChipLabel">Ticket</span>
                <span
                  className="ard-detailChipVal ard-ticketLink"
                  onClick={() => ticket && navigate(`/manager/complaints/${ticket.id || approval.ticketCode}`)}
                  style={{ cursor: ticket ? "pointer" : "default" }}
                >
                  {approval.ticketCode || "—"}
                </span>
              </div>
              <div className="ard-detailChip">
                <span className="ard-detailChipLabel">Submitted By</span>
                <span className="ard-detailChipVal">{approval.submittedBy || "—"}</span>
              </div>
              <div className="ard-detailChip">
                <span className="ard-detailChipLabel">Submitted On</span>
                <span className="ard-detailChipVal">{submittedDate}</span>
              </div>
              {approval.decidedBy && (
                <div className="ard-detailChip">
                  <span className="ard-detailChipLabel">Decided By</span>
                  <span className="ard-detailChipVal">{approval.decidedBy}</span>
                </div>
              )}
              {decisionDate && (
                <div className="ard-detailChip">
                  <span className="ard-detailChipLabel">Decision Date</span>
                  <span className="ard-detailChipVal">{decisionDate}</span>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT */}
          <div className="ard-rightCol">

            {/* Linked ticket */}
            {ticket && (
              <div className="ard-ticketCard">
                <h3 className="ard-cardTitle">Linked Ticket</h3>
                <div className="ard-ticketSnippet">
                  <div className="ard-ticketSnippetCode">{ticket.ticket_code || approval.ticketCode}</div>
                  <div className="ard-ticketSnippetSubject">{ticket.subject || "—"}</div>
                  <div className="ard-ticketSnippetMeta">
                    <span className={`ard-priorityDot ard-priorityDot--${(ticket.priority || "").toLowerCase()}`} />
                    <span>{ticket.priorityText || ticket.priority || "—"}</span>
                    <span className="ard-dot">·</span>
                    <span>{ticket.status || "—"}</span>
                    <span className="ard-dot">·</span>
                    <span>{ticket.department || "—"}</span>
                  </div>
                </div>
                <button
                  className="ard-viewTicketBtn"
                  type="button"
                  onClick={() => navigate(`/manager/complaints/${ticket.id || approval.ticketCode}`)}
                >
                  View Full Ticket →
                </button>
              </div>
            )}

            {/* Timeline */}
            <div className="ard-timelineCard">
              <h3 className="ard-cardTitle">Timeline</h3>
              <div className="ard-timeline">
                <div className="ard-tlItem">
                  <div className="ard-tlDot ard-tlDot--purple" />
                  <div>
                    <div className="ard-tlTitle">Request submitted</div>
                    <div className="ard-tlDate">{submittedDate}</div>
                  </div>
                </div>

                {approval.status === "Approved" && (
                  <div className="ard-tlItem">
                    <div className="ard-tlDot ard-tlDot--green" />
                    <div>
                      <div className="ard-tlTitle">Approved by {approval.decidedBy || "manager"}</div>
                      <div className="ard-tlDate">{decisionDate || "—"}</div>
                    </div>
                  </div>
                )}

                {approval.status === "Rejected" && (
                  <div className="ard-tlItem">
                    <div className="ard-tlDot ard-tlDot--red" />
                    <div>
                      <div className="ard-tlTitle">Rejected by {approval.decidedBy || "manager"}</div>
                      <div className="ard-tlDate">{decisionDate || "—"}</div>
                    </div>
                  </div>
                )}

                {isPending && (
                  <div className="ard-tlItem ard-tlItem--pending">
                    <div className="ard-tlDot ard-tlDot--pending" />
                    <div>
                      <div className="ard-tlTitle">Awaiting decision</div>
                      <div className="ard-tlDate">Pending manager review</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Toast */}
      {toast.show && (
        <div className={`ard-toast ard-toast--${toast.type}`}>
          <span>{toast.message}</span>
          <button onClick={() => setToast((t) => ({ ...t, show: false }))}>✕</button>
        </div>
      )}

      <ConfirmDialog
        open={confirm.open}
        title={confirm.decision === "Approved" ? "Approve Request" : "Reject Request"}
        message={
          confirm.decision === "Approved"
            ? "Are you sure you want to approve this request? This will apply the requested change."
            : "Are you sure you want to reject this request? This cannot be undone."
        }
        variant={confirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={confirm.decision === "Approved" ? "Yes, Approve" : "Yes, Reject"}
        onConfirm={() => {
          const d = confirm.decision;
          closeConfirm();
          decide(d);
        }}
        onCancel={closeConfirm}
      />
    </Layout>
  );
}