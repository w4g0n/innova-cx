import Layout from "../../components/Layout";
import "./ChatbotAnalysis.css";
import { useState, useEffect } from "react"; // eslint-disable-line no-unused-vars -- TODO: review - useEffect unused
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function ChatbotAnalysis() {
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState("all");

  // Chart Colors
  const pieColors = ["#401c51", "#9b71a3", "#cfc3d7"];
  const barColors = ["#401c51", "#9b71a3"]; // eslint-disable-line no-unused-vars -- TODO: review - barColors unused

  // Sample dynamic chart data (replace with Postman mock/dummy API)
  const responseTimeData = [
    { day: "Mon", value: 2.4 },
    { day: "Tue", value: 2.6 },
    { day: "Wed", value: 2.9 },
    { day: "Thu", value: 3.1 },
    { day: "Fri", value: 2.8 },
    { day: "Sat", value: 2.7 },
    { day: "Sun", value: 2.8 },
  ];

  const resolutionStatusData = [
    { name: "Fully resolved", value: 88 },
    { name: "Partially resolved", value: 7 },
    { name: "Escalated", value: 5 },
  ];

  const accuracyData = [
    { category: "Billing", value: 95 },
    { category: "Technical", value: 91 },
    { category: "Visas", value: 94 },
    { category: "Account", value: 92 },
  ];

  const dailyHandledData = [
    { day: "Mon", handled: 480, resolved: 420 },
    { day: "Tue", handled: 510, resolved: 450 },
    { day: "Wed", handled: 495, resolved: 435 },
    { day: "Thu", handled: 520, resolved: 460 },
    { day: "Fri", handled: 505, resolved: 445 },
    { day: "Sat", handled: 470, resolved: 410 },
    { day: "Sun", handled: 482, resolved: 425 },
  ];

  // Sample complaints
  const complaints = [
    {
      id: "CX-1021",
      customer: "Ahmed Ali",
      category: "Billing",
      description: "Charged twice for the same invoice.",
      timestamp: "24 Nov 2025, 16:12",
      status: "resolved",
    },
    {
      id: "CX-1044",
      customer: "Sara Khan",
      category: "Technical",
      description: "Chatbot unable to process password reset.",
      timestamp: "24 Nov 2025, 15:47",
      status: "escalated",
    },
    {
      id: "CX-1050",
      customer: "Omar Hassan",
      category: "Account",
      description: "Incorrect profile information shown.",
      timestamp: "24 Nov 2025, 14:33",
      status: "unresolved",
    },
  ];

  const filteredComplaints = complaints.filter((c) => {
    if (filter === "all") return true;
    if (filter === "resolved") return c.status === "resolved";
    if (filter === "unresolved") return c.status === "unresolved";
    if (filter === "partial") return c.status === "escalated";
    return true;
  });

  return (
    <Layout role="operator">
      <main className="main">
        {/* TOP BAR */}
        <header className="top-bar">
          <PageHeader
            title="Chatbot Performance Analytics"
            subtitle="Real-time insights into speed, accuracy, and resolution quality."
          />

          <div className="top-actions">
            <div className="chatbotSelect">
              <PillSelect
                value={"Week"}
                onChange={() => {}}
                ariaLabel="Filter by time range"
                options={[
                  { label: "Today", value: "Today" },
                  { label: "Week", value: "Week" },
                  { label: "Month", value: "Month" },
                  { label: "Year", value: "Year" },
                ]}
              />
            </div>

            <button
              className="purple-btn"
              onClick={() => setModalOpen(true)}
              type="button"
            >
              View handled Complaints
            </button>
          </div>
        </header>

        {/* KPI CARDS */}
        <section className="kpi-row">
          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Average Response Time</span>
              <span className="kpi-pill">Seconds</span>
            </div>
            <div className="kpi-value">2.8s</div>
            <div className="kpi-change negative">+12% slower vs last period</div>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Overall Accuracy</span>
              <span className="kpi-pill">Classification</span>
            </div>
            <div className="kpi-value">93%</div>
            <div className="kpi-change positive">+3% vs last period</div>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Resolution Rate</span>
              <span className="kpi-pill">Fully Handled</span>
            </div>
            <div className="kpi-value">88%</div>
            <div className="kpi-change positive">+5% vs last period</div>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Total Inquiries</span>
              <span className="kpi-pill">Conversations</span>
            </div>
            <div className="kpi-value">3,462</div>
            <div className="kpi-change neutral">vs 3,410 last period</div>
          </article>
        </section>

        {/* CHARTS ROW */}
        <section className="charts-row">
          {/* Response Time Line Chart */}
          <article className="card">
            <h2 className="card-title">Response Time Trend</h2>
            <p className="card-subtitle">
              Average response time by day for the selected period.
            </p>
            <div className="chart-inner">
              <LineChart width={650} height={350} data={responseTimeData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ textAnchor: "middle" }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#401c51" strokeWidth={3} dot={true} />
              </LineChart>
            </div>
          </article>

          {/* Resolution Status Pie Chart */}
          <article className="card">
            <h2 className="card-title">Inquiry Resolution Status</h2>
            <p className="card-subtitle">
              Distribution of fully resolved, partially resolved, and escalated cases.
            </p>
            <div className="chart-inner">
              <PieChart width={650} height={350}>
                <Pie
                  data={resolutionStatusData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={120}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  isAnimationActive={true}
                >
                  {resolutionStatusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Legend verticalAlign="bottom" />
                <Tooltip />
              </PieChart>
            </div>
          </article>
        </section>

        {/* Charts Row 2 */}
        <section className="charts-row">
          {/* Accuracy Bar Chart */}
          <article className="card">
            <h2 className="card-title">Accuracy by Category</h2>
            <p className="card-subtitle">
              Chatbot classification accuracy across key inquiry types.
            </p>
            <div className="chart-inner">
              <BarChart width={650} height={350} data={accuracyData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="category" tick={{ textAnchor: "middle" }} />
                <YAxis />
                <Tooltip />
                <Legend verticalAlign="bottom" />
                <Bar dataKey="value" fill="#401c51" isAnimationActive={true} />
              </BarChart>
            </div>
          </article>

          {/* Daily Handled vs Resolved */}
          <article className="card">
            <h2 className="card-title">Daily Handled vs Resolved</h2>
            <p className="card-subtitle">
              Comparison of total inquiries received vs. fully resolved each day.
            </p>
            <div className="chart-inner">
              <BarChart width={650} height={350} data={dailyHandledData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ textAnchor: "middle" }} />
                <YAxis />
                <Tooltip />
                <Legend verticalAlign="bottom" />
                <Bar dataKey="handled" fill="#401c51" isAnimationActive={true} />
                <Bar dataKey="resolved" fill="#9b71a3" isAnimationActive={true}/>
              </BarChart>
            </div>
          </article>
        </section>

        {/* Alerts */}
        <section className="card alerts-card">
          <h2 className="card-title">Active Alerts</h2>
          <ul className="alerts-list">
            <li className="alert-item alert-warning">
              Response time increased by 12% between 4–6 PM today.
            </li>
            <li className="alert-item alert-success">
              Resolution rate exceeded 90% for billing inquiries.
            </li>
            <li className="alert-item alert-info">
              Monitoring: accuracy for technical issues slightly below target (91%).
            </li>
          </ul>
        </section>

        {/* Modal */}
        {modalOpen && (
          <div className="modal-backdrop show" onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}>
            <div className="modal">
              <div className="modal-header">
                <h2>All Complaints</h2>
                <button className="close-btn" onClick={() => setModalOpen(false)} type="button">
                  Close
                </button>
              </div>

              <div className="modal-filters">
                <button className={`filter-chip ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>All complaints</button>
                <button className={`filter-chip ${filter === "resolved" ? "active" : ""}`} onClick={() => setFilter("resolved")}>Resolved</button>
                <button className={`filter-chip ${filter === "unresolved" ? "active" : ""}`} onClick={() => setFilter("unresolved")}>Unresolved</button>
                <button className={`filter-chip ${filter === "partial" ? "active" : ""}`} onClick={() => setFilter("partial")}>Partially resolved</button>
              </div>

              <div className="modal-table-wrapper">
                <table className="complaints-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Customer</th>
                      <th>Category</th>
                      <th>Description</th>
                      <th>Timestamp</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComplaints.map((c) => (
                      <tr key={c.id}>
                        <td>{c.id}</td>
                        <td>{c.customer}</td>
                        <td>{c.category}</td>
                        <td>{c.description}</td>
                        <td>{c.timestamp}</td>
                        <td>
                          <span className={`status-pill ${c.status}`}>
                            {c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </Layout>
  );
}
