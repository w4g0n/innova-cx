import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PillSelect from "../../components/common/PillSelect";
import ExportPdfButton from "../../components/common/ExportPdfButton";
import operatorDashboardData from "../../mock-data/operatorDashboard.json";
import "./OperatorDashboard.css";
import { PDFDownloadLink } from "@react-pdf/renderer";
import OperatorDashboardPDF from "./OperatorDashboardPDF.jsx";

export default function OperatorDashboard() {
  const navigate = useNavigate();
  const [range, setRange] = useState("last_1_hour");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      setLoading(true);
      setError(null);
      setData(operatorDashboardData);
    } catch (err) { // eslint-disable-line no-unused-vars -- TODO: review - err unused
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [range]);

  if (loading) {
    return (
      <Layout role="operator">
        <div className="opDash">Loading system dashboard…</div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout role="operator">
        <div className="opDash error">⚠️ {error}</div>
      </Layout>
    );
  }

  return (
    <Layout role="operator">
      <div className="opDash">
        
        <header className="top-bar">
          <div>
            <h1 className="page-title">Operator System Dashboard</h1>
            <p className="page-subtitle">
              High-level health of the complaint-handling platform and AI services.
            </p>
          </div>

          <div className="top-actions">
            <div className="opDashSelect">
              <PillSelect
                value={range}
                onChange={setRange}
                ariaLabel="Filter by time range"
                options={[
                  { label: "Last 30 minutes", value: "last_30_min" },
                  { label: "Last 1 hour", value: "last_1_hour" },
                  { label: "Today", value: "today" },
                  { label: "Last 7 days", value: "last_7_days" },
                ]}
              />
            </div>

            <PDFDownloadLink
              className="exportPdfLink"
              document={<OperatorDashboardPDF data={data} range={range} />}
              fileName={`operator-dashboard-${new Date()
                .toISOString()
                .slice(0, 10)}.pdf`}
            >
              {({ loading }) => (
                <span className={`exportPdfBtn ${loading ? "isLoading" : ""}`}>
                  <ExportPdfButton loading={loading} />
                </span>
              )}
            </PDFDownloadLink>
          </div>
        </header>

        
        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Core Services Status</h2>
            <p className="card-subtitle">Real-time health of critical components.</p>

            <div className="status-grid">
              {data.coreServices.map((svc) => (
                <div key={svc.name} className="status-item">
                  <div className="status-label">{svc.name}</div>
                  <span className={`status-pill status-${svc.severity}`}>
                    {svc.status}
                  </span>
                  <p className="status-note">{svc.note}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="card narrow-card">
            <h2 className="card-title">Error & Fallback Overview</h2>

            <div className="mini-kpi-column">
              <MiniKpi
                label="System errors"
                {...data.errorFallbackOverview.systemErrors}
              />
              <MiniKpi
                label="Chatbot → Human fallbacks"
                {...data.errorFallbackOverview.chatbotToHumanFallbacks}
              />
              <MiniKpi
                label="Routing failures"
                {...data.errorFallbackOverview.routingFailures}
                critical
              />
            </div>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Integrations Status</h2>

            <ul className="integration-list">
              {data.integrations.map((i) => (
                <li key={i.name} className="integration-item">
                  <div>
                    <div className="integration-name">{i.name}</div>
                    <div className="integration-note">{i.note}</div>
                  </div>
                  <span className={`status-pill status-${i.severity}`}>
                    {i.status}
                  </span>
                </li>
              ))}
            </ul>
          </article>

          <article className="card">
            <h2 className="card-title">Pipeline & Queue Health</h2>

            <div className="queue-grid">
              {data.queues.map((q) => (
                <div key={q.name} className="queue-item">
                  <div className="queue-label">{q.name}</div>
                  <div className="queue-value">{q.value}</div>
                  <div
                    className={`queue-note ${
                      q.severity === "warning" ? "queue-note-warning" : ""
                    }`}
                  >
                    {q.note}
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="card full-width-card">
          <h2 className="card-title">Incident & Event Feed</h2>

          <ul className="event-feed">
            {data.eventFeed.map((e, idx) => (
              <li key={idx} className={`event-item event-${e.severity}`}>
                <span className="event-dot" />
                <div className="event-content">
                  <div className="event-header">
                    <span className="event-title">{e.title}</span>
                    <span className="event-time">{e.time}</span>
                  </div>
                  <p className="event-description">{e.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">AI & Chatbot Versions</h2>

            <ul className="version-list">
              {data.versions.map((v) => (
                <li key={v.component} className="version-item">
                  <div>
                    <div className="version-name">{v.component}</div>
                    <div className="version-meta">
                      {v.version} · Deployed {v.deployedAt}
                    </div>
                  </div>
                  <button
                    className="link-btn"
                    onClick={() => navigate("/operator/model-analysis")}
                  >
                    View details
                  </button>
                </li>
              ))}
            </ul>
          </article>

          <article className="card">
            <h2 className="card-title">Safety & Maintenance</h2>

            <ul className="safety-list">
              {Object.entries(data.safetyMaintenance).map(([k, v]) => (
                <li key={k} className="safety-item">
                  <span className="safety-label">{k}</span>
                  <span className="config-pill">{v}</span>
                </li>
              ))}
            </ul>
          </article>
        </section>
      </div>
    </Layout>
  );
}

function MiniKpi({ label, count, trendLabel, critical }) {
  return (
    <div className="mini-kpi">
      <span className="mini-kpi-label">{label}</span>
      <span className="mini-kpi-value">{count}</span>
      <span
        className={`mini-kpi-trend ${
          critical ? "mini-kpi-critical" : "mini-kpi-normal"
        }`}
      >
        {trendLabel}
      </span>
    </div>
  );
}