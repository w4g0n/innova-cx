import { useState } from "react";
import Layout from "../../components/Layout";
import dailyHandled from "./ChatbotAnalysis_Images/dailyHandled.png";
import accuracyBars from "./ChatbotAnalysis_Images/accuracyBars.png";
import pieChart from "./ChatbotAnalysis_Images/piechart.png";
import purpPie from "./ChatbotAnalysis_Images/purpPie.png";
import respTime from "./ChatbotAnalysis_Images/respTime.png";
import "./ChatbotAnalysis.css";

export default function ChatbotAnalysis() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <Layout role="operator">
      <main className="main">
      {/* TOP BAR */}
        <header className="top-bar">
          <div>
            <h1 className="page-title">Chatbot Performance Analytics</h1>
            <p className="page-subtitle">
              Real-time insights into speed, accuracy, and resolution quality.
            </p>
          </div>

          <div className="top-actions">
            <div className="select-wrapper">
              <select>
                <option>Today</option>
                <option selected>Week</option>
                <option>Month</option>
                <option>Year</option>
              </select>
            </div>
            <button className="purple-btn" onClick={() => setModalOpen(true)}>
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
                <button className="close-btn" onClick={() => setModalOpen(false)}>
                  Close
                </button>
              </div>

              <div className="modal-filters">
                <button className="filter-chip active">All complaints</button>
                <button className="filter-chip">Resolved only</button>
                <button className="filter-chip">Unresolved only</button>
                <button className="filter-chip">Partially resolved</button>
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
                    <tr>
                      <td>CX-1021</td>
                      <td>Ahmed Ali</td>
                      <td>Billing</td>
                      <td>Charged twice for the same invoice.</td>
                      <td>24 Nov 2025, 16:12</td>
                      <td>
                        <span className="status-pill resolved">Resolved</span>
                      </td>
                    </tr>
                    <tr>
                      <td>CX-1044</td>
                      <td>Sara Khan</td>
                      <td>Technical</td>
                      <td>Chatbot unable to process password reset.</td>
                      <td>24 Nov 2025, 15:47</td>
                      <td>
                        <span className="status-pill escalated">Escalated</span>
                      </td>
                    </tr>
                    <tr>
                      <td>CX-1050</td>
                      <td>Omar Hassan</td>
                      <td>Account</td>
                      <td>Incorrect profile information shown.</td>
                      <td>24 Nov 2025, 14:33</td>
                      <td>
                        <span className="status-pill unresolved">Unresolved</span>
                      </td>
                    </tr>
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
