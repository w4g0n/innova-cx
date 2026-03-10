import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import { apiUrl } from "../../config/apiBase";
import "./Approvals.css";
import useScrollReveal from "../../utils/useScrollReveal";

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

function ConfidenceBar({ pct }) {
  const color = pct >= 70 ? "#16a34a" : pct >= 50 ? "#d97706" : "#dc2626";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 999,
        background: "rgba(0,0,0,0.08)", overflow: "hidden",
      }}>
        <div style={{
          width: `${Math.min(pct, 100)}%`, height: "100%",
          background: color, borderRadius: 999, transition: "width 0.4s",
        }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 40, textAlign: "right" }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

// ─── Main Approvals page ──────────────────────────────────────────────────────
export default function Approvals() {
  const revealRef = useScrollReveal();
  const navigate = useNavigate();

  // ── Approval requests state ───────────────────────────────────────────────
  const [query, setQuery] = useState("");
  const [requestType, setRequestType] = useState("All Request Types");
  const [status, setStatus] = useState("All Status");
  const [rows, setRows] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedDepartments, setSelectedDepartments] = useState({});
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState({
    open: false, requestId: null, decision: null, selectedDepartment: undefined,
  });
  const closeConfirm = () =>
    setConfirm({ open: false, requestId: null, decision: null, selectedDepartment: undefined });

  // ── Routing review state ──────────────────────────────────────────────────
  const [rrqRows, setRrqRows]           = useState([]);
  const [rrqLoading, setRrqLoading]     = useState(true);
  const [rrqQuery, setRrqQuery]         = useState("");
  const [rrqStatus, setRrqStatus]       = useState("Pending");
  const [rrqOverrides, setRrqOverrides] = useState({});
  const [rrqConfirm, setRrqConfirm]     = useState({ open: false, reviewId: null, decision: null, department: null });
  const [rrqToast, setRrqToast]         = useState({ visible: false, message: "", type: "success" });
  const closeRrqConfirm = () => setRrqConfirm({ open: false, reviewId: null, decision: null, department: null });

  const showRrqToast = (message, type = "success") => {
    setRrqToast({ visible: true, message, type });
    setTimeout(() => setRrqToast({ visible: false, message: "", type: "success" }), 3000);
  };

  const token = getAuthToken();
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  // ── Fetch approval requests ───────────────────────────────────────────────
  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    setLoading(true);

    fetch(apiUrl("/api/manager/approvals"), { headers })
      .then((res) => {
        if (res.status === 401) navigate("/login");
        return res.json();
      })
      .then((data) => {
        const formatted = data.map((a) => ({
          requestId:       a.requestId,
          ticketId:        a.ticketCode,
          ticketUuid:      a.ticketId,
          type:            a.type,
          source:          a.source || "employee",
          current:         a.current,
          requested:       a.requested,
          submittedBy:     a.submittedBy,
          modelConfidence: a.modelConfidence,
          submittedOn:     new Date(a.submittedOn).toLocaleString(),
          status:          a.status,
        }));
        setRows(formatted);
      })
      .catch((err) => console.error("Error fetching approvals:", err))
      .finally(() => setLoading(false));

    fetch(apiUrl("/api/manager/departments"), { headers })
      .then((res) => res.json())
      .then((data) => setDepartments(Array.isArray(data) ? data : []))
      .catch(() => setDepartments([]));
  }, [navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch routing review queue ────────────────────────────────────────────
  const fetchRrq = () => {
    setRrqLoading(true);
    fetch(apiUrl(`/api/manager/routing-review?status_filter=${rrqStatus}`), { headers })
      .then((r) => r.json())
      .then((d) => setRrqRows(d.items || []))
      .catch(() => setRrqRows([]))
      .finally(() => setRrqLoading(false));
  };
  useEffect(() => { if (token) fetchRrq(); }, [rrqStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Approval request actions ──────────────────────────────────────────────
  const confirmDecide = (requestId, decision, selectedDepartment = undefined) => {
    setConfirm({ open: true, requestId, decision, selectedDepartment });
  };

  const decide = async (requestId, decision, selectedDepartment = undefined) => {
    if (!token) { navigate("/login"); return; }
    setRows((prev) =>
      prev.map((r) => (r.requestId === requestId ? { ...r, status: decision } : r))
    );
    try {
      const res = await fetch(apiUrl(`/api/manager/approvals/${requestId}`), {
        method: "PATCH",
        headers,
        body: JSON.stringify({ decision, selected_department: selectedDepartment }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }
    } catch (e) {
      setRows((prev) =>
        prev.map((r) => (r.requestId === requestId ? { ...r, status: "Pending" } : r))
      );
      alert(e.message || "Failed to save decision. Please try again.");
    }
  };

  // ── Routing review actions ────────────────────────────────────────────────
  const decideRrq = async (reviewId, decision, department) => {
    setRrqRows((prev) =>
      prev.map((r) => (r.reviewId === reviewId ? { ...r, status: decision } : r))
    );
    try {
      const res = await fetch(apiUrl(`/api/manager/routing-review/${reviewId}`), {
        method: "PATCH",
        headers,
        body: JSON.stringify({ decision, approved_department: department || undefined }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed (${res.status})`);
      }
      showRrqToast(decision === "Approved" ? "AI routing confirmed ✓" : `Routing overridden → ${department}`);
    } catch (e) {
      setRrqRows((prev) =>
        prev.map((r) => (r.reviewId === reviewId ? { ...r, status: "Pending" } : r))
      );
      showRrqToast(e.message || "Failed to save decision.", "error");
    }
  };

  // ── Filters ───────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesQuery =
        !q ||
        String(r.requestId).toLowerCase().includes(q) ||
        String(r.ticketId).toLowerCase().includes(q) ||
        String(r.submittedBy).toLowerCase().includes(q);
      const matchesType   = requestType === "All Request Types" || r.type === requestType;
      const matchesStatus = status === "All Status" || r.status === status;
      return matchesQuery && matchesType && matchesStatus;
    });
  }, [rows, query, requestType, status]);

  const rrqFiltered = useMemo(() => {
    const q = rrqQuery.trim().toLowerCase();
    return rrqRows.filter((r) =>
      !q ||
      r.ticketCode?.toLowerCase().includes(q) ||
      r.predictedDepartment?.toLowerCase().includes(q) ||
      r.subject?.toLowerCase().includes(q)
    );
  }, [rrqRows, rrqQuery]);

  const totals = useMemo(() => ({
    total:    rows.length,
    pending:  rows.filter((r) => r.status === "Pending").length,
    approved: rows.filter((r) => r.status === "Approved").length,
    rejected: rows.filter((r) => r.status === "Rejected").length,
  }), [rows]);

  const rrqTotals = useMemo(() => ({
    pending:    rrqRows.filter((r) => r.status === "Pending").length,
    confirmed:  rrqRows.filter((r) => r.status === "Approved").length,
    overridden: rrqRows.filter((r) => r.status === "Overridden").length,
  }), [rrqRows]);

  const handleReset = () => { setQuery(""); setRequestType("All Request Types"); setStatus("All Status"); };

  return (
    <Layout role="manager">
      <div className="mgrApprovals" ref={revealRef}>

        {/* ── Section 1: Approval Requests ─────────────────────────── */}
        <PageHeader
          title="Approvals"
          subtitle="Approve or reject requests for rescoring and rerouting complaints."
        />

        <section className="kpiRow">
          <KpiCard label="Total Requests" value={loading ? "—" : totals.total}    caption="All approval requests" />
          <KpiCard label="Pending"         value={loading ? "—" : totals.pending}  caption="Awaiting decision" />
          <KpiCard label="Approved"        value={loading ? "—" : totals.approved} caption="Approved by manager" />
          <KpiCard label="Rejected"        value={loading ? "—" : totals.rejected} caption="Rejected by manager" />
        </section>

        <section className="searchSection">
          <PillSearch value={query} onChange={setQuery} placeholder="Search by ID, ticket, or employee…" />
        </section>

        <section className="filtersRow">
          <div className="filtersLeft">
            <div className="pillSelectHolder">
              <PillSelect
                value={requestType} onChange={setRequestType}
                ariaLabel="Filter by request type"
                options={[
                  { value: "All Request Types", label: "All Request Types" },
                  { value: "Rescoring",          label: "Rescoring" },
                  { value: "Rerouting",          label: "Rerouting" },
                ]}
              />
            </div>
            <div className="pillSelectHolder">
              <PillSelect
                value={status} onChange={setStatus}
                ariaLabel="Filter by status"
                options={[
                  { value: "All Status", label: "All Status" },
                  { value: "Pending",    label: "Pending" },
                  { value: "Approved",   label: "Approved" },
                  { value: "Rejected",   label: "Rejected" },
                ]}
              />
            </div>
            <FilterPillButton onClick={handleReset} label="Reset">Reset</FilterPillButton>
          </div>
        </section>

        <section className="tableWrapper">
          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Ticket ID</th>
                  <th>Request Type</th>
                  <th>Source</th>
                  <th>Current</th>
                  <th>Requested Change</th>
                  <th>Submitted By</th>
                  <th>Submitted On</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td className="emptyRow" colSpan={10} style={{ textAlign: "center", color: "rgba(17,17,17,0.45)" }}>
                      Loading requests…
                    </td>
                  </tr>
                )}
                {!loading && filtered.map((r) => (
                  <tr key={r.requestId}>
                    <td>
                      <span className="requestIdLink" onClick={() => navigate(`/manager/approvals/${r.requestId}`)}>
                        {r.requestId}
                      </span>
                    </td>
                    <td>{r.ticketId}</td>
                    <td>{r.type}</td>
                    <td>
                      {r.source === "agent" ? "AI Agent" : "Employee"}
                      {r.source === "agent" && typeof r.modelConfidence === "number"
                        ? ` (${(r.modelConfidence * 100).toFixed(1)}%)` : ""}
                    </td>
                    <td>{r.current}</td>
                    <td>{r.requested}</td>
                    <td>{r.submittedBy}</td>
                    <td>{r.submittedOn}</td>
                    <td>
                      <span className={
                        r.status === "Approved" ? "statusPill statusPill--approved" :
                        r.status === "Rejected" ? "statusPill statusPill--rejected" :
                                                  "statusPill statusPill--pending"
                      }>
                        {r.status}
                      </span>
                    </td>
                    <td className="actionsCell">
                      {r.type === "Rerouting" && r.status === "Pending" && (
                        <div className="deptSelectWrap">
                          <select
                            className="deptSelect"
                            value={selectedDepartments[r.requestId] || ""}
                            onChange={(e) =>
                              setSelectedDepartments((prev) => ({ ...prev, [r.requestId]: e.target.value }))
                            }
                          >
                            <option value="">Use requested department</option>
                            {departments.map((dept) => (
                              <option key={dept} value={dept}>{dept}</option>
                            ))}
                          </select>
                        </div>
                      )}
                      <button
                        className="actionBtn actionBtn--primary"
                        type="button"
                        onClick={() => confirmDecide(
                          r.requestId, "Approved",
                          selectedDepartments[r.requestId] ||
                            (r.type === "Rerouting" ? String(r.requested || "").replace("Dept:", "").trim() : undefined)
                        )}
                        disabled={r.status !== "Pending"}
                      >
                        Approve
                      </button>
                      <button
                        className="actionBtn"
                        type="button"
                        onClick={() => confirmDecide(r.requestId, "Rejected")}
                        disabled={r.status !== "Pending"}
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}
                {!loading && filtered.length === 0 && (
                  <tr>
                    <td className="emptyRow" colSpan={10}>No approval requests match your filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Section 2: Routing Review Queue ──────────────────────── */}
        <div className="rrq-sectionHeader">
          <div className="rrq-sectionHeaderLeft">
            <div className="rrq-sectionIcon">🧭</div>
            <div>
              <h2 className="rrq-sectionTitle">Routing Review Queue</h2>
              <p className="rrq-sectionSubtitle">
                Tickets where the AI's department confidence fell below the threshold — confirm or override the suggested routing.
              </p>
            </div>
          </div>
          <div className="rrq-kpiStrip">
            <div className="rrq-kpiChip">
              <span className="rrq-kpiVal rrq-kpiVal--pending">{rrqLoading ? "—" : rrqTotals.pending}</span>
              <span className="rrq-kpiLabel">Pending</span>
            </div>
            <div className="rrq-kpiDivider" />
            <div className="rrq-kpiChip">
              <span className="rrq-kpiVal rrq-kpiVal--confirmed">{rrqLoading ? "—" : rrqTotals.confirmed}</span>
              <span className="rrq-kpiLabel">Confirmed</span>
            </div>
            <div className="rrq-kpiDivider" />
            <div className="rrq-kpiChip">
              <span className="rrq-kpiVal rrq-kpiVal--overridden">{rrqLoading ? "—" : rrqTotals.overridden}</span>
              <span className="rrq-kpiLabel">Overridden</span>
            </div>
          </div>
        </div>

        <section className="rrq-controls">
          <PillSearch
            value={rrqQuery}
            onChange={(v) => typeof v === "string" ? setRrqQuery(v) : setRrqQuery(v?.target?.value ?? "")}
            placeholder="Search by ticket, department, or subject…"
          />
          <div className="filtersLeft" style={{ marginTop: 0 }}>
            <div className="pillSelectHolder">
              <PillSelect
                value={rrqStatus} onChange={setRrqStatus}
                ariaLabel="Filter routing review by status"
                options={[
                  { value: "Pending",    label: "Pending" },
                  { value: "Approved",   label: "Confirmed" },
                  { value: "Overridden", label: "Overridden" },
                  { value: "All",        label: "All" },
                ]}
              />
            </div>
            <FilterPillButton onClick={() => { setRrqQuery(""); setRrqStatus("Pending"); }} label="Reset" />
          </div>
        </section>

        <section className="tableWrapper">
          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Review ID</th>
                  <th>Ticket</th>
                  <th>Subject</th>
                  <th>AI Suggested Dept</th>
                  <th>Confidence</th>
                  <th>Current Dept</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rrqLoading && (
                  <tr>
                    <td className="emptyRow" colSpan={9} style={{ textAlign: "center", color: "rgba(17,17,17,0.45)" }}>
                      Loading…
                    </td>
                  </tr>
                )}
                {!rrqLoading && rrqFiltered.map((r) => (
                  <tr key={r.reviewId}>
                    <td>
                      <span className="requestIdLink" onClick={() => navigate(`/manager/routing-review/${r.reviewId}`)}>
                        {String(r.reviewId).slice(0, 8)}…
                      </span>
                    </td>
                    <td>
                      <span
                        className="requestIdLink"
                        onClick={() => navigate(`/manager/complaints/${r.ticketCode}`)}
                      >
                        {r.ticketCode}
                      </span>
                    </td>
                    <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.subject}
                    </td>
                    <td style={{ fontWeight: 600 }}>{r.predictedDepartment}</td>
                    <td><ConfidenceBar pct={r.confidencePct} /></td>
                    <td>{r.currentDepartment || "—"}</td>
                    <td>
                      <span className={
                        r.status === "Approved"   ? "statusPill statusPill--approved" :
                        r.status === "Overridden" ? "statusPill statusPill--overridden" :
                                                    "statusPill statusPill--pending"
                      }>
                        {r.status === "Approved" ? "Confirmed" : r.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "rgba(17,17,17,0.55)" }}>
                      {r.createdAt ? new Date(r.createdAt).toLocaleDateString() : "—"}
                    </td>
                    <td className="actionsCell">
                      {r.status === "Pending" ? (
                        <>
                          <div className="deptSelectWrap" style={{ marginBottom: 6 }}>
                            <select
                              className="deptSelect"
                              value={rrqOverrides[r.reviewId] || ""}
                              onChange={(e) =>
                                setRrqOverrides((prev) => ({ ...prev, [r.reviewId]: e.target.value }))
                              }
                            >
                              <option value="">Override dept…</option>
                              {departments.map((d) => (
                                <option key={d} value={d}>{d}</option>
                              ))}
                            </select>
                          </div>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              className="actionBtn actionBtn--primary"
                              type="button"
                              onClick={() => setRrqConfirm({ open: true, reviewId: r.reviewId, decision: "Approved", department: r.predictedDepartment })}
                            >
                              ✓ Confirm
                            </button>
                            <button
                              className="actionBtn"
                              type="button"
                              disabled={!rrqOverrides[r.reviewId]}
                              onClick={() => setRrqConfirm({ open: true, reviewId: r.reviewId, decision: "Overridden", department: rrqOverrides[r.reviewId] })}
                            >
                              ↺ Override
                            </button>
                          </div>
                        </>
                      ) : (
                        <span style={{ fontSize: 12, color: "rgba(17,17,17,0.5)", fontStyle: "italic" }}>
                          {r.status === "Approved"
                            ? `→ ${r.approvedDepartment || r.predictedDepartment}`
                            : `↺ ${r.approvedDepartment}`}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {!rrqLoading && rrqFiltered.length === 0 && (
                  <tr>
                    <td className="emptyRow" colSpan={9}>
                      {rrqStatus === "Pending"
                        ? "No pending routing reviews — all AI decisions are above the confidence threshold."
                        : "No items match your filters."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Approval confirm dialog */}
      <ConfirmDialog
        open={confirm.open}
        title={confirm.decision === "Approved" ? "Approve Request" : "Reject Request"}
        message={
          confirm.decision === "Approved"
            ? "Are you sure you want to approve this request? This action will apply the requested change."
            : "Are you sure you want to reject this request? This cannot be undone."
        }
        variant={confirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={confirm.decision === "Approved" ? "Yes, Approve" : "Yes, Reject"}
        onConfirm={() => {
          const { requestId, decision, selectedDepartment } = confirm;
          closeConfirm();
          decide(requestId, decision, selectedDepartment);
        }}
        onCancel={closeConfirm}
      />

      {/* Routing review confirm dialog */}
      <ConfirmDialog
        open={rrqConfirm.open}
        title={rrqConfirm.decision === "Approved" ? "Confirm AI Routing" : "Override Routing"}
        message={
          rrqConfirm.decision === "Approved"
            ? `Confirm that this ticket should be routed to "${rrqConfirm.department}"?`
            : `Override AI routing and assign this ticket to "${rrqConfirm.department}"?`
        }
        variant={rrqConfirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={rrqConfirm.decision === "Approved" ? "Yes, Confirm" : "Yes, Override"}
        onConfirm={() => {
          const { reviewId, decision, department } = rrqConfirm;
          closeRrqConfirm();
          decideRrq(reviewId, decision, department);
        }}
        onCancel={closeRrqConfirm}
      />

      {/* Routing review toast */}
      <div style={{
        position: "fixed", bottom: 28, right: 28,
        background: rrqToast.type === "error" ? "#c0392b" : "#1e1e2e",
        color: "#fff", padding: "12px 20px", borderRadius: 10,
        fontSize: 14, fontWeight: 500,
        boxShadow: "0 4px 20px rgba(0,0,0,0.25)",
        display: "flex", alignItems: "center", gap: 8,
        opacity: rrqToast.visible ? 1 : 0,
        transform: rrqToast.visible ? "translateY(0)" : "translateY(12px)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
        pointerEvents: "none", zIndex: 9999,
      }}>
        <span style={{ fontSize: 16 }}>{rrqToast.type === "error" ? "❌" : "✅"}</span>
        {rrqToast.message}
      </div>
    </Layout>
  );
}