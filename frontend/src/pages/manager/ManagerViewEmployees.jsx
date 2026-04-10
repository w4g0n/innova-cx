import Layout from "../../components/Layout";
import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { pdf } from "@react-pdf/renderer";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import KpiCard from "../../components/common/KpiCard";
import EmployeeReportPDF from "../employee/EmployeeReportPDF";
import { apiUrl } from "../../config/apiBase";
import {
  sanitizeText,
  sanitizeId,
  sanitizeSearchQuery,
  MAX_SEARCH_LEN,
} from "./ManagerSanitize";
import "./ManagerViewEmployees.css";

const API_BASE = apiUrl("/api");

function getAuthToken() {
  const direct =
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken");
  if (direct) return direct;
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return "";
    const user = JSON.parse(raw);
    return user?.access_token || "";
  } catch {
    return "";
  }
}

/** Build a structured report object from the employee row data we have. */
function buildEmployeeReport(emp) {
  const now   = new Date();
  const month = now.toLocaleString("default", { month: "long", year: "numeric" });
  const total = (emp.completed || 0) + (emp.inProgress || 0);
  const slaPct = total > 0 ? `${Math.round(((emp.completed || 0) / total) * 100)}%` : "N/A";
  const rating =
    (emp.completed || 0) >= 20 ? "Excellent" :
    (emp.completed || 0) >= 10 ? "Good"      : "Needs Improvement";

  return {
    month,
    kpis: {
      rating,
      resolved:    emp.completed  || 0,
      sla:         slaPct,
      avgResponse: "N/A",
    },
    summary: [
      { label: "Total Assigned",  value: String(total) },
      { label: "Completed",       value: String(emp.completed  || 0) },
      { label: "In Progress",     value: String(emp.inProgress || 0) },
      { label: "SLA Compliance",  value: slaPct },
      { label: "Role",            value: emp.role || "Employee" },
    ],
    weekly: [
      { week: "Week 1", assigned: "—", resolved: "—", sla: "—", avg: "—" },
      { week: "Week 2", assigned: "—", resolved: "—", sla: "—", avg: "—" },
      { week: "Week 3", assigned: "—", resolved: "—", sla: "—", avg: "—" },
      { week: "Week 4", assigned: "—", resolved: "—", sla: "—", avg: "—" },
    ],
    notes: [
      `${emp.name} completed ${emp.completed || 0} ticket(s) this period.`,
      `${emp.inProgress || 0} ticket(s) are currently in progress.`,
      "Full weekly breakdown requires backend analytics integration.",
    ],
  };
}

function DownloadReportButton({ employee: e }) {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try {
      const blob = await pdf(
        <EmployeeReportPDF
          report={buildEmployeeReport(e)}
          employeeName={e.name}
          employeeId={e.id}
          downloadDate={new Date()}
        />
      ).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${e.id}-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF generation failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      className={`ve-reportBtn${loading ? " ve-reportBtn--loading" : ""}`}
      onClick={handleDownload}
      disabled={loading}
    >
      {loading ? "Preparing…" : "⬇ View Report"}
    </button>
  );
}

export default function ManagerViewEmployees() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setEmployees([]);
      setLoading(false);
      setError("Unauthorized. Please log in again.");
      return;
    }

    const fetchEmployees = async () => {
      try {
        const res = await fetch(`${API_BASE}/manager/employees`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        });

        if (res.status === 401) {
          setEmployees([]);
          setError("Unauthorized. Please log in again.");
          return;
        }

        if (!res.ok) {
          throw new Error(`Failed to fetch employees (${res.status})`);
        }

        const data = await res.json();
        const raw = Array.isArray(data) ? data : data.employees || [];
        setEmployees(raw.map((e) => ({
          ...e,
          name: sanitizeText(e.name, 100),
          id:   sanitizeId(e.id),
          role: sanitizeText(e.role, 100),
        })));
      } catch (err) {
        console.error(err);
        setEmployees([]);
        setError("Failed to load employees. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchEmployees();
  }, [navigate]);

  const filteredEmployees = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return employees;

    return employees.filter(
      (e) =>
        e.name?.toLowerCase().includes(q) ||
        e.id?.toLowerCase().includes(q) ||
        e.role?.toLowerCase().includes(q)
    );
  }, [employees, query]);

  const kpiEmployees = employees.length;
  const kpiCompleted = employees.reduce(
    (sum, e) => sum + (e.completed || 0),
    0
  );
  const kpiInProgress = employees.reduce(
    (sum, e) => sum + (e.inProgress || 0),
    0
  );
  const kpiAvg =
    kpiEmployees > 0 ? (kpiCompleted / kpiEmployees).toFixed(1) : "0.0";

  const topPerformer =
    employees.length > 0
      ? employees.reduce(
          (best, e) =>
            (e.completed || 0) > (best.completed || 0) ? e : best,
          employees[0]
        )
      : null;

  const lowestPerformer =
    employees.length > 0
      ? employees.reduce(
          (worst, e) =>
            (e.completed || 0) < (worst.completed || 0) ? e : worst,
          employees[0]
        )
      : null;

  return (
    <Layout role="manager">
      <main className="ve-main">
        <PageHeader
          title="View Employees"
          subtitle="Search employees and access their auto-generated reports."
        />

        {loading && <div className="ve-empty">Loading employees...</div>}
        {error && <div className="ve-empty">{error}</div>}

        {!loading && !error && (
          <>
            <section className="ve-kpiRow">
              <KpiCard label="Employees" value={kpiEmployees} />
              <KpiCard label="Tickets Completed" value={kpiCompleted} />
              <KpiCard label="In Progress" value={kpiInProgress} />
              <KpiCard label="Avg Per Employee" value={kpiAvg} />
              <KpiCard label="Top Performer" value={topPerformer?.name || "-"} />
              <KpiCard
                label="Lowest Performer"
                value={lowestPerformer?.name || "-"}
              />
            </section>

            <section className="ve-searchRow">
              <PillSearch
                value={query}
                onChange={(v) => {
                  const raw = typeof v === "string" ? v : (v?.target?.value ?? "");
                  setQuery(sanitizeSearchQuery(raw));
                }}
                placeholder="Search employees by name, ID, or role..."
                maxLength={MAX_SEARCH_LEN}
              />
            </section>

            <section className="ve-tableWrapper">
              <table className="ve-table">
                <thead>
                  <tr>
                    <th>Employee Name</th>
                    <th>Employee ID</th>
                    <th>Role</th>
                    <th>Tickets Completed</th>
                    <th>In Progress</th>
                    <th>Report</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredEmployees.map((e) => (
                    <tr key={e.id}>
                      <td className="ve-left">{e.name}</td>
                      <td className="ve-left">{e.id}</td>
                      <td className="ve-left">{e.role}</td>
                      <td>{e.completed || 0}</td>
                      <td>{e.inProgress || 0}</td>
                      <td>
                        <DownloadReportButton employee={e} />
                      </td>
                    </tr>
                  ))}

                  {filteredEmployees.length === 0 && (
                    <tr>
                      <td className="ve-empty" colSpan={6}>
                        No employees match “{query}”.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </>
        )}
      </main>
    </Layout>
  );
}