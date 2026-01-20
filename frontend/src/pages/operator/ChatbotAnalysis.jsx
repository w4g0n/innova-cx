import Layout from "../../components/Layout";
import dailyHandled from "./ChatbotAnalysis_Images/dailyHandled.png";
import accuracyBars from "./ChatbotAnalysis_Images/accuracyBars.png";
import pieChart from "./ChatbotAnalysis_Images/piechart.png";
import respTime from "./ChatbotAnalysis_Images/respTime.png";
import "./ChatbotAnalysis.css";

import { useState } from "react";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";

export default function ChatbotAnalysis() {
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState("all");

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
    if (filter === "partial") return c.status === "escalated"; // assuming "partially resolved" = "escalated"
    return true;
  });

  return (
    <Layout role="operator">
      <main className="main">
        {/* TOP BAR */}
        <header className="top-bar">
          <div>
            <PageHeader
              title="Chatbot Performance Analytics"
              subtitle="Real-time insights into speed, accuracy, and resolution quality."
            />
          </div>

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

            <button className="purple-btn" onClick={() => setModalOpen(true)} type="button">
              View handled Complaints
            </button>
          </div>
        </header>

        {/* KPI CARDS (keep business logic + text exactly the same) */}
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

        {/* CHARTS ROW 1 */}
        <section className="charts-row">
          <article className="card">
            <h2 className="card-title">Response Time Trend</h2>
            <p className="card-subtitle">
              Average response time by hour for the selected period.
            </p>
            <div className="chart-inner">
              <img src={respTime} alt="Response time trend chart" />
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Inquiry Resolution Status</h2>
            <p className="card-subtitle">
              Distribution of fully resolved, partially resolved, and escalated cases.
            </p>
            <div className="chart-inner">
              <img src={pieChart} alt="Inquiry resolution status pie chart" />
            </div>
          </article>
        </section>

        {/* CHARTS ROW 2 */}
        <section className="charts-row">
          <article className="card">
            <h2 className="card-title">Accuracy by Category</h2>
            <p className="card-subtitle">
              Chatbot classification accuracy across key inquiry types.
            </p>
            <div className="chart-inner">
              <img src={accuracyBars} alt="Accuracy by category bar chart" />
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Daily Handled vs Resolved</h2>
            <p className="card-subtitle">
              Comparison of total inquiries received vs. fully resolved each day.
            </p>
            <div className="chart-inner">
              <img src={dailyHandled} alt="Daily handled vs resolved chart" />
            </div>
          </article>
        </section>

        {/* ACTIVE ALERTS */}
        <section className="card alerts-card">
          <h2 className="card-title">Active Alerts</h2>
          <p className="card-subtitle">
            Real-time signals for performance drops or achievements.
          </p>
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

        {/* MODAL */}
        {modalOpen && (
          <div
            className="modal-backdrop show"
            onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}
          >
            <div className="modal">
              <div className="modal-header">
                <h2>All Complaints</h2>
                <button className="close-btn" onClick={() => setModalOpen(false)} type="button">
                  Close
                </button>
              </div>

              <div className="modal-filters">
                <button
                  className={`filter-chip ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                  type="button"
                >
                  All complaints
                </button>
                <button
                  className={`filter-chip ${filter === "resolved" ? "active" : ""}`}
                  onClick={() => setFilter("resolved")}
                  type="button"
                >
                  Resolved
                </button>
                <button
                  className={`filter-chip ${filter === "unresolved" ? "active" : ""}`}
                  onClick={() => setFilter("unresolved")}
                  type="button"
                >
                  Unresolved
                </button>
                <button
                  className={`filter-chip ${filter === "partial" ? "active" : ""}`}
                  onClick={() => setFilter("partial")}
                  type="button"
                >
                  Partially resolved
                </button>
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
