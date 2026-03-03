import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import operatorDashboardData from "../../mock-data/operatorDashboard.json";
import "./OperatorDashboard.css";
import useScrollReveal from "../../utils/useScrollReveal";

export default function OperatorDashboard() {
  const revealRef = useScrollReveal();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      setLoading(true);
      setError(null);
      setData(operatorDashboardData);
    } catch (err) {
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  const kpis = useMemo(() => {
    if (!data) {
      return {
        systemErrors: 0,
        fallbacks: 0,
        routingFailures: 0,
        ingestionQueue: 0,
        modelQueue: 0,
      };
    }

    const ingestion =
      data.queues?.find((q) => /ingestion/i.test(q.name))?.value ?? 0;

    const modelQ =
      data.queues?.find((q) => /model/i.test(q.name))?.value ??
      data.queues?.find((q) => /processing/i.test(q.name))?.value ??
      0;

    return {
      systemErrors: data.errorFallbackOverview?.systemErrors?.count ?? 0,
      fallbacks: data.errorFallbackOverview?.chatbotToHumanFallbacks?.count ?? 0,
      routingFailures: data.errorFallbackOverview?.routingFailures?.count ?? 0,
      ingestionQueue: ingestion,
      modelQueue: modelQ,
    };
  }, [data]);

  if (loading) {
    return (
      <Layout role="operator">
        <div className="opDash">Loading…</div>
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

  return (
    <Layout role="operator">
      <div className="opDash opDash--simple" ref={revealRef}>
        <PageHeader
          title="Operator System Dashboard"
          subtitle="Quick overview of the platform’s operational state."
        />

        {/* KPI ROW */}
        <section className="operatorKpiRow">
          <KpiCard label="System Errors" value={kpis.systemErrors} />
          <KpiCard label="Chatbot Fallbacks" value={kpis.fallbacks} />
          <KpiCard label="Routing Failures" value={kpis.routingFailures} />
          <KpiCard label="Ingestion Queue" value={kpis.ingestionQueue} />
          <KpiCard label="Model Queue" value={kpis.modelQueue} />
        </section>

        <p className="operatorIntro">
          Use these quick actions to move between Operator screens.
        </p>

        {/* 3 NAVIGATION CARDS ONLY */}
        <section className="operatorQuickGrid">
          <Link to="/operator/model-health" className="operatorQuickCard">
            <span className="operatorQuickTag">Models</span>
            <div className="operatorQuickTitle">Model Health</div>
            <div className="operatorQuickDesc">
              Service health, latency, drift indicators, and model stability checks.
            </div>
            <div className="operatorQuickLink">Open →</div>
          </Link>

          <Link to="/operator/quality-control" className="operatorQuickCard">
            <span className="operatorQuickTag">QA</span>
            <div className="operatorQuickTitle">Quality Control</div>
            <div className="operatorQuickDesc">
              Review tickets, validate routing results, and approve corrections.
            </div>
            <div className="operatorQuickLink">Open →</div>
          </Link>

          <Link to="/operator/users" className="operatorQuickCard">
            <span className="operatorQuickTag">Access</span>
            <div className="operatorQuickTitle">Users Management</div>
            <div className="operatorQuickDesc">
              Manage RBAC roles, user access, and account status.
            </div>
            <div className="operatorQuickLink">Open →</div>
          </Link>
        </section>

        {/* SUMMARY (NO LINKS INSIDE) */}
        <section className="operatorSummaryRow">
          <div className="operatorSummaryCard">
            <h3 className="operatorSummaryTitle">Model Health Summary</h3>
            <ul className="operatorSummaryList">
              <li>
                <span>Overall status</span>
                <b>Healthy</b>
              </li>
              <li>
                <span>Average latency</span>
                <b>~420 ms</b>
              </li>
              <li>
                <span>Error rate</span>
                <b>0.6%</b>
              </li>
              <li>
                <span>Drift detected</span>
                <b>No</b>
              </li>
            </ul>
          </div>

          <div className="operatorSummaryCard">
            <h3 className="operatorSummaryTitle">Quality Control Summary</h3>
            <ul className="operatorSummaryList">
              <li>
                <span>Pending reviews</span>
                <b>12</b>
              </li>
              <li>
                <span>Average review time</span>
                <b>4m 10s</b>
              </li>
              <li>
                <span>Flagged tickets today</span>
                <b>3</b>
              </li>
              <li>
                <span>Oldest pending review</span>
                <b>1h 22m</b>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </Layout>
  );
}