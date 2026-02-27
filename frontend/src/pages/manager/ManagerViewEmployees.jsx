import Layout from "../../components/Layout";
import { useMemo, useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import KpiCard from "../../components/common/KpiCard";
import { apiUrl } from "../../config/apiBase";
import "./ManagerViewEmployees.css";

export default function ManagerViewEmployees() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setEmployees([]);
      setLoading(false);
      setError("Unauthorized. Please log in again.");
      return;
    }

    const fetchEmployees = async () => {
      try {
        const res = await fetch(apiUrl("/manager/employees"), {
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
        setEmployees(Array.isArray(data) ? data : data.employees || []);
      } catch (err) {
        console.error(err);
        setEmployees([]);
        setError("Failed to load employees.");
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
                onChange={(v) =>
                  typeof v === "string"
                    ? setQuery(v)
                    : setQuery(v?.target?.value ?? "")
                }
                placeholder="Search employees by name, ID, or role..."
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
                        <Link
                          className="ve-reportBtn"
                          to={`/manager/employees/${e.id}`}
                        >
                          View report
                        </Link>
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
