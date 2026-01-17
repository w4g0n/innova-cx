import Layout from "../../components/Layout";
import "./OperatorDashboard.css";

export default function OperatorDashboard() {
  return (
    <Layout role="operator">
      <div className="opDash">
        {/* TOP BAR */}
        <header className="top-bar">
          <div>
            <h1 className="page-title">Operator System Dashboard</h1>
            <p className="page-subtitle">
              High-level health of the complaint-handling platform and AI services.
            </p>
          </div>

          <div className="top-actions">
            <div className="select-wrapper">
              <select defaultValue="Last 1 hour">
                <option>Last 30 minutes</option>
                <option>Last 1 hour</option>
                <option>Today</option>
                <option>Last 7 days</option>
              </select>
            </div>

            <button
              className="export-btn"
              onClick={() => alert("Export will be connected later (demo).")}
            >
              <span className="export-icon">⭳</span>
              Export
            </button>
          </div>
        </header>

        {/* ROW 1: GLOBAL SYSTEM HEALTH */}
        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Core Services Status</h2>
            <p className="card-subtitle">Real-time health of critical components.</p>

            <div className="status-grid">
              <div className="status-item">
                <div className="status-label">Complaint Ingestion</div>
                <span className="status-pill status-ok">Healthy</span>
                <p className="status-note">No backlog detected.</p>
              </div>

              <div className="status-item">
                <div className="status-label">Routing Engine (Model)</div>
                <span className="status-pill status-ok">Running</span>
                <p className="status-note">Latency within normal range.</p>
              </div>

              <div className="status-item">
                <div className="status-label">Chatbot Service</div>
                <span className="status-pill status-warning">Degraded</span>
                <p className="status-note">Increased fallback to human agents.</p>
              </div>

              <div className="status-item">
                <div className="status-label">Database & Storage</div>
                <span className="status-pill status-ok">Connected</span>
                <p className="status-note">Last backup completed at 03:00.</p>
              </div>

              <div className="status-item">
                <div className="status-label">Notification Services</div>
                <span className="status-pill status-ok">Operational</span>
                <p className="status-note">Email & SMS queues processing normally.</p>
              </div>

              <div className="status-item">
                <div className="status-label">User Credentials</div>
                <span className="status-pill status-ok">Connected</span>
                <p className="status-note">Connection is stable.</p>
              </div>
            </div>
          </article>

          <article className="card narrow-card">
            <h2 className="card-title">Error & Fallback Overview</h2>
            <p className="card-subtitle">Abnormal behaviour in the last hour.</p>

            <div className="mini-kpi-column">
              <div className="mini-kpi">
                <span className="mini-kpi-label">System errors</span>
                <span className="mini-kpi-value">3</span>
                <span className="mini-kpi-trend mini-kpi-normal">
                  Within normal range
                </span>
              </div>

              <div className="mini-kpi">
                <span className="mini-kpi-label">Chatbot → Human fallbacks</span>
                <span className="mini-kpi-value">7</span>
                <span className="mini-kpi-trend mini-kpi-warning">
                  Slightly elevated
                </span>
              </div>

              <div className="mini-kpi">
                <span className="mini-kpi-label">Routing failures</span>
                <span className="mini-kpi-value">1</span>
                <span className="mini-kpi-trend mini-kpi-critical">Needs review</span>
              </div>
            </div>
          </article>
        </section>

        {/* ROW 2: INTEGRATIONS & PIPELINE */}
        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Integrations Status</h2>
            <p className="card-subtitle">Connectivity to external systems.</p>

            <ul className="integration-list">
              <li className="integration-item">
                <div>
                  <div className="integration-name">CRM / Ticketing</div>
                  <div className="integration-note">All events syncing correctly.</div>
                </div>
                <span className="status-pill status-ok">Connected</span>
              </li>

              <li className="integration-item">
                <div>
                  <div className="integration-name">Identity / SSO</div>
                  <div className="integration-note">
                    No failed logins due to provider issues.
                  </div>
                </div>
                <span className="status-pill status-ok">OK</span>
              </li>

              <li className="integration-item">
                <div>
                  <div className="integration-name">Audio Transcriber</div>
                  <div className="integration-note">Fully functional.</div>
                </div>
                <span className="status-pill status-ok">OK</span>
              </li>
            </ul>
          </article>

          <article className="card">
            <h2 className="card-title">Pipeline & Queue Health</h2>
            <p className="card-subtitle">Flow of complaints through the system.</p>

            <div className="queue-grid">
              <div className="queue-item">
                <div className="queue-label">Ingestion queue</div>
                <div className="queue-value">0</div>
                <div className="queue-note">No stuck records.</div>
              </div>

              <div className="queue-item">
                <div className="queue-label">Model processing queue</div>
                <div className="queue-value">3</div>
                <div className="queue-note">Within expected range.</div>
              </div>

              <div className="queue-item">
                <div className="queue-label">Notification queue</div>
                <div className="queue-value">27</div>
                <div className="queue-note queue-note-warning">
                  Higher than typical; monitor.
                </div>
              </div>

              <div className="queue-item">
                <div className="queue-label">Audit / logging pipeline</div>
                <div className="queue-value">Healthy</div>
                <div className="queue-note">All events captured.</div>
              </div>
            </div>
          </article>
        </section>

        {/* ROW 3: INCIDENT FEED */}
        <section className="card full-width-card">
          <h2 className="card-title">Incident & Event Feed</h2>
          <p className="card-subtitle">
            Recent system-level events for operator awareness.
          </p>

          <ul className="event-feed">
            <li className="event-item event-critical">
              <span className="event-dot"></span>
              <div className="event-content">
                <div className="event-header">
                  <span className="event-title">Chatbot service latency spike</span>
                  <span className="event-time">10:02</span>
                </div>
                <p className="event-description">
                  Response times exceeded threshold; temporary failover to human
                  agents activated.
                </p>
              </div>
            </li>

            <li className="event-item event-warning">
              <span className="event-dot"></span>
              <div className="event-content">
                <div className="event-header">
                  <span className="event-title">Routing error rate above baseline</span>
                  <span className="event-time">09:47</span>
                </div>
                <p className="event-description">
                  Error rate at 2.5% vs typical 0.5% for the last 15 minutes.
                </p>
              </div>
            </li>

            <li className="event-item event-info">
              <span className="event-dot"></span>
              <div className="event-content">
                <div className="event-header">
                  <span className="event-title">Routing model v1.3 deployed</span>
                  <span className="event-time">09:30</span>
                </div>
                <p className="event-description">
                  New version activated for all departments; rollback to v1.2 available.
                </p>
              </div>
            </li>

            <li className="event-item event-info">
              <span className="event-dot"></span>
              <div className="event-content">
                <div className="event-header">
                  <span className="event-title">Nightly database backup completed</span>
                  <span className="event-time">03:00</span>
                </div>
                <p className="event-description">
                  Backup finished successfully; restore point created for the last 24
                  hours.
                </p>
              </div>
            </li>
          </ul>
        </section>

        {/* ROW 4: VERSIONS & SAFETY */}
        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">AI & Chatbot Versions</h2>
            <p className="card-subtitle">What is currently live in production.</p>

            <ul className="version-list">
              <li className="version-item">
                <div>
                  <div className="version-name">Routing model</div>
                  <div className="version-meta">v1.3 · Deployed 24 Nov 2025</div>
                </div>
                <button
                  className="link-btn"
                  onClick={() => alert("Later: link to Model Analysis")}
                >
                  View details
                </button>
              </li>

              <li className="version-item">
                <div>
                  <div className="version-name">Priority scoring model</div>
                  <div className="version-meta">v2.1 · Deployed 20 Nov 2025</div>
                </div>
                <button className="link-btn" onClick={() => alert("Demo only")}>
                  View details
                </button>
              </li>

              <li className="version-item">
                <div>
                  <div className="version-name">Chatbot NLU</div>
                  <div className="version-meta">build 5.4 · Deployed 22 Nov 2025</div>
                </div>
                <button className="link-btn" onClick={() => alert("Demo only")}>
                  View details
                </button>
              </li>
            </ul>
          </article>

          <article className="card">
            <h2 className="card-title">Safety & Maintenance</h2>
            <p className="card-subtitle">Configuration and scheduled jobs.</p>

            <ul className="safety-list">
              <li className="safety-item">
                <span className="safety-label">PII anonymization</span>
                <span className="status-pill status-ok">Enabled</span>
              </li>

              <li className="safety-item">
                <span className="safety-label">Logging level</span>
                <span className="config-pill">Standard</span>
              </li>

              <li className="safety-item">
                <span className="safety-label">Admin-only changes</span>
                <span className="status-pill status-ok">Enforced</span>
              </li>

              <li className="safety-item">
                <span className="safety-label">Next maintenance window</span>
                <span className="config-pill">Sunday · 02:00–03:00</span>
              </li>
            </ul>
          </article>
        </section>
      </div>
    </Layout>
  );
}