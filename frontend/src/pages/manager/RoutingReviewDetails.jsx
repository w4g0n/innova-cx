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
    Denied:     { cls: "rrd-badge--denied",     icon: "✕", label: "Denied" },
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
  const [confirm, setConfirm]       = useState({ open: false, decision: null });
  const closeConfirm = () => setConfirm({ open: false, decision: null });
  const [overrideOpen, setOverrideOpen] = useState(false);

  const token   = getAuthToken();
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
  };

  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    setLoading(true);

    const DEPT_FALLBACK = [
      'Facilities Management', 'Legal & Compliance', 'Safety & Security',
      'HR', 'Leasing', 'Maintenance', 'IT'
    ];

    Promise.all([
      fetch(apiUrl(`/api/manager/routing-review?status_filter=All`), { headers }).then((r) => r.json()),
      // Try both common endpoint paths; fall back to hardcoded list if both fail
      fetch(apiUrl("/api/manager/departments"), { headers })
        .then((r) => r.ok ? r.json() : fetch(apiUrl("/manager/departments"), { headers }).then((r2) => r2.json()))
        .catch(() => DEPT_FALLBACK),
    ])
      .then(([data, depts]) => {
        const found = (data.items || []).find((i) => i.reviewId === reviewId);
        if (!found) { setError("Routing review item not found."); return; }
        setItem(found);
        const deptList = Array.isArray(depts) && depts.length > 0 ? depts : DEPT_FALLBACK;
        setDepts(deptList);

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
    const cls = decision === "Approved" ? "rrd-flash--confirm"
              : decision === "Denied"   ? "rrd-flash--override"
              :                          "rrd-flash--override";
    setFlash(cls);
    setTimeout(() => setFlash(""), 900);
  };

  const decide = async (decision, explicitDept) => {
    if (!token) { navigate("/login"); return; }
    const dept = explicitDept || selDept;
    if (decision === "Overridden" && !dept) {
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
          // For Denied, send no approved_department (ticket keeps current dept)
          approved_department: decision === "Overridden" ? dept
                             : decision === "Approved"   ? item.predictedDepartment
                             : undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }
      setItem((prev) => ({
        ...prev,
        status:             decision,
        approvedDepartment: decision === "Overridden" ? dept
                          : decision === "Approved"   ? prev.predictedDepartment
                          : null,
      }));
      showToast(
        decision === "Approved"   ? `✓ AI routing confirmed → ${item.predictedDepartment}`
        : decision === "Denied"   ? "✕ Routing suggestion denied. Ticket keeps its current department."
        :                           `↺ Routing overridden → ${dept}`,
        decision === "Denied" ? "error" : "success"
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
      <div className="rrd-page" onClick={() => setOverrideOpen(false)}>

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
              <div className="rrd-heroIcon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
              </div>
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
                  {/* Override — popup menu */}
                  <div className="rrd-overrideWrap">
                    <button
                      className="rrd-btnOverride"
                      type="button"
                      disabled={deciding}
                      onClick={(e) => { e.stopPropagation(); setOverrideOpen((o) => !o); }}
                    >
                      ↺ Override
                    </button>
                    {overrideOpen && (
                      <div className="rrd-overrideMenu" onClick={(e) => e.stopPropagation()}>
                        <div className="rrd-overrideMenuTitle">Override to department</div>
                        {departments.map((d) => (
                          <button
                            key={d}
                            type="button"
                            className="rrd-overrideMenuItem"
                            onClick={() => {
                              setSelDept(d);
                              setOverrideOpen(false);
                              setConfirm({ open: true, decision: "Overridden", overrideDept: d });
                            }}
                          >
                            <span className="rrd-overrideMenuDot" />{d}
                            {d === item.predictedDepartment && (
                              <span className="rrd-overrideMenuAiBadge">AI pick</span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  {/* FIX (Issue 4): Deny button — rejects the AI routing suggestion */}
                  <button
                    className="rrd-btnDeny"
                    type="button"
                    disabled={deciding}
                    onClick={() => setConfirm({ open: true, decision: "Denied" })}
                  >
                    {deciding ? "…" : "✕ Deny"}
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

              {/* Show resolved/denied banner when not pending */}
              {!isPending && (finalDept || item?.status === "Denied") && (
                <div className={`rrd-resolvedBanner${item.status === "Denied" ? " rrd-resolvedBanner--denied" : ""}`}>
                  {item.status === "Approved"   ? "✓ Confirmed →"
                   : item.status === "Denied"   ? "✕ Denied — ticket keeps current department"
                   :                              "↺ Overridden →"}{" "}
                  {finalDept && <strong>{finalDept}</strong>}
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
                <span className="rrd-cardHeaderIcon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </span>
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
                <span className="rrd-cardHeaderIcon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a7 7 0 0 1 7 7c0 3.5-2.5 5.5-3 8H8c-.5-2.5-3-4.5-3-8a7 7 0 0 1 7-7z"/><line x1="9" y1="21" x2="15" y2="21"/><line x1="10" y1="17" x2="14" y2="17"/></svg>
                </span>
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

            {/* Timeline — horizontal stepper */}
            <div className="rrd-card">
              <div className="rrd-cardHeader">
                <span className="rrd-cardHeaderIcon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </span>
                <h2 className="rrd-cardTitle">Timeline</h2>
              </div>
              <div className="rrd-stepper">
                {[
                  {
                    color: "#7c3aed",
                    title: "Review Created",
                    sub: createdAt?.toLocaleString() || "—",
                    done: true,
                  },
                  {
                    color: "#fbbf24",
                    title: "AI Routed",
                    sub: `→ ${item.predictedDepartment}`,
                    done: true,
                  },
                  {
                    color: "#f97316",
                    title: "Low Confidence",
                    sub: `${confidence.toFixed(1)}% · below 75%`,
                    done: true,
                  },
                  {
                    color: "#60a5fa",
                    title: "Sent for Review",
                    sub: "Flagged to manager",
                    done: true,
                  },
                  item.status === "Approved"
                    ? { color: "#34d399", title: "Routing Confirmed", sub: `${item.decidedBy || "Manager"} · ${decidedAt?.toLocaleString() || "—"}`, done: true }
                    : item.status === "Overridden"
                    ? { color: "#818cf8", title: "Routing Overridden", sub: `→ ${item.approvedDepartment}`, done: true }
                    : { color: "#d97706", title: "Awaiting Decision", sub: "Pending manager review", done: false, pending: true },
                ].map((step, i) => (
                  <div key={i} className="rrd-stepItem">
                    {/* connector line before (skip first) */}
                    {i > 0 && <div className={`rrd-stepLine ${step.done ? "rrd-stepLine--done" : "rrd-stepLine--pending"}`} />}
                    <div className="rrd-stepDotWrap">
                      <div
                        className={`rrd-stepDot ${step.pending ? "rrd-stepDot--pending" : ""}`}
                        style={step.pending ? {} : { background: step.color, boxShadow: `0 0 0 3px ${step.color}28` }}
                      />
                    </div>
                    <div className="rrd-stepLabel">
                      <div className="rrd-stepTitle" style={{ color: step.done && !step.pending ? step.color : undefined }}>{step.title}</div>
                      <div className="rrd-stepSub">{step.sub}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Ticket details */}
            {ticket?.details && (
              <div className="rrd-card">
                <div className="rrd-cardHeader">
                  <span className="rrd-cardHeaderIcon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                  </span>
                  <h2 className="rrd-cardTitle">Ticket Content</h2>
                </div>
                <p className="rrd-ticketDetails">{ticket.details}</p>
              </div>
            )}

            {/* Decision notes */}
            {item.decisionNotes && (
              <div className="rrd-card">
                <div className="rrd-cardHeader">
                  <span className="rrd-cardHeaderIcon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  </span>
                  <h2 className="rrd-cardTitle">Decision Notes</h2>
                </div>
                <p className="rrd-ticketDetails">{item.decisionNotes}</p>
              </div>
            )}
          </div>

          {/* RIGHT ─ ticket info + timeline */}
          <div className="rrd-rightCol">

            {/* Linked ticket — always show when we have a ticketCode */}
            {item.ticketCode && (
              <div className="rrd-sideCard">
                <h3 className="rrd-sideCardTitle">Linked Ticket</h3>
                <div className="rrd-ticketSnippetCode">{item.ticketCode}</div>
                <div className="rrd-ticketSnippetSubject">
                  {ticket?.subject || item.subject || item.ticketCode}
                </div>
                <div className="rrd-ticketSnippetMeta">
                  {(ticket?.priority || item.priority) && (
                    <span className={`rrd-priorityDot rrd-priorityDot--${((ticket?.priority || item.priority) || "").toLowerCase()}`} />
                  )}
                  {(ticket?.priority || item.priority) && (
                    <span>{ticket?.priority || item.priority}</span>
                  )}
                  {(ticket?.priority || item.priority) && <span className="rrd-dot">·</span>}
                  <span>{ticket?.status || item.status || "Pending"}</span>
                  <span className="rrd-dot">·</span>
                  <span>{ticket?.department || item.currentDepartment || item.predictedDepartment || "—"}</span>
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
        title={
          confirm.decision === "Approved"   ? "Confirm AI Routing"
          : confirm.decision === "Denied"   ? "Deny Routing Suggestion"
          :                                   "Override Routing"
        }
        message={
          confirm.decision === "Approved"
            ? `Confirm that this ticket should stay routed to "${item.predictedDepartment}"?`
            : confirm.decision === "Denied"
            ? `Deny this routing suggestion? The ticket will keep its current department assignment.`
            : `Override AI routing and assign this ticket to "${confirm.overrideDept || selDept}"?`
        }
        variant={confirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={
          confirm.decision === "Approved" ? "Yes, Confirm"
          : confirm.decision === "Denied" ? "Yes, Deny"
          :                                 "Yes, Override"
        }
        onConfirm={() => {
          const d = confirm.decision;
          const dept = confirm.overrideDept || selDept;
          closeConfirm();
          decide(d, dept);
        }}
        onCancel={closeConfirm}
      />
    </Layout>
  );
}