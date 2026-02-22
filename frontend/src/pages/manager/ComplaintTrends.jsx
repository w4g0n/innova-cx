import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import "./ComplaintTrends.css";

import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";

export default function ComplaintTrends() {
  const navigate = useNavigate();

  // ------------------- State -------------------
  const [timeRange, setTimeRange] = useState("This Month");
  const [department, setDepartment] = useState("All Departments");
  const [priority, setPriority] = useState("All Priorities");

  const [apiData, setApiData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ------------------- Reset Filters -------------------
  const resetFilters = () => {
    setTimeRange("This Month");
    setDepartment("All Departments");
    setPriority("All Priorities");
  };

  // ------------------- Fetch Data with Session -------------------
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
      return;
    }

    const params = new URLSearchParams({ timeRange, department, priority });

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(
          `http://localhost:8000/manager/trends?${params.toString()}`,
          {
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (res.status === 401) {
          navigate("/login");
          return;
        }
        if (!res.ok) throw new Error("Failed to load trends");

        const data = await res.json();
        setApiData(data);
      } catch (err) {
        setError(err.message);
        setApiData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [timeRange, department, priority, navigate]);

  // ------------------- Normalize Data for UI -------------------
  const view = useMemo(() => {
    if (!apiData) return null;

    const monthOrder = {
      January: 1, February: 2, March: 3, April: 4,
      May: 5, June: 6, July: 7, August: 8,
      September: 9, October: 10, November: 11, December: 12,
    };

    const sortedTable = [...apiData.table].sort(
      (a, b) => (monthOrder[a.month.trim()] || 0) - (monthOrder[b.month.trim()] || 0)
    );

    const normalizedTable = sortedTable.map((row, index, arr) => {
      const prevSla = index > 0 ? arr[index - 1].within_sla || 0 : 0;
      const currSla = row.within_sla || 0;
      const diff = currSla - prevSla;

      const delta = {
        type: diff >= 0 ? "pos" : "neg",
        value: `${diff >= 0 ? "+" : ""}${diff}%`,
      };

      return {
        month: row.month.trim(),
        total: row.total,
        resolved: row.resolved,
        withinSla: `${row.within_sla}%`,
        avgResponse: row.avg_response != null ? `${row.avg_response} mins` : "—",
        avgResolve: row.avg_resolve != null ? `${row.avg_resolve} days` : "—",
        delta,
      };
    });

    return {
      kpis: {
        complaints: apiData.kpis.complaints,
        sla: apiData.kpis.sla,
        response: apiData.kpis.response,
        resolve: apiData.kpis.resolve,
        topCategory: apiData.kpis.topCategory,
        repeat: apiData.kpis.repeat,
        complaintsCaption: "",
        slaCaption: "",
        responseCaption: "",
        resolveCaption: "",
        topCategoryCaption: "",
        repeatCaption: "",
      },
      bars: apiData.bars,
      categories: apiData.categories,
      table: normalizedTable,
    };
  }, [apiData]);

  const bars = useMemo(() => {
    const values = (view?.bars || []).map((b) => b.value);
    const max = Math.max(...values, 1);
    return (view?.bars || []).map((b) => ({
      ...b,
      heightPct: `${Math.round((b.value / max) * 100)}%`,
    }));
  }, [view]);

  // ------------------- Loading / Error -------------------
  if (loading) {
    return (
      <Layout role="manager">
        <div className="mgrTrends">Loading trends…</div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout role="manager">
        <div className="mgrTrends">{error}</div>
      </Layout>
    );
  }

  if (!view) return null;

  // ------------------- JSX -------------------
  return (
    <Layout role="manager">
      <div className="mgrTrends">
        <PageHeader
          title="Complaint Trends"
          subtitle="Track complaint volumes, resolution performance, and top categories over time."
        />

        <section className="filtersRow">
          <div className="filtersLeft">
            <div className="pillSelectHolder">
              <PillSelect
                value={timeRange}
                onChange={setTimeRange}
                ariaLabel="Filter by time range"
                options={[
                  { value: "This Month", label: "This Month" },
                  { value: "Last 3 Months", label: "Last 3 Months" },
                  { value: "Last 6 Months", label: "Last 6 Months" },
                  { value: "Last 12 Months", label: "Last 12 Months" },
                ]}
              />

              <PillSelect
                value={department}
                onChange={setDepartment}
                ariaLabel="Filter by department"
                options={[
                  { value: "All Departments", label: "All Departments" },
                  { value: "Facilities Management", label: "Facilities Management" },
                  { value: "Security", label: "Security" },
                  { value: "Cleaning", label: "Cleaning" },
                  { value: "IT Support", label: "IT Support" },
                ]}
              />

              <PillSelect
                value={priority}
                onChange={setPriority}
                ariaLabel="Filter by priority"
                options={[
                  { value: "All Priorities", label: "All Priorities" },
                  { value: "Critical only", label: "Critical only" },
                  { value: "High & Critical", label: "High & Critical" },
                  { value: "Low & Medium", label: "Low & Medium" },
                ]}
              />
            </div>

            <FilterPillButton onClick={resetFilters} label="Reset" />
          </div>
        </section>

        <section className="kpiRow">
          <KpiCard label="Complaints This Month" value={view.kpis.complaints} />
          <KpiCard label="Resolved Within SLA" value={view.kpis.sla} />
          <KpiCard label="Average Response Time" value={view.kpis.response} />
          <KpiCard label="Average Resolve Time" value={view.kpis.resolve} />
          <KpiCard label="Top Category" value={view.kpis.topCategory} />
          <KpiCard label="Repeat Complaints" value={view.kpis.repeat} />
        </section>

        <section className="chartsGrid">
          <div className="card">
            <h2 className="cardTitle">Complaints Over Time</h2>
            <div className="trendBars">
              {bars.map((b) => (
                <div key={b.label} className="trendBar" style={{ height: b.heightPct }}>
                  <span className="trendValue">{b.value}</span>
                </div>
              ))}
            </div>
            <div className="trendLabels">
              {bars.map((b) => (
                <span key={b.label}>{b.label}</span>
              ))}
            </div>
          </div>

          <aside className="card">
            <h2 className="cardTitle">Top Complaint Categories</h2>
            <div className="categoryList">
              {view.categories.map((c) => (
                <div key={c.name} className="categoryRow">
                  <span className="categoryName">{c.name}</span>
                  <div className="categoryBar">
                    <div className="categoryBarFill" style={{ width: `${c.pct}%` }} />
                  </div>
                  <span className="categoryValue">{c.pct}%</span>
                </div>
              ))}
            </div>
          </aside>
        </section>

        <section className="tableWrapper">
          <h2 className="cardTitle">Monthly Trend Summary</h2>
          <div className="trendsTableWrap">
            <table className="trendsTable">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Total Complaints</th>
                  <th>Resolved</th>
                  <th>Within SLA</th>
                  <th>Avg Response Time</th>
                  <th>Avg Resolve Time</th>
                  <th>SLA Performance</th>
                </tr>
              </thead>

              <tbody>
                {view.table.map((row) => (
                  <tr key={row.month}>
                    <td>{row.month}</td>
                    <td>{row.total}</td>
                    <td>{row.resolved}</td>
                    <td>{row.withinSla}</td>
                    <td>{row.avgResponse}</td>
                    <td>{row.avgResolve}</td>
                    <td>
                      <span
                        className={row.delta.type === "pos" ? "deltaPositive" : "deltaNegative"}
                      >
                        {row.delta.value}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}
