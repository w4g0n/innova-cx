import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../../components/Layout";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import { apiUrl } from "../../config/apiBase";
import "./RoutingReviewDetails.css";

function getAuthToken() {
  try {
    const raw = localStorage.getItem("user");
    if (raw) { const u = JSON.parse(raw); if (u?.access_token) return u.access_token; }
  } catch { /* ignore */ }
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") || ""
  );
}

// ── Confidence ring ───────────────────────────────────────────────────────────
function ConfidenceRing({ pct }) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = pct >= 70 ? "#34d399" : pct >= 50 ? "#fbbf24" : "#f87171";
  const label = pct >= 70 ? "Moderate" : pct >= 50 ? "Low" : "Very Low";

  return (
    <div className="rrd-ring">
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="10" />
        <circle
          cx="55" cy="55" r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div className="rrd-ringInner">
        <span className="rrd-ringPct" style={{ color }}>{pct.toFixed(0)}%</span>
        <span className="rrd-ringLabel">{label}</span>
      </div>
    </div>
  );
}

// ── Keyword chip ──────────────────────────────────────────────────────────────
function KeywordChip({ word, weight }) {
  const opacity = 0.35 + weight * 0.65;
  const size    = 11 + Math.round(weight * 4);
  return (
    <span className="rrd-kwChip" style={{ opacity, fontSize: size }}>
      {word}
    </span>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const cfg = {
    Pending:    { cls: "rrd-badge--pending",    icon: "●", label: "Pending" },
    Approved:   { cls: "rrd-badge--confirmed",  icon: "✓", label: "Confirmed" },
    Overridden: { cls: "rrd-badge--overridden", icon: "↺", label: "Overridden" },
  }[status] || { cls: "rrd-badge--pending", icon: "●", label: status };
  return <span className={`rrd-badge ${cfg.cls}`}>{cfg.icon} {cfg.label}</span>;
}

// ── Keyword extractor — pulls meaningful words from ticket text ───────────────
function extractKeywords(text = "", targetDept = "") {
  if (!text) return [];

  // Department-adjacent signal words (extend as needed)
  const deptSignals = {
    it: ["network", "vpn", "server", "software", "hardware", "system", "access", "login", "password", "computer", "laptop", "wifi", "internet", "database", "app", "application", "email", "outlook", "Teams"],
    hr: ["employee", "payroll", "salary", "leave", "vacation", "policy", "contract", "benefits", "hire", "training", "onboarding", "performance", "review"],
    facilities: ["office", "desk", "chair", "room", "building", "printer", "parking", "ac", "heating", "cleaning", "maintenance", "elevator", "lights"],
    finance: ["invoice", "payment", "expense", "budget", "reimburse", "tax", "bill", "cost", "refund", "transaction", "payable", "receivable"],
    security: ["badge", "access", "door", "camera", "lock", "threat", "breach", "incident", "alert", "suspicious", "unauthorized"],
    legal: ["contract", "compliance", "regulation", "dispute", "litigation", "agreement", "clause", "liability"],
    operations: ["process", "workflow", "pipeline", "schedule", "delay", "shipment", "delivery", "logistics"],
  };

  const deptKey = targetDept.toLowerCase().split(" ")[0];
  const signals = deptSignals[deptKey] || Object.values(deptSignals).flat();

  const words = text.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((w) => w.length > 3);
  const freq  = {};
  words.forEach((w) => { freq[w] = (freq[w] || 0) + 1; });

  const stopWords = new Set(["this", "that", "with", "have", "from", "they", "been", "were", "when", "what", "your", "our", "the", "and", "for", "not", "you", "all", "can", "more", "also", "some", "will", "just", "into", "over", "such", "than", "then", "them"]);

  return Object.entries(freq)
    .filter(([w]) => !stopWords.has(w))
    .map(([word, count]) => ({
      word,
      weight: Math.min(1, (signals.includes(word) ? 0.6 : 0) + count * 0.1),
      isSignal: signals.includes(word),
    }))
    .sort((a, b) => b.weight - a.weight || b.word.length - a.word.length)
    .slice(0, 18);
}

// ── Main component ────────────────────────────────────────────────────────────
export default function RoutingReviewDetails() {
  const { reviewId } = useParams();
  const navigate     = useNavigate();
  const heroRef      = useRef(null);

  const [item, setItem]         = useState(null);
  const [ticket, setTicket]     = useState(null);
  const [routing] = useState(null); // routing_outputs row
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [deciding, setDeciding] = useState(false);
  const [selDept, setSelDept]   = useState("");
  const [departments, setDepts] = useState([]);
  const [flashClass, setFlash]  = useState("");
  const [toast, setToast]       = useState({ show: false, message: "", type: "success" });
  const [confirm, setConfirm]   = useState({ open: false, decision: null });
  const closeConfirm = () => setConfirm({ open: false, decision: null });

  const token   = getAuthToken();
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    setLoading(true);

    Promise.all([
      fetch(apiUrl(`/api/manager/routing-review?status_filter=All`), { headers }).then((r) => r.json()),
      fetch(apiUrl("/api/manager/departments"), { headers }).then((r) => r.json()).catch(() => []),
    ])
      .then(([data, depts]) => {
        const found = (data.items || []).find((i) => i.reviewId === reviewId);
        if (!found) { setError("Routing review item not found."); return; }
        setItem(found);
        setDepts(Array.isArray(depts) ? depts : []);

        // Fetch linked ticket for subject/details/keywords
        if (found.ticketCode) {
          return fetch(apiUrl(`/api/manager/complaints/${found.ticketCode}`), { headers })
            .then((r) => r.json())
            .then((t) => { if (!t.error) setTicket(t); })
            .catch(() => null);
        }
      })
      .catch((e) => setError(e.message || "Failed to load."))
      .finally(() => setLoading(false));
  }, [reviewId]); // eslint-disable-line react-hooks/exhaustive-deps

  const triggerFlash = (decision) => {
    setFlash(decision === "Approved" ? "rrd-flash--confirm" : "rrd-flash--override");
    setTimeout(() => setFlash(""), 900);
  };

  const decide = async (decision) => {
    if (!token) { navigate("/login"); return; }
    if (decision === "Overridden" && !selDept) {
      showToast("Please select a department to override to.", "error");
      return;
    }

    setDeciding(true);
    triggerFlash(decision);

    try {
      const res = await fetch(apiUrl(`/api/manager/routing-review/${reviewId}`), {
        method: "PATCH",
        headers,
        body: JSON.stringify({
          decision,
          approved_department: decision === "Overridden" ? selDept : item.predictedDepartment,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }
      setItem((prev) => ({
        ...prev,
        status:             decision,
        approvedDepartment: decision === "Overridden" ? selDept : prev.predictedDepartment,
      }));
      showToast(
        decision === "Approved"
          ? `✓ AI routing confirmed → ${item.predictedDepartment}`
          : `↺ Routing overridden → ${selDept}`,
        "success"
      );
    } catch (e) {
      showToast(e.message || "Failed to save decision.", "error");
    } finally {
      setDeciding(false);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────
  const isPending  = item?.status === "Pending";
  const confidence = item ? parseFloat(item.confidencePct) : 0;
  const keywords   = extractKeywords(ticket?.details || ticket?.subject || "", item?.predictedDepartment || "");
  const signalWords = keywords.filter((k) => k.isSignal);
  const otherWords  = keywords.filter((k) => !k.isSignal);

  const createdAt  = item?.createdAt  ? new Date(item.createdAt)  : null;
  const decidedAt  = item?.decidedAt  ? new Date(item.decidedAt)  : null;
  const daysOpen   = createdAt ? Math.floor((Date.now() - createdAt) / 86400000) : null;
  const reasoning  = item?.modelReasoning || routing?.reasoning || null;

  const finalDept  = item?.status === "Overridden"
    ? item.approvedDepartment
    : item?.status === "Approved"
    ? item.predictedDepartment
    : null;

  if (loading) return (
    <Layout role="manager">
      <div className="rrd-loading"><div className="rrd-spinner" /><p>Loading routing review…</p></div>
    </Layout>
  );
  if (error || !item) return (
    <Layout role="manager">
      <div className="rrd-error">
        <div className="rrd-errorIcon">🧭</div>
        <h2>{error || "Item not found"}</h2>
        <button className="rrd-backBtn" onClick={() => navigate(-1)}>← Go Back</button>
      </div>
    </Layout>
  );

  return (
    <Layout role="manager">
      <div className="rrd-page">

        {/* Back */}
        <div className="rrd-topBar">
          <button className="rrd-backBtn" onClick={() => navigate("/manager/approvals")}>
            ← Back to Approvals
          </button>
        </div>

        {/* Hero */}
        <div className={`rrd-hero ${flashClass}`} ref={heroRef}>
          <div className="rrd-heroGlow rrd-heroGlow--1" />
          <div className="rrd-heroGlow rrd-heroGlow--2" />
          <div className="rrd-heroGrid" />

          <div className="rrd-heroContent">
            <div className="rrd-heroLeft">
              <div className="rrd-heroIcon">🧭</div>
              <div>
                <div className="rrd-heroSub">Routing Review</div>
                <h1 className="rrd-heroTitle">{item.ticketCode}</h1>
                <p className="rrd-heroSubject">{ticket?.subject || item.subject || ""}</p>
                <div className="rrd-heroMeta">
                  <StatusBadge status={item.status} />
                  <span className="rrd-typePill">AI Confidence Review</span>
                  {item.priority && (
                    <span className={`rrd-typePill rrd-priority--${(item.priority || "").toLowerCase()}`}>
                      {item.priority}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="rrd-heroRight">
              <div className="rrd-heroStats">
                <div className="rrd-heroStat">
                  <span className="rrd-heroStatVal">{item.predictedDepartment}</span>
                  <span className="rrd-heroStatLabel">AI Suggested</span>
                </div>
                <div className="rrd-heroStatDivider" />
                <div className="rrd-heroStat">
                  <span className="rrd-heroStatVal">{item.currentDepartment || "—"}</span>
                  <span className="rrd-heroStatLabel">Current Dept</span>
                </div>
                <div className="rrd-heroStatDivider" />
                <div className="rrd-heroStat">
                  <span className="rrd-heroStatVal">{daysOpen !== null ? `${daysOpen}d` : "—"}</span>
                  <span className="rrd-heroStatLabel">Days Open</span>
                </div>
              </div>

              {isPending && (
                <div className="rrd-heroActions">
                  {/* Override department picker */}
                  <select
                    className="rrd-deptSelect"
                    value={selDept}
                    onChange={(e) => setSelDept(e.target.value)}
                  >
                    <option value="">Override to dept…</option>
                    {departments.filter((d) => d !== item.predictedDepartment).map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  <button
                    className="rrd-btnOverride"
                    type="button"
                    disabled={deciding || !selDept}
                    onClick={() => setConfirm({ open: true, decision: "Overridden" })}
                  >
                    {deciding ? "…" : "↺ Override"}
                  </button>
                  <button
                    className="rrd-btnConfirm"
                    type="button"
                    disabled={deciding}
                    onClick={() => setConfirm({ open: true, decision: "Approved" })}
                  >
                    {deciding ? "…" : "✓ Confirm Routing"}
                  </button>
                </div>
              )}

              {!isPending && finalDept && (
                <div className="rrd-resolvedBanner">
                  {item.status === "Approved" ? "✓ Confirmed →" : "↺ Overridden →"} <strong>{finalDept}</strong>
                  {item.decidedBy && <span style={{ opacity: 0.7 }}> by {item.decidedBy}</span>}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Main grid */}
        <div className="rrd-grid">

          {/* LEFT ─ confidence + AI reasoning */}
          <div className="rrd-leftCol">

            {/* Confidence card */}
            <div className="rrd-card">
              <div className="rrd-cardHeader">
                <span className="rrd-cardHeaderIcon">📊</span>
                <h2 className="rrd-cardTitle">Model Confidence Analysis</h2>
              </div>
              <div className="rrd-confidenceBody">
                <ConfidenceRing pct={confidence} />
                <div className="rrd-confidenceText">
                  <p className="rrd-confidenceHeading">
                    {confidence >= 70
                      ? "The model had moderate confidence in this routing."
                      : confidence >= 50
                      ? "The model was uncertain — manual review recommended."
                      : "The model had very low confidence. Human override likely needed."}
                  </p>
                  <div className="rrd-confidenceMeta">
                    <div className="rrd-cmRow">
                      <span className="rrd-cmLabel">Predicted department</span>
                      <span className="rrd-cmVal">{item.predictedDepartment}</span>
                    </div>
                    <div className="rrd-cmRow">
                      <span className="rrd-cmLabel">Confidence score</span>
                      <span className="rrd-cmVal">{confidence.toFixed(2)}%</span>
                    </div>
                    <div className="rrd-cmRow">
                      <span className="rrd-cmLabel">Threshold</span>
                      <span className="rrd-cmVal">75.0% (system default)</span>
                    </div>
                    <div className="rrd-cmRow">
                      <span className="rrd-cmLabel">Below threshold by</span>
                      <span className="rrd-cmVal rrd-cmVal--warn">{Math.max(0, 75 - confidence).toFixed(2)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Model reasoning */}
            <div className="rrd-card">
              <div className="rrd-cardHeader">
                <span className="rrd-cardHeaderIcon">🤖</span>
                <h2 className="rrd-cardTitle">Why the Model Chose This Department</h2>
              </div>

              {reasoning ? (
                <div className="rrd-reasoningBox">
                  <p className="rrd-reasoningText">{reasoning}</p>
                </div>
              ) : (
                <p className="rrd-reasoningAbsent">
                  No explicit reasoning was stored by the model for this routing decision.
                  The keyword signals below are inferred from the ticket content.
                </p>
              )}

              {/* Signal keywords */}
              {(ticket?.details || ticket?.subject) && (
                <>
                  <div className="rrd-kwSection">
                    <div className="rrd-kwSectionLabel">
                      🎯 Strong department signals
                      <span className="rrd-kwNote">Words that strongly match "{item.predictedDepartment}"</span>
                    </div>
                    <div className="rrd-kwCloud">
                      {signalWords.length > 0
                        ? signalWords.map((k) => <KeywordChip key={k.word} {...k} />)
                        : <span className="rrd-kwEmpty">No strong signal words detected</span>}
                    </div>
                  </div>

                  <div className="rrd-kwSection">
                    <div className="rrd-kwSectionLabel">
                      📝 Other notable terms
                      <span className="rrd-kwNote">Additional words from ticket content</span>
                    </div>
                    <div className="rrd-kwCloud">
                      {otherWords.slice(0, 10).map((k) => (
                        <KeywordChip key={k.word} word={k.word} weight={k.weight * 0.6} />
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Ticket details */}
            {ticket?.details && (
              <div className="rrd-card">
                <div className="rrd-cardHeader">
                  <span className="rrd-cardHeaderIcon">📋</span>
                  <h2 className="rrd-cardTitle">Ticket Content</h2>
                </div>
                <p className="rrd-ticketDetails">{ticket.details}</p>
              </div>
            )}

            {/* Decision notes */}
            {item.decisionNotes && (
              <div className="rrd-card">
                <div className="rrd-cardHeader">
                  <span className="rrd-cardHeaderIcon">📝</span>
                  <h2 className="rrd-cardTitle">Decision Notes</h2>
                </div>
                <p className="rrd-ticketDetails">{item.decisionNotes}</p>
              </div>
            )}
          </div>

          {/* RIGHT ─ ticket info + timeline */}
          <div className="rrd-rightCol">

            {/* Linked ticket */}
            {ticket && (
              <div className="rrd-sideCard">
                <h3 className="rrd-sideCardTitle">Linked Ticket</h3>
                <div className="rrd-ticketSnippetCode">{item.ticketCode}</div>
                <div className="rrd-ticketSnippetSubject">{ticket.subject || "—"}</div>
                <div className="rrd-ticketSnippetMeta">
                  <span className={`rrd-priorityDot rrd-priorityDot--${(ticket.priority || "").toLowerCase()}`} />
                  <span>{ticket.priority || "—"}</span>
                  <span className="rrd-dot">·</span>
                  <span>{ticket.status || "—"}</span>
                  <span className="rrd-dot">·</span>
                  <span>{ticket.department || item.currentDepartment || "—"}</span>
                </div>
                <button
                  className="rrd-viewTicketBtn"
                  onClick={() => navigate(`/manager/complaints/${item.ticketCode}`)}
                >
                  View Full Ticket →
                </button>
              </div>
            )}

            {/* Department comparison */}
            <div className="rrd-sideCard">
              <h3 className="rrd-sideCardTitle">Department Comparison</h3>
              <div className="rrd-deptCompare">
                <div className="rrd-deptBox rrd-deptBox--current">
                  <div className="rrd-deptBoxLabel">Currently Assigned</div>
                  <div className="rrd-deptBoxValue">{item.currentDepartment || "Unassigned"}</div>
                </div>
                <div className="rrd-deptArrow">→</div>
                <div className={`rrd-deptBox rrd-deptBox--suggested ${item.status !== "Pending" && item.status !== "Overridden" ? "rrd-deptBox--active" : ""}`}>
                  <div className="rrd-deptBoxLabel">AI Suggested</div>
                  <div className="rrd-deptBoxValue">{item.predictedDepartment}</div>
                  {item.status === "Approved" && <div className="rrd-deptBoxBadge">✓ Applied</div>}
                </div>
              </div>
              {item.status === "Overridden" && (
                <div className="rrd-deptOverriddenNote">
                  ↺ Manager overrode to <strong>{item.approvedDepartment}</strong>
                </div>
              )}
            </div>

            {/* Detail chips */}
            <div className="rrd-sideCard">
              <h3 className="rrd-sideCardTitle">Details</h3>
              <div className="rrd-detailGrid">
                {[
                  { label: "Review ID",   val: reviewId?.slice(0, 8) + "…" },
                  { label: "Ticket",      val: item.ticketCode },
                  { label: "Submitted",   val: createdAt?.toLocaleString() || "—" },
                  { label: "Decided At",  val: decidedAt?.toLocaleString() || "—" },
                  { label: "Decided By",  val: item.decidedBy || "—" },
                  { label: "Status",      val: item.status },
                ].map(({ label, val }) => (
                  <div key={label} className="rrd-detailRow">
                    <span className="rrd-detailLabel">{label}</span>
                    <span className="rrd-detailVal">{val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div className="rrd-sideCard">
              <h3 className="rrd-sideCardTitle">Timeline</h3>
              <div className="rrd-timeline">
                <div className="rrd-tlItem">
                  <div className="rrd-tlDot rrd-tlDot--purple" />
                  <div>
                    <div className="rrd-tlTitle">Routing review created</div>
                    <div className="rrd-tlDate">{createdAt?.toLocaleString() || "—"}</div>
                  </div>
                </div>
                <div className="rrd-tlItem">
                  <div className="rrd-tlDot rrd-tlDot--yellow" />
                  <div>
                    <div className="rrd-tlTitle">AI routed → {item.predictedDepartment}</div>
                    <div className="rrd-tlDate">Confidence: {confidence.toFixed(1)}% (below 75% threshold)</div>
                  </div>
                </div>
                {item.status === "Approved" && (
                  <div className="rrd-tlItem">
                    <div className="rrd-tlDot rrd-tlDot--green" />
                    <div>
                      <div className="rrd-tlTitle">Routing confirmed by {item.decidedBy || "manager"}</div>
                      <div className="rrd-tlDate">{decidedAt?.toLocaleString() || "—"}</div>
                    </div>
                  </div>
                )}
                {item.status === "Overridden" && (
                  <div className="rrd-tlItem">
                    <div className="rrd-tlDot rrd-tlDot--indigo" />
                    <div>
                      <div className="rrd-tlTitle">Overridden → {item.approvedDepartment} by {item.decidedBy || "manager"}</div>
                      <div className="rrd-tlDate">{decidedAt?.toLocaleString() || "—"}</div>
                    </div>
                  </div>
                )}
                {isPending && (
                  <div className="rrd-tlItem rrd-tlItem--pending">
                    <div className="rrd-tlDot rrd-tlDot--pending" />
                    <div>
                      <div className="rrd-tlTitle">Awaiting manager review</div>
                      <div className="rrd-tlDate">Pending</div>
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
        <div className={`rrd-toast rrd-toast--${toast.type}`}>
          <span>{toast.message}</span>
          <button onClick={() => setToast((t) => ({ ...t, show: false }))}>✕</button>
        </div>
      )}

      <ConfirmDialog
        open={confirm.open}
        title={confirm.decision === "Approved" ? "Confirm AI Routing" : "Override Routing"}
        message={
          confirm.decision === "Approved"
            ? `Confirm that this ticket should stay routed to "${item.predictedDepartment}"?`
            : `Override AI routing and assign this ticket to "${selDept}"?`
        }
        variant={confirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={confirm.decision === "Approved" ? "Yes, Confirm" : "Yes, Override"}
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