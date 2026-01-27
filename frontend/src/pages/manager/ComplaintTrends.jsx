import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import "./ComplaintTrends.css";

import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import FilterPillButton from "../../components/common/FilterPillButton";

export default function ComplaintTrends() {
  const [timeRange, setTimeRange] = useState("This Month");
  const [department, setDepartment] = useState("All Departments");
  const [priority, setPriority] = useState("All Priorities");

  const resetFilters = () => {
    setTimeRange("This Month");
    setDepartment("All Departments");
    setPriority("All Priorities");
  };

  // Demo dataset (so the UI actually changes with filters)
  // Keys match your dropdown values exactly.
  const data = useMemo(
    () => ({
      "This Month": {
        "All Departments": {
          "All Priorities": {
            kpis: {
              complaints: 128,
              sla: "91%",
              response: "38 mins",
              resolve: "1.6 days",
              topCategory: "HVAC Issues",
              repeat: "9%",
              complaintsCaption: "↑ 12% vs last month",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "32 tickets this month",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jun", value: 84 },
              { label: "Jul", value: 101 },
              { label: "Aug", value: 118 },
              { label: "Sep", value: 132 },
            ],
            categories: [
              { name: "HVAC / Temperature", pct: 32 },
              { name: "Plumbing / Leakage", pct: 24 },
              { name: "Cleaning / Housekeeping", pct: 17 },
              { name: "Electrical / Lighting", pct: 12 },
              { name: "Other", pct: 15 },
            ],
            table: [
              {
                month: "June",
                total: 84,
                resolved: 79,
                withinSla: "88%",
                avgResponse: "45 mins",
                avgResolve: "2.1 days",
                delta: { type: "neg", value: "- 6%" },
              },
              {
                month: "July",
                total: 101,
                resolved: 95,
                withinSla: "90%",
                avgResponse: "41 mins",
                avgResolve: "1.9 days",
                delta: { type: "pos", value: "+ 20%" },
              },
              {
                month: "August",
                total: 118,
                resolved: 110,
                withinSla: "92%",
                avgResponse: "39 mins",
                avgResolve: "1.7 days",
                delta: { type: "pos", value: "+ 17%" },
              },
              {
                month: "September",
                total: 132,
                resolved: 124,
                withinSla: "91%",
                avgResponse: "38 mins",
                avgResolve: "1.6 days",
                delta: { type: "pos", value: "+ 12%" },
              },
            ],
          },

          "Critical only": {
            kpis: {
              complaints: 34,
              sla: "89%",
              response: "42 mins",
              resolve: "1.9 days",
              topCategory: "Electrical / Lighting",
              repeat: "11%",
              complaintsCaption: "↑ 6% vs last month",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "9 tickets this month",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jun", value: 18 },
              { label: "Jul", value: 26 },
              { label: "Aug", value: 31 },
              { label: "Sep", value: 34 },
            ],
            categories: [
              { name: "Electrical / Lighting", pct: 30 },
              { name: "HVAC / Temperature", pct: 25 },
              { name: "Plumbing / Leakage", pct: 20 },
              { name: "Security", pct: 15 },
              { name: "Other", pct: 10 },
            ],
            table: [
              {
                month: "June",
                total: 18,
                resolved: 16,
                withinSla: "86%",
                avgResponse: "50 mins",
                avgResolve: "2.4 days",
                delta: { type: "neg", value: "- 3%" },
              },
              {
                month: "July",
                total: 26,
                resolved: 23,
                withinSla: "88%",
                avgResponse: "46 mins",
                avgResolve: "2.1 days",
                delta: { type: "pos", value: "+ 8%" },
              },
              {
                month: "August",
                total: 31,
                resolved: 28,
                withinSla: "90%",
                avgResponse: "43 mins",
                avgResolve: "2.0 days",
                delta: { type: "pos", value: "+ 12%" },
              },
              {
                month: "September",
                total: 34,
                resolved: 31,
                withinSla: "89%",
                avgResponse: "42 mins",
                avgResolve: "1.9 days",
                delta: { type: "pos", value: "+ 6%" },
              },
            ],
          },

          "High & Critical": {
            kpis: {
              complaints: 62,
              sla: "90%",
              response: "40 mins",
              resolve: "1.8 days",
              topCategory: "HVAC Issues",
              repeat: "10%",
              complaintsCaption: "↑ 9% vs last month",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "18 tickets this month",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jun", value: 40 },
              { label: "Jul", value: 49 },
              { label: "Aug", value: 56 },
              { label: "Sep", value: 62 },
            ],
            categories: [
              { name: "HVAC / Temperature", pct: 34 },
              { name: "Plumbing / Leakage", pct: 22 },
              { name: "Electrical / Lighting", pct: 16 },
              { name: "Cleaning / Housekeeping", pct: 14 },
              { name: "Other", pct: 14 },
            ],
            table: [
              {
                month: "June",
                total: 40,
                resolved: 36,
                withinSla: "87%",
                avgResponse: "47 mins",
                avgResolve: "2.0 days",
                delta: { type: "neg", value: "- 4%" },
              },
              {
                month: "July",
                total: 49,
                resolved: 45,
                withinSla: "89%",
                avgResponse: "43 mins",
                avgResolve: "1.9 days",
                delta: { type: "pos", value: "+ 10%" },
              },
              {
                month: "August",
                total: 56,
                resolved: 52,
                withinSla: "91%",
                avgResponse: "41 mins",
                avgResolve: "1.8 days",
                delta: { type: "pos", value: "+ 14%" },
              },
              {
                month: "September",
                total: 62,
                resolved: 58,
                withinSla: "90%",
                avgResponse: "40 mins",
                avgResolve: "1.8 days",
                delta: { type: "pos", value: "+ 9%" },
              },
            ],
          },

          "Low & Medium": {
            kpis: {
              complaints: 66,
              sla: "92%",
              response: "36 mins",
              resolve: "1.4 days",
              topCategory: "Cleaning / Housekeeping",
              repeat: "8%",
              complaintsCaption: "↑ 14% vs last month",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "21 tickets this month",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jun", value: 44 },
              { label: "Jul", value: 52 },
              { label: "Aug", value: 62 },
              { label: "Sep", value: 66 },
            ],
            categories: [
              { name: "Cleaning / Housekeeping", pct: 30 },
              { name: "HVAC / Temperature", pct: 24 },
              { name: "Plumbing / Leakage", pct: 18 },
              { name: "Electrical / Lighting", pct: 10 },
              { name: "Other", pct: 18 },
            ],
            table: [
              {
                month: "June",
                total: 44,
                resolved: 43,
                withinSla: "90%",
                avgResponse: "44 mins",
                avgResolve: "1.8 days",
                delta: { type: "neg", value: "- 2%" },
              },
              {
                month: "July",
                total: 52,
                resolved: 50,
                withinSla: "92%",
                avgResponse: "39 mins",
                avgResolve: "1.6 days",
                delta: { type: "pos", value: "+ 18%" },
              },
              {
                month: "August",
                total: 62,
                resolved: 60,
                withinSla: "93%",
                avgResponse: "37 mins",
                avgResolve: "1.5 days",
                delta: { type: "pos", value: "+ 16%" },
              },
              {
                month: "September",
                total: 66,
                resolved: 66,
                withinSla: "92%",
                avgResponse: "36 mins",
                avgResolve: "1.4 days",
                delta: { type: "pos", value: "+ 14%" },
              },
            ],
          },
        },

        // Department-specific examples (you can add more combos later)
        "IT Support": {
          "All Priorities": {
            kpis: {
              complaints: 22,
              sla: "94%",
              response: "29 mins",
              resolve: "1.2 days",
              topCategory: "Network Outages",
              repeat: "7%",
              complaintsCaption: "↑ 8% vs last month",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "6 tickets this month",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jun", value: 12 },
              { label: "Jul", value: 16 },
              { label: "Aug", value: 19 },
              { label: "Sep", value: 22 },
            ],
            categories: [
              { name: "Network Outages", pct: 28 },
              { name: "Access Requests", pct: 22 },
              { name: "Hardware", pct: 20 },
              { name: "Software", pct: 18 },
              { name: "Other", pct: 12 },
            ],
            table: [
              {
                month: "June",
                total: 12,
                resolved: 11,
                withinSla: "92%",
                avgResponse: "34 mins",
                avgResolve: "1.5 days",
                delta: { type: "pos", value: "+ 5%" },
              },
              {
                month: "July",
                total: 16,
                resolved: 15,
                withinSla: "93%",
                avgResponse: "32 mins",
                avgResolve: "1.3 days",
                delta: { type: "pos", value: "+ 9%" },
              },
              {
                month: "August",
                total: 19,
                resolved: 18,
                withinSla: "94%",
                avgResponse: "30 mins",
                avgResolve: "1.2 days",
                delta: { type: "pos", value: "+ 12%" },
              },
              {
                month: "September",
                total: 22,
                resolved: 21,
                withinSla: "94%",
                avgResponse: "29 mins",
                avgResolve: "1.2 days",
                delta: { type: "pos", value: "+ 8%" },
              },
            ],
          },
        },
      },

      // Time-range variations (example)
      "Last 3 Months": {
        "All Departments": {
          "All Priorities": {
            kpis: {
              complaints: 351,
              sla: "90%",
              response: "40 mins",
              resolve: "1.8 days",
              topCategory: "HVAC Issues",
              repeat: "10%",
              complaintsCaption: "↑ 5% vs previous period",
              slaCaption: "Target: 90%",
              responseCaption: "First agent response",
              resolveCaption: "From creation to closure",
              topCategoryCaption: "84 tickets in 3 months",
              repeatCaption: "Same issue in 30 days",
            },
            bars: [
              { label: "Jul", value: 101 },
              { label: "Aug", value: 118 },
              { label: "Sep", value: 132 },
              { label: "Oct", value: 0 }, // placeholder bar to keep layout consistent
            ],
            categories: [
              { name: "HVAC / Temperature", pct: 31 },
              { name: "Plumbing / Leakage", pct: 23 },
              { name: "Cleaning / Housekeeping", pct: 16 },
              { name: "Electrical / Lighting", pct: 14 },
              { name: "Other", pct: 16 },
            ],
            table: [
              {
                month: "July",
                total: 101,
                resolved: 95,
                withinSla: "90%",
                avgResponse: "41 mins",
                avgResolve: "1.9 days",
                delta: { type: "pos", value: "+ 20%" },
              },
              {
                month: "August",
                total: 118,
                resolved: 110,
                withinSla: "92%",
                avgResponse: "39 mins",
                avgResolve: "1.7 days",
                delta: { type: "pos", value: "+ 17%" },
              },
              {
                month: "September",
                total: 132,
                resolved: 124,
                withinSla: "91%",
                avgResponse: "38 mins",
                avgResolve: "1.6 days",
                delta: { type: "pos", value: "+ 12%" },
              },
            ],
          },
        },
      },
    }),
    []
  );

  const view = useMemo(() => {
    const byTime = data[timeRange] || data["This Month"];
    const byDept = byTime[department] || byTime["All Departments"];
    const byPriority =
      byDept[priority] || byDept["All Priorities"] || byTime["All Departments"]["All Priorities"];

    return byPriority;
  }, [data, timeRange, department, priority]);

  // Normalize bars to the same max height logic as before
  const bars = useMemo(() => {
    const values = (view?.bars || []).map((b) => b.value);
    const max = Math.max(...values, 1);
    return (view?.bars || []).map((b) => ({
      ...b,
      heightPct: `${Math.round((b.value / max) * 100)}%`,
    }));
  }, [view]);

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
            </div>

            <div className="pillSelectHolder">
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
            </div>

            <div className="pillSelectHolder">
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
          <KpiCard
            label="Complaints This Month"
            value={view.kpis.complaints}
            caption={view.kpis.complaintsCaption}
          />
          <KpiCard
            label="Resolved Within SLA"
            value={view.kpis.sla}
            caption={view.kpis.slaCaption}
          />
          <KpiCard
            label="Average Response Time"
            value={view.kpis.response}
            caption={view.kpis.responseCaption}
          />
          <KpiCard
            label="Average Resolve Time"
            value={view.kpis.resolve}
            caption={view.kpis.resolveCaption}
          />
          <KpiCard
            label="Top Category"
            value={view.kpis.topCategory}
            caption={view.kpis.topCategoryCaption}
          />
          <KpiCard
            label="Repeat Complaints"
            value={view.kpis.repeat}
            caption={view.kpis.repeatCaption}
          />
        </section>

        <section className="chartsGrid">
          <div className="card">
            <h2 className="cardTitle">Complaints Over Time</h2>
            <p className="cardSubtitle">
              Monthly volume of complaints for your department.
            </p>

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
            <p className="cardSubtitle">
              Share of complaints by type (current month).
            </p>

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
          <p className="cardSubtitle">
            Compare volumes and SLA performance month by month.
          </p>

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
                      <span className={row.delta.type === "pos" ? "deltaPositive" : "deltaNegative"}>
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
