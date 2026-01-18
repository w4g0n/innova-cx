import Layout from "../../components/Layout";
import routingAcc from "./ChatbotAnalysis_Images/M-routingaccuracybydeptCROP.png";
import reroutedComp from "./ChatbotAnalysis_Images/M-reroutedcomp.png";
import prioAcc from "./ChatbotAnalysis_Images/M-prioACCbAR.png";
import rescoredComp from "./ChatbotAnalysis_Images/M-rescoredcomplain.png";
import resolSugg from "./ChatbotAnalysis_Images/M-Resolsugg.png";
import resolEff from "./ChatbotAnalysis_Images/M-ResolutionEff.png";
import "./ModelAnalysis.css";

export default function ModelAnalysis() {
  return (
    <Layout role="operator">
      <div className="modelAnalysis">
        <header className="top-bar">
          <div>
            <h1 className="page-title">Model Performance Dashboard</h1>
            <p className="page-subtitle">
              Routing and priority scoring accuracy for model-driven complaint handling.
            </p>
          </div>

          <div className="top-actions">
            <div className="select-wrapper">
              <select defaultValue="Last 7 days">
                <option>Last 7 days</option>
                <option>Last 30 days</option>
                <option>This quarter</option>
              </select>
            </div>

            <div className="select-wrapper">
              <select defaultValue="All departments">
                <option>All departments</option>
                <option>Billing</option>
                <option>Technical Support</option>
                <option>Facilities</option>
                <option>Leasing</option>
              </select>
            </div>

            <button
              className="toggle-btn"
              onClick={() => alert("Filter toggle will be connected later (demo).")}
            >
              Show misrouted / rescored
            </button>
          </div>
        </header>

        <section className="kpi-row">
          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Routing Accuracy</span>
              <span className="kpi-pill">Target ≥ 90%</span>
            </div>
            <div className="kpi-main">
              <span className="kpi-value">93%</span>
              <span className="kpi-change kpi-positive">+3% vs last period</span>
            </div>
            <p className="kpi-subtext">
              Percentage of complaints routed to the correct department.
            </p>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Reroute Rate</span>
              <span className="kpi-pill kpi-pill-blue">Lower is better</span>
            </div>
            <div className="kpi-main">
              <span className="kpi-value">7%</span>
              <span className="kpi-change kpi-positive">-2% vs last period</span>
            </div>
            <p className="kpi-subtext">
              Complaints manually rerouted after the model’s decision.
            </p>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Priority Scoring Accuracy</span>
              <span className="kpi-pill">Target ≥ 85%</span>
            </div>
            <div className="kpi-main">
              <span className="kpi-value">88%</span>
              <span className="kpi-change kpi-neutral">+1% vs last period</span>
            </div>
            <p className="kpi-subtext">
              Model’s 1–5 priority score matches the final human score.
            </p>
          </article>

          <article className="kpi-card">
            <div className="kpi-top">
              <span className="kpi-label">Rescore Rate</span>
              <span className="kpi-pill kpi-pill-grey">Monitor</span>
            </div>
            <div className="kpi-main">
              <span className="kpi-value">12%</span>
              <span className="kpi-change kpi-negative">+3% vs last period</span>
            </div>
            <p className="kpi-subtext">
              Complaints where operators changed the model’s priority score.
            </p>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Routing Accuracy by Department</h2>
            <p className="card-subtitle">
              How often the model chose the correct department.
            </p>
            <div className="chart-inner">
              <img className="chart-img" src={routingAcc} alt="Routing Accuracy by Department" />
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Rerouted Complaints</h2>
            <p className="card-subtitle">
              Distribution of accepted vs manually rerouted complaints.
            </p>
            <div className="chart-inner chart-inner--short">
              <img className="chart-img" src={reroutedComp} alt="Rerouted complaints donut chart" />
            </div>

            <ul className="mini-legend">
              <li><span className="dot dot-purple" />Accepted model routing</li>
              <li><span className="dot dot-blue" />Rerouted by employee</li>
              <li><span className="dot dot-grey" />Pending review</li>
            </ul>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Priority Accuracy by Score</h2>
            <p className="card-subtitle">
              How often each priority level (1–5) is confirmed by employees.
            </p>
            <div className="chart-inner">
              <img className="chart-img" src={prioAcc} alt="Priority accuracy by score bar chart" />
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Rescored Complaints</h2>
            <p className="card-subtitle">
              Where employees changed the model’s priority score.
            </p>
            <div className="chart-inner chart-inner--short">
              <img className="chart-img" src={rescoredComp} alt="Rescored complaints chart" />
            </div>

            <ul className="mini-legend">
              <li><span className="dot dot-purple" />Accepted scores</li>
              <li><span className="dot dot-lavender" />Adjusted scores</li>
            </ul>
          </article>
        </section>

        <section className="cards-row">
          <article className="card">
            <h2 className="card-title">Resolution Suggestion Adoption Rate</h2>
            <p className="card-subtitle">
              How often employees apply or lightly edit the model’s suggested resolution.
            </p>
            <div className="chart-inner">
              <img className="chart-img" src={resolSugg} alt="Resolution suggestion adoption rate chart" />
            </div>
          </article>

          <article className="card">
            <h2 className="card-title">Resolution Effectiveness</h2>
            <p className="card-subtitle">
              Outcomes where the model’s suggested resolution was used.
            </p>
            <div className="chart-inner chart-inner--short">
              <img className="chart-img" src={resolEff} alt="Resolution effectiveness donut chart" />
            </div>

            <ul className="mini-legend">
              <li><span className="dot dot-purple" />Resolved on first contact</li>
              <li><span className="dot dot-lavender" />Follow-up needed</li>
            </ul>
          </article>
        </section>

        <section className="card table-card">
          <h2 className="card-title">Cases Requiring Review</h2>
          <p className="card-subtitle">
            Sampled complaints where routing or priority was overridden by employees.
          </p>

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
                <tr>
                  <td>CX-10482</td>
                  <td>24 Nov 2025 – 10:14</td>
                  <td>Tenant</td>
                  <td><span className="route-change">Model: Facilities → Final: Facilities</span></td>
                  <td><span className="priority-change">3 → 5</span></td>
                  <td><span className="reason-pill reason-critical">Under-scored urgency</span></td>
                  <td>
                    <button className="link-btn" onClick={() => alert("Open complaint (demo).")}>
                      Open complaint
                    </button>
                  </td>
                </tr>

                <tr>
                  <td>CX-10431</td>
                  <td>24 Nov 2025 – 09:02</td>
                  <td>Tenant</td>
                  <td><span className="route-change">Model: Billing → Final: Leasing</span></td>
                  <td><span className="priority-change">2 → 3</span></td>
                  <td><span className="reason-pill reason-policy">Policy exception</span></td>
                  <td>
                    <button className="link-btn" onClick={() => alert("Open complaint (demo).")}>
                      Open complaint
                    </button>
                  </td>
                </tr>

                <tr>
                  <td>CX-10398</td>
                  <td>23 Nov 2025 – 16:41</td>
                  <td>Vendor</td>
                  <td><span className="route-change">Model: Technical → Final: Facilities</span></td>
                  <td><span className="priority-change">4 → 4</span></td>
                  <td><span className="reason-pill reason-routing">Wrong department</span></td>
                  <td>
                    <button className="link-btn" onClick={() => alert("Open complaint (demo).")}>
                      Open complaint
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}
