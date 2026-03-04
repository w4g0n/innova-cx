import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import ExportPdfButton from "../../components/common/ExportPdfButton";
import operatorDashboardData from "../../mock-data/operatorDashboard.json";
import "./OperatorDashboard.css";
import { PDFDownloadLink } from "@react-pdf/renderer";
import OperatorDashboardPDF from "./OperatorDashboardPDF.jsx";
import useScrollReveal from "../../utils/useScrollReveal";

export default function OperatorDashboard() {
  const revealRef = useScrollReveal();
  const navigate = useNavigate();
  const [range, setRange] = useState("last_1_hour");

  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    try {
      setLoading(true);
      setError(null);
      setData(operatorDashboardData);
    } catch (err) { // eslint-disable-line no-unused-vars
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
        <div className="opDash">⚠️ {error}</div>
      </Layout>
    );
  }

  const headerActions = (
    <div className="opDash__topActions">
      <div className="opDash__selectWrap">
        <PillSelect
          value={range}
          onChange={setRange}
          ariaLabel="Filter by time range"
          options={[
            { label: "Last 30 minutes", value: "last_30_min" },
            { label: "Last 1 hour",     value: "last_1_hour" },
            { label: "Today",           value: "today" },
            { label: "Last 7 days",     value: "last_7_days" },
          ]}
        />
      </div>

      <PDFDownloadLink
        className="exportPdfLink"
        document={<OperatorDashboardPDF data={data} range={range} />}
        fileName={`operator-dashboard-${new Date().toISOString().slice(0, 10)}.pdf`}
      >
        {({ loading: pdfLoading }) => (
          <span className={`exportPdfBtn ${pdfLoading ? "isLoading" : ""}`}>
            <ExportPdfButton loading={pdfLoading} />
          </span>
        )}
      </PDFDownloadLink>
    </div>
  );

  return (
    <Layout role="operator">
      <div className="opDash" ref={revealRef}>

        <PageHeader
          title="Operator System Dashboard"
          subtitle="High-level health of the complaint-handling platform and AI services."
          actions={headerActions}
        />

        {/* Row 1 — Core Services + Error Overview */}
        <section className="opDash__cardsRow">
          <article className="opDash__card">
            <h2 className="opDash__cardTitle">Core Services Status</h2>
            <p className="opDash__cardSubtitle">Real-time health of critical components.</p>

            <div className="opDash__statusGrid">
              {data.coreServices.map((svc) => (
                <div key={svc.name} className="opDash__statusItem">
                  <div className="opDash__statusLabel">{svc.name}</div>
                  <span className={`opDash__statusPill opDash__status--${svc.severity}`}>
                    {svc.status}
                  </span>
                  <p className="opDash__statusNote">{svc.note}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="opDash__card opDash__card--narrow">
            <h2 className="opDash__cardTitle">Error & Fallback Overview</h2>

            <div className="opDash__miniKpiCol">
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

        {/* Row 2 — Integrations + Queue Health */}
        <section className="opDash__cardsRow">
          <article className="opDash__card">
            <h2 className="opDash__cardTitle">Integrations Status</h2>

            <ul className="opDash__list">
              {data.integrations.map((i) => (
                <li key={i.name} className="opDash__listItem">
                  <div>
                    <div className="opDash__itemName">{i.name}</div>
                    <div className="opDash__itemMeta">{i.note}</div>
                  </div>
                  <span className={`opDash__statusPill opDash__status--${i.severity}`}>
                    {i.status}
                  </span>
                </li>
              ))}
            </ul>
          </article>

          <article className="opDash__card">
            <h2 className="opDash__cardTitle">Pipeline & Queue Health</h2>

            <div className="opDash__queueGrid">
              {data.queues.map((q) => (
                <div key={q.name} className="opDash__queueItem">
                  <div className="opDash__queueLabel">{q.name}</div>
                  <div className="opDash__queueValue">{q.value}</div>
                  <div className={`opDash__queueNote${q.severity === "warning" ? " opDash__queueNote--warning" : ""}`}>
                    {q.note}
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>

        {/* Full-width — Event Feed */}
        <section className="opDash__card opDash__card--full">
          <h2 className="opDash__cardTitle">Incident & Event Feed</h2>

          <ul className="opDash__eventFeed">
            {data.eventFeed.map((e, idx) => (
              <li key={idx} className={`opDash__eventItem opDash__event--${e.severity}`}>
                <span className="opDash__eventDot" />
                <div className="opDash__eventContent">
                  <div className="opDash__eventHeader">
                    <span className="opDash__eventTitle">{e.title}</span>
                    <span className="opDash__eventTime">{e.time}</span>
                  </div>
                  <p className="opDash__eventDesc">{e.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* Row 3 — AI Versions + Safety */}
        <section className="opDash__cardsRow">
          <article className="opDash__card">
            <h2 className="opDash__cardTitle">AI & Chatbot Versions</h2>

            <ul className="opDash__list">
              {data.versions.map((v) => (
                <li key={v.component} className="opDash__listItem">
                  <div>
                    <div className="opDash__itemName">{v.component}</div>
                    <div className="opDash__itemMeta">
                      {v.version} · Deployed {v.deployedAt}
                    </div>
                  </div>
                  <button
                    className="opDash__linkBtn"
                    onClick={() => navigate("/operator/model-health")}
                  >
                    View details
                  </button>
                </li>
              ))}
            </ul>
          </article>

          <article className="opDash__card">
            <h2 className="opDash__cardTitle">Safety & Maintenance</h2>

            <ul className="opDash__safetyList">
              {Object.entries(data.safetyMaintenance).map(([k, v]) => (
                <li key={k} className="opDash__safetyItem">
                  <span className="opDash__safetyLabel">{k}</span>
                  <span className="opDash__configPill">{v}</span>
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
    <div className="opDash__miniKpi">
      <span className="opDash__miniKpiLabel">{label}</span>
      <span className="opDash__miniKpiValue">{count}</span>
      <span className={`opDash__miniKpiTrend${critical ? " opDash__miniKpiTrend--critical" : " opDash__miniKpiTrend--normal"}`}>
        {trendLabel}
      </span>
    </div>
  );
}
