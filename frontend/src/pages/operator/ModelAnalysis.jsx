import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import FilterPillButton from "../../components/common/FilterPillButton";

import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import "./ModelAnalysis.css";

import operatorModelAnalysis from "../../mock-data/operatorModelAnalysis.json";

const PURPLE = "#401c51";
const LIGHT_PURPLE = "#9b71a3";
const LIGHT_GREY = "#cfc3d7";
const GREEN = "#22c55e";
const ORANGE = "#f59e0b";
const RED = "#ef4444";

export default function ModelAnalysis() {
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [timeFilter, setTimeFilter] = useState("last30days");
  const [deptFilter, setDeptFilter] = useState("all");

  useEffect(() => {
    let filteredData = operatorModelAnalysis;

    if (deptFilter !== "all") {
      filteredData = {
        ...filteredData,
        reviewCases: filteredData.reviewCases.filter(
          (c) => c.department === deptFilter
        ),
      };
    }

    setData(filteredData);
  }, [timeFilter, deptFilter]);

  const resetFilters = () => {
    setTimeFilter("last30days");
    setDeptFilter("all");
  };

  const openComplaint = (ticketId) => {
    navigate(`/operator/complaints/${ticketId}`);
  };

  if (!data) {
    return (
      <Layout role="operator">
        <div className="modelAnalysis loading-container">
          <div className="spinner"></div>
        </div>
      </Layout>
    );
  }

  const { kpis, charts: rawCharts, reviewCases } = data;

  const charts = {
    routingAccuracyByDepartment:
      rawCharts?.routingAccuracyByDepartment?.labels.map((label, idx) => ({
        department: label,
        accuracy: rawCharts.routingAccuracyByDepartment.values[idx],
        totalComplaints: rawCharts.routingAccuracyByDepartment.values[idx] * 1,
      })) || [],
    reroutedComplaints:
      rawCharts?.reroutedComplaints?.segments.map((s) => ({
        label: s.label,
        value: s.value,
      })) || [],
    priorityAccuracyByScore:
      rawCharts?.priorityAccuracyByScore?.labels.map((label, idx) => ({
        score: label,
        accuracy: rawCharts.priorityAccuracyByScore.values[idx],
      })) || [],
    rescoredComplaints:
      rawCharts?.rescoredComplaints?.labels.map((label, idx) => ({
        label,
        value: rawCharts.rescoredComplaints.values[idx],
      })) || [],
    resolutionSuggestionAdoption:
      rawCharts?.resolutionSuggestionAdoption?.labels.map((label, idx) => ({
        label,
        value: rawCharts.resolutionSuggestionAdoption.values[idx],
      })) || [],
    resolutionEffectiveness:
      rawCharts?.resolutionEffectiveness?.segments.map((s) => ({
        label: s.label,
        value: s.value,
      })) || [],
  };

  const pieColors = [PURPLE, LIGHT_PURPLE, LIGHT_GREY, GREEN, ORANGE, RED];
  const renderPieLabel = ({ percent }) => `${(percent * 100).toFixed(0)}%`;

  return (
    <Layout role="operator">
      <div className="modelAnalysis">
        <header className="top-bar">
          <PageHeader
            title="Model Performance Dashboard"
            subtitle="Routing and priority scoring accuracy for model-driven complaint handling."
          />

          <div className="top-actions">
            <div className="modelSelect">
              <PillSelect
                value={timeFilter}
                onChange={setTimeFilter}
                ariaLabel="Filter by time range"
                options={[
                  { label: "Last 7 days", value: "last7days" },
                  { label: "Last 30 days", value: "last30days" },
                  { label: "This quarter", value: "quarter" },
                ]}
              />
            </div>

            <div className="modelSelect">
              <PillSelect
                value={deptFilter}
                onChange={setDeptFilter}
                ariaLabel="Filter by department"
                options={[
                  { label: "All departments", value: "all" },
                  { label: "Billing", value: "Billing" },
                  { label: "Technical Support", value: "Technical Support" },
                  { label: "Facilities", value: "Facilities" },
                  { label: "Leasing", value: "Leasing" },
                ]}
              />
            </div>

            {/* ✅ Swapped to the same reset pill used in ManagerViewAllComplaints */}
            <div className="modelReset">
              <FilterPillButton onClick={resetFilters} label="Reset" />
            </div>
          </div>
        </header>

        <section className="kpi-row">
          {[
            {
              label: "Routing Accuracy",
              value: kpis.routingAccuracyPct,
              change: kpis.routingAccuracyChangePct,
              pill: "Target ≥ 90%",
              subtext: "Percentage of complaints routed correctly.",
            },
            {
              label: "Reroute Rate",
              value: kpis.rerouteRatePct,
              change: kpis.rerouteRateChangePct,
              pill: "Lower is better",
              subtext: "Complaints manually rerouted after model decision.",
            },
            {
              label: "Priority Accuracy",
              value: kpis.priorityAccuracyPct,
              change: kpis.priorityAccuracyChangePct,
              pill: "Target ≥ 85%",
              subtext: "Model priority vs final human score.",
            },
            {
              label: "Rescore Rate",
              value: kpis.rescoreRatePct,
              change: kpis.rescoreRateChangePct,
              pill: "Monitor",
              subtext: "Operators changed the model’s score.",
            },
          ].map((kpi, i) => (
            <article key={i} className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">{kpi.label}</span>
                <span className="kpi-pill">{kpi.pill}</span>
              </div>
              <div className="kpi-main">
                <span className="kpi-value">{kpi.value}%</span>
                <span
                  className={`kpi-change ${
                    kpi.change > 0
                      ? "kpi-positive"
                      : kpi.change < 0
                      ? "kpi-negative"
                      : "kpi-neutral"
                  }`}
                >
                  {kpi.change > 0 ? "+" : ""}
                  {kpi.change}% vs last period
                </span>
              </div>
              <p className="kpi-subtext">{kpi.subtext}</p>
            </article>
          ))}
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Routing Accuracy by Department</h2>
            <div className="routing-blocks">
              {charts.routingAccuracyByDepartment.map((d) => (
                <div key={d.department} className="routing-block">
                  <div className="routing-label-row">
                    <span className="routing-label">{d.department}</span>
                    <span className="accuracy-text">{d.accuracy}%</span>
                  </div>

                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${d.accuracy}%` }}
                    ></div>
                  </div>

                  <div className="total-complaints">
                    {d.totalComplaints} complaints
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Rerouted Complaints</h2>
            <div className="chart-inner chart-inner--short">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={charts.reroutedComplaints}
                    dataKey="value"
                    nameKey="label"
                    innerRadius={50}
                    outerRadius={80}
                    stroke="none"
                    label={renderPieLabel}
                  >
                    {charts.reroutedComplaints.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={pieColors[index % pieColors.length]}
                      />
                    ))}
                  </Pie>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Priority Accuracy by Score</h2>
            <div className="chart-inner">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={charts.priorityAccuracyByScore}>
                  <XAxis dataKey="score" stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <YAxis stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <Tooltip />
                  <Bar dataKey="accuracy" fill={PURPLE} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Rescored Complaints</h2>
            <div className="chart-inner chart-inner--short">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={charts.rescoredComplaints}>
                  <XAxis dataKey="label" stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <YAxis stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <Tooltip />
                  <Bar dataKey="value" fill={PURPLE} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Resolution Suggestion Adoption</h2>
            <div className="chart-inner">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={charts.resolutionSuggestionAdoption}>
                  <XAxis dataKey="label" stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <YAxis stroke={PURPLE} tick={{ fill: PURPLE }} />
                  <Tooltip />
                  <Bar dataKey="value" fill={PURPLE} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Resolution Effectiveness</h2>
            <div className="chart-inner chart-inner--short">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={charts.resolutionEffectiveness}
                    dataKey="value"
                    nameKey="label"
                    innerRadius={50}
                    outerRadius={80}
                    stroke="none"
                    label={renderPieLabel}
                  >
                    {charts.resolutionEffectiveness.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={pieColors[index % pieColors.length]}
                      />
                    ))}
                  </Pie>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </article>
        </section>

        <section className="card table-card">
          <h2 className="card-title">Cases Requiring Review</h2>
          <div className="table-wrapper">
            <table className="review-table">
              <thead>
                <tr>
                  <th>Ticket ID</th>
                  <th>Timestamp</th>
                  <th>Customer Type</th>
                  <th>Routing</th>
                  <th>Priority</th>
                  <th>Reason</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reviewCases.map((c) => (
                  <tr key={c.ticketId}>
                    <td>{c.ticketId}</td>
                    <td>{new Date(c.timestamp).toLocaleString()}</td>
                    <td>{c.customerType}</td>
                    <td>
                      <span className="route-change">
                        Model: {c.routing.model} → Final: {c.routing.final}
                      </span>
                    </td>
                    <td>
                      <span className="priority-change">
                        {c.priority.model} → {c.priority.final}
                      </span>
                    </td>
                    <td>
                      <span className="reason-pill">{c.reason}</span>
                    </td>
                    <td>
                      <button
                        className="link-btn"
                        onClick={() => openComplaint(c.ticketId)}
                        type="button"
                      >
                        Open complaint
                      </button>
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
