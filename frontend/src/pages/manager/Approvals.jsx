import { useMemo, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import { apiUrl } from "../../config/apiBase";
import {
  sanitizeText,
  sanitizeId,
  sanitizeSearchQuery,
  ALLOWED_SORT_KEYS,
  MAX_SEARCH_LEN,
} from "./ManagerSanitize";
import "./Approvals.css";
import useScrollReveal from "../../utils/useScrollReveal";

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

// ── Confidence bar ─────────────────────────────────────────────────────────────
function ConfidenceBar({ pct }) {
  const color = pct >= 70 ? "#16a34a" : pct >= 50 ? "#d97706" : "#dc2626";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 130 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: "rgba(0,0,0,0.08)", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: color, borderRadius: 999, transition: "width 0.6s ease" }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 40, textAlign: "right" }}>{pct.toFixed(1)}%</span>
    </div>
  );
}


// ── Value pill — parses "Priority: High" or "Dept: Facilities" ────────────────
const PRIORITY_COLORS = {
  critical: { bg: "rgba(220,38,38,0.1)",   border: "rgba(220,38,38,0.3)",   color: "#b91c1c" },
  high:     { bg: "rgba(245,158,11,0.1)",  border: "rgba(245,158,11,0.3)",  color: "#b45309" },
  medium:   { bg: "rgba(59,130,246,0.1)",  border: "rgba(59,130,246,0.25)", color: "#1d4ed8" },
  low:      { bg: "rgba(16,185,129,0.1)",  border: "rgba(16,185,129,0.25)", color: "#065f46" },
};

const PILL_W = { width: 150, minWidth: 150, maxWidth: 150, justifyContent: "center", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-flex" };

function ValuePill({ value, isRequested }) {
  if (!value) return <span style={{ color: "rgba(17,17,17,0.35)", minWidth: 110, display: "inline-flex", justifyContent: "center" }}>—</span>;

  const str = String(value).trim();
  const priorityMatch = str.match(/^Priority:\s*(.+)$/i);
  const deptMatch     = str.match(/^Dept:\s*(.+)$/i);

  if (priorityMatch) {
    const label = priorityMatch[1].trim();
    const key   = label.toLowerCase();
    const c     = PRIORITY_COLORS[key] || { bg: "rgba(107,114,128,0.1)", border: "rgba(107,114,128,0.2)", color: "#374151" };
    return (
      <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 2, width: 150 }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(17,17,17,0.4)", width: 150, textAlign: "center", display: "block" }}>Priority</span>
        <span style={{ display: "inline-flex", alignItems: "center", padding: "4px 10px", borderRadius: 999, fontSize: 12, fontWeight: 800, background: c.bg, border: `1px solid ${c.border}`, color: c.color, whiteSpace: "nowrap", ...PILL_W }}>
          {label}
        </span>
      </span>
    );
  }

  if (deptMatch) {
    const label = deptMatch[1].trim();
    return (
      <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 2, width: 150 }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(17,17,17,0.4)", width: 150, textAlign: "center", display: "block" }}>Dept</span>
        <span style={{ display: "inline-flex", alignItems: "center", padding: "4px 10px", borderRadius: 8, fontSize: 12, fontWeight: 700, background: isRequested ? "rgba(89,36,180,0.08)" : "rgba(107,114,128,0.08)", border: isRequested ? "1px solid rgba(89,36,180,0.22)" : "1px solid rgba(107,114,128,0.2)", color: isRequested ? "#5b21b6" : "#374151", whiteSpace: "nowrap", ...PILL_W }}>
          {label}
        </span>
      </span>
    );
  }

  // fallback — plain pill
  return (
    <span style={{ display: "inline-flex", alignItems: "center", padding: "4px 10px", borderRadius: 999, fontSize: 12, fontWeight: 700, background: isRequested ? "rgba(89,36,180,0.08)" : "rgba(107,114,128,0.1)", border: isRequested ? "1px solid rgba(89,36,180,0.2)" : "1px solid rgba(107,114,128,0.2)", color: isRequested ? "#5b21b6" : "#374151", ...PILL_W }}>
      {str}
    </span>
  );
}

// ── Toast system ───────────────────────────────────────────────────────────────
function ToastStack({ toasts }) {
  return (
    <div className="apr-toastStack">
      {toasts.map((t) => (
        <div key={t.id} className={`apr-toast apr-toast--${t.type}`}>
          <span className="apr-toastIcon">{t.type === "success" ? "✓" : "✕"}</span>
          {t.message}
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = "success") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200);
  }, []);
  return { toasts, push };
}

// ── Sortable column header ─────────────────────────────────────────────────────
function SortableHeader({ label, col, sortCol, sortDir, onSort, style }) {
  const active = sortCol === col;
  return (
    <th style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", ...style }} onClick={() => onSort(col)}
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
      {label}
      <span style={{ opacity: active ? 1 : 0.3, fontSize: "10px", marginLeft: 4 }}>
        {active ? (sortDir === "asc" ? " ▲" : " ▼") : " ⇅"}
      </span>
    </th>
  );
}

function useSort(defaultCol, defaultDir = "asc") {
  const [sortCol, setSortCol] = useState(defaultCol);
  const [sortDir, setSortDir] = useState(defaultDir);
  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };
  return { sortCol, sortDir, handleSort };
}

// ── Tab button ─────────────────────────────────────────────────────────────────
function TabBtn({ active, onClick, children, badge }) {
  return (
    <button type="button" className={`apr-tab ${active ? "apr-tab--active" : ""}`} onClick={onClick}>
      {children}
      {badge > 0 && <span className="apr-tabBadge">{badge > 99 ? "99+" : badge}</span>}
    </button>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function Approvals() {
  const revealRef = useScrollReveal();
  const navigate  = useNavigate();
  const { toasts, push: pushToast } = useToast();

  const [activeTab, setActiveTab] = useState("approvals"); // "approvals" | "rrq"

  // ── Approval requests state ────────────────────────────────────────────────
  const [query, setQuery]           = useState("");
  const [requestType, setRequestType] = useState("All Request Types");
  const [status, setStatus]         = useState("Pending");
  const [activeKpi, setActiveKpi]   = useState(null);
  const [rows, setRows]             = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [confirm, setConfirm]       = useState({ open: false, requestId: null, decision: null, selectedDepartment: undefined });
  const closeConfirm = () => setConfirm({ open: false, requestId: null, decision: null, selectedDepartment: undefined });
  const [aprOverride, setAprOverride] = useState({ open: false, requestId: null, type: null, overrideValue: "" });
  const closeAprOverride = () => setAprOverride({ open: false, requestId: null, type: null, overrideValue: "" });
  const [openAprOverrideFor, setOpenAprOverrideFor] = useState(null); // requestId with open popup

  const aprSort = useSort("submittedOn", "desc");

  // ── Routing review state ───────────────────────────────────────────────────
  const [rrqRows, setRrqRows]           = useState([]);
  const [rrqLoading, setRrqLoading]     = useState(true);
  const [rrqQuery, setRrqQuery]         = useState("");
  const [rrqStatus, setRrqStatus]       = useState("Pending");
  const [rrqActiveKpi, setRrqActiveKpi] = useState(null);
  const [rrqConfirm, setRrqConfirm]     = useState({ open: false, reviewId: null, decision: null, department: null });
  const closeRrqConfirm = () => setRrqConfirm({ open: false, reviewId: null, decision: null, department: null });
  const [openOverrideFor, setOpenOverrideFor] = useState(null); // reviewId of open popup

  const DEPT_FALLBACK = [
    'Facilities Management', 'Legal & Compliance', 'Safety & Security',
    'HR', 'Leasing', 'Maintenance', 'IT'
  ];

  const rrqSort = useSort("createdAt", "desc");

  const token   = getAuthToken();
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  // ── Fetch ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    setLoading(true);
    fetch(apiUrl("/api/manager/approvals"), { headers })
      .then((res) => { if (res.status === 401) navigate("/login"); return res.json(); })
      .then((data) => {
        setRows(data.map((a) => ({
          requestId:       sanitizeId(a.requestId),
          ticketId:        sanitizeId(a.ticketCode),
          ticketUuid:      sanitizeId(a.ticketId),
          type:            sanitizeText(a.type, 50),
          source:          sanitizeText(a.source || "employee", 50),
          current:         sanitizeText(a.current, 200),
          requested:       sanitizeText(a.requested, 200),
          submittedBy:     sanitizeText(a.submittedBy, 100),
          modelConfidence: a.modelConfidence,
          submittedOn:     new Date(a.submittedOn).toLocaleString(),
          submittedOnRaw:  new Date(a.submittedOn).getTime(),
          status:          sanitizeText(a.status, 50),
        })));
      })
      .catch((err) => console.error("Error fetching approvals:", err))
      .finally(() => setLoading(false));

    fetch(apiUrl("/api/manager/departments"), { headers })
      .then((res) => res.json())
      .then((data) => {
        const list = Array.isArray(data) && data.length > 0 ? data : DEPT_FALLBACK;
        setDepartments(list);
      })
      .catch(() => setDepartments(DEPT_FALLBACK));
  }, [navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRrq = useCallback(() => {
    setRrqLoading(true);
    const statusParam = rrqActiveKpi ? "All" : rrqStatus;
    fetch(apiUrl(`/api/manager/routing-review?status_filter=${statusParam}`), { headers })
      .then((r) => r.json())
      .then((d) => setRrqRows(d.items || []))
      .catch(() => setRrqRows([]))
      .finally(() => setRrqLoading(false));
  }, [rrqStatus, rrqActiveKpi]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (token) fetchRrq(); }, [fetchRrq]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── KPI totals ─────────────────────────────────────────────────────────────
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

  // ── KPI click-to-filter ────────────────────────────────────────────────────
  const handleKpiClick = (label) => {
    if (activeKpi === label) { setActiveKpi(null); setStatus("All Status"); return; }
    setActiveKpi(label);
    setStatus(label === "Pending" ? "Pending" : label === "Approved" ? "Approved" : label === "Rejected" ? "Rejected" : "All Status");
    setQuery("");
  };

  const handleRrqKpiClick = (label) => {
    if (rrqActiveKpi === label) { setRrqActiveKpi(null); return; }
    setRrqActiveKpi(label);
    setRrqQuery("");
  };

  // ── Filtering ──────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesQuery  = !q ||
        String(r.requestId  || "").toLowerCase().includes(q) ||
        String(r.ticketId   || "").toLowerCase().includes(q) ||
        String(r.ticketUuid || "").toLowerCase().includes(q) ||
        String(r.submittedBy || "").toLowerCase().includes(q);
      const matchesType   = requestType === "All Request Types" || r.type === requestType;
      const matchesStatus = activeKpi
        ? (activeKpi === "Total Requests" ? true : r.status === activeKpi)
        : (status === "All Status" || r.status === status);
      return matchesQuery && matchesType && matchesStatus;
    });
  }, [rows, query, requestType, status, activeKpi]);

  const rrqFiltered = useMemo(() => {
    const q = rrqQuery.trim().toLowerCase();
    return rrqRows.filter((r) => {
      const matchesSearch = !q || r.ticketCode?.toLowerCase().includes(q) || r.predictedDepartment?.toLowerCase().includes(q) || r.subject?.toLowerCase().includes(q);
      const matchesStatus = rrqActiveKpi
        ? (rrqActiveKpi === "Pending" ? r.status === "Pending" : rrqActiveKpi === "Confirmed" ? r.status === "Approved" : rrqActiveKpi === "Overridden" ? r.status === "Overridden" : true)
        : (rrqStatus === "All" || r.status === rrqStatus);
      return matchesSearch && matchesStatus;
    });
  }, [rrqRows, rrqQuery, rrqStatus, rrqActiveKpi]);

  // ── Sorting ────────────────────────────────────────────────────────────────
  const sortedFiltered = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let av, bv;
      switch (aprSort.sortCol) {
        case "ticketId":     av = a.ticketId || "";     bv = b.ticketId || "";     break;
        case "type":         av = a.type || "";         bv = b.type || "";         break;
        case "source":       av = a.source || "";       bv = b.source || "";       break;
        case "current":      av = a.current || "";      bv = b.current || "";      break;
        case "requested":    av = a.requested || "";    bv = b.requested || "";    break;
        case "change":       av = a.requested || "";    bv = b.requested || "";    break;
        case "submittedBy":  av = a.submittedBy || "";  bv = b.submittedBy || "";  break;
        case "submittedOn":  av = a.submittedOnRaw || 0; bv = b.submittedOnRaw || 0; break;
        case "status":       av = a.status || "";       bv = b.status || "";       break;
        case "actions":      av = a.status || "";       bv = b.status || "";       break;
        default: return 0;
      }
      if (typeof av === "number") return aprSort.sortDir === "asc" ? av - bv : bv - av;
      return aprSort.sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return arr;
  }, [filtered, aprSort.sortCol, aprSort.sortDir]);

  const sortedRrq = useMemo(() => {
    const arr = [...rrqFiltered];
    arr.sort((a, b) => {
      let av, bv;
      switch (rrqSort.sortCol) {
        case "ticketCode":           av = a.ticketCode || "";           bv = b.ticketCode || "";           break;
        case "subject":              av = a.subject || "";              bv = b.subject || "";              break;
        case "predictedDepartment":  av = a.predictedDepartment || "";  bv = b.predictedDepartment || "";  break;
        case "confidencePct":        av = a.confidencePct ?? 0;         bv = b.confidencePct ?? 0;         break;
        case "status":               av = a.status || "";               bv = b.status || "";               break;
        case "createdAt":            av = a.createdAt ? new Date(a.createdAt).getTime() : 0; bv = b.createdAt ? new Date(b.createdAt).getTime() : 0; break;
        default: return 0;
      }
      if (typeof av === "number") return rrqSort.sortDir === "asc" ? av - bv : bv - av;
      return rrqSort.sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return arr;
  }, [rrqFiltered, rrqSort.sortCol, rrqSort.sortDir]);

  // ── Actions ────────────────────────────────────────────────────────────────
  const decide = async (requestId, decision, selectedDepartment = undefined, overrideValue = undefined) => {
    if (!token) { navigate("/login"); return; }
    const safeRequestId  = sanitizeId(requestId);
    const safeOverride   = overrideValue ? sanitizeText(overrideValue, 200) : undefined;

    // Optimistically update UI
    setRows((prev) => prev.map((r) => {
      if (r.requestId !== safeRequestId) return r;
      if (safeOverride) return { ...r, status: "Overridden", overriddenValue: safeOverride };
      return { ...r, status: decision };
    }));

    try {
      const body = { decision: "Approved" };
      if (safeOverride) {
        body.override_value = safeOverride;
      } else if (decision === "Rejected") {
        body.decision = "Rejected";
      } else if (selectedDepartment) {
        // Normal reroute approve
      }

      const res = await fetch(apiUrl(`/api/manager/approvals/${encodeURIComponent(safeRequestId)}`), {
        method: "PATCH", headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`Failed (${res.status})`);
      }
      pushToast(
        safeOverride
          ? `Overridden → ${safeOverride} ✓`
          : decision === "Approved" ? "Request approved ✓" : "Request rejected",
        decision === "Rejected" ? "error" : "success"
      );
    } catch {
      setRows((prev) => prev.map((r) =>
        r.requestId === safeRequestId ? { ...r, status: "Pending", overriddenValue: undefined } : r
      ));
      pushToast("Failed to save decision. Please try again.", "error");
    }
  };

  const decideRrq = async (reviewId, decision, department) => {
    setRrqRows((prev) => prev.map((r) => (r.reviewId === reviewId ? { ...r, status: decision } : r)));
    try {
      const res = await fetch(apiUrl(`/api/manager/routing-review/${encodeURIComponent(sanitizeId(reviewId))}`), {
        method: "PATCH", headers,
        body: JSON.stringify({ decision, approved_department: sanitizeText(department, 100) || undefined }),
      });
      if (!res.ok) { throw new Error(`Failed (${res.status})`); }
      pushToast(decision === "Approved" ? "AI routing confirmed ✓" : decision === "Denied" ? "Routing request denied" : `Routing overridden → ${sanitizeText(department, 100)}`, decision === "Denied" ? "error" : "success");
    } catch {
      setRrqRows((prev) => prev.map((r) => (r.reviewId === reviewId ? { ...r, status: "Pending" } : r)));
      pushToast("Failed to save decision. Please try again.", "error");
    }
  };

  const handleReset    = () => { setQuery(""); setRequestType("All Request Types"); setStatus("Pending"); setActiveKpi(null); };
  const handleRrqReset = () => { setRrqQuery(""); setRrqStatus("Pending"); setRrqActiveKpi(null); };

  const shApr = { sortCol: aprSort.sortCol, sortDir: aprSort.sortDir, onSort: aprSort.handleSort };
  const shRrq = { sortCol: rrqSort.sortCol, sortDir: rrqSort.sortDir, onSort: rrqSort.handleSort };

  // ── JSX ────────────────────────────────────────────────────────────────────
  return (
    <Layout role="manager">
      <ToastStack toasts={toasts} />
      <div className="mgrApprovals" ref={revealRef} onClick={() => { setOpenOverrideFor(null); setOpenAprOverrideFor(null); }}>

        <PageHeader
          title="Approvals"
          subtitle="Approve or reject requests for rescoring and rerouting complaints."
        />

        {/* ── Tabs ─────────────────────────────────────────────────────────── */}
        <div className="apr-tabBar">
          <TabBtn active={activeTab === "approvals"} onClick={() => setActiveTab("approvals")} badge={totals.pending}>
            Approval Requests
          </TabBtn>
          <TabBtn active={activeTab === "rrq"} onClick={() => setActiveTab("rrq")} badge={rrqTotals.pending}>
            AI Routing Review Queue
          </TabBtn>
        </div>

        {/* ════════════════════════════════════════════════════════════════════
            TAB 1 — APPROVAL REQUESTS
        ════════════════════════════════════════════════════════════════════ */}
        {activeTab === "approvals" && (
          <div className="apr-tabContent">
            {/* KPI row — clickable */}
            <section className="kpiRow">
              {[
                { label: "Total Requests", value: loading ? "—" : totals.total,    caption: "All requests" },
                { label: "Pending",        value: loading ? "—" : totals.pending,  caption: "Awaiting decision" },
                { label: "Approved",       value: loading ? "—" : totals.approved, caption: "Approved" },
                { label: "Rejected",       value: loading ? "—" : totals.rejected, caption: "Rejected" },
              ].map(({ label, value, caption }) => (
                <div key={label} className={`apr-kpiWrap ${activeKpi === label ? "apr-kpiWrap--active" : ""}`}
                  onClick={() => handleKpiClick(label)} title={`Filter by: ${label}`}>
                  <KpiCard label={label} value={value} caption={caption} />
                </div>
              ))}
            </section>

            <section className="searchSection">
              <PillSearch value={query} onChange={(v) => { const raw = typeof v === "string" ? v : (v?.target?.value ?? ""); setQuery(sanitizeSearchQuery(raw)); }} placeholder="Search by request ID, ticket code, or employee…" maxLength={MAX_SEARCH_LEN} />
            </section>

            <section className="filtersRow">
              <div className="filtersLeft">
                <div className="pillSelectHolder">
                  <PillSelect value={requestType} onChange={(v) => { setRequestType(v); setActiveKpi(null); }} ariaLabel="Filter by request type"
                    options={[
                      { value: "All Request Types", label: "All Changes" },
                      { value: "Rescoring",         label: "Priority Rescoring" },
                      { value: "Rerouting",         label: "Department Rerouting" },
                    ]}
                  />
                </div>
                <div className="pillSelectHolder">
                  <PillSelect value={status} onChange={(v) => { setStatus(v); setActiveKpi(null); }} ariaLabel="Filter by status"
                    options={[
                      { value: "All Status", label: "All Status" },
                      { value: "Pending",    label: "Pending" },
                      { value: "Approved",   label: "Approved" },
                      { value: "Rejected",   label: "Rejected" },
                    ]}
                  />
                </div>
                <FilterPillButton onClick={handleReset} label="Reset" />
              </div>
              <span className="apr-resultCount">
                {activeKpi && <span className="apr-resultCount__kpi">{activeKpi} · </span>}
                Showing <strong>{sortedFiltered.length}</strong> of <strong>{rows.length}</strong>
              </span>
            </section>

            <section className="tableWrapper">
              <div className="trendsTableWrap">
                <table className="trendsTable">
                  <thead>
                    <tr>
                      <SortableHeader label="Ticket ID"       col="ticketId"    {...shApr} />
                      <SortableHeader label="Request Type"    col="type"        {...shApr} />
                      <SortableHeader label="Change"          col="change"      {...shApr} style={{ textAlign: "center" }} />
                      <SortableHeader label="Submitted By"    col="submittedBy" {...shApr} />
                      <SortableHeader label="Submitted On"    col="submittedOn" {...shApr} />
                      <SortableHeader label="Status"          col="status"      {...shApr} />
                      <SortableHeader label="Actions"         col="actions"     {...shApr} />
                    </tr>
                  </thead>
                  <tbody>
                    {loading && (
                      <tr><td className="emptyRow" colSpan={7} style={{ textAlign: "center", color: "rgba(17,17,17,0.45)" }}>Loading requests…</td></tr>
                    )}
                    {!loading && sortedFiltered.map((r) => (
                      <tr key={r.requestId} className="approvalRow" onClick={() => navigate(`/manager/approvals/${r.requestId}`)}>
                        <td>{r.ticketId}</td>
                        <td>
                          <span className={`apr-typePill apr-typePill--${r.type?.toLowerCase()}`}>{r.type}</span>
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <div className="apr-changeCell">
                            <ValuePill value={r.current} isRequested={false} />
                            <span className={`apr-changeArrow ${r.status === "Pending" ? "apr-changeArrow--animated" : ""}`}>
                              →
                            </span>
                            <ValuePill value={r.requested} isRequested={true} />
                          </div>
                        </td>
                        <td>{r.submittedBy}</td>
                        <td style={{ fontSize: 12, color: "rgba(17,17,17,0.6)" }}>{r.submittedOn}</td>
                        <td>
                          <span className={`statusPill ${
                            r.status === "Approved"   ? "statusPill--approved"   :
                            r.status === "Rejected"   ? "statusPill--rejected"   :
                            r.status === "Overridden" ? "statusPill--overridden" :
                            "statusPill--pending"
                          }`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="actionsCell" onClick={(e) => e.stopPropagation()}>
                          {r.status !== "Pending" ? (
                            <span className={`statusPill ${
                              r.status === "Approved"   ? "statusPill--approved"   :
                              r.status === "Rejected"   ? "statusPill--rejected"   :
                              r.status === "Overridden" ? "statusPill--overridden" :
                              "statusPill--pending"
                            }`}>
                              {r.status}{r.overriddenValue ? ` → ${r.overriddenValue}` : ""}
                            </span>
                          ) : (
                            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                              <button className="actionBtn actionBtn--primary" type="button"
                                onClick={(e) => { e.stopPropagation(); setConfirm({ open: true, requestId: r.requestId, decision: "Approved", selectedDepartment: r.type === "Rerouting" ? String(r.requested || "").replace(/^Dept:\s*/i, "").trim() : undefined }); }}>
                                ✓ Approve
                              </button>
                              <button className="actionBtn actionBtn--deny" type="button"
                                onClick={(e) => { e.stopPropagation(); setConfirm({ open: true, requestId: r.requestId, decision: "Rejected" }); }}>
                                ✕ Deny
                              </button>
                              <div className="apr-overrideWrap">
                                <button className="actionBtn" type="button"
                                  onClick={(e) => { e.stopPropagation(); setOpenAprOverrideFor((prev) => prev === r.requestId ? null : r.requestId); }}>
                                  ↺ Override
                                </button>
                                {openAprOverrideFor === r.requestId && (
                                  <div className="apr-overrideMenu" onClick={(e) => e.stopPropagation()}>
                                    {r.type === "Rescoring" ? (
                                      <>
                                        <div className="apr-overrideMenuTitle">Override priority to</div>
                                        {["Low", "Medium", "High", "Critical"].map((p) => {
                                          const currentVal = String(r.current || "").replace(/^Priority:\s*/i, "").trim();
                                          const requestedVal = String(r.requested || "").replace(/^Priority:\s*/i, "").trim();
                                          return (
                                            <button key={p} type="button" className="apr-overrideMenuItem"
                                              onClick={() => {
                                                setOpenAprOverrideFor(null);
                                                setAprOverride({ open: true, requestId: r.requestId, type: "Rescoring", overrideValue: p });
                                              }}>
                                              <span className={`apr-overrideMenuDot apr-overrideMenuDot--${p.toLowerCase()}`} />
                                              {p}
                                              {p === currentVal && <span className="apr-overrideMenuCurrentBadge">current</span>}
                                              {p === requestedVal && <span className="apr-overrideMenuAiBadge">requested</span>}
                                            </button>
                                          );
                                        })}
                                      </>
                                    ) : (
                                      <>
                                        <div className="apr-overrideMenuTitle">Override department to</div>
                                        {(departments.length > 0 ? departments : DEPT_FALLBACK).map((d) => {
                                          const currentVal = String(r.current || "").replace(/^Dept:\s*/i, "").trim();
                                          const requestedVal = String(r.requested || "").replace(/^Dept:\s*/i, "").trim();
                                          return (
                                            <button key={d} type="button" className="apr-overrideMenuItem"
                                              onClick={() => {
                                                setOpenAprOverrideFor(null);
                                                setAprOverride({ open: true, requestId: r.requestId, type: "Rerouting", overrideValue: d });
                                              }}>
                                              <span className="apr-overrideMenuDot" />
                                              {d}
                                              {d === currentVal && <span className="apr-overrideMenuCurrentBadge">current</span>}
                                              {d === requestedVal && <span className="apr-overrideMenuAiBadge">requested</span>}
                                            </button>
                                          );
                                        })}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                    {!loading && sortedFiltered.length === 0 && (
                      <tr><td className="emptyRow" colSpan={7}>No approval requests match your filters.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════════════
            TAB 2 — AI ROUTING REVIEW QUEUE
        ════════════════════════════════════════════════════════════════════ */}
        {activeTab === "rrq" && (
          <div className="apr-tabContent">

            {/* Flashy header banner */}
            <div className="rrq-heroBanner">
              <div className="rrq-heroBannerGlow" />
              <div className="rrq-heroLeft">
                <div className="rrq-heroIcon">AI</div>
                <div>
                  <h2 className="rrq-heroTitle">AI Routing Review Queue</h2>
                  <p className="rrq-heroSubtitle">
                    Tickets where AI confidence fell below threshold — confirm or override the suggested routing.
                  </p>
                </div>
              </div>
              <div className="rrq-heroKpis">
                {[
                  { label: "Pending",    value: rrqLoading ? "—" : rrqTotals.pending,    cls: "rrq-kpiVal--pending",    key: "Pending" },
                  { label: "Confirmed",  value: rrqLoading ? "—" : rrqTotals.confirmed,  cls: "rrq-kpiVal--confirmed",  key: "Confirmed" },
                  { label: "Overridden", value: rrqLoading ? "—" : rrqTotals.overridden, cls: "rrq-kpiVal--overridden", key: "Overridden" },
                ].map(({ label, value, cls, key }, i, arr) => (
                  <div key={label} className="rrq-heroKpiGroup">
                    <div
                      className={`rrq-heroKpiChip ${rrqActiveKpi === label ? "rrq-heroKpiChip--active" : ""}`}
                      onClick={() => handleRrqKpiClick(key)}
                      title={`Filter by: ${label}`}
                    >
                      <span className={`rrq-kpiVal ${cls}`}>{value}</span>
                      <span className="rrq-kpiLabel">{label}</span>
                    </div>
                    {i < arr.length - 1 && <div className="rrq-kpiDivider" />}
                  </div>
                ))}
              </div>
            </div>

            {/* Controls */}
            <section className="rrq-controls">
              <PillSearch
                value={rrqQuery}
                onChange={(v) => { const raw = typeof v === "string" ? v : (v?.target?.value ?? ""); setRrqQuery(sanitizeSearchQuery(raw)); }}
                placeholder="Search by ticket, department, or subject…"
                maxLength={MAX_SEARCH_LEN}
              />
              <div className="filtersLeft">
                <div className="pillSelectHolder">
                  <PillSelect value={rrqStatus} onChange={(v) => { setRrqStatus(v); setRrqActiveKpi(null); }} ariaLabel="Filter routing review by status"
                    options={[
                      { value: "Pending",    label: "Pending" },
                      { value: "Approved",   label: "Confirmed" },
                      { value: "Overridden", label: "Overridden" },
                      { value: "All",        label: "All" },
                    ]}
                  />
                </div>
                <FilterPillButton onClick={handleRrqReset} label="Reset" />
              </div>
              <span className="apr-resultCount">
                {rrqActiveKpi && <span className="apr-resultCount__kpi">{rrqActiveKpi} · </span>}
                Showing <strong>{sortedRrq.length}</strong> of <strong>{rrqRows.length}</strong>
              </span>
            </section>

            <section className="tableWrapper">
              <div className="trendsTableWrap">
                <table className="trendsTable">
                  <thead>
                    <tr>
                      <SortableHeader label="Ticket"          col="ticketCode"           {...shRrq} />
                      <SortableHeader label="Subject"         col="subject"              {...shRrq} />
                      <SortableHeader label="AI Suggested"    col="predictedDepartment"  {...shRrq} />
                      <SortableHeader label="Confidence"      col="confidencePct"        {...shRrq} />
                      <SortableHeader label="Status"          col="status"               {...shRrq} />
                      <SortableHeader label="Submitted"       col="createdAt"            {...shRrq} />
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rrqLoading && (
                      <tr><td className="emptyRow" colSpan={6} style={{ textAlign: "center", color: "rgba(17,17,17,0.45)" }}>Loading…</td></tr>
                    )}
                    {!rrqLoading && sortedRrq.map((r) => {
                      const isLowConf = r.confidencePct < 50;
                      return (
                        <tr key={r.reviewId} className={`approvalRow ${isLowConf && r.status === "Pending" ? "rrq-row--lowConf" : ""}`}
                          onClick={() => navigate(`/manager/routing-review/${r.reviewId}`)}>
                          <td style={{ fontWeight: 700, color: "#374151" }}>{r.ticketCode}</td>
                          <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.subject}</td>
                          <td><span className="apr-deptPill">{r.predictedDepartment}</span></td>
                          <td><ConfidenceBar pct={r.confidencePct} /></td>
                          <td>
                            <span className={`statusPill ${r.status === "Approved" ? "statusPill--approved" : r.status === "Overridden" ? "statusPill--overridden" : r.status === "Denied" ? "statusPill--denied" : "statusPill--pending"}`}>
                              {r.status === "Approved" ? "Confirmed" : r.status}
                            </span>
                          </td>
                          <td style={{ fontSize: 12, color: "rgba(17,17,17,0.55)" }}>
                            {r.createdAt ? new Date(r.createdAt).toLocaleDateString() : "—"}
                          </td>
                          <td className="actionsCell" onClick={(e) => e.stopPropagation()}>
                          {r.status === "Pending" ? (
                              <div style={{ display: "flex", gap: 6, position: "relative" }} onClick={(e) => e.stopPropagation()}>
                                <button className="actionBtn actionBtn--primary" type="button"
                                  onClick={() => setRrqConfirm({ open: true, reviewId: r.reviewId, decision: "Approved", department: r.predictedDepartment })}>
                                  ✓ Confirm
                                </button>
                                <button className="actionBtn actionBtn--deny" type="button"
                                  onClick={(e) => { e.stopPropagation(); setRrqConfirm({ open: true, reviewId: r.reviewId, decision: "Denied", department: r.predictedDepartment }); }}>
                                  ✕ Deny
                                </button>
                                <div className="apr-overrideWrap">
                                  <button className="actionBtn" type="button"
                                    onClick={(e) => { e.stopPropagation(); setOpenOverrideFor((prev) => prev === r.reviewId ? null : r.reviewId); }}>
                                    ↺ Override
                                  </button>
                                  {openOverrideFor === r.reviewId && (
                                    <div className="apr-overrideMenu" onClick={(e) => e.stopPropagation()}>
                                      <div className="apr-overrideMenuTitle">Override to department</div>
                                      {(departments.length > 0 ? departments : DEPT_FALLBACK).map((d) => (
                                        <button key={d} type="button" className="apr-overrideMenuItem"
                                          onClick={() => {
                                            setOpenOverrideFor(null);
                                            setRrqConfirm({ open: true, reviewId: r.reviewId, decision: "Overridden", department: d });
                                          }}>
                                          <span className="apr-overrideMenuDot" />
                                          {d}
                                          {d === r.predictedDepartment && (
                                            <span className="apr-overrideMenuAiBadge">AI pick</span>
                                          )}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ) : (
                              <span style={{ fontSize: 12, color: "rgba(17,17,17,0.5)", fontStyle: "italic" }}>
                                {r.status === "Approved" ? `→ ${r.approvedDepartment || r.predictedDepartment}` : r.status === "Denied" ? `✕ Denied` : `↺ ${r.approvedDepartment}`}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {!rrqLoading && sortedRrq.length === 0 && (
                      <tr>
                        <td className="emptyRow" colSpan={6}>
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
        )}
      </div>

      {/* Confirm dialogs */}
      <ConfirmDialog
        open={confirm.open}
        title={confirm.decision === "Approved" ? "Approve Request" : "Reject Request"}
        message={confirm.decision === "Approved"
          ? "Are you sure you want to approve this request? This action will apply the requested change."
          : "Are you sure you want to reject this request? This cannot be undone."}
        variant={confirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={confirm.decision === "Approved" ? "Yes, Approve" : "Yes, Reject"}
        onConfirm={() => { const { requestId, decision, selectedDepartment } = confirm; closeConfirm(); decide(requestId, decision, selectedDepartment); }}
        onCancel={closeConfirm}
      />
      <ConfirmDialog
        open={aprOverride.open}
        title={aprOverride.type === "Rescoring" ? "Override Priority" : "Override Department"}
        message={aprOverride.type === "Rescoring"
          ? `Override the requested priority and set it to "${aprOverride.overrideValue}"?`
          : `Override the requested department and assign to "${aprOverride.overrideValue}"?`}
        variant="danger"
        confirmLabel="Yes, Override"
        onConfirm={() => {
          const { requestId, overrideValue } = aprOverride;
          closeAprOverride();
          decide(requestId, "Approved", undefined, overrideValue);
        }}
        onCancel={closeAprOverride}
      />
      <ConfirmDialog
        open={rrqConfirm.open}
        title={rrqConfirm.decision === "Approved" ? "Confirm AI Routing" : rrqConfirm.decision === "Denied" ? "Deny Routing Request" : "Override Routing"}
        message={rrqConfirm.decision === "Approved"
          ? `Confirm that this ticket should be routed to "${rrqConfirm.department}"?`
          : rrqConfirm.decision === "Denied"
          ? `Deny this routing request? The ticket will keep its current department assignment.`
          : `Override AI routing and assign this ticket to "${rrqConfirm.department}"?`}
        variant={rrqConfirm.decision === "Approved" ? "success" : "danger"}
        confirmLabel={rrqConfirm.decision === "Approved" ? "Yes, Confirm" : rrqConfirm.decision === "Denied" ? "Yes, Deny" : "Yes, Override"}
        onConfirm={() => { const { reviewId, decision, department } = rrqConfirm; closeRrqConfirm(); decideRrq(reviewId, decision, department); }}
        onCancel={closeRrqConfirm}
      />
    </Layout>
  );
}