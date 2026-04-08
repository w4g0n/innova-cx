import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./QualityControl.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";
import {
  ALLOWED_TIME_FILTERS,
  ALLOWED_DEPARTMENTS,
  ALLOWED_QC_SECTIONS,
} from "./Operatorsanitize";

function getStoredToken() {
  const direct = localStorage.getItem("access_token") || localStorage.getItem("token") || localStorage.getItem("jwt") || localStorage.getItem("authToken");
  if (direct) return direct;
  try { const u = JSON.parse(localStorage.getItem("user") || "{}"); return u?.access_token || ""; } catch { return ""; }
}

async function apiFetch(path, params = {}) {
  const token = getStoredToken();
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  const qs = new URLSearchParams(clean).toString();
  const url = apiUrl(`/api${path}${qs ? `?${qs}` : ""}`);
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 401 || res.status === 403) { window.location.href = "/login"; throw new Error("Session expired."); }
  if (!res.ok) { const d = await res.text().catch(() => res.statusText); throw new Error(`${res.status}: ${d}`); }
  return res.json();
}

const C = { purple: "#401c51", mid: "#6b3a8a", light: "#9b71a3", pale: "#cfc3d7", green: "#22c55e", amber: "#f59e0b", red: "#ef4444", blue: "#3b82f6", text: "#1a1a2e", muted: "rgba(26,26,46,0.55)", border: "rgba(64,28,81,0.12)" };

function KpiCard({ label, value, pill, sub, flag }) {
  return (
    <article className={`ma-kpi ${flag ? `ma-kpi--${flag}` : ""}`}>
      <div className="ma-kpi__top"><span className="ma-kpi__label">{label}</span>{pill && <span className="ma-kpi__pill">{pill}</span>}</div>
      <div className="ma-kpi__value">{value}</div>
      {sub && <div className="ma-kpi__sub">{sub}</div>}
    </article>
  );
}

function Card({ title, subtitle, children, wide }) {
  return (
    <article className={`ma-card${wide ? " ma-card--wide" : ""}`}>
      <h2 className="ma-card__title">{title}</h2>
      {subtitle && <p className="ma-card__sub">{subtitle}</p>}
      {children}
    </article>
  );
}

function ProgressBar({ value, max = 100, warn, danger }) {
  const pct = Math.min((value / max) * 100, 100);
  const cls = danger && value >= danger ? "danger" : warn && value >= warn ? "warn" : "ok";
  return (
    <div className="ma-prog">
      <div className="ma-prog__track"><div className={`ma-prog__fill ma-prog__fill--${cls}`} style={{ width: `${pct}%` }} /></div>
      <span className={`ma-prog__val ma-prog__val--${cls}`}>{value.toFixed(1)}</span>
    </div>
  );
}

function EmptyState({ message = "No data for this period." }) {
  return <div className="ma-empty-state">{message}</div>;
}

function TabLoading() { return <div className="ma-tab-loading">Loading analytics…</div>; }
function TabError({ message, onRetry }) {
  return (
    <div className="ma-tab-error">
      {message}<br />
      <button type="button" className="ma-tab-error__retry" onClick={onRetry}>Retry</button>
    </div>
  );
}

const renderPctLabel = ({ percent }) => `${(percent * 100).toFixed(0)}%`;

/* DateRangePicker — wired to API via dateFrom/dateTo query params */
function DateRangePicker({ dateRange, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const fmt = (d) => d ? new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";
  const label = dateRange.from || dateRange.to ? `${fmt(dateRange.from)} → ${fmt(dateRange.to)}` : "Custom range";
  return (
    <div className="qc-datepicker" ref={ref}>
      <button type="button" className="qc-datepicker__btn" onClick={() => setOpen((v) => !v)}>
        {label}
        <span className="qc-datepicker__icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
        </span>
      </button>
      {open && (
        <div className="qc-datepicker__dropdown">
          <div className="qc-datepicker__row">
            <label className="qc-datepicker__label">From</label>
            <input type="date" className="qc-datepicker__input" value={dateRange.from || ""} onChange={(e) => onChange({ ...dateRange, from: e.target.value })} />
          </div>
          <div className="qc-datepicker__row">
            <label className="qc-datepicker__label">To</label>
            <input type="date" className="qc-datepicker__input" value={dateRange.to || ""} onChange={(e) => onChange({ ...dateRange, to: e.target.value })} />
          </div>
          <button type="button" className="qc-datepicker__clear" onClick={() => { onChange({ from: "", to: "" }); setOpen(false); }}>Clear</button>
        </div>
      )}
    </div>
  );
}

function AcceptanceView({ data, loading, error, onRetry }) {
  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} onRetry={onRetry} />;
  if (!data) return null;
  const { kpis, trend, breakdown } = data;
  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard label="Acceptance Rate" value={`${kpis.acceptanceRate}%`} pill="Period" sub="Employees used AI suggestion unchanged" />
        <KpiCard label="Declined (Custom)" value={`${kpis.declinedRate}%`} pill="Period" sub="Employee edited before submitting" flag={kpis.declinedRate > 40 ? "warn" : undefined} />
        <KpiCard label="Rejected (No Action)" value="0%" pill="Period" sub="No separate rejected status — see declined_custom" flag="neutral" />
        <KpiCard label="Total Resolutions" value={kpis.totalResolutions.toLocaleString()} pill="Period" sub="Feedback rows in ticket_resolution_feedback" />
      </div>
      <div className="ma-cards-row">
        <Card title="Acceptance Trend" subtitle="Daily accepted vs declined_custom. A week-long decline in acceptance is a model signal.">
          <div className="ma-chart-box">
            {trend.length === 0 ? <EmptyState /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={trend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 11 }} />
                  <YAxis tick={{ fill: C.muted, fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: `1px solid ${C.border}` }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="accepted" name="Accepted" stackId="a" fill={C.purple} radius={[0, 0, 0, 0]} />
                  <Bar dataKey="declined" name="Declined (Custom)" stackId="a" fill={C.pale} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card title="Acceptance vs Declined Breakdown" subtitle="Overall split for the selected period.">
          <div className="ma-chart-box">
            {(breakdown.accepted + breakdown.declined) === 0 ? <EmptyState /> : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={[{ label: "Accepted", value: breakdown.accepted }, { label: "Declined (Custom)", value: breakdown.declined }]} dataKey="value" nameKey="label" innerRadius={60} outerRadius={95} stroke="none" label={renderPctLabel} labelLine={false}>
                    <Cell fill={C.purple} /><Cell fill={C.pale} />
                  </Pie>
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 10 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function RescoringView({ data, loading, error, onRetry }) {
  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} onRetry={onRetry} />;
  if (!data) return null;
  const { kpis, byDepartment } = data;
  return (
    <div className="ma-view">
      <div className="ma-kpi-row">
        <KpiCard label="Rescore Rate" value={`${kpis.rescoreRate}%`} pill="vs model_priority" sub="Employees changed AI-assigned priority" flag={kpis.rescoreRate > 15 ? "warn" : undefined} />
        <KpiCard label="Upscores" value={kpis.upscores} pill="Period" sub="Employee raised priority above model" />
        <KpiCard label="Downscores" value={kpis.downscores} pill="Period" sub="Employee lowered priority below model" />
        <KpiCard label="Unchanged" value={`${kpis.unchanged}%`} pill="Period" sub="Model priority accepted as-is" />
      </div>
      <Card title="Rescore Direction by Department" subtitle="Upscores vs downscores per department. Consistent upscoring = model undertriages that team's tickets." wide>
        <div className="ma-chart-box">
          {byDepartment.length === 0 ? <EmptyState /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={byDepartment} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="department" tick={{ fill: C.muted, fontSize: 12 }} />
                <YAxis tick={{ fill: C.muted, fontSize: 12 }} />
                <Tooltip contentStyle={{ borderRadius: 10 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="upscored" name="Upscored" fill={C.light} radius={[4, 4, 0, 0]} />
                <Bar dataKey="downscored" name="Downscored" fill={C.purple} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  );
}

function ReroutingView({ data, loading, error, onRetry }) {
  const navigate = useNavigate();
  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} onRetry={onRetry} />;
  if (!data) return null;
  const { reassignmentByDept, reviewCases } = data;
  return (
    <div className="ma-view">
      <div className="ma-cards-row">
        <Card title="Reassignment Rate by Department" subtitle="Avg rerouting requests per ticket. Darker = higher concern. High avg = DepartmentRoutingAgent miscalibrated.">
          {reassignmentByDept.length === 0 ? <EmptyState message="No rerouting data for this period." /> : (
            <div className="ma-routing-list">
              {reassignmentByDept.map((d) => (
                <div key={d.department} className="ma-routing-row">
                  <span className="ma-routing-dept">{d.department}</span>
                  <ProgressBar value={d.avg} max={2} warn={0.5} danger={1} />
                </div>
              ))}
              <div className="ma-routing-legend">
                <span className="ma-dot ma-dot--ok" /> &lt; 0.5 &nbsp;&nbsp;
                <span className="ma-dot ma-dot--warn" /> ≥ 0.5 &nbsp;&nbsp;
                <span className="ma-dot ma-dot--danger" /> ≥ 1
              </div>
            </div>
          )}
        </Card>
        <Card title="Cases Requiring Review" subtitle="Tickets with routing or priority overrides in the selected period.">
          {reviewCases.length === 0 ? <EmptyState message="No override cases in this period." /> : (
            <div className="ma-table-wrap">
              <table className="ma-table">
                <thead><tr><th>Ticket</th><th>Date</th><th>Department</th><th>Priority</th><th>Override</th><th></th></tr></thead>
                <tbody>
                  {reviewCases.slice(0, REVIEW_CASES_PREVIEW_LIMIT).map((c) => {
                    const reason = c.humanOverridden && c.wasRescored ? "Override + Rescore" : c.humanOverridden ? "Override" : "Rescore";
                    return (
                      <tr key={c.ticketId}>
                        <td className="ma-td--code">{c.ticketCode}</td>
                        <td className="ma-td--muted">{c.createdAt ? new Date(c.createdAt).toLocaleDateString("en-GB") : "—"}</td>
                        <td>{c.department}</td>
                        <td>{c.modelPriority && c.modelPriority !== c.priority ? <span className="ma-route-text">{c.modelPriority} → {c.priority}</span> : <span>{c.priority}</span>}</td>
                        <td><span className={`ma-reason-pill ma-reason-pill--${reason.includes("Override") ? "amber" : "blue"}`}>{reason}</span></td>
                        <td><button className="ma-open-btn" type="button" onClick={() => navigate(`/operator/complaints/${c.ticketCode}`)}><span className="ma-open-btn__icon">↗</span> Open</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

const REVIEW_CASES_PREVIEW_LIMIT = 20;

/* Each tab has its own dedicated endpoint */
const QC_SECTIONS = [
  { id: "acceptance", label: "A — Acceptance", endpoint: "/operator/analytics/qc/acceptance" },
  { id: "rescoring",  label: "B — Rescoring",  endpoint: "/operator/analytics/qc/rescoring"  },
  { id: "rerouting",  label: "C — Rerouting",  endpoint: "/operator/analytics/qc/rerouting"  },
  { id: "learning",   label: "D — Learning",   endpoint: null },
];

const LEARNING_TABLES = [
  { id: "reroute",    label: "Routing Corrections",  endpoint: "/operator/learning/reroute"     },
  { id: "rescore",    label: "Priority Corrections",  endpoint: "/operator/learning/rescore"     },
  { id: "resolution", label: "Suggested Resolution",  endpoint: "/operator/learning/resolution"  },
];

const SOURCE_LABEL = {
  manager_review:         "Manager Review",
  employee_request:       "Employee Request",
  operator_override:      "Operator Override",
  manager_routing_review: "Manager Review",
  approval_rerouting:     "Employee Request",
  approval_rescoring:     "Rescoring Request",
  operator_correction:    "Operator Override",
};

const fmtDate = (ts) => ts ? new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";

function ExpandedDetail({ tableId, r }) {
  return (
    <div className="lrn-expand">
      {tableId === "reroute" && (
        <div className="lrn-io">
          <div className="lrn-io__col">
            <span className="lrn-io__label">Previous Department</span>
            <span className="lrn-io__val">{r.original_dept || "—"}</span>
          </div>
          <div className="lrn-io__arrow">→</div>
          <div className="lrn-io__col">
            <span className="lrn-io__label">New Department</span>
            <span className="lrn-io__val lrn-io__val--new">{r.corrected_dept || "—"}</span>
          </div>
          <div className="lrn-io__col lrn-io__col--right">
            <span className="lrn-io__label">Source</span>
            <span className="lrn-io__val">{SOURCE_LABEL[r.source_type] || r.source_type || "—"}</span>
          </div>
          {r.decided_by_name && (
            <div className="lrn-io__col lrn-io__col--right">
              <span className="lrn-io__label">Decided By</span>
              <span className="lrn-io__val">{r.decided_by_name}</span>
            </div>
          )}
        </div>
      )}
      {tableId === "rescore" && (
        <div className="lrn-io">
          <div className="lrn-io__col">
            <span className="lrn-io__label">Previous Priority</span>
            <span className="lrn-io__val">{r.original_priority || "—"}</span>
          </div>
          <div className="lrn-io__arrow">→</div>
          <div className="lrn-io__col">
            <span className="lrn-io__label">New Priority</span>
            <span className="lrn-io__val lrn-io__val--new">{r.corrected_priority || "—"}</span>
          </div>
          <div className="lrn-io__col lrn-io__col--right">
            <span className="lrn-io__label">Department</span>
            <span className="lrn-io__val">{r.department || "—"}</span>
          </div>
          {r.decided_by_name && (
            <div className="lrn-io__col lrn-io__col--right">
              <span className="lrn-io__label">Decided By</span>
              <span className="lrn-io__val">{r.decided_by_name}</span>
            </div>
          )}
        </div>
      )}
      {tableId === "resolution" && (
        <div className="lrn-res-io">
          <div className="lrn-res-io__col">
            <span className="lrn-io__label">Model Suggested</span>
            <p className="lrn-res-io__text">{r.suggested_text || <em>Not recorded</em>}</p>
          </div>
          <div className="lrn-res-io__col">
            <span className="lrn-io__label">Employee Final</span>
            <p className="lrn-res-io__text lrn-res-io__text--final">{r.final_text || <em>Not recorded</em>}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function RerouteRow({ r, expanded, onToggle }) {
  return (
    <div className={`lrn-row lrn-row--clickable${expanded ? " lrn-row--expanded" : ""}`} onClick={onToggle}>
      <div className="lrn-row__main">
        <span className="lrn-row__code lrn-row__code--static">{r.ticket_code || "—"}</span>
        <span className="lrn-row__change">
          {r.original_dept || "—"} <span className="lrn-arrow">→</span> {r.corrected_dept || "—"}
        </span>
        <span className="lrn-row__meta">{SOURCE_LABEL[r.source_type] || r.source_type || "—"} · {fmtDate(r.created_at)}</span>
        <span className="lrn-row__chevron">{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && <ExpandedDetail tableId="reroute" r={r} />}
    </div>
  );
}
function RescoreRow({ r, expanded, onToggle }) {
  return (
    <div className={`lrn-row lrn-row--clickable${expanded ? " lrn-row--expanded" : ""}`} onClick={onToggle}>
      <div className="lrn-row__main">
        <span className="lrn-row__code lrn-row__code--static">{r.ticket_code || "—"}</span>
        <span className="lrn-row__change">
          {r.original_priority || "—"} <span className="lrn-arrow">→</span> {r.corrected_priority || "—"}
        </span>
        <span className="lrn-row__meta">{r.department || "—"} · {fmtDate(r.created_at)}</span>
        <span className="lrn-row__chevron">{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && <ExpandedDetail tableId="rescore" r={r} />}
    </div>
  );
}
function ResolutionRow({ r, expanded, onToggle }) {
  return (
    <div className={`lrn-row lrn-row--clickable${expanded ? " lrn-row--expanded" : ""}`} onClick={onToggle}>
      <div className="lrn-row__main">
        <span className="lrn-row__code">{r.ticket_code || "—"}</span>
        <span className={`lrn-decision lrn-decision--${r.decision === "accepted" ? "green" : "amber"}`}>
          {r.decision || "—"}
        </span>
        <span className="lrn-row__meta">{r.department || "—"} · {fmtDate(r.created_at)}</span>
        <span className="lrn-row__chevron">{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && <ExpandedDetail tableId="resolution" r={r} />}
    </div>
  );
}

function FullTable({ tableId, rows, search, onSearchChange }) {
  const [expandedId, setExpandedId] = useState(null);
  const q = search.trim().toLowerCase();
  const filtered = rows.filter((r) =>
    !q ||
    (r.ticket_code || "").toLowerCase().includes(q) ||
    (r.subject || "").toLowerCase().includes(q) ||
    (r.department || "").toLowerCase().includes(q) ||
    (r.decided_by_name || r.employee_name || "").toLowerCase().includes(q)
  );

  const colCount = tableId === "reroute" ? 7 : tableId === "rescore" ? 8 : 7;

  return (
    <>
      <div className="ma-learning-search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="search" className="ma-learning-search__input" placeholder="Search…" value={search} onChange={(e) => onSearchChange(e.target.value)} />
      </div>
      {filtered.length === 0 ? <EmptyState message="No records found." /> : (
        <div className="ma-table-wrap">
          <table className="ma-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Subject</th>
                {tableId !== "reroute" && <th>Department</th>}
                {tableId === "reroute"    && <><th>From</th><th>To</th><th>Source</th><th>By</th></>}
                {tableId === "rescore"    && <><th>From</th><th>To</th><th>Source</th><th>By</th></>}
                {tableId === "resolution" && <><th>Decision</th><th>Employee</th></>}
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const isExp = expandedId === r.id;
                return (
                  <>
                    <tr key={r.id} className={`ma-tr ma-tr--clickable${isExp ? " ma-tr--expanded" : ""}`}
                        onClick={() => setExpandedId(isExp ? null : r.id)}>
                      <td className={tableId === "resolution" ? "ma-td--code" : "ma-td--ticket-static"}>{r.ticket_code || "—"}</td>
                      <td className="ma-td--subject">{r.subject || "—"}</td>
                      {tableId === "reroute" && (
                        <>
                          <td>{r.original_dept || "—"}</td>
                          <td><span className="ma-arrow-change">{r.corrected_dept || "—"}</span></td>
                          <td><span className="ma-source-pill">{SOURCE_LABEL[r.source_type] || r.source_type || "—"}</span></td>
                          <td>{r.decided_by_name || "—"}</td>
                        </>
                      )}
                      {tableId === "rescore" && (
                        <>
                          <td>{r.department || "—"}</td>
                          <td>{r.original_priority || "—"}</td>
                          <td><span className="ma-arrow-change">{r.corrected_priority || "—"}</span></td>
                          <td><span className="ma-source-pill">{SOURCE_LABEL[r.source_type] || r.source_type || "—"}</span></td>
                          <td>{r.decided_by_name || "—"}</td>
                        </>
                      )}
                      {tableId === "resolution" && (
                        <>
                          <td>{r.department || "—"}</td>
                          <td><span className={`ma-decision-pill ma-decision-pill--${r.decision === "accepted" ? "green" : "amber"}`}>{r.decision || "—"}</span></td>
                          <td>{r.employee_name || "—"}</td>
                        </>
                      )}
                      <td className="ma-td--muted">{fmtDate(r.created_at)}</td>
                    </tr>
                    {isExp && (
                      <tr key={`${r.id}-exp`} className="ma-tr-detail">
                        <td colSpan={colCount} style={{ padding: 0 }}>
                          <ExpandedDetail tableId={tableId} r={r} />
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function LearningBox({ tbl, deptFilter }) {
  const [rows,    setRows]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [modal,   setModal]   = useState(false);
  const [search,  setSearch]  = useState("");

  const [expandedId, setExpandedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = {};
      if (deptFilter && deptFilter !== "All Departments") params.department = deptFilter;
      const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([,v]) => v))).toString();
      const url = apiUrl(`/api${tbl.endpoint}${qs ? `?${qs}` : ""}`);
      const res = await fetch(url, { headers: { Authorization: `Bearer ${getStoredToken()}` } });
      if (res.status === 401 || res.status === 403) { window.location.href = "/login"; return; }
      if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => res.statusText)}`);
      setRows(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [tbl.endpoint, deptFilter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!modal) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setModal(false);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [modal]);

  const preview = rows.slice(0, 5);

  return (
    <>
      <article className="lrn-box">
        <div className="lrn-box__header">
          <h3 className="lrn-box__title">{tbl.label}</h3>
          {!loading && !error && <span className="lrn-box__count">{rows.length}</span>}
        </div>

        <div className="lrn-box__body">
          {loading ? (
            <div className="lrn-box__loading">Loading…</div>
          ) : error ? (
            <div className="lrn-box__error">{error} <button type="button" className="lrn-retry" onClick={load}>Retry</button></div>
          ) : preview.length === 0 ? (
            <div className="lrn-box__empty">No records yet</div>
          ) : (
            preview.map((r) => {
              const isExp = expandedId === r.id;
              const toggle = () => setExpandedId(isExp ? null : r.id);
              return tbl.id === "reroute"    ? <RerouteRow    key={r.id} r={r} expanded={isExp} onToggle={toggle} /> :
                     tbl.id === "rescore"    ? <RescoreRow    key={r.id} r={r} expanded={isExp} onToggle={toggle} /> :
                                               <ResolutionRow key={r.id} r={r} expanded={isExp} onToggle={toggle} />;
            })
          )}
        </div>

        {!loading && !error && rows.length > 0 && (
          <button type="button" className="lrn-box__all-btn" onClick={() => setModal(true)}>
            View all {rows.length} records →
          </button>
        )}
      </article>

      {/* Full-table modal */}
      {modal && createPortal(
        <div className="lrn-modal-backdrop" onClick={() => setModal(false)}>
          <div className="lrn-modal" role="dialog" aria-modal="true" aria-label={tbl.label} onClick={(e) => e.stopPropagation()}>
            <div className="lrn-modal__header">
              <h2 className="lrn-modal__title">{tbl.label}</h2>
              <button type="button" className="lrn-modal__close" onClick={() => setModal(false)} aria-label="Close">✕</button>
            </div>
            <div className="lrn-modal__body">
              <FullTable tableId={tbl.id} rows={rows} search={search} onSearchChange={setSearch} />
            </div>
          </div>
        </div>,
        document.body,
      )}

    </>
  );
}

function LearningView({ deptFilter }) {
  return (
    <div className="ma-view">
      <div className="lrn-grid">
        {LEARNING_TABLES.map((tbl) => (
          <LearningBox key={tbl.id} tbl={tbl} deptFilter={deptFilter} />
        ))}
      </div>
    </div>
  );
}

export default function QualityControl() {
  const revealRef = useScrollReveal();
  const [activeSection, setActiveSection] = useState("acceptance");
  const [timeFilter, setTimeFilter] = useState("last30days");
  const [deptFilter, setDeptFilter] = useState("All Departments");
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [tabData, setTabData] = useState({});
  const [tabLoading, setTabLoading] = useState({});
  const [tabError, setTabError] = useState({});

  const buildParams = useCallback(() => {
    if (dateRange.from && dateRange.to) return { dateFrom: dateRange.from, dateTo: dateRange.to, department: deptFilter };
    return { timeRange: timeFilter, department: deptFilter };
  }, [timeFilter, deptFilter, dateRange]);

  const loadTab = useCallback(async (sectionId) => {
    const section = QC_SECTIONS.find((s) => s.id === sectionId);
    if (!section) return;
    setTabLoading((p) => ({ ...p, [sectionId]: true }));
    setTabError((p) => ({ ...p, [sectionId]: null }));
    try {
      const data = await apiFetch(section.endpoint, buildParams());
      setTabData((p) => ({ ...p, [sectionId]: data }));
    } catch {
      setTabError((p) => ({ ...p, [sectionId]: "Failed to load data. Please try again." }));
    } finally {
      setTabLoading((p) => ({ ...p, [sectionId]: false }));
    }
  }, [buildParams]);

  const handleFilterChange = useCallback((setter) => (value) => { setter(value); setTabData({}); }, []);

  const handleDateRangeChange = useCallback((newRange) => {
    setDateRange(newRange);
    if ((newRange.from && newRange.to) || (!newRange.from && !newRange.to)) setTabData({});
  }, []);

  useEffect(() => { loadTab(activeSection); }, [activeSection, loadTab]);

  return (
    <Layout role="operator">
      <div className="modelAnalysis" ref={revealRef}>
        <PageHeader
          title="Quality Control"
          subtitle="Acceptance, rescoring, and rerouting analytics for InnovaCX agents."
          actions={
            <div className="ma-top-actions">
              <PillSelect value={timeFilter} onChange={handleFilterChange((v) => { if (ALLOWED_TIME_FILTERS.includes(v)) setTimeFilter(v); })} ariaLabel="Filter by time range"
                options={[{ label: "Last 7 days", value: "last7days" }, { label: "Last 30 days", value: "last30days" }, { label: "This quarter", value: "quarter" }]} />
              <PillSelect value={deptFilter} onChange={handleFilterChange((v) => { if (ALLOWED_DEPARTMENTS.includes(v)) setDeptFilter(v); })} ariaLabel="Filter by department"
                options={[{ label: "All Departments", value: "All Departments" }, { label: "Facilities Management", value: "Facilities Management" }, { label: "Legal & Compliance", value: "Legal & Compliance" }, { label: "Safety & Security", value: "Safety & Security" }, { label: "HR", value: "HR" }, { label: "Leasing", value: "Leasing" }, { label: "Maintenance", value: "Maintenance" }, { label: "IT", value: "IT" }]} />
              <DateRangePicker dateRange={dateRange} onChange={handleDateRangeChange} />
            </div>
          }
        />
        <div className="ma-nav">
          {QC_SECTIONS.map((s) => (
            <button key={s.id} className={`ma-nav__btn ${activeSection === s.id ? "ma-nav__btn--active" : ""}`}
              onClick={() => { if (ALLOWED_QC_SECTIONS.includes(s.id)) setActiveSection(s.id); }} type="button">
              {s.label}
            </button>
          ))}
        </div>
        {activeSection === "acceptance" && <AcceptanceView data={tabData.acceptance} loading={!!tabLoading.acceptance} error={tabError.acceptance} onRetry={() => loadTab("acceptance")} />}
        {activeSection === "rescoring"  && <RescoringView  data={tabData.rescoring}  loading={!!tabLoading.rescoring}  error={tabError.rescoring}  onRetry={() => loadTab("rescoring")}  />}
        {activeSection === "rerouting"  && <ReroutingView  data={tabData.rerouting}  loading={!!tabLoading.rerouting}  error={tabError.rerouting}  onRetry={() => loadTab("rerouting")}  />}
        {activeSection === "learning"   && <LearningView   deptFilter={deptFilter} />}
      </div>
    </Layout>
  );
}
