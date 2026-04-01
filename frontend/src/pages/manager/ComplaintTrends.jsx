import { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ComplaintTrends.css";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";
import { apiUrl } from "../../config/apiBase";
import { sanitizeText, ALLOWED_SORT_KEYS } from "./ManagerSanitize";
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

// ─── Tiny chart primitives ────────────────────────────────────────────────────
function MiniBar({ value, max, color = "#7c3aed", label, sub }) {
  const pct = max > 0 ? Math.max((value / max) * 100, 2) : 0;
  return (
    <div className="ct-miniBar">
      <div className="ct-miniBar__labels">
        <span className="ct-miniBar__label">{label}</span>
        <span className="ct-miniBar__sub">{sub}</span>
      </div>
      <div className="ct-miniBar__track">
        <div className="ct-miniBar__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function DualLineChart({ data, h1Key, h2Key, h1Label, h2Label, h1Color, h2Color, dayKey = "day" }) {
  if (!data || data.length === 0) return <div className="ct-empty">No data for this period.</div>;
  const allVals = data.flatMap((d) => [d[h1Key] ?? 0, d[h2Key] ?? 0]);
  const maxVal  = Math.max(...allVals, 1);
  const W = 100, H = 60;
  const pts = (key) =>
    data
      .map((d, i) => {
        const x = (i / Math.max(data.length - 1, 1)) * W;
        const y = H - ((d[key] ?? 0) / maxVal) * H;
        return `${x},${y}`;
      })
      .join(" ");
  return (
    <div className="ct-dualLine">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="ct-dualLine__svg">
        <polyline points={pts(h1Key)} fill="none" stroke={h1Color} strokeWidth="1.5" />
        <polyline points={pts(h2Key)} fill="none" stroke={h2Color} strokeWidth="1.5" strokeDasharray="3 2" />
      </svg>
      <div className="ct-dualLine__legend">
        <span style={{ color: h1Color }}>● {h1Label}</span>
        <span style={{ color: h2Color }}>● {h2Label}</span>
      </div>
      <div className="ct-dualLine__xLabels">
        {data.length <= 12
          ? data.map((d) => <span key={d[dayKey]}>{d[dayKey]?.slice(5) ?? ""}</span>)
          : [data[0], data[Math.floor(data.length / 2)], data[data.length - 1]].map((d) => (
              <span key={d[dayKey]}>{d[dayKey]?.slice(5) ?? ""}</span>
            ))}
      </div>
    </div>
  );
}

function StackedAreaChart({ data, keys, colors, totalKey = "total" }) {
  if (!data || data.length === 0) return <div className="ct-empty">No data for this period.</div>;
  const W = 100, H = 60;
  const maxVal = Math.max(...data.map((d) => d[totalKey] ?? 0), 1);
  return (
    <div className="ct-stackedArea">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="ct-stackedArea__svg">
        {[...keys].reverse().map((key, ki) => {
          const cumulativeKeys = keys.slice(0, keys.length - ki);
          const pts = data
            .map((d, i) => {
              const x = (i / Math.max(data.length - 1, 1)) * W;
              const sum = cumulativeKeys.reduce((acc, k) => acc + (d[k] ?? 0), 0);
              const y = H - (sum / maxVal) * H;
              return `${x},${y}`;
            })
            .join(" ");
          const revPts  = data
            .slice()
            .reverse()
            .map((d, i) => {
              const ri = data.length - 1 - i;
              const x  = (ri / Math.max(data.length - 1, 1)) * W;
              const prevKeys = cumulativeKeys.slice(0, -1);
              const prev = prevKeys.reduce((acc, k) => acc + (d[k] ?? 0), 0);
              const y = H - (prev / maxVal) * H;
              return `${x},${y}`;
            })
            .join(" ");
          return (
            <polygon
              key={key}
              points={`${pts} ${revPts}`}
              fill={colors[keys.indexOf(key)]}
              fillOpacity={0.35}
            />
          );
        })}
        {/* Total volume line */}
        <polyline
          points={data.map((d, i) => {
            const x = (i / Math.max(data.length - 1, 1)) * W;
            const y = H - ((d[totalKey] ?? 0) / maxVal) * H;
            return `${x},${y}`;
          }).join(" ")}
          fill="none"
          stroke="#64748b"
          strokeWidth="1"
          strokeDasharray="2 2"
        />
      </svg>
      <div className="ct-dualLine__legend">
        {keys.map((k, i) => (
          <span key={k} style={{ color: colors[i] }}>● {k}</span>
        ))}
        <span style={{ color: "#64748b" }}>– – Total</span>
      </div>
    </div>
  );
}

function Heatmap({ data }) {
  if (!data || data.length === 0) return <div className="ct-empty">No recurring issues in this period.</div>;
  const priorities = ["Critical", "High", "Medium", "Low"];
  const depts = [...new Set(data.map((d) => d.department))].sort();
  const cellMap = {};
  data.forEach((d) => { cellMap[`${d.department}__${d.priority}`] = d.count; });
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const priColor = { Critical: "#ef4444", High: "#f97316", Medium: "#eab308", Low: "#22c55e" };
  return (
    <div className="ct-heatmap">
      <table className="ct-heatmap__table">
        <thead>
          <tr>
            <th>Department</th>
            {priorities.map((p) => (
              <th key={p} style={{ color: priColor[p] }}>{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {depts.map((dept) => (
            <tr key={dept}>
              <td className="ct-heatmap__dept">{sanitizeText(dept, 100)}</td>
              {priorities.map((p) => {
                const count = cellMap[`${dept}__${p}`] || 0;
                const opacity = count ? 0.1 + (count / maxCount) * 0.85 : 0;
                return (
                  <td
                    key={p}
                    className="ct-heatmap__cell"
                    style={{ background: count ? `${priColor[p]}` : "transparent", opacity: count ? (opacity + 0.15) : 1 }}
                    title={`${dept} – ${p}: ${count} recurring`}
                  >
                    {count || "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GaugeKpi({ value, target, label, prevValue, unit = "%" }) {
  const pct = Math.min((value / Math.max(target * 2, 1)) * 100, 100);
  const isGood = unit === "%" ? value <= target : value <= target;
  const delta  = prevValue != null ? (value - prevValue) : null;
  return (
    <div className="ct-gauge">
      <div className="ct-gauge__label">{label}</div>
      <div className="ct-gauge__track">
        <div
          className="ct-gauge__fill"
          style={{
            width: `${pct}%`,
            background: isGood ? "#22c55e" : value <= target * 1.25 ? "#eab308" : "#ef4444",
          }}
        />
        <div
          className="ct-gauge__target"
          style={{ left: `${Math.min((target / Math.max(target * 2, 1)) * 100, 100)}%` }}
        />
      </div>
      <div className="ct-gauge__row">
        <span className="ct-gauge__value">{value}{unit}</span>
        <span className="ct-gauge__target-label">target: {target}{unit}</span>
        {delta != null && (
          <span className={`ct-gauge__delta ${delta <= 0 ? "pos" : "neg"}`}>
            {delta > 0 ? "+" : ""}{delta.toFixed(1)}{unit} vs prev
          </span>
        )}
      </div>
    </div>
  );
}

function EmployeeRow({ emp, teamAcceptAvg }) {
  const [open, setOpen] = useState(false);
  const alerts = [
    emp.alertHighBreach   && "High breach rate",
    emp.alertSlowResolve  && "Slow resolution",
    emp.alertLowAcceptance && "Low AI acceptance",
    emp.alertHighRescore  && "High rescore rate",
    emp.alertLowVolume    && "Low ticket volume",
  ].filter(Boolean);

  return (
    <>
      <tr
        className={`ct-empRow ${alerts.length > 0 ? "ct-empRow--alert" : ""}`}
        onClick={() => setOpen((s) => !s)}
      >
        <td className="ct-empRow__name">
          {sanitizeText(emp.name, 100)}
          {alerts.length > 0 && <span className="ct-empRow__badge">{alerts.length} alert{alerts.length > 1 ? "s" : ""}</span>}
        </td>
        <td>{sanitizeText(emp.role, 100)}</td>
        <td><strong>{emp.ticketsHandled}</strong></td>
        <td>
          <span className={emp.breachRate > 10 ? "ct-bad" : emp.breachRate > 5 ? "ct-warn" : "ct-good"}>
            {emp.breachRate}%
          </span>
          <span className="ct-dimVal"> / {emp.companyBreachRate}% avg</span>
        </td>
        <td>
          {emp.avgRespondMins > 0 ? `${Math.round(emp.avgRespondMins)} min` : "—"}
        </td>
        <td>
          <span className={emp.avgResolveMins > 480 ? "ct-bad" : emp.avgResolveMins > 240 ? "ct-warn" : "ct-good"}>
            {emp.avgResolveMins > 0 ? `${Math.round(emp.avgResolveMins / 60 * 10) / 10} hrs` : "—"}
          </span>
        </td>
        <td>
          {emp.acceptanceRate != null
            ? <span className={emp.acceptanceRate < 50 ? "ct-bad" : "ct-good"}>{emp.acceptanceRate}%</span>
            : <span className="ct-dimVal">—</span>}
        </td>
        <td>
          <span className={emp.rescoreRate > 30 ? "ct-bad" : "ct-good"}>{emp.rescoreRate}%</span>
        </td>
        <td className="ct-empRow__chevron">{open ? "▲" : "▼"}</td>
      </tr>

      {open && (
        <tr className="ct-empDetail">
          <td colSpan={9}>
            <div className="ct-empDetail__grid">
              <div className="ct-empDetail__card">
                <div className="ct-empDetail__cardTitle">SLA Breach</div>
                <div className="ct-empDetail__val ct-bad">{emp.breachRate}%</div>
                <div className="ct-empDetail__sub">Dept avg: {emp.companyBreachRate}% · Target: ≤10%</div>
              </div>
              <div className="ct-empDetail__card">
                <div className="ct-empDetail__cardTitle">Resolution Speed</div>
                <div className="ct-empDetail__val">{Math.round(emp.avgResolveMins)} min</div>
                <div className="ct-empDetail__sub">Team avg: {Math.round(emp.companyResolveMins)} min · Flag: &gt;480</div>
              </div>
              <div className="ct-empDetail__card">
                <div className="ct-empDetail__cardTitle">AI Acceptance</div>
                <div className="ct-empDetail__val">{emp.acceptanceRate != null ? `${emp.acceptanceRate}%` : "—"}</div>
                <div className="ct-empDetail__sub">
                  Accepted: {emp.acceptedCount} · Declined: {emp.declinedCount}
                  <br />Team avg: {teamAcceptAvg}%
                </div>
              </div>
              <div className="ct-empDetail__card">
                <div className="ct-empDetail__cardTitle">Priority Rescoring</div>
                <div className="ct-empDetail__val">{emp.rescoreRate}%</div>
                <div className="ct-empDetail__sub">
                  ▲ {emp.upscored} upscored · ▼ {emp.downscored} downscored
                  {emp.rescoreRate > 30 && " · ⚠ Review AI calibration"}
                </div>
              </div>
              {alerts.length > 0 && (
                <div className="ct-empDetail__card ct-empDetail__card--alerts">
                  <div className="ct-empDetail__cardTitle">Active Alerts</div>
                  {alerts.map((a) => (
                    <div key={a} className="ct-empDetail__alert">⚠ {a}</div>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
const TABS = ["Section A — Complaint Trends", "Section B — SLA Performance", "Section C — Employee Reports"];

export default function ComplaintTrends() {
  const revealRef = useScrollReveal();
  const navigate  = useNavigate();
  const [tab, setTab]           = useState(0);
  const [timeRange, setTimeRange]   = useState("Last 12 Months");
  // Initialise to empty string — overwritten once we learn the manager's dept from /api/manager
  const [department, setDepartment] = useState("");
  const [priority, setPriority]     = useState("All Priorities");
  const [apiData, setApiData]       = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);

  // Dynamic department list from /api/manager/departments
  const [deptOptions, setDeptOptions] = useState([]);
  // The logged-in manager's own department — used as the default filter
  const [myDepartment, setMyDepartment] = useState("");

  // On mount: fetch (1) manager identity to learn own dept, (2) full dept list
  useEffect(() => {
    const token = getAuthToken();
    if (!token) { navigate("/login"); return; }
    const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    // Fetch manager identity — /api/manager now returns managerName + departmentName
    fetch(apiUrl("/api/manager"), { headers })
      .then((r) => { if (r.status === 401) { navigate("/login"); return null; } return r.json(); })
      .then((data) => {
        if (!data) return;
        const dept = sanitizeText(data.departmentName || "", 100);
        setMyDepartment(dept);
        // Only set department if it hasn't been manually changed yet (still empty)
        setDepartment((prev) => prev === "" ? (dept || "All Departments") : prev);
      })
      .catch(() => {
        setDepartment("All Departments");
      });

    // Fetch real department list from DB
    fetch(apiUrl("/api/manager/departments"), { headers })
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setDeptOptions(data);
        }
      })
      .catch(() => {});
  }, [navigate]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    // Don't fetch until we know which department to default to
    if (department === "") return;
    const token = getAuthToken();
    if (!token) { navigate("/login"); return; }
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ timeRange, department, priority });
    try {
      const res = await fetch(apiUrl(`/api/manager/trends?${params}`), {
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { navigate("/login"); return; }
      if (!res.ok) throw new Error("Failed to load analytics");
      setApiData(await res.json());
    } catch (e) {
      setError("Failed to load analytics. Please try again.");
      setApiData(null);
    } finally {
      setLoading(false);
    }
  }, [timeRange, department, priority, navigate]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const B = apiData?.sectionB;
  const A = apiData?.sectionA;
  const C = apiData?.sectionC;

  // Legacy bars for Section A
  const legacyBars = useMemo(() => {
    const vals = (apiData?.bars || []).map((b) => b.value);
    const max  = Math.max(...vals, 1);
    return (apiData?.bars || []).map((b) => ({ ...b, pct: Math.round((b.value / max) * 100) }));
  }, [apiData]);

  const maxEscalation = useMemo(
    () => Math.max(...(B?.escalationByDept || []).map((d) => d.rate), 1),
    [B]
  );
  const maxBreachDept = useMemo(
    () => Math.max(...(B?.breachByDept || []).map((d) => d.breachRate), 1),
    [B]
  );

  if (loading) return <Layout role="manager"><div className="mgrTrends"><div className="ct-loading">Loading analytics…</div></div></Layout>;
  if (error)   return <Layout role="manager"><div className="mgrTrends"><div className="ct-error">{error}</div></div></Layout>;
  if (!apiData) return null;

  return (
    <Layout role="manager">
      <div className="mgrTrends" ref={revealRef}>
        <PageHeader
          title="Manager Analytics"
          subtitle="Complaint trends, SLA accountability, and employee performance."
        />

        {/* ── Global Filters ── */}
        {(() => {
          const ALLOWED_TIME_RANGES = ["Last 7 Days", "Last 30 Days", "This Month", "Last 3 Months", "Last 6 Months", "Last 12 Months"];
          const ALLOWED_PRIORITIES_TREND = ["All Priorities", "Critical", "High", "Medium", "Low"];
          const allDeptOptions = [
            "All Departments",
            ...(deptOptions.length > 0
              ? deptOptions
              : ["Safety & Security", "HR", "IT", "Leasing", "Maintenance", "Legal & Compliance", "Facilities Management"]
            ),
          ];
          return (
            <section className="filtersRow">
              <div className="filtersLeft">
                <div className="pillSelectHolder">
                  <PillSelect value={timeRange}
                    onChange={(v) => { if (ALLOWED_TIME_RANGES.includes(v)) setTimeRange(v); }}
                    ariaLabel="Time range"
                    options={ALLOWED_TIME_RANGES.map((r) => ({ value: r, label: r }))}
                  />
                  <PillSelect value={department}
                    onChange={(v) => { if (allDeptOptions.includes(v)) setDepartment(v); }}
                    ariaLabel="Department"
                    options={allDeptOptions.map((d) => ({ value: d, label: d }))}
                  />
                  <PillSelect value={priority}
                    onChange={(v) => { if (ALLOWED_PRIORITIES_TREND.includes(v)) setPriority(v); }}
                    ariaLabel="Priority"
                    options={ALLOWED_PRIORITIES_TREND.map((p) => ({ value: p, label: p }))}
                  />
                </div>
                <FilterPillButton onClick={() => { setTimeRange("Last 12 Months"); setDepartment(myDepartment || "All Departments"); setPriority("All Priorities"); }} label="Reset" />
              </div>
            </section>
          );
        })()}

        {/* ── Tabs ── */}
        <div className="ct-tabs">
          {TABS.map((t, i) => (
            <button key={t} className={`ct-tab ${tab === i ? "ct-tab--active" : ""}`} onClick={() => setTab(i)}>
              {t}
            </button>
          ))}
        </div>

        {/* ══════════════════════════════════════════════════════════════════
            SECTION A — COMPLAINT TRENDS
        ══════════════════════════════════════════════════════════════════ */}
        {tab === 0 && (
          <div className="ct-section">
            {/* A — KPI row */}
            <section className="kpiRow">
              <KpiCard label="Total Tickets" value={apiData.kpis.complaints} />
              <KpiCard label="SLA Compliance" value={apiData.kpis.sla} />
              <KpiCard label="Avg Response" value={apiData.kpis.response} />
              <KpiCard label="Avg Resolve" value={apiData.kpis.resolve} />
              <KpiCard label="Top Department" value={apiData.kpis.topCategory} />
              <KpiCard label="Repeat Rate" value={apiData.kpis.repeat} />
            </section>

            <div className="ct-grid2">
              {/* A1 — Complaint vs Inquiry */}
              <div className="card">
                <h2 className="cardTitle">Complaint vs Inquiry Volume</h2>
                <p className="ct-cardDesc">Daily count of complaints (solid) vs inquiries (dashed). Spikes indicate systemic events worth investigating.</p>
                <DualLineChart
                  data={A?.complaintVsInquiry || []}
                  h1Key="complaints" h2Key="inquiries"
                  h1Label="Complaints" h2Label="Inquiries"
                  h1Color="#7c3aed" h2Color="#06b6d4"
                />
              </div>

              {/* A2 — Daily volume with rolling avg */}
              <div className="card">
                <h2 className="cardTitle">Daily Volume + 7-Day Rolling Average</h2>
                <p className="ct-cardDesc">Bars represent daily total. The rolling line smooths noise so trend direction is clear.</p>
                <div className="ct-volBars">
                  {(A?.dailyVolume || []).map((d) => {
                    const maxV = Math.max(...(A?.dailyVolume || []).map((x) => x.count), 1);
                    return (
                      <div key={d.day} className="ct-volBar" title={`${d.day}: ${d.count}`}>
                        <div className="ct-volBar__fill" style={{ height: `${(d.count / maxV) * 100}%` }} />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* A3 — Complaint Category Breakdown */}
            <div className="card">
              <h2 className="cardTitle">Complaint Volume by Month</h2>
              <div className="trendBars">
                {legacyBars.map((b) => (
                  <div key={b.label} className="trendBar" style={{ height: `${b.pct}%` }}>
                    <span className="trendValue">{b.value}</span>
                  </div>
                ))}
              </div>
              <div className="trendLabels">
                {legacyBars.map((b) => <span key={b.label}>{b.label}</span>)}
              </div>
            </div>

            {/* A4 — Category share + Recurring heatmap */}
            <div className="ct-grid2">
              <div className="card">
                <h2 className="cardTitle">Top Complaint Categories</h2>
                <div className="categoryList">
                  {(apiData.categories || []).map((c) => (
                    <div key={c.name} className="categoryRow">
                      <span className="categoryName">{c.name}</span>
                      <div className="categoryBar">
                        <div className="categoryBarFill" style={{ width: `${c.pct}%` }} />
                      </div>
                      <span className="categoryValue">{Math.round(c.pct)}%</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h2 className="cardTitle">Recurring Issue Heatmap</h2>
                <p className="ct-cardDesc">Departments × severity. High-intensity cells = unresolved root causes needing intervention.</p>
                <Heatmap data={A?.recurringHeatmap || []} />
              </div>
            </div>

            {/* A5 — Monthly summary table */}
            <div className="card">
              <h2 className="cardTitle">Monthly Trend Summary</h2>
              <div className="trendsTableWrap">
                <table className="trendsTable">
                  <thead>
                    <tr>
                      <th>Month</th><th>Total</th><th>Resolved</th>
                      <th>Within SLA</th><th>Avg Response</th><th>Avg Resolve</th><th>Δ SLA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(apiData.table || []).map((row, i, arr) => {
                      const prev = i > 0 ? arr[i - 1].within_sla || 0 : null;
                      const curr = row.within_sla || 0;
                      const diff = prev != null ? curr - prev : null;
                      return (
                        <tr key={row.month}>
                          <td>{row.month?.trim()}</td>
                          <td>{row.total}</td>
                          <td>{row.resolved}</td>
                          <td>{row.within_sla != null ? `${row.within_sla}%` : "—"}</td>
                          <td>{row.avg_response != null ? `${row.avg_response} min` : "—"}</td>
                          <td>{row.avg_resolve != null ? `${row.avg_resolve} days` : "—"}</td>
                          <td>
                            {diff != null
                              ? <span className={diff >= 0 ? "deltaPositive" : "deltaNegative"}>{diff >= 0 ? "+" : ""}{diff}%</span>
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            SECTION B — SLA PERFORMANCE & BREACHES
        ══════════════════════════════════════════════════════════════════ */}
        {tab === 1 && B && (
          <div className="ct-section">
            {/* B1 — Headline KPIs */}
            <section className="kpiRow">
              <KpiCard label="Total Tickets" value={B.kpis.totalTickets} />
              <KpiCard label="SLA Breach Rate" value={`${B.kpis.breachRate}%`}
                caption={`${B.kpis.breachDelta >= 0 ? "+" : ""}${B.kpis.breachDelta}% vs prev period`} />
              <KpiCard label="Prev Period Breach" value={`${B.kpis.prevBreachRate}%`} />
              <KpiCard label="Escalation Rate" value={`${B.kpis.escalationRate}%`} />
              <KpiCard label="Avg Respond Time" value={`${Math.round(B.kpis.avgRespondMins)} min`} />
              <KpiCard label="Avg Resolve Time" value={`${Math.round(B.kpis.avgResolveMins / 60 * 10) / 10} hrs`} />
            </section>

            {/* B2 — Gauge row: breach + escalation */}
            <div className="card">
              <h2 className="cardTitle">SLA Accountability Gauges</h2>
              <div className="ct-gaugeRow">
                <GaugeKpi value={B.kpis.breachRate} target={10} label="Overall SLA Breach Rate"
                  prevValue={B.kpis.prevBreachRate} unit="%" />
                <GaugeKpi value={B.kpis.escalationRate} target={8} label="Escalation Rate" unit="%" />
                <GaugeKpi value={Math.round(B.kpis.avgRespondMins)} target={60}
                  label="Avg Response Time (min)" unit=" min" />
                <GaugeKpi value={Math.round(B.kpis.avgResolveMins / 60 * 10) / 10} target={18}
                  label="Avg Resolve Time (hrs)" unit=" hrs" />
              </div>
            </div>

            {/* B3 — Response & Resolve time by priority vs target */}
            <div className="card">
              <h2 className="cardTitle">Response & Resolution Time vs SLA Target — by Priority</h2>
              <p className="ct-cardDesc">Compare actual average times against SLA targets. Red = over target.</p>
              <div className="trendsTableWrap">
                <table className="trendsTable">
                  <thead>
                    <tr>
                      <th>Priority</th><th>Tickets</th>
                      <th>Avg Respond</th><th>Target Respond</th>
                      <th>Avg Resolve</th><th>Target Resolve</th>
                      <th>Respond Status</th><th>Resolve Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(B.timeByPriority || []).map((r) => (
                      <tr key={r.priority}>
                        <td><span className={`ct-priTag ct-pri--${r.priority?.toLowerCase()}`}>{r.priority}</span></td>
                        <td>{r.total}</td>
                        <td>{Math.round(r.avgRespond)} min</td>
                        <td className="ct-dimVal">{r.targetRespond} min</td>
                        <td>{Math.round(r.avgResolve / 60 * 10) / 10} hrs</td>
                        <td className="ct-dimVal">{Math.round(r.targetResolve / 60 * 10) / 10} hrs</td>
                        <td>
                          <span className={r.avgRespond <= r.targetRespond ? "ct-good" : "ct-bad"}>
                            {r.avgRespond <= r.targetRespond ? "✓ On target" : "✗ Over"}
                          </span>
                        </td>
                        <td>
                          <span className={r.avgResolve <= r.targetResolve ? "ct-good" : "ct-bad"}>
                            {r.avgResolve <= r.targetResolve ? "✓ On target" : "✗ Over"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="ct-grid2">
              {/* B4 — Breach rate by department */}
              <div className="card">
                <h2 className="cardTitle">SLA Breach Rate by Department</h2>
                <p className="ct-cardDesc">Overall breach rate per department. Bars show Critical + High as priority tier focus.</p>
                {(B.breachByDept || []).map((d) => (
                  <MiniBar key={d.department} label={d.department}
                    sub={`${d.breachRate}% breach · ${d.total} tickets`}
                    value={d.breachRate} max={maxBreachDept}
                    color={d.breachRate > 20 ? "#ef4444" : d.breachRate > 10 ? "#f97316" : "#7c3aed"} />
                ))}
              </div>

              {/* B5 — Escalation rate by department */}
              <div className="card">
                <h2 className="cardTitle">Escalation Rate by Department</h2>
                <p className="ct-cardDesc">Departments with high escalation rates need routing or staffing review.</p>
                {(B.escalationByDept || []).map((d) => (
                  <MiniBar key={d.department} label={d.department}
                    sub={`${d.rate}% · ${d.escalated} of ${d.total} escalated`}
                    value={d.rate} max={maxEscalation}
                    color={d.rate > 20 ? "#ef4444" : d.rate > 10 ? "#f97316" : "#22c55e"} />
                ))}
              </div>
            </div>

            {/* B6 — Breach timeline stacked area */}
            <div className="card">
              <h2 className="cardTitle">SLA Breach Timeline — Daily by Priority</h2>
              <p className="ct-cardDesc">Stacked areas show daily breach counts per priority tier. The dashed line is total ticket volume. If breaches rise with volume = capacity problem. If breaches rise while volume is flat = process problem.</p>
              <StackedAreaChart
                data={B.breachTimeline || []}
                keys={["Critical", "High", "Medium", "Low"]}
                colors={["#ef4444", "#f97316", "#eab308", "#22c55e"]}
              />
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            SECTION C — EMPLOYEE REPORTS
        ══════════════════════════════════════════════════════════════════ */}
        {tab === 2 && C && (
          <div className="ct-section ct-sectionC">
            {/* C1 — Team summary KPIs */}
            <section className="kpiRow">
              <KpiCard label="Employees Active" value={(C.employees || []).length} />
              <KpiCard label="Team Breach Rate" value={`${C.companyBreachRate}%`} />
              <KpiCard label="AI Accept Avg" value={`${C.teamAcceptAvg}%`} />
              <KpiCard label="Alert Flags"
                value={(C.employees || []).reduce((n, e) => n + [e.alertHighBreach, e.alertSlowResolve, e.alertLowAcceptance, e.alertHighRescore, e.alertLowVolume].filter(Boolean).length, 0)} />
            </section>

            {/* C2 — Alert threshold reference */}
            <div className="card ct-alertRef">
              <h2 className="cardTitle">Alert Threshold Reference</h2>
              <div className="trendsTableWrap">
                <table className="trendsTable">
                  <thead>
                    <tr><th>Metric</th><th>Flag Threshold</th><th>What It Likely Means</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Tickets handled</td><td>&lt;5 / period</td><td>Underutilisation or absence</td></tr>
                    <tr><td>SLA breach rate</td><td>&gt;10%</td><td>Consistent SLA failure — investigate workload or process</td></tr>
                    <tr><td>Avg resolution time</td><td>&gt;480 min</td><td>Slow resolution — check complexity mix before concluding</td></tr>
                    <tr><td>AI acceptance rate</td><td>&lt;50%</td><td>Low model trust or disengagement</td></tr>
                    <tr><td>Priority rescore rate</td><td>&gt;30%</td><td>Systematic model disagreement — worth a calibration review</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* C3 — Employee performance table with expandable rows */}
            <div className="card">
              <h2 className="cardTitle">Employee Performance — Click a row for details</h2>
              <div className="trendsTableWrap">
                <table className="trendsTable ct-empTable">
                  <thead>
                    <tr>
                      <th>Employee</th><th>Role</th><th>Tickets</th>
                      <th>Breach Rate</th><th>Avg Respond</th><th>Avg Resolve</th>
                      <th>AI Accept</th><th>Rescore Rate</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(C.employees || []).length === 0 ? (
                      <tr><td colSpan={9} className="ct-empty">No employee data for this period.</td></tr>
                    ) : (
                      (C.employees || []).map((emp) => (
                        <EmployeeRow key={emp.empId || emp.name} emp={emp} teamAcceptAvg={C.teamAcceptAvg} />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}