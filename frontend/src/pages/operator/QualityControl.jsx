import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./QualityControl.css";
import useScrollReveal from "../../utils/useScrollReveal";
import { apiUrl } from "../../config/apiBase";

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

function SectionHeading({ icon, label, accent }) {
  return (
    <div className={`ma-section-heading ma-section-heading--${accent}`}>
      <span className="ma-section-heading__icon">{icon}</span>
      <span className="ma-section-heading__label">{label}</span>
    </div>
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
  return <div style={{ padding: "1.5rem", color: C.muted, textAlign: "center", fontSize: 14 }}>{message}</div>;
}

function TabLoading() { return <div style={{ padding: "2rem", textAlign: "center", color: C.muted }}>Loading analytics…</div>; }
function TabError({ message, onRetry }) {
  return (
    <div style={{ padding: "2rem", textAlign: "center", color: C.red }}>
      {message}<br />
      <button type="button" style={{ marginTop: 12, cursor: "pointer" }} onClick={onRetry}>Retry</button>
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
        <span className="qc-datepicker__icon">📅</span>{label}
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

/* ── Tab views ── */
function AcceptanceView({ data, loading, error, onRetry }) {
  if (loading) return <TabLoading />;
  if (error) return <TabError message={error} onRetry={onRetry} />;
  if (!data) return null;
  const { kpis, trend, breakdown } = data;
  return (
    <div className="ma-view">
      <SectionHeading icon="🎯" label="A — Suggested Resolution Acceptance" accent="purple" />
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
      <SectionHeading icon="⚖️" label="B — Priority Rescoring" accent="amber" />
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
                <Bar dataKey="upscored" name="Upscored" fill={C.amber} radius={[4, 4, 0, 0]} />
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
      <SectionHeading icon="🔀" label="C — Department Rerouting" accent="blue" />
      <div className="ma-cards-row">
        <Card title="Reassignment Rate by Department" subtitle="Avg rerouting requests per ticket. Amber ≥ 0.5, red ≥ 1. High avg = DepartmentRoutingAgent miscalibrated.">
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
                  {reviewCases.slice(0, 20).map((c) => {
                    const reason = c.humanOverridden && c.wasRescored ? "Override + Rescore" : c.humanOverridden ? "Override" : "Rescore";
                    return (
                      <tr key={c.ticketId}>
                        <td className="ma-td--code">{c.ticketCode}</td>
                        <td className="ma-td--muted">{c.createdAt ? new Date(c.createdAt).toLocaleDateString("en-GB") : "—"}</td>
                        <td>{c.department}</td>
                        <td>{c.modelPriority && c.modelPriority !== c.priority ? <span className="ma-route-text">{c.modelPriority} → {c.priority}</span> : <span>{c.priority}</span>}</td>
                        <td><span className={`ma-reason-pill ma-reason-pill--${reason.includes("Override") ? "amber" : "blue"}`}>{reason}</span></td>
                        <td><button className="ma-link-btn" type="button" onClick={() => navigate(`/operator/complaints/${c.ticketCode}`)}><span className="ma-open-btn__icon">↗</span> Open</button></td>
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

/* Each tab has its own dedicated endpoint */
const QC_SECTIONS = [
  { id: "acceptance", label: "A — Acceptance", icon: "🎯", endpoint: "/operator/analytics/qc/acceptance" },
  { id: "rescoring",  label: "B — Rescoring",  icon: "⚖️", endpoint: "/operator/analytics/qc/rescoring"  },
  { id: "rerouting",  label: "C — Rerouting",  icon: "🔀", endpoint: "/operator/analytics/qc/rerouting"  },
];

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
    } catch (err) {
      setTabError((p) => ({ ...p, [sectionId]: err.message }));
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
              <PillSelect value={timeFilter} onChange={handleFilterChange(setTimeFilter)} ariaLabel="Filter by time range"
                options={[{ label: "Last 7 days", value: "last7days" }, { label: "Last 30 days", value: "last30days" }, { label: "This quarter", value: "quarter" }]} />
              <PillSelect value={deptFilter} onChange={handleFilterChange(setDeptFilter)} ariaLabel="Filter by department"
                options={[{ label: "All departments", value: "All Departments" }, { label: "Warehouse", value: "Warehouse" }, { label: "Office", value: "Office" }, { label: "Retail Store", value: "Retail Store" }]} />
              <DateRangePicker dateRange={dateRange} onChange={handleDateRangeChange} />
            </div>
          }
        />
        <div className="ma-nav">
          {QC_SECTIONS.map((s) => (
            <button key={s.id} className={`ma-nav__btn ${activeSection === s.id ? "ma-nav__btn--active" : ""}`} onClick={() => setActiveSection(s.id)} type="button">
              <span>{s.icon}</span> {s.label}
            </button>
          ))}
        </div>
        {activeSection === "acceptance" && <AcceptanceView data={tabData.acceptance} loading={!!tabLoading.acceptance} error={tabError.acceptance} onRetry={() => loadTab("acceptance")} />}
        {activeSection === "rescoring"  && <RescoringView  data={tabData.rescoring}  loading={!!tabLoading.rescoring}  error={tabError.rescoring}  onRetry={() => loadTab("rescoring")}  />}
        {activeSection === "rerouting"  && <ReroutingView  data={tabData.rerouting}  loading={!!tabLoading.rerouting}  error={tabError.rerouting}  onRetry={() => loadTab("rerouting")}  />}
      </div>
    </Layout>
  );
}